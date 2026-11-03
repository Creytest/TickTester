"""
Badanie zdarzeń dla wskaźników bez wejść / SL / TP.

Pierwszy wskaźnik: Auto Levels & Trendlines + Breakout Check
(strategies/tradingview/AutoLevelsTrendlines.py). Autor nie podaje
zasad handlu, więc nie robimy backtestu z kapitałem, tylko liczymy:

1. Ile było wybić i jaki odsetek skrypt oznaczył jako TRUE,
   FALSE, potwierdzone retestem itd.
2. Ruch ceny po 5 / 10 / 20 świecach od zamknięcia świecy
   z sygnałem (w kierunku wybicia), w ATR(14) i w %,
   porównany z losowymi świecami: wszystkie świece z okresu
   z tym samym kierunkiem co sygnał.

Sygnały:
- "breakout": świeca wybicia (alert „breakout”),
- "true":     świeca, na której wybicie zostało uznane za TRUE
              (alert „true breakout”),
- "false":    świeca, na której cena wróciła za granicę (alert
              „false breakout”), ruch liczony w kierunku
              PIERWOTNEGO wybicia (ujemny = cena dalej wraca).

Bez kosztów (spread, prowizja): to nie są transakcje. Dla skali:
typowy spread z danych jest wypisywany obok w ATR.

Wyniki: wyniki/event_study_<wskaźnik>/
    events_<aktywo>_<interwał>.csv — każde wybicie,
    summary.csv                     — tabela zbiorcza.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from tick_config import ASSETS, REVERSE_BID_ASK
from tick_data import load_ticks_cached
from tick_engine import build_bars
from strategies.tiktok.SR_Retest import atr as atr_rma
from strategies.tradingview import AutoLevelsTrendlines as indicator


# ============================================================
# KONFIGURACJA
# ============================================================

ASSETS_TO_TEST = ["XAUUSD", "Bitcoin", "EURUSD", "Brent"]
TIMEFRAMES_TO_TEST = ["15min", "1h", "4h"]

START_DATE = "2021-01-01"
END_DATE = "2025-12-31"

# Świece rozgrzewki przed START_DATE (pivoty, ATR, pierwsze strefy).
WARMUP_DAYS = 90

# Po ilu świecach mierzymy ruch.
HORIZONS = [5, 10, 20]

# Ustawienia wskaźnika inne niż domyślne autora, np. {"conf_bars": 2}.
PARAMS = {}

OUTPUT_DIR = Path(__file__).resolve().parent / "wyniki" / "event_study_AutoLevels"


# ============================================================
# DANE
# ============================================================

def load_bars(asset: str, timeframes: list[str]) -> dict:
    """Świece dla wszystkich interwałów, ticki wczytywane rok po roku."""
    start = pd.Timestamp(START_DATE) - pd.Timedelta(days=WARMUP_DAYS)
    end = pd.Timestamp(END_DATE) + pd.Timedelta(days=1)

    edges = [start] + [
        pd.Timestamp(f"{year}-01-01")
        for year in range(start.year + 1, end.year + 1)
        if pd.Timestamp(f"{year}-01-01") < end
    ] + [end]

    parts = {tf: [] for tf in timeframes}
    spreads = []
    for a, b in zip(edges[:-1], edges[1:]):
        print(f"  ticki {a.date()} – {b.date()}")
        ticks = load_ticks_cached(
            ASSETS[asset],
            reverse_bid_ask=REVERSE_BID_ASK[asset],
            start_date=a.strftime("%Y-%m-%d"),
            end_date=b.strftime("%Y-%m-%d"),
        )
        if ticks.empty:
            continue
        ticks = ticks.sort_values("timestamp").reset_index(drop=True)
        spreads.append(float((ticks["ask"] - ticks["bid"]).median()))
        for tf in timeframes:
            parts[tf].append(build_bars([ticks], tf))
        del ticks

    bars = {}
    for tf in timeframes:
        if parts[tf]:
            df = pd.concat(parts[tf])
            bars[tf] = df[~df.index.duplicated(keep="last")].sort_index()
    spread = float(np.median(spreads)) if spreads else np.nan
    return bars, spread


# ============================================================
# BADANIE
# ============================================================

def forward_moves(close: np.ndarray, at: np.ndarray, dirs: np.ndarray,
                  atr: np.ndarray, h: int):
    """Ruch close[t+h] − close[t] w kierunku dir: (w ATR, w %)."""
    ok = at + h < len(close)
    at, dirs = at[ok], dirs[ok]
    move = (close[at + h] - close[at]) * dirs
    return move / atr[at], move / close[at] * 100


def study(bars: pd.DataFrame, asset: str, tf: str, spread: float):
    events = indicator.breakout_events(bars, **PARAMS)
    first = int(bars.index.searchsorted(pd.Timestamp(START_DATE)))
    events = events[events["breakout_bar"] >= first].reset_index(drop=True)

    close = bars["close"].to_numpy(dtype=float)
    atr = atr_rma(bars, 14)

    # Losowe świece: wszystkie z okresu (z ATR), ruch w górę.
    base_idx = np.arange(first, len(close))
    base_idx = base_idx[~np.isnan(atr[base_idx])]

    n = len(events)
    became_true = events["true_bar"].notna()
    row = {
        "asset": asset,
        "timeframe": tf,
        "bars": len(close) - first,
        "breakouts": n,
        "levels": int((events["kind"] == "level").sum()),
        "lines": int((events["kind"] == "line").sum()),
        "true_pct": _pct(became_true.sum(), n),
        "false_pct": _pct((events["final_state"] == "false").sum(), n),
        "awaiting_pct": _pct((events["final_state"] == "awaiting").sum(), n),
        "retest_confirmed_pct_of_true": _pct(
            (events["final_state"] == "retest_confirmed").sum(), became_true.sum()
        ),
        "retest_failed_pct_of_true": _pct(
            (events["final_state"] == "retest_failed").sum(), became_true.sum()
        ),
        "spread_atr": spread / np.nanmedian(atr[base_idx]) if len(base_idx) else np.nan,
    }

    signals = {
        "breakout": events["breakout_bar"],
        "true": events["true_bar"],
        "false": events["false_bar"].where(events["final_state"] == "false"),
    }

    for h in HORIZONS:
        up_atr, up_pct = forward_moves(close, base_idx, np.ones(len(base_idx)), atr, h)
        for name, col in signals.items():
            mask = col.notna()
            at = col[mask].to_numpy(dtype=int)
            dirs = events.loc[mask, "dir"].to_numpy(dtype=float)
            m_atr, m_pct = forward_moves(close, at, dirs, atr, h)

            # Baseline: losowe świece z tym samym kierunkiem co sygnały.
            share_up = (dirs > 0).mean() if len(dirs) else np.nan
            base_mean = share_up * up_atr.mean() - (1 - share_up) * up_atr.mean()
            base_hit = share_up * (up_atr > 0).mean() + (1 - share_up) * (up_atr < 0).mean()

            key = f"{name}_{h}"
            row[f"{key}_n"] = len(m_atr)
            row[f"{key}_mean_atr"] = _r(m_atr.mean()) if len(m_atr) else np.nan
            row[f"{key}_median_atr"] = _r(np.median(m_atr)) if len(m_atr) else np.nan
            row[f"{key}_mean_pct"] = _r(m_pct.mean(), 4) if len(m_pct) else np.nan
            row[f"{key}_hit_pct"] = _pct((m_atr > 0).sum(), len(m_atr))
            row[f"{key}_base_mean_atr"] = _r(base_mean)
            row[f"{key}_base_hit_pct"] = _r(base_hit * 100, 1)
            # Przybliżony błąd średniej (zdarzenia mogą się nakładać).
            row[f"{key}_se_atr"] = (
                _r(m_atr.std(ddof=1) / np.sqrt(len(m_atr))) if len(m_atr) > 1 else np.nan
            )

    return events, row


def _pct(a, b):
    return round(100 * a / b, 1) if b else np.nan


def _r(x, nd=3):
    return round(float(x), nd)


def print_row(row: dict) -> None:
    print(
        f"  wybić: {row['breakouts']} (poziomy {row['levels']}, linie {row['lines']}) | "
        f"TRUE {row['true_pct']}% | FALSE {row['false_pct']}% | "
        f"retest OK {row['retest_confirmed_pct_of_true']}% / "
        f"failed {row['retest_failed_pct_of_true']}% z TRUE | "
        f"spread ≈ {row['spread_atr']:.3f} ATR"
    )
    for name in ("breakout", "true", "false"):
        parts = []
        for h in HORIZONS:
            k = f"{name}_{h}"
            parts.append(
                f"+{h}: {row[k + '_mean_atr']:+.2f} ATR, w kierunku {row[k + '_hit_pct']}% "
                f"(losowe {row[k + '_base_mean_atr']:+.2f} / {row[k + '_base_hit_pct']}%)"
            )
        print(f"  {name:8s} n={row[f'{name}_{HORIZONS[0]}_n']:5d} | " + " | ".join(parts))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []

    for asset in ASSETS_TO_TEST:
        print("\n" + "=" * 60)
        print(f"{asset} | {START_DATE} – {END_DATE}")
        print("=" * 60)
        try:
            all_bars, spread = load_bars(asset, TIMEFRAMES_TO_TEST)
        except FileNotFoundError as error:
            print(f"POMINIĘTO {asset}: {error}")
            continue

        for tf, bars in all_bars.items():
            print(f"\n--- {asset} | {tf} ({len(bars)} świec) ---")
            events, row = study(bars, asset, tf, spread)
            events.to_csv(
                OUTPUT_DIR / f"events_{asset.replace(' ', '_')}_{tf}.csv", index=False
            )
            print_row(row)
            rows.append(row)

    if rows:
        summary = pd.DataFrame(rows)
        summary.to_csv(OUTPUT_DIR / "summary.csv", index=False)
        print(f"\nZapisano: {OUTPUT_DIR / 'summary.csv'}")


if __name__ == "__main__":
    main()
