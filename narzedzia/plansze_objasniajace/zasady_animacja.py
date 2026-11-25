"""Animowane zasady strategii (wersja MP4 planszy 1-2-3), 1920×1080, 30 kl./s + PNG ostatniej klatki.

Te same świece ilustracyjne i te same 3 kroki co na planszy zasad (tiktok_plansze.py), ale na jednym
dużym wykresie: świece pojawiają się po kolei, a napis u góry zmienia się z krokiem.

Użycie:
    python narzedzia/plansze_objasniajace/zasady_animacja.py luxalgo
Zapis: nagrania/<Odcinek>/<Strategia>/zasady_animacja.mp4 (+ .png). Wideo wymaga ffmpeg
(w PATH albo `pip install imageio-ffmpeg`); same PNG: --png.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import tiktok_plansze as T  # noqa: E402  (kolory, fonty, dane ilustracyjne)
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

FPS = 30
NAGRANIA = Path(__file__).resolve().parents[2] / "nagrania"


def ffmpeg_ok() -> bool:
    try:
        import imageio_ffmpeg
        matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
        return True
    except ImportError:
        return shutil.which("ffmpeg") is not None


class Scena:
    """Jeden duży wykres z tytułem i podtytułem kroku. Każda klatka rysowana od zera (świec jest mało)."""

    def __init__(self, n, ylim, right=7):
        self.fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=T.BG)
        self.title = self.fig.text(0.5, 0.92, "", color=T.FG, fontsize=64, family=T.TITLE_FONT, ha="center", va="center")
        self.sub = self.fig.text(0.5, 0.835, "", color=T.GREY, fontsize=28, ha="center", va="center", linespacing=1.4)
        self.ax = self.fig.add_axes([0.06, 0.06, 0.88, 0.70])
        self.xl, self.ylim = (-1, n + right), ylim
        self.dy = (ylim[1] - ylim[0]) * 0.035

    def reset(self, title, sub):
        self.title.set_text(title)
        self.sub.set_text(sub)
        ax = self.ax
        ax.clear()
        ax.set_facecolor(T.BG)
        ax.axis("off")
        ax.set_xlim(*self.xl)
        ax.set_ylim(*self.ylim)

    def candles(self, B, upto, hl=None, grow=1.0):
        """Świece 0..upto-1; ostatnia rośnie od otwarcia (grow 0→1)."""
        hl = hl or {}
        for i in range(upto):
            o, h, l, c = B[i]
            if i == upto - 1 and grow < 1:
                c = o + (c - o) * grow
                h, l = max(o, c) + (h - max(B[i][0], B[i][3])) * grow, min(o, c) - (min(B[i][0], B[i][3]) - l) * grow
            col = hl.get(i, T.GREY)
            lw = 3.2 if i in hl else 2.2
            self.ax.plot([i, i], [l, h], color=col, lw=lw, solid_capstyle="round", zorder=3)
            lo, hi = min(o, c), max(o, c)
            self.ax.add_patch(Rectangle((i - 0.32, lo), 0.64, max(hi - lo, self.dy * 0.15),
                                        facecolor=col, edgecolor=col, lw=lw, zorder=4))

    def text(self, x, y, s, col, size=24, **kw):
        kw.setdefault("fontweight", "bold")
        self.ax.text(x, y, s, color=col, fontsize=size, zorder=8, **kw)


def render(sc: Scena, update, sekundy, path: Path, video: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if video:
        writer = FFMpegWriter(fps=FPS, codec="libx264", bitrate=12000, extra_args=["-pix_fmt", "yuv420p"])
        with writer.saving(sc.fig, str(path.with_suffix(".mp4")), dpi=100):
            for k in range(int(round(sekundy * FPS))):
                update(k / FPS)
                writer.grab_frame(facecolor=T.BG)
        print(f"  {path.with_suffix('.mp4')}")
    update(sekundy)
    sc.fig.savefig(path.with_suffix(".png"), facecolor=T.BG)
    print(f"  {path.with_suffix('.png')}")
    plt.close(sc.fig)


# ───────────────────────── LuxAlgo S/R Breaks + MSTS ─────────────────────────
def luxalgo(video: bool) -> None:
    # dane 1:1 jak w tiktok_plansze.luxalgo()
    n = 44
    cl = T.path([(0, 100), (6, 108.5), (11, 99), (15, 104), (18, 100), (21, 105), (22, 111.5), (26, 115),
                 (28, 112.5), (32, 119), (34, 116.5), (37, 122), (40, 119), (42, 113), (43, 112)], n, 0.5)
    B = T.bars_from(cl, wick=0.7)
    SIG, PIV = 22, 6
    R = max(b[1] for b in B[:SIG])
    o, h, l, c = B[SIG]
    B[SIG] = (o, c + 0.5, o - 0.4, c)
    ts = [None] * n
    stop = min(b[2] for b in B[15:SIG + 1])
    for i in range(SIG, n):
        if i >= 3 and B[i - 2][2] < B[i - 3][2] and B[i - 2][2] < B[i - 1][2] and B[i - 2][2] > stop:
            stop = B[i - 2][2]
        ts[i] = stop
    EXIT = next(i for i in range(SIG + 1, n) if B[i][3] < ts[i - 1])
    n = EXIT + 1
    lo, hi = T.ylim_of(B, n, pad=0.15)
    sc = Scena(n, (lo, hi))

    PER = 0.12                       # sekundy na świecę
    t1 = SIG * PER                   # koniec kroku 1
    t2 = t1 + 2.6                    # świeca B + pauza
    t3 = t2 + (EXIT - SIG) * PER * 1.6
    KONIEC = t3 + 3.0
    ax = sc.ax

    def stop_line(upto):
        xs, ys = [], []
        for i in range(SIG, upto):
            xs += [i - 0.5, i + 0.5]
            ys += [ts[i - 1] if i > SIG else ts[SIG]] * 2
        ax.plot(xs, ys, color=T.RED, lw=4, zorder=5)

    def update(t):
        if t < t1 + 0.4:
            sc.reset("1. OPÓR", "Wskaźnik S/R Breaks rysuje poziom na ostatnim szczycie")
            k = min(SIG, int(t / PER) + 1)
            sc.candles(B, k, grow=min(1.0, (t % PER) / PER * 1.5) if k < SIG else 1.0)
            if k > PIV + 3:            # szczyt potwierdzony kilka świec później
                ax.plot([PIV, k + 0.5], [R, R], color=T.FG, lw=3, ls=(0, (6, 4)), zorder=2)
                sc.text(PIV, B[PIV][1] + sc.dy, "szczyt", T.GREY, size=22, ha="center", va="bottom")
                sc.text(k + 1.0, R, "opór", T.FG, va="center")
            return
        if t < t2:
            sc.reset("2. ZIELONE B = LONG",
                     "Zamknięcie nad oporem przy wysokim wolumenie. Short: czerwone B przy wybiciu wsparcia")
            g = min(1.0, (t - t1 - 0.4) / 0.6)
            sc.candles(B, SIG + 1, {SIG: T.GREEN}, grow=g)
            ax.plot([PIV, SIG + 1.5], [R, R], color=T.FG, lw=3, ls=(0, (6, 4)), zorder=2)
            if g >= 1:
                ax.text(SIG, B[SIG][2] - sc.dy * 1.0, "B", color=T.BG, fontsize=26, fontweight="bold", ha="center",
                        va="top", zorder=8, bbox=dict(boxstyle="round,pad=0.25", fc=T.GREEN, ec=T.GREEN))
                ax.plot([SIG + 0.5], [B[SIG][3]], "o", ms=18, color=T.GREEN, mec=T.FG, mew=2.5, zorder=8)
                sc.text(SIG + 1.4, B[SIG][3], "wejście", T.GREEN, va="center")
            return
        sc.reset("3. WYJŚCIE NA TRAILING STOPIE",
                 "Linia Market Structure Trailing Stop idzie za ceną. Zamknięcie pod nią = wyjście. Brak TP.")
        k = min(EXIT + 1, SIG + 1 + int((t - t2) / (PER * 1.6)))
        sc.candles(B, k, {SIG: T.GREEN, **({EXIT: T.RED} if k > EXIT else {})})
        ax.plot([PIV, SIG + 1.5], [R, R], color=T.FG, lw=2, ls=(0, (6, 4)), alpha=0.4, zorder=2)
        stop_line(k)
        ax.plot([SIG + 0.5], [B[SIG][3]], "o", ms=18, color=T.GREEN, mec=T.FG, mew=2.5, zorder=8)
        sc.text(SIG + 1.5, ts[SIG] - sc.dy * 0.6, "SL przy wejściu", T.RED, size=22, va="top")
        if k > EXIT:
            ax.plot([EXIT + 0.5], [B[EXIT][3]], marker="X", ms=24, color=T.RED, mec=T.FG, mew=2, zorder=8)
            sc.text(EXIT + 1.2, B[EXIT][3], "wyjście", T.RED, va="center")
        sc.text(-0.6, lo, "1% kapitału ryzyka do SL", T.GREY, size=20, fontweight="normal", va="bottom")

    render(sc, update, KONIEC, NAGRANIA / "TikTok" / "LuxAlgo_SR_Breaks_MSTS" / "zasady_animacja", video)


STRATEGIE = {"luxalgo": luxalgo}


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    video = "--png" not in sys.argv
    if video and not ffmpeg_ok():
        sys.exit("Brak ffmpeg. Zainstaluj: pip install imageio-ffmpeg (albo dopisz --png).")
    for name in args or STRATEGIE:
        STRATEGIE[name](video)
