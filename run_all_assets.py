from pathlib import Path

import matplotlib

# Wykresy zapisujemy do plików, bez otwierania okien.
matplotlib.use("Agg")

import pandas as pd

from tick_config import ASSETS, COMMISSION
import plot_tick_backtest_xauusd as single
from summary_chart import save_summary_chart
from plansze import save_plansze


# ============================================================
# KONFIGURACJA
# ============================================================

# Plik strategii (bez .py) — wystarczy sama nazwa, folder
# (strategies/tiktok albo strategies/reddit) znajdzie się sam.
#
# ---------------- Strategie z TikToka (strategies/tiktok) ----------------
#   "BigBeluga_Stoch_80percent" — BigBeluga Two-Pole + Stochastic 7,3,3
#   "RSI6_80_20"                — RSI 6 (80/20) RR 2:1
#   "LuxAlgo_SR_Breaks_MSTS"    — LuxAlgo S/R Breaks + Market Structure Trailing Stop
#   "CloudMA_EMA30_74"          — Cloud MA EMA 30/74 + SL na swingu
#   "SFP_Volume"                — SFP+Volume (LuxAlgo SFP + Volume Delta), tylko 30min
#   "EMA9_VWAP"                 — EMA 9 × VWAP (sesyjny), tylko short, wyjście na przecięciu w górę, 30min
#   "EMA9"                      — EMA9 (zamknięcie nad/pod EMA 9, reverse), 30min
#   "SR_Retest"                 — SR Retest (opór/wsparcie z pivotów, wybicie + retest, SL/TP 2:1), 5min
#   "SSL_IFVG"                  — SSL + IFVG (ICT: sweep płynności + odwrócony FVG, SL za luką, TP 2:1), 1min
#
# ---------------- Strategie z Reddita (strategies/reddit) ----------------
#   "IBS_MeanReversion"         — IBS Mean Reversion (zamknięcie pod progiem + IBS < 0,3, wyjście nad wczorajszym high), 1D
#                                 wariant wyjścia: EXIT_MODE w pliku strategii ("high" / "close")
#   "IBS_GoldFutures"           — IBS - gold futures (wybicie Initial Balance 8:20–9:20 NY, SL za IB, TP = szerokość IB,
#                                 wyjście na koniec sesji 13:30 NY), tylko XAUUSD, 1min
#   "RSI_90"                    — RSI 90% (RSI 14 30/70, każdy sygnał +1/10 kapitału, przeciwny odwraca, bez SL)
#   "MOC_MOO"                   — MOC to MOO (kupno na zamknięciu 16:00 NY, sprzedaż na otwarciu 9:30 NY, codziennie),
#                                 tylko US500, 15min
#   "RSI_MACD"                  — RSI MA + MACD (RSI 14 przecina swoją SMA 14, MACD przecina w ciągu 5 świec, reverse, bez SL)
#   "Gold_ThuFri"               — Gold Thursday-Friday (kupno na zamknięciu czwartku, sprzedaż na zamknięciu piątku),
#                                 tylko XAUUSD, 5min; autor: backtest 20 lat — ustaw START_DATE np. "2005-01-01" i CHUNK_YEARS = 5
#   "ATH_ATR"                   — New ATH + ATR trailing (zamknięcie nad szczytem wszech czasów, trailing stop 3 × ATR 14),
#                                 tylko long, 1% ryzyka; szczyt liczony z całego pliku danych, nie tylko z okresu
STRATEGY = "EMA9"

# Każde aktywo jest testowane na każdym z tych interwałów.
# Strategia może je nadpisać własną listą TIMEFRAMES.
TIMEFRAMES_TO_TEST = ["15min", "1h", "4h"]

START_DATE = "2021-01-01"
END_DATE = "2025-12-31"

# Długi okres liczony w kawałkach po tyle lat, żeby ticki
# zmieściły się w pamięci (np. 20 lat złota to ~650 mln ticków).
# Kapitał przechodzi z kawałka na kawałek, a wynik jest sklejony
# w jeden. Pozycja otwarta na koniec kawałka zamyka się na ostatnim
# ticku kawałka. None: cały okres naraz.
CHUNK_YEARS = None

# USA 100 pominięte: dane kończą się w 2014 roku.
# Wszystkie aktywa z tick_config.py: list(ASSETS).
ASSETS_TO_TEST = ["XAUUSD", "Bitcoin", "EURUSD", "Brent"]

# Interaktywny wykres HTML (otwierany w przeglądarce)
# i/lub statyczny obrazek PNG dla każdej kombinacji.
SAVE_HTML = True
SAVE_PNG = False

# Plansze PNG do filmu (1 wykres kapitału, 2 mediany, 3 tabela).
SAVE_PLANSZE = True

# Win Rate obiecany przez autora w procentach, np. 90.
# None: na planszy 2 zamiast Win Rate jest Profit Factor.
CLAIM_WIN_RATE = None

# Folder na wykresy, transakcje i tabelę wyników.
OUTPUT_DIR = Path(__file__).resolve().parent / "wyniki"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    rows = []
    equities = {}

    strategy_module = single.load_strategy(STRATEGY)
    strategy_name = strategy_module.NAME
    timeframes = getattr(strategy_module, "TIMEFRAMES", TIMEFRAMES_TO_TEST)
    # Strategia może ograniczyć aktywa własną listą ASSETS.
    assets = getattr(strategy_module, "ASSETS", ASSETS_TO_TEST)
    print(f"Strategia: {strategy_name}")
    print(f"Interwały: {', '.join(timeframes)}")

    # Najdłuższy interwał wyznacza zapas ticków na rozgrzewkę.
    longest = max(timeframes, key=pd.Timedelta)

    for asset in assets:
        print("\n" + "=" * 60)
        print(f"{asset} | {START_DATE} – {END_DATE}")
        print("=" * 60)

        periods = _periods(START_DATE, END_DATE, CHUNK_YEARS)
        chunked = len(periods) > 1

        # Wyniki kawałków dla każdego interwału.
        capital = {timeframe: single.INITIAL_CAPITAL for timeframe in timeframes}
        parts = {timeframe: [] for timeframe in timeframes}
        errors = {}

        for start, end in periods:
            if chunked:
                print(f"\n>>> Kawałek {start} – {end}")

            # Ticki wczytujemy raz na aktywo (i kawałek),
            # a nie raz na interwał.
            try:
                print("Wczytywanie danych tickowych...")
                ticks = single.load_period_ticks(asset, longest, start, end)
                ticks = ticks.sort_values("timestamp").reset_index(drop=True)
            except FileNotFoundError as error:
                print(f"POMINIĘTO {asset}: {error}")
                errors = {timeframe: error for timeframe in timeframes}
                break

            for timeframe in timeframes:
                print(f"\n--- {asset} | {timeframe} ---")

                name = (
                    f"{STRATEGY}_{asset.replace(' ', '_')}_{timeframe}"
                    f"_{start}_{end}"
                )

                try:
                    stats = single.main(
                        asset=asset,
                        timeframe=timeframe,
                        start_date=start,
                        end_date=end,
                        show=False,
                        save_path=OUTPUT_DIR / f"{name}.png" if SAVE_PNG else None,
                        html_path=OUTPUT_DIR / f"{name}.html" if SAVE_HTML else None,
                        trades_path=None,
                        print_trades=False,
                        ticks=ticks,
                        strategy=STRATEGY,
                        initial_capital=capital[timeframe],
                    )
                except (RuntimeError, ValueError) as error:
                    # Brak danych w kawałku — przechodzimy dalej.
                    print(f"POMINIĘTO {asset} {timeframe} {start} – {end}: {error}")
                    errors[timeframe] = error
                    continue

                capital[timeframe] = stats["final_capital"]
                parts[timeframe].append(
                    (stats.pop("equity"), stats.pop("trades_table"))
                )

            # Zwalniamy pamięć przed kolejnym kawałkiem.
            del ticks

        for timeframe in timeframes:
            if not parts[timeframe]:
                rows.append(_skipped(asset, timeframe, errors.get(timeframe)))
                continue

            name = (
                f"{STRATEGY}_{asset.replace(' ', '_')}_{timeframe}"
                f"_{START_DATE}_{END_DATE}"
            )
            equity = pd.concat(
                [part[0] for part in parts[timeframe]], ignore_index=True
            )
            trades = pd.concat(
                [part[1] for part in parts[timeframe]], ignore_index=True
            )
            if not trades.empty:
                trades.to_csv(
                    OUTPUT_DIR / f"{name}_transakcje.csv",
                    index=False, sep=";", decimal=",",
                )

            # Statystyki całego okresu ze sklejonych kawałków.
            stats = single.period_stats(trades, equity, single.INITIAL_CAPITAL)
            equities[(asset, timeframe)] = equity

            rows.append(
                {
                    "asset": asset,
                    "timeframe": timeframe,
                    "status": "OK",
                    "trades": stats["trades"],
                    "win_rate_%": _pct(stats["win_rate"]),
                    "profit_factor": _round(stats["profit_factor"]),
                    "return_%": _pct(stats["return"]),
                    "cagr_%": _pct(stats["cagr"]),
                    "max_drawdown_%": _pct(stats["max_drawdown"]),
                    "avg_trade_%": _pct(stats["avg_trade"]),
                    "final_capital": round(stats["final_capital"], 2),
                    # Najdłuższa seria strat — gdzie przewinąć wykres.
                    "seria_strat": stats["loss_streak"],
                    "seria_strat_%": _pct(stats["loss_streak_return"]),
                    "seria_od": _date(stats["loss_streak_start"]),
                    "seria_do": _date(stats["loss_streak_end"]),
                    "uwagi": f"pliki: {name}.*"
                    + (f" (wykresy po {CHUNK_YEARS} lat)" if chunked else ""),
                }
            )

    # ========================================================
    # PODSUMOWANIE
    # ========================================================

    summary = pd.DataFrame(rows)

    if "trades" in summary.columns:
        summary["trades"] = summary["trades"].astype("Int64")

    name = f"podsumowanie_{STRATEGY}_{START_DATE}_{END_DATE}"
    table = OUTPUT_DIR / f"{name}.csv"
    summary.to_csv(table, index=False, sep=";", decimal=",")

    costs = "spread z danych + prowizja " + ", ".join(
        f"{asset} {COMMISSION[asset] * 100:.4g}%"
        for asset in assets
    ) + " za stronę + 1 tick poślizgu (przybliżone)"

    ok = summary[summary["status"] == "OK"]

    if not ok.empty:
        save_summary_chart(
            OUTPUT_DIR / f"{name}.html",
            ok,
            title=f"{strategy_name} | {START_DATE} – {END_DATE}",
            costs=costs,
        )

    if SAVE_PLANSZE and not ok.empty:
        save_plansze(
            OUTPUT_DIR / f"plansze_{STRATEGY}_{START_DATE}_{END_DATE}",
            ok,
            equities,
            title=strategy_name,
            period=f"{START_DATE[:4]}–{END_DATE[:4]}",
            costs=costs,
            claim_win_rate=CLAIM_WIN_RATE,
        )

    print("\n" + "=" * 60)
    print(f"PODSUMOWANIE | {strategy_name} | {START_DATE} – {END_DATE} | {costs}")
    print("=" * 60)
    print(
        summary.drop(columns="uwagi")
        .astype(object)
        .fillna("–")
        .to_string(index=False)
    )

    if not ok.empty:
        profitable = int((ok["return_%"] > 0).sum())
        median = ok["return_%"].median()
        print(
            f"\nNa plusie po kosztach: {profitable} z {len(ok)} "
            f"kombinacji. Mediana wyniku netto: {median:.2f}%."
        )

    print(f"\nWykresy i tabela zapisane w: {OUTPUT_DIR}")


def _periods(start_date: str, end_date: str, chunk_years) -> list:
    """Okres podzielony na kawałki po chunk_years lat (daty jako tekst)."""
    if not chunk_years:
        return [(start_date, end_date)]

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    periods = []

    while start <= end:
        stop = min(
            pd.Timestamp(year=start.year + chunk_years, month=1, day=1)
            - pd.Timedelta(days=1),
            end,
        )
        periods.append((start.strftime("%Y-%m-%d"), stop.strftime("%Y-%m-%d")))
        start = stop + pd.Timedelta(days=1)

    return periods


def _skipped(asset, timeframe, error) -> dict:
    return {
        "asset": asset,
        "timeframe": timeframe,
        "status": "pominięto",
        "uwagi": str(error),
    }


def _date(value):
    return None if value is None else value.strftime("%Y-%m-%d %H:%M")


def _pct(value):
    return None if value is None else round(value * 100, 2)


def _round(value):
    return None if value is None else round(value, 2)


if __name__ == "__main__":
    main()
