"""Plansza 'czym jest stochastic' (3 segmenty — w montażu zasłaniane i odsłaniane po kolei), 1920x1080, branding kanału."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch

BG, FG, GREEN, RED = "#0B0D10", "#F2F2F2", "#00D084", "#FF3B30"
GREY = "#6B7280"
plt.rcParams["font.family"] = ["Inter", "DejaVu Sans"]
NAGRANIA = Path(__file__).resolve().parents[2] / "nagrania"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else NAGRANIA / "TikTok" / "BigBeluga_Stoch_80percent"

# 9 poprzednich świec: (open, high, low, close)
PAST = [(50, 62, 44, 58), (58, 66, 52, 54), (54, 57, 30, 36), (36, 82, 34, 76),
        (76, 80, 60, 64), (64, 78, 58, 74), (74, 76, 52, 56), (56, 60, 46, 50), (50, 54, 44, 47)]
# 9 wcześniejszych świec (niewidoczne) — tylko do policzenia linii stochastica
HIDDEN = [(40, 46, 36, 44), (44, 52, 42, 50), (50, 56, 47, 48), (48, 50, 38, 40), (40, 48, 37, 46),
          (46, 58, 45, 56), (56, 60, 50, 52), (52, 55, 44, 46), (46, 52, 43, 50)]
SCENES = [
    ("Ostatnie 10 świec", None),
    ("Zamknięcie przy dołku", (47, 49, 31, 33)),
    ("Zamknięcie przy szczycie", (47, 80, 45, 78)),
]


def stoch(cur):
    hh = max([c[1] for c in PAST] + [cur[1]])
    ll = min([c[2] for c in PAST] + [cur[2]])
    return 100 * (cur[3] - ll) / (hh - ll), hh, ll


def stoch_line(cur):
    allc = HIDDEN + PAST + ([cur] if cur else [])
    out = []
    for i in range(len(HIDDEN), len(allc)):
        w = allc[i - 9:i + 1]
        hh, ll = max(c[1] for c in w), min(c[2] for c in w)
        out.append(100 * (allc[i][3] - ll) / (hh - ll))
    return out


def candle(ax, x, o, h, l, c, col, lw=2.0, fill=True):
    ax.plot([x, x], [l, h], color=col, lw=lw, solid_capstyle="round", zorder=2)
    lo, hi = min(o, c), max(o, c)
    ax.add_patch(Rectangle((x - 0.32, lo), 0.64, max(hi - lo, 0.6), facecolor=col if fill else BG,
                           edgecolor=col, lw=lw, zorder=3))


def scene(fig, rect, title, cur):
    x0, y0, w, h = rect
    ax = fig.add_axes([x0, y0 + h * 0.34, w, h * 0.56])
    ax.set_facecolor(BG); ax.axis("off")
    ax.set_xlim(-0.8, 10.6); ax.set_ylim(24, 92)
    for i, (o, hi, lo, c) in enumerate(PAST):
        candle(ax, i, o, hi, lo, c, GREY)
    if cur is None:
        ax.add_patch(Rectangle((9 - 0.32, 46), 0.64, 2.4, facecolor=BG, edgecolor=FG, lw=2.4, ls=(0, (3, 2)), zorder=3))
        hh, ll, val = 82, 30, None
        ax.text(9, 41, "?", color=FG, ha="center", va="top", fontsize=30, fontweight="bold")
    else:
        val, hh, ll = stoch(cur)
        col = GREEN if cur[3] > cur[0] else RED
        candle(ax, 9, *cur, col, lw=3)
    ax.axhline(hh, color=FG, lw=2, ls=(0, (6, 4)), xmin=0.02, xmax=0.98)
    ax.axhline(ll, color=FG, lw=2, ls=(0, (6, 4)), xmin=0.02, xmax=0.98)
    ax.text(-0.6, hh + 1.6, "najwyższy szczyt", color=FG, fontsize=17, va="bottom")
    ax.text(-0.6, ll - 1.6, "najniższy dołek", color=FG, fontsize=17, va="top")
    fig.text(x0 + w / 2, y0 + h * 0.97, title, color=FG, fontsize=30, fontweight="bold", ha="center", va="top")

    # panel stochastica pod świecami (jak na TradingView)
    sx = fig.add_axes([x0, y0 + h * 0.02, w, h * 0.26])
    sx.set_facecolor(BG); sx.axis("off")
    sx.set_xlim(-0.8, 10.6); sx.set_ylim(-14, 118)
    sx.add_patch(Rectangle((-0.6, 0), 10.0, 100, facecolor="#14181E", edgecolor="none", zorder=0))
    for lvl in (0, 100):
        sx.plot([-0.6, 9.4], [lvl, lvl], color=GREY, lw=1.4, ls=(0, (4, 4)), zorder=1)
        sx.text(9.6, lvl, str(lvl), color=GREY, fontsize=17, va="center")
    sx.text(-0.5, 104, "Stochastic", color=GREY, fontsize=17, va="bottom")
    line = stoch_line(cur)
    xs = list(range(len(line)))
    if cur is None:
        sx.plot(xs, line, color="#2962FF", lw=3, zorder=3)
        sx.text(9, 50, "?", color=FG, fontsize=26, fontweight="bold", ha="center", va="center")
    else:
        sx.plot(xs[:-1], line[:-1], color="#2962FF", lw=3, zorder=3)
        col = RED if val < 50 else GREEN
        sx.plot(xs[-2:], line[-2:], color=col, lw=3.5, zorder=3)
        sx.plot([9], [val], "o", ms=14, color=col, mec=FG, mew=2, zorder=4)
        sx.text(9, 106, f"{val:.0f}", color=col, fontsize=28, fontweight="bold",
                ha="center", va="bottom")

fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
for j in range(3):
    scene(fig, (0.03 + j * 0.325, 0.10, 0.29, 0.80), *SCENES[j])
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "stochastic_plansza.png", facecolor=BG)
plt.close(fig)
print("ok", OUT)
