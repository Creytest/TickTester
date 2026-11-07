"""
Czy rynek wie, że jest wyprzedany? Badanie zdarzeń dla RSI 14.

Zasady testu (ustalone przed wynikami): analizy/event_study_rsi_zasady.md

Zdarzenia:
- "wyprzedanie": RSI przecina 30 w dół,
- "wykupienie":  RSI przecina 70 w górę,
nowe zdarzenie tego samego typu dopiero po COOLDOWN świecach.

Dla każdego zdarzenia: zmiana ceny od zamknięcia świecy sygnałowej
do zamknięcia świecy +1 … +20 (w % i w ATR). Średnia = ścieżka RSI.

Kontrole (N_SIM losowań, w każdym tyle świec, ile zdarzeń):
- A: losowe świece z tego samego okresu,
- B: świece z takim samym ruchem ceny w ostatnich 14 świecach
     (w ATR, ten sam przedział 5-procentowy), bez zdarzenia.

Pas 95% dla całej ścieżki naraz: w każdym losowaniu bierzemy
największe odchylenie (w odchyleniach standardowych) na świecach
1–20; pas = średnia losowa ± 95. percentyl tego maksimum × odch. std.

Bez kosztów (to nie są transakcje). Dla skali w tabeli jest koszt
transakcji w obie strony w %.

Wyniki: wyniki/event_study_RSI/
    summary.csv                         — tabela zbiorcza,
    path_<aktywo>_<interwał>.csv        — ścieżki i pasy (1–20),
    rsi_<aktywo>_<interwał>.png         — wykres do filmu.

Uruchomienie:
    python analizy/event_study_rsi.py
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

# Uruchamianie bezpośrednio z tego folderu: dodaj folder repo do ścieżki importów.
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from narzedzia.tick_config import ASSETS, COMMISSION, REVERSE_BID_ASK
from narzedzia.tick_data import load_ticks_cached
from narzedzia.tick_engine import build_bars
from narzedzia.plansze import (
    BLACK, WHITE, GREEN, RED, GRAY, SIZE, DPI,
    _body_font, _heading_font, _heading_weight,
)
from strategies.tiktok.RSI6_80_20 import rsi
from strategies.tiktok.SR_Retest import atr as atr_rma


# ============================================================
# KONFIGURACJA (zgodnie z event_study_rsi_zasady.md)
# ============================================================

ASSETS_TO_TEST = ["XAUUSD", "Bitcoin", "EURUSD", "Brent", "US500"]

# Interwał -> (początek, koniec). None = od początku danych.
PERIODS = {
    "15min": ("2021-01-01", "2025-12-31"),
    "1h": ("2021-01-01", "2025-12-31"),
    "4h": ("2021-01-01", "2025-12-31"),
    "1D": (None, "2025-12-31"),
}
# Pierwszy rok, od którego szukamy danych dla None.
EARLIEST_YEAR = 2003

RSI_LENGTH = 14
OVERSOLD = 30
OVERBOUGHT = 70
HORIZON = 20
COOLDOWN = 20
LOOKBACK = 14        # ruch przed zdarzeniem dla kontroli B
MATCH_BINS = 20      # przedziały 5-procentowe
N_SIM = 10_000
BAND = 0.95
SEED = 42
MIN_EVENTS = 20      # mniej zdarzeń = brak wniosku

WARMUP_DAYS = 30
SAVE_PNG = True

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "wyniki" / "event_study_RSI"

EVENTS = {
    "wyprzedanie": f"RSI < {OVERSOLD}",
    "wykupienie": f"RSI > {OVERBOUGHT}",
}


# ============================================================
# DANE
# ============================================================

def load_bars(asset: str):
    """Świece dla wszystkich interwałów (ticki rok po roku) i mediana spreadu."""
    ends = [pd.Timestamp(end) + pd.Timedelta(days=1) for _, end in PERIODS.values()]
    starts = [
        pd.Timestamp(start) - pd.Timedelta(days=WARMUP_DAYS) if start
        else pd.Timestamp(f"{EARLIEST_YEAR}-01-01")
        for start, _ in PERIODS.values()
    ]
    start, end = min(starts), max(ends)

    edges = [start] + [
        pd.Timestamp(f"{year}-01-01")
        for year in range(start.year + 1, end.year + 1)
        if pd.Timestamp(f"{year}-01-01") < end
    ] + [end]

    parts = {tf: [] for tf in PERIODS}
    spreads = []
    for a, b in zip(edges[:-1], edges[1:]):
        ticks = load_ticks_cached(
            ASSETS[asset],
            reverse_bid_ask=REVERSE_BID_ASK[asset],
            start_date=a.strftime("%Y-%m-%d"),
            end_date=b.strftime("%Y-%m-%d"),
        )
        if ticks.empty:
            continue
        print(f"  ticki {a.date()} – {b.date()}")
        ticks = ticks.sort_values("timestamp").reset_index(drop=True)
        in_test = ticks["timestamp"] >= pd.Timestamp(PERIODS["1h"][0])
        if in_test.any():
            spread = ticks.loc[in_test, "ask"] - ticks.loc[in_test, "bid"]
            spreads.append(float((spread / ticks.loc[in_test, "bid"]).median()))
        for tf, (tf_start, tf_end) in PERIODS.items():
            lo = pd.Timestamp(tf_start) - pd.Timedelta(days=WARMUP_DAYS) if tf_start else start
            hi = pd.Timestamp(tf_end) + pd.Timedelta(days=1)
            if b <= lo or a >= hi:
                continue
            parts[tf].append(build_bars([ticks], tf))
        del ticks

    bars = {}
    for tf, chunks in parts.items():
        if chunks:
            df = pd.concat(chunks)
            bars[tf] = df[~df.index.duplicated(keep="last")].sort_index()
    spread_pct = float(np.median(spreads)) * 100 if spreads else np.nan
    return bars, spread_pct


# ============================================================
# BADANIE
# ============================================================

def find_events(value: np.ndarray, kind: str, valid: np.ndarray) -> np.ndarray:
    """Indeksy świec z przecięciem progu i odstępem COOLDOWN."""
    prev = np.concatenate(([np.nan], value[:-1]))
    if kind == "wyprzedanie":
        cross = (prev >= OVERSOLD) & (value < OVERSOLD)
    else:
        cross = (prev <= OVERBOUGHT) & (value > OVERBOUGHT)
    candidates = np.flatnonzero(cross & valid)

    events, last = [], -10**9
    for i in candidates:
        if i - last >= COOLDOWN:
            events.append(i)
            last = i
    return np.array(events, dtype=int)


def path_matrix(close: np.ndarray, scale: np.ndarray, idx: np.ndarray) -> np.ndarray:
    """Macierz [len(idx), HORIZON]: zmiana od close[t] do close[t+h] / scale[t]."""
    steps = np.arange(1, HORIZON + 1)
    return (close[idx[:, None] + steps] - close[idx][:, None]) / scale[idx][:, None]


def null_band(pool_paths: np.ndarray, n: int, rng, strata=None):
    """
    Średnie ścieżki N_SIM losowań po n świec. strata: lista
    (pule indeksów w pool_paths, liczba zdarzeń) dla kontroli B.
    Zwraca (średnia, odch. std, macierz średnich [N_SIM, HORIZON]).
    """
    sims = np.empty((N_SIM, HORIZON))
    batch = max(1, 2_000_000 // max(n * HORIZON, 1))
    for s in range(0, N_SIM, batch):
        k = min(batch, N_SIM - s)
        if strata is None:
            pick = rng.integers(0, len(pool_paths), size=(k, n))
        else:
            pick = np.concatenate([
                pool[rng.integers(0, len(pool), size=(k, count))]
                for pool, count in strata
            ], axis=1)
        sims[s:s + k] = pool_paths[pick].mean(axis=1)
    mu = sims.mean(axis=0)
    sd = sims.std(axis=0, ddof=1)
    return mu, sd, sims


def band_test(observed: np.ndarray, mu: np.ndarray, sd: np.ndarray, sims: np.ndarray):
    """Pas dla całej ścieżki (statystyka maksimum) i p-value dwustronne."""
    sd = np.where(sd > 0, sd, np.nan)
    sim_max = np.nanmax(np.abs((sims - mu) / sd), axis=1)
    crit = float(np.quantile(sim_max, BAND))
    obs_max = float(np.nanmax(np.abs((observed - mu) / sd)))
    p = float((np.sum(sim_max >= obs_max) + 1) / (len(sim_max) + 1))
    return mu - crit * sd, mu + crit * sd, p


def study(bars: pd.DataFrame, asset: str, tf: str, spread_pct: float, rng):
    start, end = PERIODS[tf]
    close = bars["close"].to_numpy(dtype=float)
    value = rsi(bars["close"], RSI_LENGTH)
    value = np.asarray(value, dtype=float)
    atr = atr_rma(bars, 14)

    first = int(bars.index.searchsorted(pd.Timestamp(start))) if start else 0
    last = int(bars.index.searchsorted(pd.Timestamp(end) + pd.Timedelta(days=1))) - 1
    n_bars = len(close)

    idx_all = np.arange(n_bars)
    valid = (
        (idx_all >= max(first, LOOKBACK))
        & (idx_all <= min(last, n_bars - 1 - HORIZON))
        & ~np.isnan(value) & ~np.isnan(atr) & (atr > 0)
    )
    pool = np.flatnonzero(valid)
    if len(pool) == 0:
        return None, None

    pool_pct = path_matrix(close, close / 100, pool)
    pool_atr = path_matrix(close, atr, pool)
    past = (close[pool] - close[pool - LOOKBACK]) / atr[pool]
    edges = np.quantile(past, np.linspace(0, 1, MATCH_BINS + 1)[1:-1])
    pool_bin = np.searchsorted(edges, past, side="right")
    position = np.full(n_bars, -1)
    position[pool] = np.arange(len(pool))
    period_start = bars.index[pool[0]]
    period_end = bars.index[pool[-1]]
    mid = pool[len(pool) // 2]

    row = {
        "asset": asset,
        "timeframe": tf,
        "start": period_start.date(),
        "end": period_end.date(),
        "bars": len(pool),
        "cost_roundtrip_pct": round(spread_pct + 2 * COMMISSION[asset] * 100, 4),
    }
    path = {"h": np.arange(1, HORIZON + 1)}

    for kind in EVENTS:
        ev = find_events(value, kind, valid)
        n = len(ev)
        row[f"{kind}_n"] = n
        if n < MIN_EVENTS:
            print(f"  {kind}: {n} zdarzeń — za mało (min {MIN_EVENTS})")
            continue

        ev_pos = position[ev]
        obs_pct = pool_pct[ev_pos].mean(axis=0)
        obs_atr = pool_atr[ev_pos].mean(axis=0)

        # Kontrola A: losowe świece.
        mu_a, sd_a, sims_a = null_band(pool_pct, n, rng)
        lo_a, hi_a, p_a = band_test(obs_pct, mu_a, sd_a, sims_a)
        mu_a_atr = pool_atr.mean(axis=0)

        # Kontrola B: ten sam ruch w ostatnich 14 świecach, bez zdarzenia.
        not_event = np.ones(len(pool), dtype=bool)
        not_event[ev_pos] = False
        strata = []
        for b, count in zip(*np.unique(pool_bin[ev_pos], return_counts=True)):
            members = np.flatnonzero((pool_bin == b) & not_event)
            if len(members):
                strata.append((members, count))
        mu_b, sd_b, sims_b = null_band(pool_pct, n, rng, strata=strata)
        lo_b, hi_b, p_b = band_test(obs_pct, mu_b, sd_b, sims_b)

        h10 = min(10, HORIZON) - 1
        early = ev_pos[ev < mid]
        late = ev_pos[ev >= mid]
        pool_early = pool < mid
        row.update({
            f"{kind}_p_A": round(p_a, 4),
            f"{kind}_p_B": round(p_b, 4),
            f"{kind}_poza_pasem_A": _outside(obs_pct, lo_a, hi_a),
            f"{kind}_poza_pasem_B": _outside(obs_pct, lo_b, hi_b),
            f"{kind}_10_pct": round(obs_pct[h10], 4),
            f"{kind}_10_losowe_pct": round(mu_a[h10], 4),
            f"{kind}_10_ten_sam_spadek_pct": round(mu_b[h10], 4),
            f"{kind}_10_atr": round(obs_atr[h10], 3),
            f"{kind}_10_losowe_atr": round(mu_a_atr[h10], 3),
            f"{kind}_10_w_gore_pct": round(100 * (pool_pct[ev_pos, h10] > 0).mean(), 1),
            f"{kind}_10_losowe_w_gore_pct": round(100 * (pool_pct[:, h10] > 0).mean(), 1),
            f"{kind}_10_1_polowa_pct": _mean(pool_pct[early, h10]),
            f"{kind}_10_1_polowa_losowe_pct": _mean(pool_pct[pool_early, h10]),
            f"{kind}_10_2_polowa_pct": _mean(pool_pct[late, h10]),
            f"{kind}_10_2_polowa_losowe_pct": _mean(pool_pct[~pool_early, h10]),
        })
        path.update({
            f"{kind}_pct": obs_pct,
            f"{kind}_losowe_pct": mu_a,
            f"{kind}_pas_A_dol": lo_a,
            f"{kind}_pas_A_gora": hi_a,
            f"{kind}_ten_sam_spadek_pct": mu_b,
            f"{kind}_pas_B_dol": lo_b,
            f"{kind}_pas_B_gora": hi_b,
        })

    return row, pd.DataFrame(path)


def holm(p_values: pd.Series) -> pd.Series:
    """Korekta Holma dla wielu testów."""
    p = p_values.dropna().sort_values()
    m = len(p)
    adjusted = (p * (m - np.arange(m))).cummax().clip(upper=1.0)
    return adjusted.reindex(p_values.index).round(4)


def _outside(obs, lo, hi) -> str:
    if np.any(obs > hi):
        return "w górę"
    if np.any(obs < lo):
        return "w dół"
    return "nie"


def _mean(values) -> float:
    return round(float(np.mean(values)), 4) if len(values) else np.nan


# ============================================================
# WYKRES
# ============================================================

def save_chart(path: pd.DataFrame, row: dict, file: Path) -> None:
    kinds = [k for k in EVENTS if f"{k}_pct" in path]
    if not kinds:
        return
    font = _body_font()
    fig, axes = plt.subplots(1, len(kinds), figsize=SIZE, dpi=DPI, facecolor=BLACK,
                             squeeze=False)
    fig.subplots_adjust(left=0.06, right=0.97, top=0.78, bottom=0.12, wspace=0.18)
    tf = row["timeframe"].replace("min", "m")
    fig.text(0.04, 0.92, f"CZY RYNEK WIE, ŻE JEST WYPRZEDANY? {row['asset']} {tf}",
             color=WHITE, fontsize=44, fontfamily=_heading_font(),
             fontweight=_heading_weight(), va="center")
    fig.text(0.04, 0.855,
             f"RSI 14 · {row['start']} – {row['end']} · szary pas = 95% wyników "
             f"losowych świec ({N_SIM:,} losowań)".replace(",", " "),
             color=GRAY, fontsize=20, fontfamily=font, va="center")

    h = path["h"].to_numpy()
    for ax, kind in zip(axes[0], kinds):
        ax.set_facecolor(BLACK)
        obs = path[f"{kind}_pct"].to_numpy()
        lo = path[f"{kind}_pas_A_dol"].to_numpy()
        hi = path[f"{kind}_pas_A_gora"].to_numpy()
        expected_up = kind == "wyprzedanie"
        outside = np.any(obs > hi) if expected_up else np.any(obs < lo)
        color = GREEN if outside else RED

        ax.fill_between(h, lo, hi, color=GRAY, alpha=0.30, linewidth=0)
        ax.plot(h, path[f"{kind}_losowe_pct"], color=GRAY, linewidth=1.5)
        ax.plot(h, obs, color=color, linewidth=4)
        ax.axhline(0, color=GRAY, linewidth=0.8, alpha=0.6)

        p = row.get(f"{kind}_p_A")
        ax.set_title(
            f"Po {EVENTS[kind]}  ·  {row[f'{kind}_n']} sygnałów  ·  p = {p:.3f}".replace(".", ","),
            color=WHITE, fontsize=22, fontfamily=font, loc="left", pad=14,
        )
        ax.set_xlabel("świece po sygnale", color=GRAY, fontsize=16, fontfamily=font)
        ax.set_ylabel("średnia zmiana ceny, %", color=GRAY, fontsize=16, fontfamily=font)
        ax.set_xlim(1, HORIZON)
        ax.set_xticks([1, 5, 10, 15, 20])
        ax.tick_params(colors=GRAY, labelsize=14)
        ax.yaxis.set_major_formatter(
            matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.2f}".replace(".", ",").replace("-", "−"))
        )
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(axis="y", color=GRAY, alpha=0.15)

    fig.savefig(file, dpi=DPI, facecolor=BLACK)
    plt.close(fig)


# ============================================================
# START
# ============================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    rows = []

    for asset in ASSETS_TO_TEST:
        print("\n" + "=" * 60)
        print(asset)
        print("=" * 60)
        try:
            all_bars, spread_pct = load_bars(asset)
        except FileNotFoundError as error:
            print(f"POMINIĘTO {asset}: {error}")
            continue

        for tf in PERIODS:
            bars = all_bars.get(tf)
            if bars is None or bars.empty:
                continue
            print(f"\n--- {asset} | {tf} ({len(bars)} świec) ---")
            row, path = study(bars, asset, tf, spread_pct, rng)
            if row is None:
                continue
            name = f"{asset.replace(' ', '_')}_{tf}"
            path.to_csv(OUTPUT_DIR / f"path_{name}.csv", index=False)
            if SAVE_PNG:
                save_chart(path, row, OUTPUT_DIR / f"rsi_{name}.png")
            print_row(row)
            rows.append(row)

    if rows:
        summary = pd.DataFrame(rows)
        for kind in EVENTS:
            for ctrl in ("A", "B"):
                col = f"{kind}_p_{ctrl}"
                if col in summary:
                    summary[f"{col}_holm"] = holm(summary[col])
        summary.to_csv(OUTPUT_DIR / "summary.csv", index=False)
        print(f"\nZapisano: {OUTPUT_DIR / 'summary.csv'}")


def print_row(row: dict) -> None:
    for kind in EVENTS:
        if f"{kind}_p_A" not in row:
            continue
        print(
            f"  {kind:11s} n={row[f'{kind}_n']:5d} | +10 świec: "
            f"{row[f'{kind}_10_pct']:+.3f}% (losowe {row[f'{kind}_10_losowe_pct']:+.3f}%, "
            f"ten sam spadek {row[f'{kind}_10_ten_sam_spadek_pct']:+.3f}%) | "
            f"poza pasem A: {row[f'{kind}_poza_pasem_A']} (p={row[f'{kind}_p_A']}) | "
            f"B: {row[f'{kind}_poza_pasem_B']} (p={row[f'{kind}_p_B']}) | "
            f"koszt {row['cost_roundtrip_pct']:.3f}%"
        )


if __name__ == "__main__":
    main()
