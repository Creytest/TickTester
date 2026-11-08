"""
Czy formacje świecowe przewidują kierunek? Badanie zdarzeń dla 12 formacji
z planszy „Candlestick Patterns” (TredWithRahul).

Zasady testu (ustalone przed wynikami): analizy/event_study_candles_zasady.md
Definicje formacji: analizy/formacje_swiecowe.py

Dla każdej formacji i wariantu (bez kontekstu / z kontekstem SMA 20):
zmiana ceny od zamknięcia ostatniej świecy formacji do zamknięcia świecy
+1 … +20 (w % i w ATR). Średnia = ścieżka formacji.

Kontrole (N_SIM losowań, metoda jak w event_study_rsi.py):
- A: losowe świece z tego samego okresu,
- B: (tylko wariant z kontekstem) świece z takim samym ruchem ceny
     w ostatnich 14 świecach, bez formacji.

Wyniki: wyniki/event_study_candles/
    summary.csv                          — wiersz = aktywo × interwał × formacja ×
                                           wariant (dopisywany po każdej kombinacji),
    ranking.csv, ranking.png             — w ilu kombinacjach formacja wychodzi
                                           z pasu w kierunku z planszy,
    path_<aktywo>_<interwał>.csv         — ścieżki i pasy (1–20),
    formacje_<aktywo>_<interwał>_<wariant>.png — siatka 12 wykresów do filmu.

Uruchomienie:
    python analizy/event_study_candles.py
Sam ranking z istniejącego summary.csv:
    python analizy/event_study_candles.py --ranking
"""

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np
import pandas as pd

# Uruchamianie bezpośrednio z tego folderu: dodaj folder repo do ścieżki importów.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from narzedzia.tick_config import COMMISSION
from narzedzia.plansze import (
    BLACK, WHITE, GREEN, RED, GRAY, SIZE, DPI,
    _body_font, _heading_font, _heading_weight,
)
from strategies.tiktok.SR_Retest import atr as atr_rma
from analizy.formacje_swiecowe import PATTERNS, detect_patterns, context_mask
# Wspólne z badaniem RSI: dane, ścieżki, pas, korekta Holma.
from analizy.event_study_rsi import (
    load_bars, path_matrix, null_band, band_test, holm, _outside, _mean,
)
import analizy.event_study_rsi as rsi_study


# ============================================================
# KONFIGURACJA (zgodnie z event_study_candles_zasady.md)
# ============================================================

ASSETS_TO_TEST = ["XAUUSD", "Bitcoin", "EURUSD", "Brent", "US500"]

# Interwał -> (początek, koniec). None = od początku danych.
PERIODS = {
    "15min": ("2021-01-01", "2025-12-31"),
    "1h": ("2021-01-01", "2025-12-31"),
    "4h": ("2021-01-01", "2025-12-31"),
    "1D": (None, "2025-12-31"),
}

HORIZON = 20
COOLDOWN = 20
LOOKBACK = 14        # ruch przed zdarzeniem dla kontroli B
MATCH_BINS = 20      # przedziały 5-procentowe
SMA_CONTEXT = 20
N_SIM = 10_000
BAND = 0.95
SEED = 42
MIN_EVENTS = 20      # mniej zdarzeń = brak wniosku
SAVE_PNG = True

VARIANTS = {
    "bez_kontekstu": "bez kontekstu",
    "z_kontekstem": f"po spadku / wzroście (SMA {SMA_CONTEXT})",
}

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "wyniki" / "event_study_candles"

# Funkcje z event_study_rsi czytają te stałe ze swojego modułu.
rsi_study.PERIODS = PERIODS
rsi_study.HORIZON = HORIZON
rsi_study.N_SIM = N_SIM
rsi_study.BAND = BAND


# ============================================================
# BADANIE
# ============================================================

def find_events(signal: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Indeksy świec z formacją, z odstępem COOLDOWN."""
    events, last = [], -10**9
    for i in np.flatnonzero(signal & valid):
        if i - last >= COOLDOWN:
            events.append(i)
            last = i
    return np.array(events, dtype=int)


def study(bars: pd.DataFrame, asset: str, tf: str, spread_pct: float, rng):
    start, end = PERIODS[tf]
    close = bars["close"].to_numpy(dtype=float)
    atr = atr_rma(bars, 14)
    signals = detect_patterns(bars, atr)
    context = context_mask(bars, SMA_CONTEXT)

    first = int(bars.index.searchsorted(pd.Timestamp(start))) if start else 0
    last = int(bars.index.searchsorted(pd.Timestamp(end) + pd.Timedelta(days=1))) - 1
    n_bars = len(close)

    idx_all = np.arange(n_bars)
    valid = (
        (idx_all >= max(first, LOOKBACK, SMA_CONTEXT + 3))
        & (idx_all <= min(last, n_bars - 1 - HORIZON))
        & ~np.isnan(atr) & (atr > 0)
    )
    pool = np.flatnonzero(valid)
    if len(pool) == 0:
        return [], None

    pool_pct = path_matrix(close, close / 100, pool)
    pool_atr = path_matrix(close, atr, pool)
    mu_a_atr = pool_atr.mean(axis=0)
    past = (close[pool] - close[pool - LOOKBACK]) / atr[pool]
    edges = np.quantile(past, np.linspace(0, 1, MATCH_BINS + 1)[1:-1])
    pool_bin = np.searchsorted(edges, past, side="right")
    position = np.full(n_bars, -1)
    position[pool] = np.arange(len(pool))
    mid = pool[len(pool) // 2]
    pool_early = pool < mid
    h10 = min(10, HORIZON) - 1

    base = {
        "asset": asset,
        "timeframe": tf,
        "start": bars.index[pool[0]].date(),
        "end": bars.index[pool[-1]].date(),
        "bars": len(pool),
        "cost_roundtrip_pct": round(spread_pct + 2 * COMMISSION[asset] * 100, 4),
    }
    rows = []
    path = {"h": np.arange(1, HORIZON + 1)}

    for name, (direction, _) in PATTERNS.items():
        for variant in VARIANTS:
            signal = signals[name]
            if variant == "z_kontekstem":
                signal = signal & context[name]
            ev = find_events(signal, valid)
            n = len(ev)
            row = dict(base, formacja=name, kierunek_plansza="w górę" if direction > 0 else "w dół",
                       wariant=variant, n=n)
            if n < MIN_EVENTS:
                row["wynik"] = "brak wniosku"
                rows.append(row)
                continue

            ev_pos = position[ev]
            obs_pct = pool_pct[ev_pos].mean(axis=0)
            obs_atr = pool_atr[ev_pos].mean(axis=0)

            # Kontrola A: losowe świece.
            mu_a, sd_a, sims_a = null_band(pool_pct, n, rng)
            lo_a, hi_a, p_a = band_test(obs_pct, mu_a, sd_a, sims_a)

            promised = np.any(obs_pct > hi_a) if direction > 0 else np.any(obs_pct < lo_a)
            opposite = np.any(obs_pct < lo_a) if direction > 0 else np.any(obs_pct > hi_a)
            if promised:
                verdict = "zgodnie z planszą"
            elif opposite:
                verdict = "odwrotnie niż plansza"
            else:
                verdict = "jak przypadek"

            early = ev_pos[ev < mid]
            late = ev_pos[ev >= mid]
            row.update({
                "wynik": verdict,
                "p_A": round(p_a, 4),
                "poza_pasem_A": _outside(obs_pct, lo_a, hi_a),
                "10_pct": round(obs_pct[h10], 4),
                "10_losowe_pct": round(mu_a[h10], 4),
                "10_atr": round(obs_atr[h10], 3),
                "10_losowe_atr": round(mu_a_atr[h10], 3),
                "10_w_gore_pct": round(100 * (pool_pct[ev_pos, h10] > 0).mean(), 1),
                "10_losowe_w_gore_pct": round(100 * (pool_pct[:, h10] > 0).mean(), 1),
                "10_1_polowa_pct": _mean(pool_pct[early, h10]),
                "10_1_polowa_losowe_pct": _mean(pool_pct[pool_early, h10]),
                "10_2_polowa_pct": _mean(pool_pct[late, h10]),
                "10_2_polowa_losowe_pct": _mean(pool_pct[~pool_early, h10]),
            })
            key = f"{name}|{variant}"
            path.update({
                f"{key}|pct": obs_pct,
                f"{key}|losowe_pct": mu_a,
                f"{key}|pas_A_dol": lo_a,
                f"{key}|pas_A_gora": hi_a,
            })

            # Kontrola B: ten sam ruch w ostatnich 14 świecach, bez formacji.
            if variant == "z_kontekstem":
                not_event = np.ones(len(pool), dtype=bool)
                not_event[ev_pos] = False
                strata = []
                for b, count in zip(*np.unique(pool_bin[ev_pos], return_counts=True)):
                    members = np.flatnonzero((pool_bin == b) & not_event)
                    if len(members):
                        strata.append((members, count))
                mu_b, sd_b, sims_b = null_band(pool_pct, n, rng, strata=strata)
                lo_b, hi_b, p_b = band_test(obs_pct, mu_b, sd_b, sims_b)
                row.update({
                    "p_B": round(p_b, 4),
                    "poza_pasem_B": _outside(obs_pct, lo_b, hi_b),
                    "10_ten_sam_ruch_pct": round(mu_b[h10], 4),
                })
                path.update({
                    f"{key}|ten_sam_ruch_pct": mu_b,
                    f"{key}|pas_B_dol": lo_b,
                    f"{key}|pas_B_gora": hi_b,
                })
            rows.append(row)

    return rows, pd.DataFrame(path)


# ============================================================
# ZAPIS
# ============================================================

def save_summary(rows: list) -> pd.DataFrame:
    """
    Dopisuje wiersze kombinacji do summary.csv. Wyniki z wcześniejszych
    biegów zostają (to samo aktywo × interwał jest zastępowane),
    korekty Holma liczą się od nowa po wszystkich.
    """
    file = OUTPUT_DIR / "summary.csv"
    new = pd.DataFrame(rows)
    if file.exists():
        old = pd.read_csv(file)
        old = old.loc[:, [c for c in old.columns if "_holm" not in c]]
        same = (old["asset"] == rows[0]["asset"]) & (old["timeframe"] == rows[0]["timeframe"])
        summary = pd.concat([old[~same], new], ignore_index=True)
    else:
        summary = new
    for ctrl in ("A", "B"):
        col = f"p_{ctrl}"
        if col not in summary:
            continue
        summary[f"{col}_holm_formacja"] = np.nan
        for _, group in summary.groupby(["formacja", "wariant"]):
            summary.loc[group.index, f"{col}_holm_formacja"] = holm(group[col])
        summary[f"{col}_holm_wszystko"] = holm(summary[col])
    summary.to_csv(file, index=False)
    print(f"  zapisano summary.csv ({len(summary)} wierszy)")
    return summary


def ranking(summary: pd.DataFrame) -> pd.DataFrame:
    """Dla każdej formacji i wariantu: ile kombinacji zgodnie / odwrotnie / jak przypadek."""
    out = []
    for name, (direction, _) in PATTERNS.items():
        for variant in VARIANTS:
            g = summary[(summary["formacja"] == name) & (summary["wariant"] == variant)]
            if g.empty:
                continue
            tested = g[g["wynik"] != "brak wniosku"]
            holm_ok = 0
            if "p_A_holm_formacja" in tested:
                holm_ok = int(((tested["wynik"] == "zgodnie z planszą")
                               & (tested["p_A_holm_formacja"] < 0.05)).sum())
            out.append({
                "formacja": name,
                "kierunek_plansza": "w górę" if direction > 0 else "w dół",
                "wariant": variant,
                "kombinacje": len(g),
                "przetestowane": len(tested),
                "zgodnie_z_plansza": int((tested["wynik"] == "zgodnie z planszą").sum()),
                "zgodnie_po_Holmie": holm_ok,
                "odwrotnie": int((tested["wynik"] == "odwrotnie niż plansza").sum()),
                "jak_przypadek": int((tested["wynik"] == "jak przypadek").sum()),
                "brak_wniosku": len(g) - len(tested),
                "mediana_10_pct": _median(tested.get("10_pct")),
                "mediana_10_losowe_pct": _median(tested.get("10_losowe_pct")),
                "mediana_kosztu_pct": _median(tested.get("cost_roundtrip_pct")),
            })
    return pd.DataFrame(out)


def _median(values) -> float:
    if values is None or len(values) == 0:
        return np.nan
    return round(float(np.median(values)), 4)


# ============================================================
# WYKRESY
# ============================================================

def _style(ax, font):
    ax.set_facecolor(BLACK)
    ax.tick_params(colors=GRAY, labelsize=11)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color=GRAY, alpha=0.15)
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(
        lambda v, _: f"{v:+.2f}".replace(".", ",").replace("-", "−")))


def save_grid(path: pd.DataFrame, rows: list, variant: str, file: Path) -> None:
    """Siatka 2 × 6: górny rząd bullish, dolny bearish (jak kolumny planszy)."""
    font = _body_font()
    by_name = {r["formacja"]: r for r in rows if r["wariant"] == variant}
    first = rows[0]
    fig, axes = plt.subplots(2, 6, figsize=SIZE, dpi=DPI, facecolor=BLACK)
    fig.subplots_adjust(left=0.05, right=0.98, top=0.74, bottom=0.07, wspace=0.38, hspace=0.42)
    tf = first["timeframe"].replace("min", "m")
    fig.text(0.04, 0.93, f"FORMACJE ŚWIECOWE · {first['asset']} {tf}",
             color=WHITE, fontsize=44, fontfamily=_heading_font(),
             fontweight=_heading_weight(), va="center")
    fig.text(0.04, 0.865,
             f"{VARIANTS[variant]} · {first['start']} – {first['end']} · "
             f"średnia zmiana ceny w % · szary pas = 95% wyników losowych świec",
             color=GRAY, fontsize=18, fontfamily=font, va="center")

    bullish = [n for n, (d, _) in PATTERNS.items() if d > 0]
    bearish = [n for n, (d, _) in PATTERNS.items() if d < 0]
    h = path["h"].to_numpy()
    for r, names in enumerate((bullish, bearish)):
        for c, name in enumerate(names):
            ax = axes[r, c]
            _style(ax, font)
            row = by_name.get(name, {})
            key = f"{name}|{variant}"
            ax.set_title(name, color=WHITE, fontsize=15, fontfamily=font, loc="left", pad=22)
            if f"{key}|pct" not in path:
                ax.text(0.5, 0.5, f"za mało sygnałów\n({row.get('n', 0)})", color=GRAY,
                        fontsize=13, fontfamily=font, ha="center", va="center",
                        transform=ax.transAxes)
                ax.set_yticks([])
                ax.tick_params(bottom=False, labelbottom=False)
                ax.grid(False)
                continue
            obs = path[f"{key}|pct"].to_numpy()
            color = GREEN if row["wynik"] == "zgodnie z planszą" else RED
            ax.fill_between(h, path[f"{key}|pas_A_dol"], path[f"{key}|pas_A_gora"],
                            color=GRAY, alpha=0.30, linewidth=0)
            ax.plot(h, path[f"{key}|losowe_pct"], color=GRAY, linewidth=1.2)
            ax.plot(h, obs, color=color, linewidth=3)
            ax.axhline(0, color=GRAY, linewidth=0.8, alpha=0.6)
            ax.text(0, 1.03, f"{row['n']} sygnałów · {row['wynik']}", color=GRAY,
                    fontsize=11, fontfamily=font, transform=ax.transAxes)
            ax.set_xlim(1, HORIZON)
            ax.set_xticks([1, 10, 20])

    fig.savefig(file, dpi=DPI, facecolor=BLACK)
    plt.close(fig)


def save_ranking_chart(rank: pd.DataFrame, variant: str, file: Path) -> None:
    """Słupki: w ilu kombinacjach formacja zrobiła to, co obiecuje plansza."""
    data = rank[rank["wariant"] == variant]
    if data.empty:
        return
    font = _body_font()
    fig, ax = plt.subplots(figsize=SIZE, dpi=DPI, facecolor=BLACK)
    fig.subplots_adjust(left=0.20, right=0.95, top=0.80, bottom=0.08)
    fig.text(0.04, 0.93, "CZY FORMACJA ROBI TO, CO OBIECUJE PLANSZA?",
             color=WHITE, fontsize=44, fontfamily=_heading_font(),
             fontweight=_heading_weight(), va="center")
    fig.text(0.04, 0.865,
             f"{VARIANTS[variant]} · liczba kombinacji (aktywo × interwał), w których cena "
             f"wyszła z pasu losowego w obiecanym kierunku",
             color=GRAY, fontsize=18, fontfamily=font, va="center")
    ax.set_facecolor(BLACK)
    y = np.arange(len(data))[::-1]
    total = data["przetestowane"].to_numpy()
    ok = data["zgodnie_z_plansza"].to_numpy()
    bad = data["odwrotnie"].to_numpy()
    ax.barh(y, total, color=GRAY, alpha=0.25, height=0.6)
    ax.barh(y, ok, color=GREEN, height=0.6)
    ax.barh(y, bad, left=ok, color=RED, height=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(data["formacja"], color=WHITE, fontsize=16, fontfamily=font)
    for yy, o, b, t in zip(y, ok, bad, total):
        ax.text(max(t, 1) + 0.3, yy, f"{o}/{t}" + (f"  ·  odwrotnie {b}" if b else ""),
                color=WHITE, fontsize=15, fontfamily=font, va="center")
    ax.set_xlim(0, max(int(data["kombinacje"].max()), 1) + 4)
    ax.tick_params(colors=GRAY, labelsize=12)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.savefig(file, dpi=DPI, facecolor=BLACK)
    plt.close(fig)


def save_ranking(summary: pd.DataFrame) -> None:
    rank = ranking(summary)
    rank.to_csv(OUTPUT_DIR / "ranking.csv", index=False)
    if SAVE_PNG:
        for variant in VARIANTS:
            save_ranking_chart(rank, variant, OUTPUT_DIR / f"ranking_{variant}.png")


def print_rows(rows: list) -> None:
    for r in rows:
        if r["wynik"] == "brak wniosku":
            print(f"  {r['formacja']:21s} {r['wariant']:13s} n={r['n']:5d} | za mało")
            continue
        extra = f" | B p={r['p_B']}" if "p_B" in r else ""
        print(
            f"  {r['formacja']:21s} {r['wariant']:13s} n={r['n']:5d} | +10: "
            f"{r['10_pct']:+.3f}% (losowe {r['10_losowe_pct']:+.3f}%) | "
            f"{r['wynik']} (p={r['p_A']}){extra}"
        )


# ============================================================
# START
# ============================================================

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if "--ranking" in sys.argv:
        save_ranking(pd.read_csv(OUTPUT_DIR / "summary.csv"))
        print("zapisano ranking")
        return

    rng = np.random.default_rng(SEED)
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
            rows, path = study(bars, asset, tf, spread_pct, rng)
            if not rows:
                continue
            name = f"{asset.replace(' ', '_')}_{tf}"
            path.to_csv(OUTPUT_DIR / f"path_{name}.csv", index=False)
            if SAVE_PNG:
                for variant in VARIANTS:
                    save_grid(path, rows, variant, OUTPUT_DIR / f"formacje_{name}_{variant}.png")
            print_rows(rows)
            summary = save_summary(rows)
            save_ranking(summary)


if __name__ == "__main__":
    main()
