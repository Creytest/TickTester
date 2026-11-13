"""Plansze 'na czym testuję': rynki × interwały. 1920x1080, branding kanału.
Fonty Anton/Inter z fonts/ (nie trzeba instalować)."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
TIKTOK = HERE.parents[1] / "nagrania" / "TikTok"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
for f in (HERE / "fonts").glob("*.[ot]tf"):
    font_manager.fontManager.addfont(str(f))
BG, FG, GREEN, RED, GREY, CARD, LINE = "#0B0D10", "#F2F2F2", "#00D084", "#FF3B30", "#8A919C", "#14181E", "#262B33"
plt.rcParams["font.family"] = ["Inter", "DejaVu Sans"]
TF = "Anton"

ALL = {"XAUUSD": ("Złoto", "metal"), "BTCUSD": ("Bitcoin", "kryptowaluta"), "EURUSD": ("Euro / dolar", "forex"),
       "BRENT": ("Ropa Brent", "surowiec"), "US500": ("S&P 500", "indeks akcji")}


def odmiana(n, f1, f2, f5):
    if n == 1:
        return f1
    return f2 if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else f5


def plansza(symbols, tfs, name):
    path = (OUT / name.name) if OUT else name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1920); ax.set_ylim(1080, 0); ax.axis("off")

    def card(x, y, w, h, ec=LINE, fc=CARD, lw=1.6):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=18", fc=fc, ec=ec, lw=lw))

    ax.text(960, 45, "NA CZYM TESTUJĘ", color=FG, fontsize=58, family=TF, ha="center", va="top")
    ax.text(960, 168, "5 pełnych lat: od początku 2021 do końca 2025 roku", color=GREY, fontsize=24, ha="center", va="top")

    CW, GAP, LW = 300, 20, 240
    n = len(symbols)
    L = (1920 - (LW + GAP + n * (CW + GAP) - GAP)) / 2       # wyśrodkowanie całego bloku
    X0 = L + LW + GAP
    for j, sym in enumerate(symbols):
        nm, cat = ALL[sym]
        x = X0 + j * (CW + GAP)
        card(x, 240, CW, 195)
        ax.plot([x + 30, x + 70], [272, 272], color=GREEN, lw=4, solid_capstyle="round")
        ax.text(x + 30, 292, sym, color=FG, fontsize=40, family=TF, va="top")
        ax.text(x + 30, 365, nm, color=FG, fontsize=20, fontweight="bold", va="top")
        ax.text(x + 30, 400, cat, color=GREY, fontsize=16, va="top")

    for i, tf in enumerate(tfs):
        y = 465 + i * 125
        card(L, y, LW, 105)
        ax.text(L + LW / 2, y + 52, tf, color=FG, fontsize=40, family=TF, ha="center", va="center")
        for j in range(n):
            x = X0 + j * (CW + GAP)
            card(x, y, CW, 105, fc=BG)
            ax.plot([x + CW / 2], [y + 52], "o", ms=22, color=GREEN, mec=BG, mew=0, alpha=0.18)
            ax.plot([x + CW / 2], [y + 52], "o", ms=11, color=GREEN)
    ax.text(L + LW / 2, 450, "INTERWAŁ", color=GREY, fontsize=16, ha="center", va="bottom", fontweight="bold")

    k = len(tfs)
    txt = (f"{n} {odmiana(n, 'rynek', 'rynki', 'rynków')}  ×  {k} {odmiana(k, 'interwał', 'interwały', 'interwałów')}"
           f"  =  {n * k} {odmiana(n * k, 'test', 'testy', 'testów')}")
    ax.text(960, 875, txt, color=FG, fontsize=44, family=TF, ha="center", va="top")
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    print("ok", path)


if __name__ == "__main__":
    plansza(["XAUUSD", "BTCUSD", "EURUSD", "BRENT", "US500"], ["5 min", "15 min", "30 min"], TIKTOK / "plansza_rynki.png")
    # Cloud MA EMA 30/74: aktywa i interwały jak w repo (ASSETS w strategii, TIMEFRAMES_TO_TEST w run_all_assets)
    plansza(["BTCUSD", "EURUSD"], ["15 min", "1 h", "4 h"], TIKTOK / "CloudMA_EMA30_74" / "plansza_rynki.png")
