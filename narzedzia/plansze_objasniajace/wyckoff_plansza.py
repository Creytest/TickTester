"""Plansza 'jak działa strategia Wyckoff [LunqFX]' (3 segmenty — w montażu zasłaniane i odsłaniane po kolei),
1920x1080, branding kanału. Świece są ilustracyjne (nie z danych)."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

BG, FG, GREEN, RED = "#0B0D10", "#F2F2F2", "#00D084", "#FF3B30"
GREY, INDIGO = "#6B7280", "#7C8CFF"
plt.rcParams["font.family"] = ["Inter", "DejaVu Sans"]
NAGRANIA = Path(__file__).resolve().parents[2] / "nagrania"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else NAGRANIA / "TradingView" / "Wyckoff"

# (open, high, low, close, wolumen)
C = [
    (100, 101, 95, 96, 40), (96, 98, 91, 92, 45), (92, 94, 88, 89, 42), (89, 92, 86, 90, 38),
    (90, 91, 83, 84, 50), (84, 86, 79, 80, 55), (80, 82, 76, 77, 52), (77, 78, 72, 73, 60),
    (73, 74, 60, 66, 150),                                                   # 8  SC
    (66, 72, 65, 71, 70), (71, 77, 70, 76, 65), (76, 80, 74, 79, 60), (79, 83, 77, 81, 55),
    (81, 84, 78, 79, 50),                                                    # 13 AR (high 84)
    (79, 80, 74, 75, 45), (75, 77, 70, 71, 48), (71, 73, 66, 67, 50), (67, 69, 63.5, 68, 52),  # 17 ST
    (68, 73, 67, 72, 40), (72, 78, 71, 77, 42), (77, 80, 75, 76, 38), (76, 77, 70, 71, 40),
    (71, 72, 66, 67, 44), (67, 68, 62, 63, 50),
    (63, 64, 56, 64.5, 90),                                                  # 24 SPRING
    (64.5, 70, 64, 69, 60), (69, 74, 68, 73, 55), (73, 79, 72, 78, 58), (78, 82, 76, 80, 55),
    (80, 89, 79.5, 88, 95),                                                  # 29 SOS
]
SC, AR, ST, SPRING, SOS = 8, 13, 17, 24, 29
BOT, TOP = 60, 84                 # zakres: dołek SC – szczyt AR (creek)
H = TOP - BOT
T1, T2, INV = TOP + H, TOP + 2 * H, C[SPRING][2]
ENTRY = C[SOS][3]

SCENES = [
    ("1. Schemat Wyckoffa", "Klimaks zatrzymuje spadek, odbicie wyznacza zakres,\nspring wybija dołem i wraca do środka"),
    ("2. Wejście na SOS", "Zamknięcie nad górną krawędzią → long\nSL pod springiem, TP = T2 (2 × zakres)"),
    ("3. Haczyk", "T2 jest liczone od krawędzi zakresu,\na nie od ceny wejścia"),
]


def candle(ax, x, o, h, l, c, col, lw=2.0):
    ax.plot([x, x], [l, h], color=col, lw=lw, solid_capstyle="round", zorder=3)
    lo, hi = min(o, c), max(o, c)
    ax.add_patch(Rectangle((x - 0.32, lo), 0.64, max(hi - lo, 0.4), facecolor=col, edgecolor=col, lw=lw, zorder=4))


def tag(ax, x, y, text, col, below):
    ax.text(x, y + (-2.2 if below else 2.2), text, color=col, fontsize=17, fontweight="bold",
            ha="center", va="top" if below else "bottom", zorder=6)


def header(fig, x0, w, y_top, title, sub):
    fig.text(x0 + w / 2, y_top, title, color=FG, fontsize=32, fontweight="bold", ha="center", va="top")
    fig.text(x0 + w / 2, y_top - 0.06, sub, color=GREY, fontsize=17, ha="center", va="top", linespacing=1.4)


def price_axes(fig, rect, ylim, n):
    ax = fig.add_axes(rect)
    ax.set_facecolor(BG); ax.axis("off")
    ax.set_xlim(-1, n + 6.5); ax.set_ylim(*ylim)
    return ax


def draw_candles(ax, upto, hi_sc=False):
    for i, (o, h, l, c, _) in enumerate(C[:upto]):
        col = GREY
        if i == SOS:
            col = GREEN
        candle(ax, i, o, h, l, c, col, lw=2.6 if i in (SC, SPRING, SOS) else 1.8)


def scene1(fig, x0, w):
    header(fig, x0, w, 0.93, *SCENES[0])
    ax = price_axes(fig, [x0, 0.27, w, 0.50], (50, 106), SOS)
    ax.add_patch(Rectangle((SC - 0.5, BOT), SOS - SC, H, facecolor=INDIGO, alpha=0.12, edgecolor=INDIGO, lw=1.5, zorder=1))
    ax.plot([AR, SOS - 0.5], [TOP, TOP], color=GREEN, lw=2.2, ls=(0, (6, 4)), zorder=2)
    ax.text(SOS - 0.3, TOP, " creek", color=GREEN, fontsize=16, va="center")
    draw_candles(ax, SOS)
    tag(ax, SC, C[SC][2], "SC", FG, True)
    tag(ax, AR, C[AR][1], "AR", FG, False)
    tag(ax, ST, C[ST][2], "ST", GREY, True)
    tag(ax, SPRING, C[SPRING][2], "SPRING", INDIGO, True)
    ax.text(SOS - 0.8, TOP + 1.2, "zakres", color=INDIGO, fontsize=16, va="bottom", ha="right", zorder=5)
    # wolumen: klimaks i spring wyróżnione
    vx = fig.add_axes([x0, 0.10, w, 0.14]); vx.set_facecolor(BG); vx.axis("off")
    vx.set_xlim(-1, SOS + 6.5); vx.set_ylim(0, 170)
    for i, (*_, v) in enumerate(C[:SOS]):
        vx.add_patch(Rectangle((i - 0.32, 0), 0.64, v, facecolor=FG if i == SC else "#2A2E35", zorder=2))
    vx.text(-0.8, 160, "wolumen", color=GREY, fontsize=15, va="top")
    vx.text(SC + 0.6, 150, "1,5 × średnia", color=FG, fontsize=15, va="top")


def scene2(fig, x0, w):
    header(fig, x0, w, 0.93, *SCENES[1])
    ax = fig.add_axes([x0, 0.08, w, 0.70]); ax.set_facecolor(BG); ax.axis("off")
    ax.set_xlim(-0.5, SOS + 12); ax.set_ylim(50, 138)
    ax.add_patch(Rectangle((SC - 0.5, BOT), SOS - SC + 0.5, H, facecolor=INDIGO, alpha=0.12, edgecolor=INDIGO, lw=1.5, zorder=1))
    draw_candles(ax, SOS + 1)
    tag(ax, SOS, C[SOS][1], "SOS", GREEN, False)
    x1 = SOS + 3
    for y, lab, col, ls in ((T2, "TP = T2", GREEN, "-"), (T1, "T1", GREY, (0, (6, 4))),
                            (ENTRY, "wejście", FG, (0, (2, 3))),
                            (TOP, "creek", GREEN, (0, (6, 4))), (INV, "SL = INVALID", RED, "-")):
        start = SOS + 0.5 if lab == "wejście" else SC - 0.5
        ax.plot([start, x1], [y, y], color=col, lw=2.4, ls=ls, zorder=2)
        ax.text(x1 + 0.3, y, lab, color=col, fontsize=17, fontweight="bold", ha="left", va="center")
    ax.text(SC, 52, "1% kapitału ryzyka do SL", color=GREY, fontsize=16, va="bottom")


def bracket(ax, x, y0, y1, text, col):
    ax.plot([x, x], [y0, y1], color=col, lw=4, solid_capstyle="butt")
    for y in (y0, y1):
        ax.plot([x - 0.18, x + 0.18], [y, y], color=col, lw=3)
    ax.text(x + 0.3, (y0 + y1) / 2, text, color=col, fontsize=19, fontweight="bold", va="center")


def scene3(fig, x0, w):
    header(fig, x0, w, 0.93, *SCENES[2])
    ax = fig.add_axes([x0, 0.08, w, 0.70]); ax.set_facecolor(BG); ax.axis("off")
    ax.set_xlim(0, 10); ax.set_ylim(42, 142)
    for y, col in ((T2, GREEN), (TOP, GREEN), (ENTRY, FG), (INV, RED)):
        ax.plot([0.3, 9.7], [y, y], color=col, lw=1.4, ls=(0, (4, 4)), alpha=0.6)
    ax.text(0.3, T2 + 1, "T2", color=GREEN, fontsize=16, va="bottom")
    ax.text(0.3, TOP - 1, "creek", color=GREEN, fontsize=16, va="top")
    ax.text(0.3, ENTRY + 1, "wejście", color=FG, fontsize=16, va="bottom")
    ax.text(0.3, INV - 1, "SL", color=RED, fontsize=16, va="top")
    ax.text(2.6, 141, "Na wykresie", color=GREY, fontsize=20, ha="center", va="top")
    ax.text(7.2, 141, "Od wejścia", color=FG, fontsize=20, ha="center", va="top", fontweight="bold")
    bracket(ax, 2.2, TOP, T2, "2 zakresy", GREEN)
    bracket(ax, 2.2, INV, TOP, "1 zakres", RED)
    to_tp, to_sl = T2 - ENTRY, ENTRY - INV
    bracket(ax, 6.6, ENTRY, T2, f"{to_tp / H:.1f} zakresu".replace(".", ","), GREEN)
    bracket(ax, 6.6, INV, ENTRY, f"{to_sl / H:.1f} zakresu".replace(".", ","), RED)
    rr = f"{to_tp / to_sl:.1f}".replace(".", ",")
    ax.text(5, 44, f"Zysk do ryzyka: {rr} : 1, a nie 2 : 1", color=FG, fontsize=22, fontweight="bold", ha="center")


if __name__ == "__main__":
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
    W = 0.30
    for j, fn in enumerate((scene1, scene2, scene3)):
        fn(fig, 0.025 + j * 0.325, W)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "wyckoff_plansza.png", facecolor=BG)
    plt.close(fig)
    print("ok", OUT)
