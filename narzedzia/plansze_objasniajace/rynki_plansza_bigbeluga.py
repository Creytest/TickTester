"""Plansza BigBeluga Stoch 80%: 5 rynków × 15m/1h/4h = 15 kombinacji. 1920x1080, branding kanału.
Fonty Anton/Inter z fonts/ (nie trzeba instalować)."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[1] / "nagrania" / "TikTok" / "BigBeluga_Stoch_80percent"
OUT.mkdir(parents=True, exist_ok=True)
for f in (HERE / "fonts").glob("*.[ot]tf"):
    font_manager.fontManager.addfont(str(f))
BG, FG, GREEN, RED, GREY, CARD, LINE = "#0B0D10", "#F2F2F2", "#00D084", "#FF3B30", "#8A919C", "#14181E", "#262B33"
plt.rcParams["font.family"] = ["Inter", "DejaVu Sans"]
TF = "Anton"

ASSETS = [("XAUUSD", "Złoto", "metal"), ("BTCUSD", "Bitcoin", "kryptowaluta"), ("EURUSD", "Euro / dolar", "forex"),
          ("BRENT", "Ropa Brent", "surowiec"), ("US500", "S&P 500", "indeks akcji")]
TFS = ["15 min", "1 h", "4 h"]

fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1920); ax.set_ylim(1080, 0); ax.axis("off")


def card(x, y, w, h, ec=LINE, fc=CARD, lw=1.6):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=18", fc=fc, ec=ec, lw=lw))


ax.text(960, 45, "NA CZYM TESTUJĘ", color=FG, fontsize=58, family=TF, ha="center", va="top")
ax.text(960, 168, "5 pełnych lat: od początku 2021 do końca 2025 roku", color=GREY, fontsize=24, ha="center", va="top")

# kolumny = rynki
X0, CW, GAP = 300, 300, 20
for j, (sym, name, cat) in enumerate(ASSETS):
    x = X0 + j * (CW + GAP)
    card(x, 240, CW, 195)
    ax.plot([x + 30, x + 70], [272, 272], color=GREEN, lw=4, solid_capstyle="round")
    ax.text(x + 30, 292, sym, color=FG, fontsize=40, family=TF, va="top")
    ax.text(x + 30, 365, name, color=FG, fontsize=20, fontweight="bold", va="top")
    ax.text(x + 30, 400, cat, color=GREY, fontsize=16, va="top")

# wiersze = interwały, siatka 15 kombinacji
for i, tf in enumerate(TFS):
    y = 465 + i * 125
    card(40, y, 240, 105)
    ax.text(160, y + 52, tf, color=FG, fontsize=40, family=TF, ha="center", va="center")
    for j in range(len(ASSETS)):
        x = X0 + j * (CW + GAP)
        card(x, y, CW, 105, fc=BG)
        ax.plot([x + CW / 2], [y + 52], "o", ms=22, color=GREEN, mec=BG, mew=0, alpha=0.18)
        ax.plot([x + CW / 2], [y + 52], "o", ms=11, color=GREEN)
ax.text(160, 450, "INTERWAŁ", color=GREY, fontsize=16, ha="center", va="bottom", fontweight="bold")

# podsumowanie
ax.text(960, 875, "5 rynków  ×  3 interwały  =  15 testów", color=FG, fontsize=44, family=TF, ha="center", va="top")
fig.savefig(OUT / "plansza_rynki.png", facecolor=BG)
print("ok")
