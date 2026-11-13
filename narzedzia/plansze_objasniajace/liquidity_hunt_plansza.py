"""Plansza 'jak działa Liquidity Hunt Pro' (3 segmenty — w montażu zasłaniane i odsłaniane po kolei), 1920x1080, branding kanału."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BG, FG, GREEN, RED = "#0B0D10", "#F2F2F2", "#00D084", "#FF3B30"
GREY, ORANGE, AQUA, BLUE = "#6B7280", "#FF9800", "#00BCD4", "#2962FF"
plt.rcParams["font.family"] = ["Inter", "DejaVu Sans"]
NAGRANIA = Path(__file__).resolve().parents[2] / "nagrania"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else NAGRANIA / "TradingView" / "LiquidityHuntPro"

# (open, high, low, close)
C = [(61, 64, 60, 63), (63, 67, 62, 66), (66, 70, 65, 67), (67, 68, 63, 64), (64, 65, 60, 61),
     (61, 62, 58, 60), (60, 64, 59, 63), (63, 65, 61, 62), (62, 63, 59, 60), (59, 61, 55, 60.5),
     (60.5, 64, 60, 63.5), (63.5, 66, 62.5, 65), (65, 74.5, 64.5, 74)]
SH, SL_SWING, SWEEP, MSS = 70, 58, 9, 12
ENTRY, STOP = C[MSS][3], C[SWEEP][2]
RISK = ENTRY - STOP
TPS = [ENTRY + RISK * k for k in (1, 2, 3)]

SCENES = [
    ("1. Sweep płynności", "Knot schodzi pod ostatni dołek,\nświeca zamyka się nad nim", SWEEP + 1, (50, 80)),
    ("2. Zmiana struktury", "W ciągu 10 świec mocna zielona świeca\nzamyka się nad ostatnim szczytem", MSS + 1, (50, 80)),
    ("3. SL i trzy cele", "SL pod knotem sweepu,\nTP1 / TP2 / TP3 = 1×, 2×, 3× ryzyko", MSS + 1, (49.5, 134)),
]


def candle(ax, x, o, h, l, c, col, lw=2.0):
    ax.plot([x, x], [l, h], color=col, lw=lw, solid_capstyle="round", zorder=2)
    lo, hi = min(o, c), max(o, c)
    ax.add_patch(Rectangle((x - 0.32, lo), 0.64, max(hi - lo, 0.25), facecolor=col, edgecolor=col, lw=lw, zorder=3))


def level(ax, y, x0, x1, col, text, side="left", ls=(0, (6, 4)), lw=2.2, fs=17, below=False):
    ax.plot([x0, x1], [y, y], color=col, lw=lw, ls=ls, zorder=1)
    if side == "left" and text:
        ax.text(x0, y - 0.6 if below else y + 0.6, text, color=col, fontsize=fs,
                va="top" if below else "bottom", ha="left")
    else:
        ax.text(x1 + 0.2, y, text, color=col, fontsize=fs, va="center", ha="left", fontweight="bold")


def scene(fig, rect, k):
    title, sub, upto, ylim = SCENES[k]
    x0, y0, w, h = rect
    fig.text(x0 + w / 2, y0 + h, title, color=FG, fontsize=32, fontweight="bold", ha="center", va="top")
    fig.text(x0 + w / 2, y0 + h - 0.065, sub, color=GREY, fontsize=19, ha="center", va="top", linespacing=1.4)
    ax = fig.add_axes([x0, y0, w, h * 0.74])
    ax.set_facecolor(BG); ax.axis("off")
    ax.set_xlim((3.2, 17.6) if k == 2 else (-0.8, 14)); ax.set_ylim(*ylim)

    for i in range(4 if k == 2 else 0, upto):
        col = GREY
        if i == SWEEP:
            col = AQUA
        if i == MSS:
            col = GREEN
        candle(ax, i, *C[i], col, lw=3 if i in (SWEEP, MSS) else 2)

    if k < 2:
        level(ax, SL_SWING, 5, 13, AQUA, "swing low", below=True)
    else:
        level(ax, SL_SWING, 5, 13, AQUA, "", lw=1.6)
    if k == 1:
        level(ax, SH, 2, 13, ORANGE, "swing high")
    elif k == 2:
        level(ax, SH, 4, 13, ORANGE, "", lw=1.6)

    # sweep: kółko pod knotem
    ax.plot([SWEEP], [STOP - (1.6 if k < 2 else 3.2)], "o", ms=13, clip_on=False, color=AQUA, mec=FG, mew=1.5, zorder=4)
    if k == 0:
        ax.annotate("sweep", (SWEEP + 0.4, STOP + 0.5), (SWEEP + 1.6, 53), color=AQUA, fontsize=20,
                    fontweight="bold", arrowprops=dict(arrowstyle="-", color=AQUA, lw=1.5))
    if k >= 1:
        y_buy = C[MSS][1] + (1.2 if k == 1 else 3)
        ax.text(MSS, y_buy, "BUY", color=BG, fontsize=18 if k == 1 else 16, fontweight="bold", ha="center",
                va="bottom", zorder=5, bbox=dict(boxstyle="round,pad=0.35", fc=GREEN, ec="none"))
    if k == 1:
        ax.annotate("", (SWEEP, 51.5), (MSS, 51.5), arrowprops=dict(arrowstyle="<->", color=FG, lw=1.5))
        ax.text((SWEEP + MSS) / 2, 51.0, "max 10 świec", color=FG, fontsize=17, ha="center", va="top")

    if k == 2:
        x0l, x1l = MSS, 15.2
        level(ax, ENTRY, x0l, x1l, BLUE, "Wejście", side="right", ls="-", lw=3, fs=17)
        level(ax, STOP, SWEEP, x1l, RED, "SL", side="right", ls="-", lw=3, fs=17)
        for j, tp in enumerate(TPS):
            level(ax, tp, x0l, x1l, GREEN, f"TP{j + 1}  ({j + 1}×)", side="right", ls="-", lw=3, fs=17)
        # ryzyko = wejście - SL
        ax.annotate("", (14.3, STOP), (14.3, ENTRY), arrowprops=dict(arrowstyle="<->", color=FG, lw=1.5))
        ax.text(14.0, (STOP + ENTRY) / 2, "ryzyko", color=FG, fontsize=15, ha="right", va="center", rotation=90)


fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
for j in range(3):
    scene(fig, (0.03 + j * 0.325, 0.07, 0.29, 0.86), j)
fig.text(0.97, 0.03, "SELL: to samo w lustrzanym odbiciu", color=GREY, fontsize=17, ha="right", va="bottom")
OUT.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT / "liquidity_hunt_plansza.png", facecolor=BG)
plt.close(fig)
print("ok", OUT)
