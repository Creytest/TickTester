"""
Ile wyniku zjada spread, a ile prowizja — ta sama strategia,
te same sygnały, cztery warianty kosztów. Bitcoin 2021–2025.

Ustaw STRATEGY niżej (BigBeluga_Stoch_80percent albo EMA9)
i uruchom ten plik. Interwał bierze się z TESTS.

Warianty (logika strategii bez zmian, świece Bid te same):
  A_obecne         spread z ticków Dukascopy + 1 tick + prowizja z tick_config
  B_bez_kosztow    Ask = Bid, bez poślizgu, bez prowizji
  C_binance        Ask = Bid + 0,01 USD (1 tick BTCUSDT) + 1 tick + 0,05%/stronę
  D_tylko_spread   spread z ticków + 1 tick, bez prowizji

Zapisuje do wyniki/<STRATEGY>/koszty_spread/:
  <STRATEGY>_<aktywo>_<interwał>_<wariant>.html — wykres jak z run_all_assets,
  koszty_<aktywo>_<interwał>.csv — tabela porównania.

Dodatkowo (wariant A, strategie z SL): ile SL wybiło wyłącznie przez spread,
czyli Bid (z którego są świece) w trakcie pozycji nie dotknął SL.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Uruchamianie bezpośrednio z tego folderu: dodaj folder repo do ścieżki importów.
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from narzedzia import plot_tick_backtest_xauusd as single


# ============================================================
# KONFIGURACJA
# ============================================================

# "BigBeluga_Stoch_80percent" albo "EMA9".
STRATEGY = "BigBeluga_Stoch_80percent"

# Strategie do tego porównania i ich interwał.
TESTS = {
    "BigBeluga_Stoch_80percent": "1h",
    "EMA9": "30min",
}

ASSET = "Bitcoin"
START_DATE = "2021-01-01"
END_DATE = "2025-12-31"

# Spread na Binance Spot BTCUSDT: zwykle 1 tick (0,01 USD).
BINANCE_SPREAD = 0.01
BINANCE_COMMISSION = 0.0005

SAVE_HTML = True

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "wyniki"


# ============================================================


def variants():
    """(nazwa, Ask = Bid + ta wartość albo None = Ask z danych, prowizja, poślizg w tickach)."""
    return [
        ("A_obecne", None, single.COMMISSION[ASSET], single.SLIPPAGE_TICKS),
        ("B_bez_kosztow", 0.0, 0.0, 0),
        ("C_binance", BINANCE_SPREAD, BINANCE_COMMISSION, 1),
        ("D_tylko_spread", None, 0.0, single.SLIPPAGE_TICKS),
    ]


def spread_only_stops(trades: pd.DataFrame, ticks: pd.DataFrame) -> tuple[int, int]:
    """
    Liczba SL trafionych tylko przez spread i liczba wszystkich SL.
    Short: najwyższy Bid w trakcie pozycji < SL (wybił Ask).
    Long: najniższy Bid > SL (nie zdarza się, Bid jest ceną wyjścia longa).
    """
    if trades.empty or "reason" not in trades.columns:
        return 0, 0

    times = ticks["timestamp"].to_numpy()
    bids = ticks["bid"].to_numpy(dtype=float)
    stops = trades[trades["reason"] == "stop_loss"]
    count = 0

    for trade in stops.itertuples():
        first = times.searchsorted(np.datetime64(trade.entry_time), "left")
        last = times.searchsorted(np.datetime64(trade.exit_time), "right")
        if last <= first:
            continue
        if trade.side == "short" and bids[first:last].max() < trade.stop_loss:
            count += 1
        if trade.side == "long" and bids[first:last].min() > trade.stop_loss:
            count += 1

    return count, len(stops)


def main(strategy: str = STRATEGY, ticks: pd.DataFrame | None = None) -> pd.DataFrame:
    if strategy not in TESTS:
        raise ValueError(
            f"Strategia {strategy} nie jest w TESTS: {', '.join(TESTS)}"
        )

    timeframe = TESTS[strategy]
    strategy_module = single.load_strategy(strategy)
    out_dir = OUTPUT_DIR / strategy / "koszty_spread"
    out_dir.mkdir(parents=True, exist_ok=True)

    if ticks is None:
        print("Wczytywanie danych tickowych...")
        ticks = single.load_period_ticks(
            ASSET, timeframe, START_DATE, END_DATE, strategy_module
        )
        ticks = ticks.sort_values("timestamp").reset_index(drop=True)

    in_period = ticks["timestamp"] >= pd.Timestamp(START_DATE)
    spread = (ticks["ask"] - ticks["bid"])[in_period]
    spread_pct = (spread / ticks["bid"][in_period]).median() * 100
    print(
        f"Spread z danych {ASSET}: mediana {spread.median():.2f}, "
        f"średnia {spread.mean():.2f} ({spread_pct:.4f}% ceny)"
    )

    # Ask zmieniamy w miejscu (bez kopii ticków — oszczędza RAM)
    # i przywracamy na końcu.
    original_ask = ticks["ask"].to_numpy(dtype=float).copy()
    base_commission = single.COMMISSION[ASSET]
    base_slippage = single.SLIPPAGE_TICKS
    base_name = strategy_module.NAME
    rows = []

    try:
        for label, ask_offset, commission, slippage in variants():
            print("\n" + "=" * 60)
            print(f"{strategy} | {ASSET} {timeframe} | {label}")
            print("=" * 60)

            if ask_offset is None:
                ticks["ask"] = original_ask
            else:
                ticks["ask"] = ticks["bid"].to_numpy(dtype=float) + ask_offset

            single.COMMISSION[ASSET] = commission
            single.SLIPPAGE_TICKS = slippage
            # Wariant w tytule wykresu HTML.
            strategy_module.NAME = f"{base_name} | koszty: {label}"

            name = f"{strategy}_{ASSET.replace(' ', '_')}_{timeframe}_{label}"
            stats = single.main(
                asset=ASSET,
                timeframe=timeframe,
                start_date=START_DATE,
                end_date=END_DATE,
                show=False,
                html_path=out_dir / f"{name}.html" if SAVE_HTML else None,
                print_trades=False,
                ticks=ticks,
                strategy=strategy,
            )

            trades = stats["trades_table"]
            spread_sl = all_sl = None
            if label == "A_obecne":
                spread_sl, all_sl = spread_only_stops(trades, ticks)
                if all_sl:
                    distance = (
                        pd.to_numeric(trades["stop_loss"], errors="coerce")
                        - trades["entry_price"]
                    ).abs()
                    print(
                        f"Odległość wejście–SL: mediana {distance.median():.2f}; "
                        f"SL tylko przez spread: {spread_sl} z {all_sl}"
                    )

            rows.append(
                {
                    "wariant": label,
                    "zwrot_%": _pct(stats["return"]),
                    "profit_factor": _round(stats["profit_factor"]),
                    "pf_brutto": _round(stats["profit_factor_gross"]),
                    "win_rate_%": _pct(stats["win_rate"]),
                    "max_drawdown_%": _pct(stats["max_drawdown"]),
                    "transakcje": stats["trades"],
                    "kapital_koncowy": round(stats["final_capital"], 2),
                    "sl_tylko_przez_spread": spread_sl,
                    "sl_wszystkie": all_sl,
                }
            )
    finally:
        ticks["ask"] = original_ask
        single.COMMISSION[ASSET] = base_commission
        single.SLIPPAGE_TICKS = base_slippage
        strategy_module.NAME = base_name

    table = pd.DataFrame(rows)
    print("\n" + "=" * 60)
    print(f"{base_name} | {ASSET} {timeframe} | {START_DATE} – {END_DATE}")
    print(table.to_string(index=False))

    csv_path = out_dir / f"koszty_{ASSET.replace(' ', '_')}_{timeframe}.csv"
    table.to_csv(csv_path, index=False, sep=";", decimal=",")
    print(f"\nZapisano: {csv_path}")
    return table


def _pct(value):
    return None if value is None else round(value * 100, 2)


def _round(value):
    return None if value is None else round(value, 2)


if __name__ == "__main__":
    main()
