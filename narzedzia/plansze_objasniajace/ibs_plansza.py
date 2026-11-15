"""Plansza 'jak działa strategia' dla IBS Mean Reversion (Reddit, u/vaanam-dev).

JEDEN PNG 1920x1080 z 3 segmentami obok siebie (1 co to jest IBS, 2 wejście, 3 wyjście).
W montażu prawe segmenty są zasłonięte i odsłaniane po kolei. Świece są ilustracyjne,
ale próg wejścia, IBS i wyjście są liczone z tych świec dokładnie jak w strategies/reddit/IBS_MeanReversion.py.

Uruchomienie:  python ibs_plansza.py [folder_wyjściowy]
(domyślnie nagrania/Reddit/IBS_MeanReversion/plansza_zasady.png)
"""
import sys
from pathlib import Path

from matplotlib.patches import Rectangle, FancyArrowPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiktok_plansze import (BG, FG, GREEN, RED, GREY, BLUE, YELLOW, Seg, figure, path, bars_from,
                            ylim_of, sma, HERE)  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(sys.argv[1]) / "ibs_mean_reversion.png" if len(sys.argv) > 1 else \
    HERE.parents[1] / "nagrania" / "Reddit" / "IBS_MeanReversion" / "plansza_zasady.png"


def ibs(b):
    o, h, l, c = b
    return (c - l) / (h - l)


def segment_ibs(fig):
    """1. Dwie świece o tym samym zakresie: zamknięcie przy szczycie i przy dołku."""
    s = Seg(fig, 0, "1. CO TO JEST IBS?", "Gdzie dzień zamknął się w swoim zakresie.\n0 = na samym dołku, 1 = na samym szczycie",
            10, (-0.32, 1.22), right=0)
    ax = s.ax
    L, H = 0.0, 1.0
    strong = (0.25, H, L, 0.88)   # zamknięcie wysoko → IBS 0,88
    weak = (0.75, H, L, 0.10)     # zamknięcie nisko → IBS 0,10
    # strefa IBS < 0,3
    ax.add_patch(Rectangle((0.6, L), 9.2, 0.3, facecolor=RED, alpha=0.13, lw=0, zorder=1))
    ax.plot([0.6, 9.8], [0.3, 0.3], color=RED, lw=2, ls=(0, (6, 4)), zorder=2)
    ax.text(4.65, 0.04, "dolne 30%\nzakresu dnia", color=RED, fontsize=15, fontweight="bold",
            ha="center", va="bottom", linespacing=1.3, zorder=6)
    # skala 0–1 po lewej
    ax.plot([0.6, 0.6], [L, H], color=GREY, lw=2, zorder=2)
    for v, t in ((0, "0"), (0.3, "0,3"), (1, "1")):
        ax.plot([0.45, 0.75], [v, v], color=GREY, lw=2, zorder=2)
        ax.text(0.3, v, t, color=RED if v == 0.3 else GREY, fontsize=17, fontweight="bold", ha="right", va="center")
    ax.text(0.6, 1.07, "IBS", color=GREY, fontsize=17, fontweight="bold", ha="center", va="bottom")
    for x, (o, h, l, c), col, txt in ((2.5, strong, GREEN, "IBS = 0,88\nsilne zamknięcie"),
                                      (6.8, weak, RED, "IBS = 0,10\nsłabe zamknięcie")):
        ax.plot([x, x], [l, h], color=col, lw=3, solid_capstyle="round", zorder=3)
        ax.add_patch(Rectangle((x - 0.55, min(o, c)), 1.1, abs(c - o), facecolor=col, edgecolor=col, zorder=4))
        ax.plot([x + 0.55, x + 1.1], [c, c], color=FG, lw=2.4, zorder=5)
        ax.text(x + 1.2, c, "close", color=FG, fontsize=15, va="center", zorder=6)
        ax.text(x, -0.11, txt, color=col, fontsize=16, fontweight="bold", ha="center", va="top", linespacing=1.35)
    for x in (2.5, 6.8):
        ax.text(x, H + 0.03, "high", color=GREY, fontsize=15, ha="center", va="bottom")
        ax.text(x, L - 0.03, "low", color=GREY, fontsize=15, ha="center", va="top")
    fig.text(0.025 + 0.15, 0.06, "IBS = (close − low) / (high − low)", color=FG, fontsize=19,
             ha="center", va="center")


def data():
    """Świece ilustracyjne: spokojny wzrost, szybki spadek, odbicie. Wejście i wyjście
    liczone regułami strategii (próg z 10/25 świec, IBS < 0,3, zamknięcie nad wczorajszym high)."""
    H, n = 25, 30
    N = H + n
    cl = path([(0, 100), (H + 8, 108), (H + 11, 107), (H + 18, 99.5), (H + 20, 98.7),
               (H + 24, 103), (H + 29, 104)], N, 0.45)
    B = bars_from(cl, wick=0.55)
    hi = [b[1] for b in B]
    lo = [b[2] for b in B]
    rng = [a - b for a, b in zip(sma(hi, 25), sma(lo, 25))]
    band = [max(hi[max(0, i - 9):i + 1]) - 2.5 * rng[i] for i in range(N)]
    # świeca wejścia: pierwsza pod progiem — zamknięcie przy dołku dnia (IBS < 0,3)
    sig = next(i for i in range(H, N) if B[i][3] < band[i])
    o, h, l, c = B[sig]
    B[sig] = (o, h, c - 0.12 * (h - c) / 0.88, c)
    o2, h2, l2, c2 = B[sig + 1]
    B[sig + 1] = (c, h2, min(l2, c), c2)
    assert ibs(B[sig]) < 0.3
    ex = next(i for i in range(sig + 1, N) if B[i][3] > B[i - 1][1])
    sl = slice(H, N)
    shift = lambda i: i - H  # noqa: E731
    return B[sl], band[sl], [max(hi[max(0, i - 9):i + 1]) for i in range(N)][sl], rng[sl], shift(sig), shift(ex)


def main():
    B, band, hh, rng, SIG, EX = data()
    n = EX + 2
    B = B[:n]
    lo, hi = ylim_of(B, n, extra=[band[SIG]], pad=0.12)

    fig = figure()
    segment_ibs(fig)

    # 2. wejście
    s = Seg(fig, 1, "2. WEJŚCIE LONG", "Zamknięcie dnia pod progiem (mocny spadek)\ni jednocześnie IBS < 0,3", n, (lo, hi), right=9)
    s.candles(B, SIG + 1, {SIG: GREEN})
    x1 = SIG - 9
    s.level(hh[SIG], x1 - 0.4, SIG + 0.6, BLUE, ls="-", lw=2.6)
    s.ax.text(x1 - 0.4, hh[SIG] + s.dy * 0.6, "najwyższy high z 10 dni", color=BLUE, fontsize=16,
              fontweight="bold", va="bottom", zorder=6)
    s.level(band[SIG], x1 - 0.4, SIG + 0.6, YELLOW, "PRÓG", lw=2.6, above=False, size=18)
    xa = SIG + 5.2
    s.ax.add_patch(FancyArrowPatch((xa, hh[SIG]), (xa, band[SIG]), arrowstyle="<->", mutation_scale=18,
                                   color=YELLOW, lw=2.2, zorder=6))
    s.ax.text(xa + 0.5, (hh[SIG] + band[SIG]) / 2, "2,5 × średni\nzakres dnia\n(high − low)\nz 25 dni",
              color=YELLOW, fontsize=15, va="center", linespacing=1.3, zorder=6)
    s.entry(SIG, B[SIG][3], GREEN, f"long\nIBS = {ibs(B[SIG]):.2f}".replace(".", ","))
    s.note("wejście na otwarciu następnego dnia", y=lo)

    # 3. wyjście
    s = Seg(fig, 2, "3. WYJŚCIE", "Pierwsze zamknięcie nad wczorajszym high.\nBez SL i TP (tak jak u autora)", n, (lo, hi), right=9)
    s.candles(B, EX + 1, {SIG: GREEN, EX: GREEN})
    s.level(band[SIG], x1 - 0.4, SIG + 0.6, YELLOW, lw=2)
    s.ax.plot([SIG + 0.5], [B[SIG][3]], "o", ms=13, color=GREEN, mec=FG, mew=2, zorder=8)
    yh = B[EX - 1][1]
    s.level(yh, EX - 3.5, EX + 0.6, FG, ls=(0, (4, 3)), lw=2.4)
    s.ax.text(EX + 1.0, yh - s.dy * 0.9, "zamknięcie nad\nwczorajszym high", color=FG, fontsize=15, va="top",
              linespacing=1.25, zorder=6)
    s.exit(EX + 0.5, B[EX][3], GREEN, "wyjście")
    s.note("nasze założenie: pozycja = 100% kapitału", col=YELLOW, y=lo)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, facecolor=BG)
    plt.close(fig)
    print("ok", OUT)


if __name__ == "__main__":
    main()
