"""Animowane zasady strategii: wersja MP4 każdej planszy 1-2-3 na jednym kadrze (1920×1080, 30 kl./s + PNG).

Skrypt nie rysuje niczego od nowa. Uruchamia istniejące plansze (tiktok_plansze.py, reddit_plansze.py,
ibs_plansza.py), przechwytuje gotową figurę zamiast zapisu PNG i pokazuje ją krok po kroku:
  - jeden wykres na całą szerokość; kroki 1., 2., 3. dorysowują się na nim po kolei i zostają
    na ekranie (tytuły kroków u góry jak na planszy, opis bieżącego kroku pod nimi),
  - wykres odsłania się od lewej do prawej (świece pojawiają się po kolei, napisy, gdy kursor do nich dojdzie),
  - krok 2. i 3. zaczyna odsłanianie od miejsca, w którym skończył poprzedni.
Każda zmiana planszy 1-2-3 przechodzi więc od razu do animacji.

Użycie:
    python narzedzia/plansze_objasniajace/zasady_animacja.py                 # wszystkie strategie
    python narzedzia/plansze_objasniajace/zasady_animacja.py LuxAlgo_SR_Breaks_MSTS IBS_MeanReversion
    python narzedzia/plansze_objasniajace/zasady_animacja.py --lista
Zapis: obok planszy, pod tą samą nazwą: nagrania/<Odcinek>/<Strategia>/plansza_zasady.png → plansza_zasady.mp4
(z --png tylko ostatnia klatka: zasady_animacja.png, żeby nie nadpisać planszy).
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
# RGB → YUV wg BT.709 i oznaczenie pliku jako BT.709. Bez tego ffmpeg liczy BT.601,
# a DaVinci/odtwarzacze czytają HD jako BT.709 — czerwony #FF3B30 robi się pomarańczowy.
YUV_BT709 = ["-vf", "scale=out_color_matrix=bt709:out_range=tv", "-pix_fmt", "yuv420p",
             "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
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
    """{ścieżka PNG planszy: (figura, segmenty)} ze wszystkich skryptów plansz."""
    T.Seg.__init__, T.Seg.candles, Figure.savefig = _seg_init, _seg_candles, _savefig
    try:
        for fn in T.ALL + R.ALL + [I.main]:
            fn()
    finally:
        T.Seg.__init__, T.Seg.candles, Figure.savefig = _init, _candles, _orig_save
    return {path: (fig, _segs.get(fig, [])) for fig, path in _zlapane}


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


def _te_same_osie(a, b) -> bool:
    return all(abs(u - v) < 1e-9 for u, v in zip(a.get_xlim() + a.get_ylim(), b.get_xlim() + b.get_ylim()))


def pokaz_krok(fig, segs, j):
    """Jeden kadr: wykres kroku j na całą szerokość, a pod nim wykresy kroków 1..j−1 (te same świece,
    więc ich napisy i linie zostają na ekranie). Tytuły kroków u góry jak na planszy: przeszłe szare,
    bieżący biały, przyszłe ukryte. Opis tylko bieżącego kroku."""
    cur = segs[j]
    for k, info in enumerate(segs):
        on = k == j or (k < j and _te_same_osie(info.seg.ax, cur.seg.ax))
        for ax in info.axes:
            # z wcześniejszych kroków zostaje tylko wykres ceny; ich panele wskaźników
            # (z nieprzezroczystym tłem) zakryłyby panel bieżącego kroku
            ax.set_visible(k == j or (on and ax is info.seg.ax))
        for n, (t, (x, y)) in enumerate(zip(info.texts, info.poz_t)):
            if n == 0:                                    # tytuł: zostaje w swojej kolumnie
                t.set_visible(k <= j)
                t.set_color(T.FG if k == j else T.GREY)
            elif n == 1:                                  # opis: tylko bieżący, na środku
                t.set_visible(k == j)
                t.set_position((0.5, 0.83))
                t.set_fontsize(24)
            else:
                t.set_visible(on)
                t.set_position((_x(info, x), y))
    # Napisy na wykresie, które bieżący krok rysuje jeszcze raz (np. „EMA 74” na końcu linii),
    # chowamy w starszych krokach; starsze osie na wierzch, żeby ich napisy nie znikały pod świecami.
    biezace = {t.get_text() for ax in cur.axes for t in ax.texts}
    for k, info in enumerate(segs):
        for ax, (x0, y0, w, h) in zip(info.axes, info.poz_a):
            ax.set_position([_x(info, x0), y0, w / info.w * X_W, h])
            ax.set_zorder(len(segs) - k)
            ax.patch.set_alpha(0.0)
            if k < j:
                for t in ax.texts:
                    t.set_alpha(0.0 if t.get_text() in biezace else 1.0)


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
            if isinstance(art, Rectangle) and art.get_zorder() <= 1 and art.get_x() <= x0 + 0.5:
                continue                                  # tło panelu wskaźnika: widoczne od razu w całości
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
        writer = FFMpegWriter(fps=FPS, codec="libx264", bitrate=12000, extra_args=YUV_BT709)
        with writer.saving(fig, str(cel.with_suffix(".mp4")), dpi=100):
            for k in range(int(round(czas * FPS))):
                update(k / FPS)
                writer.grab_frame(facecolor=T.BG)
        print(f"  {cel.with_suffix('.mp4')}  ({czas:.0f} s)")
    else:
        update(czas)
        fig.savefig(cel.parent / "zasady_animacja.png", facecolor=T.BG)
        print(f"  {cel.parent / 'zasady_animacja.png'}")
    plt.close(fig)


def main():
    wszystkie = plansze()
    if "--lista" in ARGV:
        for path in wszystkie:
            print(path.parent.name)
        return
    wybrane = [a for a in ARGV if not a.startswith("--")]
    video = "--png" not in ARGV
    if video and not ffmpeg_ok():
        sys.exit("Brak ffmpeg. Zainstaluj: pip install imageio-ffmpeg (albo dopisz --png).")
    for path, (fig, segs) in wszystkie.items():
        folder = path.parent
        if wybrane and folder.name not in wybrane:
            plt.close(fig)
            continue
        if not segs:
            print(f"POMINIĘTO {folder.name}: plansza bez segmentów")
            continue
        print(folder.name)
        # Do 2026-11-26 MP4 nazywało się zasady_animacja.mp4 — nie kasujemy go (może być w montażu).
        animuj(fig, segs, path.with_suffix(""), video)


if __name__ == "__main__":
    main()
