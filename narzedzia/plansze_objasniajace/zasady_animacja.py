"""Animowane zasady strategii: wersja MP4 każdej planszy 1-2-3 (1920×1080, 30 kl./s + PNG ostatniej klatki).

Skrypt nie rysuje niczego od nowa. Uruchamia istniejące plansze (tiktok_plansze.py, reddit_plansze.py,
ibs_plansza.py), przechwytuje gotową figurę zamiast zapisu PNG i pokazuje ją krok po kroku:
  - każdy segment (1., 2., 3.) dostaje cały ekran, z tytułem i opisem u góry,
  - wykres odsłania się od lewej do prawej (świece pojawiają się po kolei, napisy, gdy kursor do nich dojdzie),
  - krok 2. i 3. zaczyna odsłanianie od miejsca, w którym skończył poprzedni.
Każda zmiana planszy 1-2-3 przechodzi więc od razu do animacji.

Użycie:
    python narzedzia/plansze_objasniajace/zasady_animacja.py                 # wszystkie strategie
    python narzedzia/plansze_objasniajace/zasady_animacja.py LuxAlgo_SR_Breaks_MSTS IBS_MeanReversion
    python narzedzia/plansze_objasniajace/zasady_animacja.py --lista
Zapis: obok planszy, nagrania/<Odcinek>/<Strategia>/zasady_animacja.mp4 (+ .png).
Wideo wymaga ffmpeg (w PATH albo `pip install imageio-ffmpeg`); same PNG: --png.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ARGV = sys.argv[1:]
sys.argv = sys.argv[:1]      # skrypty plansz czytają sys.argv przy imporcie (folder zapisu)
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.text import Text  # noqa: E402

import tiktok_plansze as T  # noqa: E402
import reddit_plansze as R  # noqa: E402
import ibs_plansza as I  # noqa: E402

FPS = 30
NA_SWIECE = 0.11      # s odsłaniania na jedną jednostkę osi x (≈ jedną świecę)
MIN_KROK, MAX_KROK = 1.5, 5.5
PAUZA = 2.2           # s stop-klatki po każdym kroku
X_L, X_W = 0.06, 0.88


# ============================================================
# PRZECHWYTYWANIE PLANSZ
# ============================================================

_segs: dict = {}        # figura → lista segmentów
_zlapane: list = []     # (figura, ścieżka planszy)


class SegInfo:
    def __init__(self, seg, n_texts, n_axes):
        self.seg, self.koniec_swiec = seg, None
        self.t0, self.a0 = n_texts, n_axes       # od których elementów figury zaczyna się segment
        self.texts, self.axes = [], []


_init, _candles, _orig_save = T.Seg.__init__, T.Seg.candles, Figure.savefig


def _seg_init(self, fig, *a, **k):
    t0, a0 = len(fig.texts), len(fig.axes)
    _init(self, fig, *a, **k)
    _segs.setdefault(fig, []).append(SegInfo(self, t0, a0))


def _seg_candles(self, B, upto, *a, **k):
    _candles(self, B, upto, *a, **k)
    for info in _segs.get(self.ax.figure, []):
        if info.seg is self:
            info.koniec_swiec = max(info.koniec_swiec or 0, upto)


def _savefig(self, path, *a, **k):
    _zlapane.append((self, Path(path)))


def plansze():
    """{folder strategii: (figura, segmenty)} ze wszystkich skryptów plansz."""
    T.Seg.__init__, T.Seg.candles, Figure.savefig = _seg_init, _seg_candles, _savefig
    try:
        for fn in T.ALL + R.ALL + [I.main]:
            fn()
    finally:
        T.Seg.__init__, T.Seg.candles, Figure.savefig = _init, _candles, _orig_save
    return {path.parent: (fig, _segs.get(fig, [])) for fig, path in _zlapane}


# ============================================================
# ANIMACJA JEDNEJ PLANSZY
# ============================================================

def ffmpeg_ok() -> bool:
    try:
        import imageio_ffmpeg
        matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
        return True
    except ImportError:
        return shutil.which("ffmpeg") is not None


def przypisz(fig, segs):
    """Segment = wszystko, co dodano do figury od jego utworzenia do następnego segmentu
    (także napisy i osie dodane później ręcznie, np. wzór IBS pod wykresem)."""
    for k, info in enumerate(segs):
        nxt = segs[k + 1] if k + 1 < len(segs) else None
        info.texts = fig.texts[info.t0: nxt.t0 if nxt else None]
        info.axes = fig.axes[info.a0: nxt.a0 if nxt else None]
        info.x0, info.w = info.seg.x0, T.W
        info.poz_t = [t.get_position() for t in info.texts]
        info.poz_a = [ax.get_position().bounds for ax in info.axes]


def osie(info):
    return [a for a in (info.seg.ax, info.seg.sx) if a is not None]


def _x(info, x):
    """x w figurze z kolumny segmentu → x na całej szerokości."""
    return X_L + (x - info.x0) / info.w * X_W


def pokaz_krok(fig, segs, j):
    """Segment j na cały ekran, reszta ukryta."""
    for k, info in enumerate(segs):
        on = k == j
        for ax in info.axes:
            ax.set_visible(on)
        for t in info.texts:
            t.set_visible(on)
    info = segs[j]
    for ax, (x0, y0, w, h) in zip(info.axes, info.poz_a):
        ax.set_position([_x(info, x0), y0, w / info.w * X_W, h])
    for k, (t, (x, y)) in enumerate(zip(info.texts, info.poz_t)):
        if k == 0:            # tytuł kroku
            t.set_position((0.5, 0.965)); t.set_fontsize(60)
        elif k == 1:          # opis kroku
            t.set_position((0.5, 0.855)); t.set_fontsize(24)
        else:
            t.set_position((_x(info, x), y))


def odslon(info, p, a, b):
    """Postęp p (0–1): na osiach ceny/wskaźnika odsłonięte x ≤ a + (b − a)·p, na innych osiach
    segmentu (np. własne rysunki) ten sam ułamek ich szerokości. Reszta ukryta."""
    for ax in info.axes:
        x0, x1 = ax.get_xlim()
        x = a + (b - a) * p if ax in osie(info) else x0 + (x1 - x0) * p
        y0, y1 = ax.get_ylim()
        clip = Rectangle((x0 - 1, y0 - (y1 - y0)), x - x0 + 1, 3 * (y1 - y0), transform=ax.transData)
        for art in ax.get_children():
            if art in (ax.patch, ax.xaxis, ax.yaxis) or art in ax.spines.values():
                continue
            if isinstance(art, Text):
                if art.get_transform() == ax.transData and art.get_text():
                    art.set_visible(art.get_position()[0] <= x + 0.3)
                continue
            try:
                art.set_clip_path(clip)
            except (AttributeError, TypeError):
                pass


def animuj(fig, segs, cel: Path, video: bool):
    przypisz(fig, segs)
    # plan: (krok, start x, koniec x, czas)
    plan, start = [], None
    for j, info in enumerate(segs):
        x0, x1 = info.seg.ax.get_xlim()
        a = x0 if start is None else max(x0, start - 0.5)
        plan.append((j, a, x1, min(MAX_KROK, max(MIN_KROK, (x1 - a) * NA_SWIECE))))
        start = info.koniec_swiec
    czas = sum(d + PAUZA for *_, d in plan)
    granice = []
    t0 = 0.0
    for j, a, b, d in plan:
        granice.append((t0, j, a, b, d))
        t0 += d + PAUZA
    stan = {"krok": None}

    def update(t):
        for t_start, j, a, b, d in reversed(granice):
            if t >= t_start:
                break
        if stan["krok"] != j:
            pokaz_krok(fig, segs, j)
            stan["krok"] = j
        p = min(1.0, (t - t_start) / d)
        odslon(segs[j], p, a, b)

    if video:
        writer = FFMpegWriter(fps=FPS, codec="libx264", bitrate=12000, extra_args=["-pix_fmt", "yuv420p"])
        with writer.saving(fig, str(cel.with_suffix(".mp4")), dpi=100):
            for k in range(int(round(czas * FPS))):
                update(k / FPS)
                writer.grab_frame(facecolor=T.BG)
        print(f"  {cel.with_suffix('.mp4')}  ({czas:.0f} s)")
    update(czas)
    fig.savefig(cel.with_suffix(".png"), facecolor=T.BG)
    plt.close(fig)


def main():
    wszystkie = plansze()
    if "--lista" in ARGV:
        for folder in wszystkie:
            print(folder.name)
        return
    wybrane = [a for a in ARGV if not a.startswith("--")]
    video = "--png" not in ARGV
    if video and not ffmpeg_ok():
        sys.exit("Brak ffmpeg. Zainstaluj: pip install imageio-ffmpeg (albo dopisz --png).")
    for folder, (fig, segs) in wszystkie.items():
        if wybrane and folder.name not in wybrane:
            plt.close(fig)
            continue
        if not segs:
            print(f"POMINIĘTO {folder.name}: plansza bez segmentów")
            continue
        print(folder.name)
        animuj(fig, segs, folder / "zasady_animacja", video)


if __name__ == "__main__":
    main()
