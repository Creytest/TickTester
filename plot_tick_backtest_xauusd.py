from itertools import islice

import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import numpy as np
from matplotlib.collections import LineCollection

from tick_config import (
    ASSETS,
    REVERSE_BID_ASK,
    INITIAL_CAPITAL,
    COMMISSION,
    SLIPPAGE_TICKS,
    RISK_PER_TRADE,
)
from tick_data import load_ticks
from tick_backtest import run_backtest
from strategies.tick_BigBeluga_Stoch_80percent import generate_signals


# ============================================================
# KONFIGURACJA
# ============================================================

ASSET = "XAUUSD"
CHUNK_SIZE = 20_000
CHUNKS_TO_TEST = 3
TIMEFRAME = "5min"

START_DATE = "2014-01-01"
END_DATE = "2014-12-31"

TICK_SIZE = 0.01

# Liczba świec przed początkiem wybranego okresu,
# które służą do rozgrzania wskaźników.
WARMUP_BARS = 300


# ============================================================
# DANE TICKOWE
# ============================================================

def tick_source():
    start = (
        pd.Timestamp(START_DATE)
        - pd.Timedelta(TIMEFRAME) * WARMUP_BARS
    )

    end = pd.Timestamp(END_DATE) + pd.Timedelta(days=1)

    yield from load_ticks(
        ASSETS[ASSET],
        chunksize=CHUNK_SIZE,
        reverse_bid_ask=REVERSE_BID_ASK[ASSET],
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
    )


def filtered_tick_source(start_time, end_time):
    """
    Zwraca ticki od początku rozgrzewki do końca wybranego okresu.

    Dzięki temu wskaźniki mają historię przed START_DATE,
    ale backtest nie przetwarza danych po END_DATE.
    """
    for chunk in tick_source():
        mask = (
            (chunk["timestamp"] >= start_time)
            & (chunk["timestamp"] < end_time)
        )

        filtered = chunk.loc[mask].copy()

        if not filtered.empty:
            yield filtered.reset_index(drop=True)


def nearest_bar_index(index: pd.DatetimeIndex, timestamp) -> int:
    timestamp = pd.Timestamp(timestamp)
    pos = index.searchsorted(timestamp, side="right") - 1
    return max(0, min(int(pos), len(index) - 1))


def main():
    start_time = pd.Timestamp(START_DATE)
    end_time = pd.Timestamp(END_DATE) + pd.Timedelta(days=1)

    if end_time <= start_time:
        raise ValueError("END_DATE musi być późniejsza niż START_DATE.")

    # ========================================================
    # 1. USTALENIE ZAKRESU DANYCH I ROZGRZEWKI
    # ========================================================

    print("Wczytywanie danych tickowych...")

    chunks = list(tick_source())

    if not chunks:
        raise RuntimeError("Nie znaleziono danych tickowych.")

    all_ticks = pd.concat(chunks, ignore_index=True)

    all_ticks = all_ticks.sort_values("timestamp").reset_index(drop=True)

    selected_ticks = all_ticks[
        (all_ticks["timestamp"] >= start_time)
        & (all_ticks["timestamp"] < end_time)
    ]

    if selected_ticks.empty:
        raise RuntimeError(
            f"Brak ticków w okresie {START_DATE} – {END_DATE}. "
            "Sprawdź zakres dat i CHUNKS_TO_TEST."
        )

    first_selected_tick = selected_ticks["timestamp"].iloc[0]

    # Początek świecy, na której znajduje się pierwszy tick okresu.
    first_selected_bar = first_selected_tick.floor(TIMEFRAME)

    # Potrzebujemy świec poprzedzających wybrany okres.
    warmup_start = first_selected_bar - pd.Timedelta(
        TIMEFRAME
    ) * WARMUP_BARS

    print(f"Okres backtestu: {START_DATE} – {END_DATE}")
    print(f"Pierwszy tick w okresie: {first_selected_tick}")
    print(f"Rozgrzewka od: {warmup_start}")

    # ========================================================
    # 2. BACKTEST
    # ========================================================

    def backtest_tick_source():
        mask = (
            (all_ticks["timestamp"] >= warmup_start)
            & (all_ticks["timestamp"] < end_time)
        )

        filtered = all_ticks.loc[mask].copy()

        # Silnik oczekuje iteratora DataFrame'ów.
        for i in range(0, len(filtered), CHUNK_SIZE):
            yield filtered.iloc[i:i + CHUNK_SIZE].reset_index(drop=True)

    result = run_backtest(
        tick_source=backtest_tick_source,
        strategy=generate_signals,
        timeframe=TIMEFRAME,
        initial_capital=INITIAL_CAPITAL,
        commission=COMMISSION,
        slippage_ticks=SLIPPAGE_TICKS,
        tick_size=TICK_SIZE,
        risk_per_trade=RISK_PER_TRADE,
    )

    bars_all = result["bars"].copy()
    trades_all = result["trades"].copy()
    equity_all = result["equity"].copy()

    if bars_all.empty:
        raise RuntimeError("Brak świec do narysowania.")

    # ========================================================
    # 3. OGRANICZENIE WYKRESU DO WYBRANEGO OKRESU
    # ========================================================

    # Wskaźniki zostały policzone na danych obejmujących rozgrzewkę.
    # Dopiero teraz ograniczamy widok do wybranego okresu.
    bars = bars_all[
        (bars_all.index >= start_time)
        & (bars_all.index < end_time)
    ].copy()

    if bars.empty:
        raise RuntimeError(
            "Brak świec w wybranym okresie po przetworzeniu danych."
        )

    # Odrzucamy transakcje, które rozpoczęły się przed okresem.
    # Ponieważ backtest rozpoczyna się od świec rozgrzewki,
    # transakcje z rozgrzewki nie powinny być częścią wyników okresu.
    trades = trades_all[
        (trades_all["entry_time"] >= start_time)
        & (trades_all["entry_time"] < end_time)
    ].copy() if not trades_all.empty else trades_all.copy()

    # Krzywa kapitału obejmuje tylko wybrany okres.
    if not equity_all.empty:
        equity = equity_all.copy()
        equity["timestamp"] = pd.to_datetime(equity["timestamp"])

        equity = equity[
            (equity["timestamp"] >= start_time)
            & (equity["timestamp"] < end_time)
        ].copy()
    else:
        equity = equity_all.copy()

    signals = generate_signals(bars_all.copy())
    signals = signals.reindex(bars.index)

    # ========================================================
    # 4. SYGNAŁY I TRANSAKCJE
    # ========================================================

    raw_buy = pd.Series(float("nan"), index=bars.index)
    raw_sell = pd.Series(float("nan"), index=bars.index)

    entries_long = pd.Series(float("nan"), index=bars.index)
    entries_short = pd.Series(float("nan"), index=bars.index)
    exits = pd.Series(float("nan"), index=bars.index)

    buy_mask = signals["buy"].fillna(False).astype(bool)
    sell_mask = signals["sell"].fillna(False).astype(bool)

    raw_buy.loc[buy_mask] = bars.loc[buy_mask, "low"] * 0.999
    raw_sell.loc[sell_mask] = bars.loc[sell_mask, "high"] * 1.001

    if not trades.empty:
        for _, trade in trades.iterrows():
            entry_idx = nearest_bar_index(
                bars.index, trade["entry_time"]
            )
            exit_idx = nearest_bar_index(
                bars.index, trade["exit_time"]
            )

            if trade["side"] == "long":
                entries_long.iloc[entry_idx] = float(
                    trade["entry_price"]
                )
            else:
                entries_short.iloc[entry_idx] = float(
                    trade["entry_price"]
                )

            exits.iloc[exit_idx] = float(trade["exit_price"])

    # ========================================================
    # 5. TWO-POLE FILTER
    # ========================================================

    close_all = bars_all["close"].astype(float)

    length = 34
    damping = 0.9

    omega = 2.0 * np.pi / length
    alpha = damping * omega
    beta = omega ** 2

    f1 = 0.0
    f2 = 0.0
    f2_values = []

    for price in close_all:
        f1 = f1 + alpha * (price - f1)
        f2 = f2 + beta * (f1 - f2)
        f2_values.append(f2)

    trend_all = pd.Series(
        f2_values,
        index=bars_all.index,
        name="Two-Pole Filter",
    )

    trend = trend_all.reindex(bars.index).copy()

    # Ukrycie początkowych 300 świec dotyczy tylko wizualizacji.
    # Nie zmienia obliczeń filtra ani sygnałów.
    trend.iloc[:min(300, len(trend))] = np.nan

    # ========================================================
    # 6. STOCHASTIC 7, 3, 3
    # ========================================================

    lowest_low = bars_all["low"].rolling(
        7, min_periods=7
    ).min()

    highest_high = bars_all["high"].rolling(
        7, min_periods=7
    ).max()

    price_range = highest_high - lowest_low

    raw_k_all = (
        100.0
        * (bars_all["close"] - lowest_low)
        / price_range
    ).where(price_range != 0)

    k_all = raw_k_all.rolling(
        3, min_periods=3
    ).mean()

    d_all = k_all.rolling(
        3, min_periods=3
    ).mean()

    k = k_all.reindex(bars.index)
    d = d_all.reindex(bars.index)

    # ========================================================
    # 7. WYKRES CENY I WSKAŹNIKÓW
    # ========================================================

    addplots = [
        mpf.make_addplot(
            raw_buy,
            type="scatter",
            marker="^",
            markersize=45,
            color="deepskyblue",
        ),
        mpf.make_addplot(
            raw_sell,
            type="scatter",
            marker="v",
            markersize=45,
            color="orange",
        ),
        mpf.make_addplot(
            entries_long,
            type="scatter",
            marker="^",
            markersize=100,
            color="lime",
        ),
        mpf.make_addplot(
            entries_short,
            type="scatter",
            marker="v",
            markersize=100,
            color="red",
        ),
        mpf.make_addplot(
            exits,
            type="scatter",
            marker="x",
            markersize=75,
            color="black",
        ),
        mpf.make_addplot(
            k,
            panel=1,
            color="blue",
            ylabel="Stochastic",
            ylim=(0, 100),
        ),
        mpf.make_addplot(
            d,
            panel=1,
            color="darkorange",
        ),
    ]

    fig, axes = mpf.plot(
        bars,
        type="candle",
        style="yahoo",
        volume=False,
        addplot=addplots,
        panel_ratios=(5, 2),
        figsize=(18, 12),
        title=(
            f"{ASSET} | {TIMEFRAME} | TickTester\n"
            f"{START_DATE} – {END_DATE}"
        ),
        ylabel="Cena Bid",
        datetime_format="%Y-%m-%d %H:%M",
        xrotation=15,
        returnfig=True,
        warn_too_much_data=10000,
    )

    price_ax = axes[0]

    # ========================================================
    # 8. TWO-POLE FILTER W KOLORACH
    # ========================================================

    x = np.arange(len(trend))
    y = trend.to_numpy(dtype=float)

    valid = np.isfinite(y)

    if valid.sum() >= 2:
        points = np.column_stack((x, y)).reshape(-1, 1, 2)
        segments = np.concatenate(
            [points[:-1], points[1:]],
            axis=1,
        )

        delta = trend.diff(2).to_numpy()
        colors = []

        for i in range(len(segments)):
            idx = i + 1

            if (
                not np.isfinite(y[i])
                or not np.isfinite(y[i + 1])
                or idx >= len(delta)
                or not np.isfinite(delta[idx])
            ):
                colors.append("yellow")
            elif delta[idx] > 0:
                colors.append("lime")
            elif delta[idx] < 0:
                colors.append("red")
            else:
                colors.append("yellow")

        line = LineCollection(
            segments,
            colors=colors,
            linewidths=2,
            zorder=5,
        )

        price_ax.add_collection(line)

    # ========================================================
    # 9. POZIOMY SL I TP
    # ========================================================

    if not trades.empty:
        for _, trade in trades.iterrows():
            entry_idx = nearest_bar_index(
                bars.index, trade["entry_time"]
            )
            exit_idx = nearest_bar_index(
                bars.index, trade["exit_time"]
            )

            if exit_idx < entry_idx:
                exit_idx = entry_idx

            sl = trade.get("stop_loss")
            tp = trade.get("take_profit")

            if pd.notna(sl):
                price_ax.hlines(
                    float(sl),
                    entry_idx,
                    exit_idx,
                    colors="red",
                    linestyles="dashed",
                    linewidth=1.0,
                    alpha=0.8,
                )

            if pd.notna(tp):
                price_ax.hlines(
                    float(tp),
                    entry_idx,
                    exit_idx,
                    colors="green",
                    linestyles="dashed",
                    linewidth=1.0,
                    alpha=0.8,
                )

    # ========================================================
    # 10. WYKRES KAPITAŁU POD WYKRESEM CENY
    # ========================================================

    # mplfinance zwraca osie obu paneli; equity dodajemy jako
    # kolejny panel Matplotlib współdzielący oś X z wykresem ceny.
    equity_ax = fig.add_axes(
        [0.10, 0.06, 0.82, 0.16],
        sharex=price_ax,
    )

    equity_ax.set_ylabel("Kapitał ($)")
    equity_ax.set_xlabel("Data")
    equity_ax.axhline(
        INITIAL_CAPITAL,
        linestyle="--",
        linewidth=1,
        color="gray",
        label="Kapitał początkowy",
    )

    if not equity.empty and {"timestamp", "equity"}.issubset(equity.columns):
        equity = equity.sort_values("timestamp")

        times = pd.to_datetime(equity["timestamp"])
        values = pd.to_numeric(equity["equity"], errors="coerce")

        valid_equity = values.notna()
        times = times[valid_equity]
        values = values[valid_equity]

        if len(values) >= 2:
            # Kolor odcinka zależy od położenia obu punktów
            # względem kapitału początkowego.
            for i in range(len(values) - 1):
                x0 = times.iloc[i]
                x1 = times.iloc[i + 1]
                y0 = values.iloc[i]
                y1 = values.iloc[i + 1]

                color = (
                    "green"
                    if y0 >= INITIAL_CAPITAL and y1 >= INITIAL_CAPITAL
                    else "red"
                    if y0 < INITIAL_CAPITAL and y1 < INITIAL_CAPITAL
                    else "gray"
                )

                equity_ax.plot(
                    [x0, x1],
                    [y0, y1],
                    color=color,
                    linewidth=1.5,
                )

            equity_ax.plot(
                times,
                values,
                alpha=0,
            )

        elif len(values) == 1:
            equity_ax.scatter(times, values, s=10)

    else:
        equity_ax.text(
            0.5,
            0.5,
            "Brak danych krzywej kapitału w wybranym okresie",
            ha="center",
            va="center",
            transform=equity_ax.transAxes,
        )

    equity_ax.grid(True, alpha=0.25)
    equity_ax.legend(loc="upper left")

    # Ukrywamy etykiety dat z górnych paneli.
    for ax in axes:
        if ax is not equity_ax:
            ax.tick_params(axis="x", labelbottom=False)

    # Dopasowanie odstępów, żeby panele nie nachodziły na siebie.
    fig.subplots_adjust(
        left=0.10,
        right=0.95,
        top=0.91,
        bottom=0.28,
        hspace=0.05,
    )

    # ========================================================
    # 11. WYNIKI
    # ========================================================

    print("\n=== TRANSAKCJE DO KONTROLI ===")

    if not trades.empty:
        columns = [
            "side",
            "entry_time",
            "exit_time",
            "entry_price",
            "exit_price",
            "stop_loss",
            "take_profit",
            "reason",
            "net_pnl",
        ]

        available_columns = [
            column for column in columns if column in trades.columns
        ]

        print(trades[available_columns].to_string(index=False))
    else:
        print("Brak zamkniętych transakcji w wybranym okresie.")

    print("\n=== PODSUMOWANIE ===")

    # Uwaga: stats z run_backtest obejmuje cały przebieg, w tym
    # ewentualne transakcje z okresu rozgrzewki. Nie należy ich
    # traktować jako statystyk wybranego zakresu.
    for key, value in result["stats"].items():
        print(f"{key}: {value}")

    plt.show()


if __name__ == "__main__":
    main()