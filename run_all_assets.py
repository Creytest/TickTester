from pathlib import Path

import matplotlib

# Wykresy zapisujemy do plików, bez otwierania okien.
matplotlib.use("Agg")

import pandas as pd

from tick_config import ASSETS
import plot_tick_backtest_xauusd as single


# ============================================================
# KONFIGURACJA
# ============================================================

TIMEFRAME = "1h"

START_DATE = "2018-01-01"
END_DATE = "2020-12-31"

# Domyślnie wszystkie aktywa z tick_config.py.
# Można zawęzić, np. ["XAUUSD", "EURUSD"].
ASSETS_TO_TEST = list(ASSETS)

# Interaktywny wykres HTML (otwierany w przeglądarce)
# i/lub statyczny obrazek PNG dla każdego aktywa.
SAVE_HTML = True
SAVE_PNG = False

# Folder na wykresy, transakcje i tabelę wyników.
OUTPUT_DIR = Path(__file__).resolve().parent / "wyniki"


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    rows = []

    for asset in ASSETS_TO_TEST:
        print("\n" + "=" * 60)
        print(f"{asset} | {TIMEFRAME} | {START_DATE} – {END_DATE}")
        print("=" * 60)

        name = (
            f"{asset.replace(' ', '_')}_{TIMEFRAME}"
            f"_{START_DATE}_{END_DATE}"
        )
        png = OUTPUT_DIR / f"{name}.png"
        html = OUTPUT_DIR / f"{name}.html"
        trades_csv = OUTPUT_DIR / f"{name}_transakcje.csv"

        try:
            stats = single.main(
                asset=asset,
                timeframe=TIMEFRAME,
                start_date=START_DATE,
                end_date=END_DATE,
                show=False,
                save_path=png if SAVE_PNG else None,
                html_path=html if SAVE_HTML else None,
                trades_path=trades_csv,
                print_trades=False,
            )
        except (FileNotFoundError, RuntimeError, ValueError) as error:
            # Brak pliku lub danych w okresie — przechodzimy dalej.
            print(f"POMINIĘTO {asset}: {error}")
            rows.append(
                {
                    "asset": asset,
                    "status": "pominięto",
                    "uwagi": str(error),
                }
            )
            continue

        rows.append(
            {
                "asset": asset,
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

    # ========================================================
    # PODSUMOWANIE
    # ========================================================

    summary = pd.DataFrame(rows)

    if "trades" in summary.columns:
        summary["trades"] = summary["trades"].astype("Int64")

    table = OUTPUT_DIR / (
        f"podsumowanie_{TIMEFRAME}_{START_DATE}_{END_DATE}.csv"
    )
    summary.to_csv(table, index=False, sep=";", decimal=",")

    print("\n" + "=" * 60)
    print(f"PODSUMOWANIE | {TIMEFRAME} | {START_DATE} – {END_DATE}")
    print("=" * 60)
    print(
        summary.drop(columns="uwagi")
        .astype(object)
        .fillna("–")
        .to_string(index=False)
    )
    print(f"\nWykresy i tabela zapisane w: {OUTPUT_DIR}")


def _pct(value):
    return None if value is None else round(value * 100, 2)


def _round(value):
    return None if value is None else round(value, 2)


if __name__ == "__main__":
    main()
