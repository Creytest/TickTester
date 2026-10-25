from pathlib import Path

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
    TICK_SIZE,
)
from tick_data import load_ticks_cached
from tick_backtest import run_backtest
from interactive_chart import save_interactive_chart
import importlib


# ============================================================
# KONFIGURACJA
# ============================================================

# Plik strategii z folderu strategies (bez .py).
# Dostępne strategie:
#   "tick_BigBeluga_Stoch_80percent" — BigBeluga Two-Pole + Stochastic 7,3,3
#   "tick_RSI6_80_20"                — RSI 6 (80/20) RR 2:1
STRATEGY = "tick_RSI6_80_20"

ASSET = "XAUUSD"
TIMEFRAME = "5min"

START_DATE = "2014-01-01"
END_DATE = "2014-12-31"

# Liczba świec przed początkiem wybranego okresu,
# które służą do rozgrzania wskaźników.
WARMUP_BARS = 300


# ============================================================
# DANE TICKOWE
# ============================================================

def load_period_ticks(
    asset: str,
    timeframe: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Wczytuje ticki od początku rozgrzewki do końca okresu.

    Przy pierwszym uruchomieniu dla danego roku tworzy pamięć
    podręczną w folderze cache, kolejne uruchomienia są szybkie.
    """
    start = (
        pd.Timestamp(start_date)
        - pd.Timedelta(timeframe) * WARMUP_BARS
    )

    end = pd.Timestamp(end_date) + pd.Timedelta(days=1)

    return load_ticks_cached(
        ASSETS[asset],
        reverse_bid_ask=REVERSE_BID_ASK[asset],
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
    )


def period_stats(
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    initial_capital: float,
) -> dict:
    """
    Statystyki wyłącznie dla wybranego okresu (bez rozgrzewki).

    Kapitał początkowy i końcowy to pierwszy i ostatni punkt
    krzywej kapitału w okresie. Wartości „gross” pomijają prowizje.
    """
    if not equity.empty:
        values = equity.sort_values("timestamp")["equity"].astype(float)
        times = pd.to_datetime(equity.sort_values("timestamp")["timestamp"])
        start_capital = float(values.iloc[0])
        final_capital = float(values.iloc[-1])
        years = (times.iloc[-1] - times.iloc[0]).days / 365.25
    else:
        values = pd.Series([initial_capital], dtype=float)
        start_capital = final_capital = float(initial_capital)
        years = 0.0

    total_return = final_capital / start_capital - 1

    cagr = (
        (final_capital / start_capital) ** (1 / years) - 1
        if years > 0 and final_capital > 0
        else None
    )

    peaks = values.cummax()
    max_drawdown = float((values / peaks - 1).min())

    stats = {
        "start_capital": start_capital,
        "final_capital": final_capital,
        "return": total_return,
        "cagr": cagr,
        "max_drawdown": max_drawdown,
        "trades": len(trades),
        "win_rate": None,
        "profit_factor": None,
        "profit_factor_gross": None,
        "avg_trade": None,
        "avg_trade_gross": None,
    }

    if trades.empty:
        return stats

    def profit_factor(pnl: pd.Series):
        wins = pnl[pnl > 0].sum()
        losses = pnl[pnl < 0].sum()
        if losses < 0:
            return float(wins / abs(losses))
        return float("inf") if wins > 0 else None

    # Kapitał przed transakcją: po zamknięciu silnik zapisuje
    # kapitał powiększony o net_pnl.
    capital_before = trades["capital"] - trades["net_pnl"]

    stats["win_rate"] = float(trades["net_pnl"].gt(0).mean())
    stats["profit_factor"] = profit_factor(trades["net_pnl"])
    stats["profit_factor_gross"] = profit_factor(trades["gross_pnl"])
    stats["avg_trade"] = float((trades["net_pnl"] / capital_before).mean())
    stats["avg_trade_gross"] = float(
        (trades["gross_pnl"] / capital_before).mean()
    )

    return stats


def draw_stats(fig, stats: dict, left: float, right: float) -> None:
    """Rysuje rząd statystyk nad wykresem ceny."""

    def pct(value):
        return "–" if value is None else f"{value * 100:.2f}%"

    def pf(value):
        if value is None:
            return "–"
        return "∞" if value == float("inf") else f"{value:.2f}"

    def sign_color(value):
        if value is None or value == 0:
            return "black"
        return "green" if value > 0 else "red"

    start = stats["start_capital"]
    final = stats["final_capital"]

    items = [
        ("START CAPITAL", f"${start:,.0f}", "black"),
        ("FINAL CAPITAL", f"${final:,.0f}", sign_color(final - start)),
        ("RETURN", pct(stats["return"]), sign_color(stats["return"])),
        ("CAGR", pct(stats["cagr"]), sign_color(stats["cagr"])),
        (
            "MAX DRAWDOWN",
            pct(stats["max_drawdown"]),
            "red" if stats["max_drawdown"] < 0 else "black",
        ),
        ("TRADES", str(stats["trades"]), "black"),
        ("WIN RATE", pct(stats["win_rate"]), "black"),
        (
            "PROFIT FACTOR",
            f"{pf(stats['profit_factor'])} "
            f"({pf(stats['profit_factor_gross'])})",
            "black"
            if stats["profit_factor"] is None
            else ("green" if stats["profit_factor"] >= 1 else "red"),
        ),
        (
            "AVG TRADE",
            f"{pct(stats['avg_trade'])} ({pct(stats['avg_trade_gross'])})",
            sign_color(stats["avg_trade"]),
        ),
    ]

    width = (right - left) / len(items)

    for i, (label, value, color) in enumerate(items):
        x = left + width * (i + 0.5)
        fig.text(
            x, 0.905, label,
            ha="center", va="center", fontsize=9, color="gray",
        )
        fig.text(
            x, 0.885, value,
            ha="center", va="center", fontsize=13,
            fontweight="bold", color=color,
        )

    fig.text(
        right, 0.93,
        "W nawiasach: bez prowizji (gross). Avg trade: % kapitału.",
        ha="right", va="center", fontsize=7, color="gray",
    )


def load_strategy(name: str):
    """Moduł strategii z folderu strategies, np. "tick_RSI6_80_20"."""
    return importlib.import_module(f"strategies.{name}")


def nearest_bar_index(index: pd.DatetimeIndex, timestamp) -> int:
    timestamp = pd.Timestamp(timestamp)
    pos = index.searchsorted(timestamp, side="right") - 1
    return max(0, min(int(pos), len(index) - 1))


def main(
    asset: str = ASSET,
    timeframe: str = TIMEFRAME,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    show: bool = True,
    save_path=None,
    html_path=None,
    trades_path=None,
    print_trades: bool = True,
    ticks: pd.DataFrame | None = None,
    strategy: str = STRATEGY,
) -> dict:
    """
    Backtest jednego aktywa z wykresem.

    show=False i save_path pozwalają zapisać wykres do pliku
    bez otwierania okna (używa tego run_all_assets.py).
    html_path zapisuje interaktywny wykres HTML, trades_path
    listę transakcji do CSV. Zwraca statystyki wybranego okresu.

    ticks pozwala podać ticki wczytane wcześniej (posortowane,
    z zapasem na rozgrzewkę), np. raz dla kilku interwałów.
    """
    strategy_module = load_strategy(strategy)

    start_time = pd.Timestamp(start_date)
    end_time = pd.Timestamp(end_date) + pd.Timedelta(days=1)

    if end_time <= start_time:
        raise ValueError("END_DATE musi być późniejsza niż START_DATE.")

    # ========================================================
    # 1. USTALENIE ZAKRESU DANYCH I ROZGRZEWKI
    # ========================================================

    if ticks is None:
        print("Wczytywanie danych tickowych...")

        all_ticks = load_period_ticks(
            asset, timeframe, start_date, end_date
        )
        all_ticks = all_ticks.sort_values("timestamp").reset_index(
            drop=True
        )
    else:
        all_ticks = ticks

    if all_ticks.empty:
        raise RuntimeError("Nie znaleziono danych tickowych.")

    selected_ticks = all_ticks[
        (all_ticks["timestamp"] >= start_time)
        & (all_ticks["timestamp"] < end_time)
    ]

    if selected_ticks.empty:
        raise RuntimeError(
            f"Brak ticków w okresie {start_date} – {end_date}. "
            "Sprawdź zakres dat i ścieżkę w tick_config.py."
        )

    first_selected_tick = selected_ticks["timestamp"].iloc[0]

    # Początek świecy, na której znajduje się pierwszy tick okresu.
    first_selected_bar = first_selected_tick.floor(timeframe)

    # Potrzebujemy świec poprzedzających wybrany okres.
    warmup_start = first_selected_bar - pd.Timedelta(
        timeframe
    ) * WARMUP_BARS

    print(f"Okres backtestu: {start_date} – {end_date}")
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

        # Silnik oczekuje iteratora DataFrame'ów.
        yield all_ticks.loc[mask].reset_index(drop=True)

    result = run_backtest(
        tick_source=backtest_tick_source,
        strategy=strategy_module.generate_signals,
        timeframe=timeframe,
        initial_capital=INITIAL_CAPITAL,
        commission=COMMISSION[asset],
        slippage_ticks=SLIPPAGE_TICKS,
        tick_size=TICK_SIZE[asset],
        risk_per_trade=RISK_PER_TRADE,
        # Świece rozgrzewki liczą wskaźniki, ale nie handlują.
        trade_start=start_time,
        opposite_signal=strategy_module.OPPOSITE_SIGNAL,
        same_signal=strategy_module.SAME_SIGNAL,
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

    signals = strategy_module.generate_signals(bars_all.copy())
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
    # 5. WSKAŹNIKI STRATEGII DO WYKRESU
    # ========================================================

    # Liczone na świecach z rozgrzewką, pokazywane tylko w okresie.
    indicators = strategy_module.indicators(bars_all.copy())

    trend = indicators.get("trend")

    if trend is not None:
        trend = trend.reindex(bars.index).copy()

        # Ukrycie początkowych 300 świec dotyczy tylko wizualizacji.
        # Nie zmienia obliczeń filtra ani sygnałów.
        trend.iloc[:min(300, len(trend))] = np.nan

    panel = dict(indicators["panel"])
    panel["lines"] = [
        (name, series.reindex(bars.index), color)
        for name, series, color in panel["lines"]
    ]

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
    ]

    for number, (_, series, color) in enumerate(panel["lines"]):
        addplots.append(
            mpf.make_addplot(
                series,
                panel=1,
                color=color,
                ylabel=panel["title"] if number == 0 else "",
                ylim=(0, 100),
            )
        )

    fig, axes = mpf.plot(
        bars,
        type="candle",
        style="yahoo",
        volume=False,
        addplot=addplots,
        panel_ratios=(5, 2),
        figsize=(18, 12),
        title=(
            f"{asset} | {timeframe} | {strategy_module.NAME}\n"
            f"{start_date} – {end_date}"
        ),
        ylabel="Cena Bid",
        datetime_format="%Y-%m-%d %H:%M",
        xrotation=15,
        returnfig=True,
        warn_too_much_data=len(bars) + 1,
    )

    price_ax = axes[0]

    # ========================================================
    # 8. TWO-POLE FILTER W KOLORACH
    # ========================================================

    x = np.arange(len(bars))
    y = (
        trend.to_numpy(dtype=float)
        if trend is not None
        else np.full(len(bars), np.nan)
    )

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
    # Szerokość i lewa krawędź jak w panelu ceny, aby daty
    # obu wykresów pokrywały się w pionie.
    price_box = price_ax.get_position()

    equity_ax = fig.add_axes(
        [price_box.x0, 0.06, price_box.width, 0.14],
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

        # Oś X jest współdzielona ze świecami, które mplfinance
        # rysuje w numerach świec (0, 1, 2...), a nie w datach.
        # Zamieniamy więc czas każdego punktu na numer świecy.
        positions = bars.index.searchsorted(times, side="right") - 1
        x_equity = np.clip(positions, 0, len(bars) - 1).astype(float)
        y_equity = values.to_numpy(dtype=float)

        if len(y_equity) >= 2:
            # Kolor odcinka zależy od położenia obu punktów
            # względem kapitału początkowego.
            y0 = y_equity[:-1]
            y1 = y_equity[1:]

            colors = np.where(
                (y0 >= INITIAL_CAPITAL) & (y1 >= INITIAL_CAPITAL),
                "green",
                np.where(
                    (y0 < INITIAL_CAPITAL) & (y1 < INITIAL_CAPITAL),
                    "red",
                    "gray",
                ),
            )

            points = np.column_stack((x_equity, y_equity))
            segments = np.stack((points[:-1], points[1:]), axis=1)

            equity_ax.add_collection(
                LineCollection(
                    segments,
                    colors=list(colors),
                    linewidths=1.5,
                )
            )

            equity_ax.set_ylim(
                min(y_equity.min(), INITIAL_CAPITAL) * 0.995,
                max(y_equity.max(), INITIAL_CAPITAL) * 1.005,
            )

        elif len(y_equity) == 1:
            equity_ax.scatter(x_equity, y_equity, s=10)

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

    # Statystyki okresu nad wykresem ceny.
    stats = period_stats(trades, equity, INITIAL_CAPITAL)
    draw_stats(fig, stats, 0.04, 0.96)

    # ========================================================
    # 11. WYNIKI
    # ========================================================

    if trades_path is not None and not trades.empty:
        trades.to_csv(trades_path, index=False, sep=";", decimal=",")

    if html_path is not None:
        try:
            save_interactive_chart(
                html_path,
                title=(
                    f"{asset} | {timeframe} | {start_date} – {end_date}"
                    f" | {strategy_module.NAME}"
                ),
                bars=bars,
                signals=signals,
                trades=trades,
                trend=trend,
                panel=panel,
                equity=equity,
                stats=stats,
                initial_capital=INITIAL_CAPITAL,
            )
        except ImportError:
            print(
                "Brak biblioteki plotly — wykres HTML pominięty. "
                "Zainstaluj ją komendą: pip install plotly"
            )

    if print_trades:
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

    print("\n=== PODSUMOWANIE OKRESU ===")

    # Statystyki tylko dla wybranego okresu, bez rozgrzewki —
    # te same, które są pokazane nad wykresem.
    for key, value in stats.items():
        print(f"{key}: {value}")

    if save_path is not None:
        fig.savefig(save_path, dpi=100)

    if show:
        plt.show()
    else:
        plt.close(fig)

    return stats


if __name__ == "__main__":
    # Obok okna matplotlib zapisujemy interaktywny wykres HTML.
    output_dir = Path(__file__).resolve().parent / "wyniki"
    output_dir.mkdir(exist_ok=True)

    main(
        html_path=output_dir / (
            f"{STRATEGY}_{ASSET.replace(' ', '_')}_{TIMEFRAME}"
            f"_{START_DATE}_{END_DATE}.html"
        )
    )
