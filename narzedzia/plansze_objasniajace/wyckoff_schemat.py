"""Plansza 'schemat Wyckoffa wg wskaźnika LunqFX' — jeden wykres na całą planszę, 1920x1080, branding kanału.
Świece ilustracyjne. Dane świec z wyckoff_plansza.py."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


from wyckoff_plansza import C, SC, AR, ST, SPRING, SOS, BOT, TOP, H, BG, FG, GREEN, RED, GREY, INDIGO, candle

OUT = Path(__file__).resolve().parents[2] / "nagrania" / "TradingView" / "Wyckoff"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams["font.family"] = ["Inter", "DejaVu Sans"]

fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
fig.text(0.5, 0.93, "Schemat Wyckoffa", color=FG, fontsize=40, fontweight="bold", ha="center", va="top")

ax = fig.add_axes([0.06, 0.25, 0.86, 0.60]); ax.set_facecolor(BG); ax.axis("off")
ax.set_xlim(-1, SOS + 3.5); ax.set_ylim(50, 104)
ax.add_patch(Rectangle((SC - 0.5, BOT), SOS - SC, H, facecolor=INDIGO, alpha=0.12, edgecolor=INDIGO, lw=1.8, zorder=1))
ax.plot([AR, SOS + 1.2], [TOP, TOP], color=GREEN, lw=2.6, ls=(0, (7, 5)), zorder=2)
ax.text(SOS + 1.4, TOP, "CREEK", color=GREEN, fontsize=22, fontweight="bold", va="center")
ax.text(SOS - 1.0, BOT + 1.0, "zakres", color=INDIGO, fontsize=20, ha="right", va="bottom", zorder=5)
for i, (o, h, l, c, _) in enumerate(C):
    col = GREEN if i == SOS else GREY
    candle(ax, i, o, h, l, c, col, lw=3.4 if i in (SC, SPRING, SOS) else 2.4)


def tag(x, y, text, col, below):
    ax.text(x, y + (-1.6 if below else 1.6), text, color=col, fontsize=26, fontweight="bold",
            ha="center", va="top" if below else "bottom", zorder=6)


tag(SC, C[SC][2], "SC", FG, True)
tag(AR, C[AR][1], "AR", FG, False)
tag(ST, C[ST][2], "ST", FG, True)
tag(SPRING, C[SPRING][2], "SPRING", INDIGO, True)
tag(SOS, C[SOS][1], "SOS", GREEN, False)

vx = fig.add_axes([0.06, 0.07, 0.86, 0.15]); vx.set_facecolor(BG); vx.axis("off")
vx.set_xlim(-1, SOS + 3.5); vx.set_ylim(0, 165)
for i, (*_, v) in enumerate(C):
    vx.add_patch(Rectangle((i - 0.32, 0), 0.64, v, facecolor=FG if i == SC else "#2A2E35", zorder=2))
vx.text(-0.8, 155, "wolumen", color=GREY, fontsize=18, va="top")

fig.savefig(OUT / "wyckoff_schemat.png", facecolor=BG)
print("ok")
