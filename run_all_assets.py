from pathlib import Path

import matplotlib

# Wykresy zapisujemy do plików, bez otwierania okien.
matplotlib.use("Agg")

import pandas as pd

from tick_config import ASSETS, COMMISSION
import plot_tick_backtest_xauusd as single
from summary_chart import save_summary_chart


# ============================================================
# KONFIGURACJA
# ============================================================

# Każde aktywo jest testowane na każdym z tych interwałów.
TIMEFRAMES_TO_TEST = ["15min", "1h", "4h"]

START_DATE = "2021-01-01"
END_DATE = "2025-12-31"

# USA 100 pominięte: dane kończą się w 2014 roku.
# Wszystkie aktywa z tick_config.py: list(ASSETS).
ASSETS_TO_TEST = ["XAUUSD", "Bitcoin", "EURUSD", "Brent"]

# Interaktywny wykres HTML (otwierany w przeglądarce)
# i/lub statyczny obrazek PNG dla każdej kombinacji.
SAVE_HTML = True
SAVE_PNG = False

# Folder na wykresy, transakcje i tabelę wyników.
OUTPUT_DIR = Path(__file__).resolve().parent / "wyniki"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    rows = []

    # Najdłuższy interwał wyznacza zapas ticków na rozgrzewkę.
    longest = max(TIMEFRAMES_TO_TEST, key=pd.Timedelta)

    for asset in ASSETS_TO_TEST:
        print("\n" + "=" * 60)
        print(f"{asset} | {START_DATE} – {END_DATE}")
        print("=" * 60)

        # Ticki wczytujemy raz na aktywo, a nie raz na interwał.
        try:
            print("Wczytywanie danych tickowych...")
            ticks = single.load_period_ticks(
                asset, longest, START_DATE, END_DATE
            )
            ticks = ticks.sort_values("timestamp").reset_index(drop=True)
        except FileNotFoundError as error:
            print(f"POMINIĘTO {asset}: {error}")
            for timeframe in TIMEFRAMES_TO_TEST:
                rows.append(_skipped(asset, timeframe, error))
            continue

        for timeframe in TIMEFRAMES_TO_TEST:
            print(f"\n--- {asset} | {timeframe} ---")

            name = (
                f"{asset.replace(' ', '_')}_{timeframe}"
                f"_{START_DATE}_{END_DATE}"
            )
            png = OUTPUT_DIR / f"{name}.png"
            html = OUTPUT_DIR / f"{name}.html"
            trades_csv = OUTPUT_DIR / f"{name}_transakcje.csv"

            try:
                stats = single.main(
                    asset=asset,
                    timeframe=timeframe,
                    start_date=START_DATE,
                    end_date=END_DATE,
                    show=False,
                    save_path=png if SAVE_PNG else None,
                    html_path=html if SAVE_HTML else None,
                    trades_path=trades_csv,
                    print_trades=False,
                    ticks=ticks,
                )
            except (RuntimeError, ValueError) as error:
                # Brak danych w okresie — przechodzimy dalej.
                print(f"POMINIĘTO {asset} {timeframe}: {error}")
                rows.append(_skipped(asset, timeframe, error))
                continue

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
                    "uwagi": f"pliki: {name}.*",
                }
            )

        # Zwalniamy pamięć przed kolejnym aktywem.
        del ticks

    # ========================================================
    # PODSUMOWANIE
    # ========================================================

    summary = pd.DataFrame(rows)

    if "trades" in summary.columns:
        summary["trades"] = summary["trades"].astype("Int64")

    name = f"podsumowanie_{START_DATE}_{END_DATE}"
    table = OUTPUT_DIR / f"{name}.csv"
    summary.to_csv(table, index=False, sep=";", decimal=",")

    costs = "spread z danych + prowizja " + ", ".join(
        f"{asset} {COMMISSION[asset] * 100:.4g}%"
        for asset in ASSETS_TO_TEST
    ) + " za stronę + 1 tick poślizgu (przybliżone)"

    ok = summary[summary["status"] == "OK"]

    if not ok.empty:
        save_summary_chart(
            OUTPUT_DIR / f"{name}.html",
            ok,
            title=f"Wszystkie kombinacje | {START_DATE} – {END_DATE}",
            costs=costs,
        )

    print("\n" + "=" * 60)
    print(f"PODSUMOWANIE | {START_DATE} – {END_DATE} | {costs}")
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


def _skipped(asset, timeframe, error) -> dict:
    return {
        "asset": asset,
        "timeframe": timeframe,
        "status": "pominięto",
        "uwagi": str(error),
    }


def _pct(value):
    return None if value is None else round(value * 100, 2)


def _round(value):
    return None if value is None else round(value, 2)


if __name__ == "__main__":
    main()
