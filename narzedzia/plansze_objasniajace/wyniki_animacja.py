"""Animowane wyniki strategii z run_all_assets (MP4 1920×1080, 30 kl./s + PNG ostatniej klatki).

Dwie sceny:
    1_krzywe.mp4  — krzywe kapitału wszystkich kombinacji rysują się równolegle (szare), mediana
                    grubą linią w kolorze znaku, licznik „X/N na plusie” i mediana zmieniają się
                    na żywo; na końcu podpisy jak na planszy 2_wykres_kapitalu,
    2_liczby.mp4  — duże liczby: X/N na plusie, mediana Profit Factor i mediana wyniku netto (odliczanie).
Liczby i krzywe są te same co na planszach (podsumowanie_*.csv i *_kapital.csv z wyniki/),
łącznie z MIN_TRADES strategii.

Użycie:
    python narzedzia/plansze_objasniajace/wyniki_animacja.py LuxAlgo_SR_Breaks_MSTS
    python narzedzia/plansze_objasniajace/wyniki_animacja.py LuxAlgo_SR_Breaks_MSTS --sztuczne   # podgląd
Wyniki: nagrania/<Odcinek>/<Strategia>/wyniki/animacja/.
Wideo wymaga ffmpeg: w PATH albo `pip install imageio-ffmpeg`. Same PNG: --png.
"""
from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from narzedzia import plansze as P  # noqa: E402  (ładuje też fonty i kolory)
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402

from narzedzia.odcinki import folder_wynikow  # noqa: E402

FPS = 30
RYSOWANIE = 9.0       # sekund rysowania krzywych
TRZYMAJ = 3.0


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ============================================================
# DANE
# ============================================================

def wczytaj(strategy: str):
    folder = folder_wynikow(strategy)
    pliki = sorted(folder.glob(f"podsumowanie_{strategy}_*.csv"), key=lambda p: p.stat().st_mtime)
    if not pliki:
        sys.exit(f"Brak podsumowania w {folder}. Najpierw run_all_assets dla {strategy}.")
    table = pliki[-1]
    okres = table.stem.removeprefix(f"podsumowanie_{strategy}_")      # 2021-01-01_2025-12-31
    data = pd.read_csv(table, sep=";", decimal=",")
    data = data[data["status"] == "OK"]
    module = importlib.import_module(_modul(strategy))
    data, _ = P.split_by_trades(data, getattr(module, "MIN_TRADES", None))
    curves = {}
    for _, row in data.iterrows():
        path = folder / f"{strategy}_{row['asset'].replace(' ', '_')}_{row['timeframe']}_{okres}_kapital.csv"
        if not path.exists():
            print(f"Brak krzywej {path.name} — pominięta")
            continue
        eq = pd.read_csv(path, sep=";", decimal=",", parse_dates=["timestamp"]).set_index("timestamp")["equity"]
        eq = eq.astype(float).sort_index()
        curves[P._label(row)] = (eq.resample("1D").last().dropna() / eq.iloc[0] - 1) * 100
    if not curves:
        sys.exit("Brak krzywych kapitału (*_kapital.csv).")
    pf = float(data["profit_factor"].astype(float).median())          # jak na planszy 1_mediany
    return module, okres.replace("_", " – "), pd.DataFrame(curves).sort_index().ffill().fillna(0.0), pf


def _modul(strategy: str) -> str:
    for path in (Path(__file__).resolve().parents[2] / "strategies").rglob(f"{strategy}.py"):
        rel = path.relative_to(Path(__file__).resolve().parents[2]).with_suffix("")
        return ".".join(rel.parts)
    sys.exit(f"Nie znaleziono strategies/**/{strategy}.py")


def sztuczne(strategy: str):
    module = importlib.import_module(_modul(strategy))
    rng = np.random.default_rng(4)
    idx = pd.bdate_range("2021-01-01", "2025-12-31")
    curves = {}
    for asset in ("XAUUSD", "BTCUSDT", "EURUSD", "Brent", "US500"):
        for tf in ("15m", "1h", "4h"):
            r = rng.normal(-0.0002, 0.006, len(idx))
            curves[f"{asset} {tf}"] = (np.exp(np.cumsum(r)) - 1) * 100
    return module, "2021-01-01 – 2025-12-31 (DANE SZTUCZNE)", pd.DataFrame(curves, index=idx), 0.94


# ============================================================
# RENDER
# ============================================================

def ffmpeg_ok() -> bool:
    try:
        import imageio_ffmpeg
        matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
        return True
    except ImportError:
        return shutil.which("ffmpeg") is not None


def render(fig, update, sekundy, path: Path, video: bool) -> None:
    if video:
        writer = FFMpegWriter(fps=FPS, codec="libx264", bitrate=12000, extra_args=["-pix_fmt", "yuv420p"])
        with writer.saving(fig, str(path.with_suffix(".mp4")), dpi=P.DPI):
            for k in range(int(round(sekundy * FPS))):
                update(k / FPS)
                writer.grab_frame(facecolor=P.BLACK)
        print(f"  {path.with_suffix('.mp4')}")
    update(sekundy)
    fig.savefig(path.with_suffix(".png"), dpi=P.DPI, facecolor=P.BLACK)
    print(f"  {path.with_suffix('.png')}")
    plt.close(fig)


def scena_krzywe(frame: pd.DataFrame, title: str, subtitle: str, path: Path, video: bool) -> None:
    median = frame.median(axis=1)
    n = len(frame.columns)
    fig, ax = P._figure()
    P._header(fig, title, subtitle)
    P._fit_width(fig, [fig.texts[0]], 0.62, min_size=24)   # miejsce na licznik po prawej
    fig.subplots_adjust(left=0.08, right=0.80, top=0.80, bottom=0.08)
    lo, hi = frame.min().min(), frame.max().max()
    pad = (hi - lo) * 0.06
    ax.set_xlim(frame.index[0], frame.index[-1])
    ax.set_ylim(min(lo, 0) - pad, max(hi, 0) + pad)
    ax.axhline(0, color=P.GRAY, linewidth=1.2, linestyle="--")
    ax.set_ylabel("Zmiana kapitału", color=P.GRAY, fontsize=18, fontfamily=P._body_font())
    ax.yaxis.set_major_formatter(lambda v, _: P._pct(v, 0))
    ax.tick_params(colors=P.GRAY, labelsize=18)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#2A2E35")
    ax.grid(axis="y", color="#1C2026", linewidth=1)

    lines = [ax.plot([], [], color=P.WHITE, alpha=0.22, linewidth=1.6)[0] for _ in frame.columns]
    med_line, = ax.plot([], [], linewidth=5)
    licznik = fig.text(0.96, 0.92, "", ha="right", va="center", fontsize=44,
                       fontfamily=P._heading_font(), fontweight=P._heading_weight())
    med_txt = fig.text(0.96, 0.855, "", ha="right", va="center", fontsize=24, fontfamily=P._body_font())
    labels = []
    x = frame.index
    vals = frame.to_numpy()

    def update(t):
        k = max(1, int(round(ease(t / RYSOWANIE) * (len(x) - 1))) + 1)
        for j, ln in enumerate(lines):
            ln.set_data(x[:k], vals[:k, j])
        m = median.iloc[k - 1]
        med_line.set_data(x[:k], median.iloc[:k])
        med_line.set_color(P._sign_color(m))
        plus = int((vals[k - 1] > 0).sum())
        licznik.set_text(f"{plus}/{n} NA PLUSIE")
        licznik.set_color(P.profitable_color(plus, n))
        med_txt.set_text(f"mediana {P._pct(m)}")
        med_txt.set_color(P._sign_color(m))
        if t >= RYSOWANIE and not labels:      # podpisy jak na planszy 2_wykres_kapitalu
            end, last = x[-1], frame.iloc[-1]
            gap = (hi - lo) * 0.06
            spec = [(median.iloc[-1], f"mediana {P._pct(median.iloc[-1])}", P._sign_color(median.iloc[-1]), 26, "bold")]
            for y, name in ((last.max(), last.idxmax()), (last.min(), last.idxmin())):
                if all(abs(y - o) > gap for o, *_ in spec):
                    spec.append((y, f"{name} {P._pct(y)}", P._sign_color(y), 22, "normal"))
                    lines[list(frame.columns).index(name)].set_alpha(0.55)
            for y, text, col, size, weight in spec:
                labels.append(ax.annotate(text, (end, y), xytext=(14, 0), textcoords="offset points",
                                          va="center", color=col, fontsize=size, fontfamily=P._body_font(),
                                          fontweight=weight, annotation_clip=False))

    render(fig, update, RYSOWANIE + TRZYMAJ, path, video)


def scena_liczby(frame: pd.DataFrame, pf: float, title: str, path: Path, video: bool) -> None:
    last = frame.iloc[-1]
    n, plus, med = len(last), int((last > 0).sum()), float(last.median())
    fig, ax = P._figure()
    ax.axis("off")
    head = fig.text(0.5, 0.88, title.upper(), ha="center", va="center", color=P.WHITE, fontsize=48,
                    fontfamily=P._heading_font(), fontweight=P._heading_weight())
    P._fit_width(fig, [head], 0.92, min_size=26)
    xs = (0.18, 0.5, 0.82)
    big = [fig.text(x, 0.52, "", ha="center", va="center", fontsize=140, fontfamily=P._heading_font(),
                    fontweight=P._heading_weight()) for x in xs]
    for x, label in zip(xs, ("kombinacji\nna plusie", "mediana\nProfit Factor", "mediana\nwyniku netto")):
        fig.text(x, 0.25, label, ha="center", va="center", color=P.GRAY, fontsize=32,
                 fontfamily=P._body_font(), linespacing=1.3)
    # rozmiar dobrany do końcowych liczb (najszersze), wspólny dla trzech
    for txt, final in zip(big, (f"{n}/{n}", P._num(pf, 2) if not np.isnan(pf) else "–", P._pct(med))):
        txt.set_text(final)
    P._fit_width(fig, big, 0.27, min_size=60)

    def update(t):
        a = ease(t / 2.0)
        done = a >= 1
        p = int(round(plus * a))
        big[0].set_text(f"{p}/{n}")
        big[0].set_color(P.profitable_color(p, n) if done else P.WHITE)
        big[1].set_text(P._num(pf * a, 2) if not np.isnan(pf) else "–")
        big[1].set_color(P.profit_factor_color(pf) if done else P.WHITE)
        big[2].set_text(P._pct(med * a))
        big[2].set_color(P._sign_color(med) if done else P.WHITE)

    render(fig, update, 2.0 + TRZYMAJ, path, video)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    strategy = args[0]
    video = "--png" not in sys.argv
    if video and not ffmpeg_ok():
        sys.exit("Brak ffmpeg. Zainstaluj: pip install imageio-ffmpeg (albo dopisz --png).")
    syn = "--sztuczne" in sys.argv
    module, okres, frame, pf = sztuczne(strategy) if syn else wczytaj(strategy)
    name = getattr(module, "NAME", strategy)
    out = folder_wynikow(strategy) / ("animacja_sztuczne" if syn else "animacja")
    out.mkdir(parents=True, exist_ok=True)
    subtitle = f"{okres} · {P.count_text(len(frame.columns), 'kombinacja', 'kombinacje', 'kombinacji')}"
    print(f"{name}: {len(frame.columns)} krzywych → {out}")
    scena_krzywe(frame, name, subtitle, out / "1_krzywe", video)
    scena_liczby(frame, pf, name, out / "2_liczby", video)


if __name__ == "__main__":
    main()
