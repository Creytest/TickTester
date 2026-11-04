"""
Track record wskaźnika Wyckoff (LunqFX) — to, co autor pokazuje
w panelu "THIS SYMBOL" i każe sprawdzić ("Check the track record
before relying on a schematic: it shows how often ranges on this
symbol and timeframe actually reached T2").

Port 1:1: strategies/tradingview/Wyckoff.py. Bez transakcji i kosztów.

Dla każdego aktywa i interwału, osobno akumulacja i dystrybucja
(tylko zakresy zakończone w okresie, jak w panelu autora):
- liczba zakresów, % ze springiem / UTAD, % z SOS / SOW,
  % T1, % T2, % FAILED, średnia długość zakresu przed wybiciem.

Do tego punkt odniesienia dla zakresów z SOS / SOW:
- "t2_of_sos_pct": jak często po wybiciu cena doszła do T2 (COMPLETE),
- "random_t2_pct": jak często doszłaby, gdyby ruch po wybiciu był
  losowy (błądzenie bez trendu): odległość do INVALID / (odległość
  do T2 + odległość do INVALID), od ceny zamknięcia świecy SOS.
  To przybliżenie (autor liczy T2 knotem, FAILED zamknięciem i ma
  wygaśnięcie po 300 świecach), ale pokazuje, ile T2 „należy się”
  samej geometrii celów. Przewaga = t2_of_sos_pct − random_t2_pct.

Wyniki: wyniki/event_study_Wyckoff/
    schematics_<aktywo>_<interwał>.csv — każdy zakres,
    summary.csv                        — tabela zbiorcza.
"""

from pathlib import Path

import numpy as np
import pandas as pd

import event_study
from strategies.tradingview import Wyckoff as indicator


# ============================================================
# KONFIGURACJA
# ============================================================

ASSETS_TO_TEST = ["XAUUSD", "Bitcoin", "EURUSD", "Brent"]
TIMEFRAMES_TO_TEST = ["15min", "1h", "4h"]

START_DATE = "2021-01-01"
END_DATE = "2025-12-31"

# Świece rozgrzewki przed START_DATE (ATR 50, klimaks z 50 świec).
WARMUP_DAYS = 90

# Ustawienia wskaźnika inne niż domyślne autora, np. {"side": "Accumulation"}.
PARAMS = {}

OUTPUT_DIR = Path(__file__).resolve().parent / "wyniki" / "event_study_Wyckoff"


# ============================================================
# BADANIE
# ============================================================

def _pct(a, b):
    return round(100 * a / b, 1) if b else np.nan


def study(bars: pd.DataFrame, asset: str, tf: str):
    table = indicator.schematics(bars, **PARAMS)
    first = int(bars.index.searchsorted(pd.Timestamp(START_DATE)))
    if len(table):
        table = table[table["climax_bar"] >= first].reset_index(drop=True)

    row = {"asset": asset, "timeframe": tf, "bars": len(bars) - first}
    rec = indicator.track_record(table)
    for name, short in (("accumulation", "acc"), ("distribution", "dist")):
        for key, value in rec[name].items():
            row[f"{short}_{key}"] = value
    row["avg_bars_before_break"] = (
        round(rec["avg_bars_before_break"], 1)
        if not np.isnan(rec["avg_bars_before_break"]) else np.nan
    )

    done = table[table["result"].notna()] if len(table) else table
    sos = done[done["sos"]] if len(done) else done
    row["sos_n"] = len(sos)
    row["t2_of_sos_pct"] = _pct(sos["t2_hit"].sum(), len(sos)) if len(sos) else np.nan
    row["failed_of_sos_pct"] = (
        _pct((sos["result"] == "failed").sum(), len(sos)) if len(sos) else np.nan
    )
    row["expired_of_sos_pct"] = (
        _pct((sos["result"] == "expired").sum(), len(sos)) if len(sos) else np.nan
    )
    if len(sos):
        to_t2 = (sos["t2"] - sos["sos_close"]) * sos["dir"]
        to_inv = (sos["sos_close"] - sos["invalid"]) * sos["dir"]
        ok = (to_t2 > 0) & (to_inv > 0)
        share = to_inv[ok] / (to_t2[ok] + to_inv[ok])
        row["random_t2_pct"] = round(100 * float(share.mean()), 1) if ok.any() else np.nan
        row["t2_dist_atr"] = round(float((to_t2 / sos["sos_atr"]).median()), 2)
        row["inv_dist_atr"] = round(float((to_inv / sos["sos_atr"]).median()), 2)
    else:
        row["random_t2_pct"] = row["t2_dist_atr"] = row["inv_dist_atr"] = np.nan
    row["edge_pct_points"] = (
        round(row["t2_of_sos_pct"] - row["random_t2_pct"], 1)
        if len(sos) and not np.isnan(row["random_t2_pct"]) else np.nan
    )
    return table, row


def print_row(row: dict) -> None:
    for short, label in (("acc", "▲ Akumulacja "), ("dist", "▼ Dystrybucja")):
        print(
            f"  {label} {row[f'{short}_ranges']:4d} zakresów | "
            f"spring/UTAD {row[f'{short}_spring_pct']}% | SOS/SOW {row[f'{short}_sos_pct']}% | "
            f"T1 {row[f'{short}_t1_pct']}% | T2 {row[f'{short}_t2_pct']}% | "
            f"FAILED {row[f'{short}_failed_pct']}%"
        )
    print(
        f"  po wybiciu (n={row['sos_n']}): T2 {row['t2_of_sos_pct']}% vs losowy ruch "
        f"{row['random_t2_pct']}% (przewaga {row['edge_pct_points']} p.p.) | "
        f"FAILED {row['failed_of_sos_pct']}% | wygasło {row['expired_of_sos_pct']}% | "
        f"do T2 {row['t2_dist_atr']} ATR, do INVALID {row['inv_dist_atr']} ATR (mediany) | "
        f"śr. zakres przed wybiciem {row['avg_bars_before_break']} świec"
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # load_bars z event_study.py czyta daty z tamtego modułu.
    event_study.START_DATE = START_DATE
    event_study.END_DATE = END_DATE
    event_study.WARMUP_DAYS = WARMUP_DAYS
    rows = []

    for asset in ASSETS_TO_TEST:
        print("\n" + "=" * 60)
        print(f"{asset} | {START_DATE} – {END_DATE}")
        print("=" * 60)
        try:
            all_bars, _ = event_study.load_bars(asset, TIMEFRAMES_TO_TEST)
        except FileNotFoundError as error:
            print(f"POMINIĘTO {asset}: {error}")
            continue

        for tf, bars in all_bars.items():
            print(f"\n--- {asset} | {tf} ({len(bars)} świec) ---")
            table, row = study(bars, asset, tf)
            table.to_csv(
                OUTPUT_DIR / f"schematics_{asset.replace(' ', '_')}_{tf}.csv", index=False
            )
            print_row(row)
            rows.append(row)

    if rows:
        summary = pd.DataFrame(rows)
        summary.to_csv(OUTPUT_DIR / "summary.csv", index=False)
        print(f"\nZapisano: {OUTPUT_DIR / 'summary.csv'}")


if __name__ == "__main__":
    main()
