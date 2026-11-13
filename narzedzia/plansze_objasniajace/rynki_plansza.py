"""Plansze 'na czym testuję': rynki × interwały. 1920x1080, branding kanału.
Fonty Anton/Inter z fonts/ (nie trzeba instalować).

Uruchomienie (z głównego folderu repo):
    python narzedzia/plansze_objasniajace/rynki_plansza.py
→ nagrania/<Odcinek>/<Strategia>/plansza_rynki.png dla każdej strategii.
Aktywa i interwały: ASSETS / TIMEFRAMES strategii, a jeśli ich nie ma —
ASSETS_TO_TEST / TIMEFRAMES_TO_TEST z run_all_assets.py. Okres: START_DATE / END_DATE z run_all_assets.py.
run_all_assets.py robi tę planszę też przy każdym teście (plansze_*/0_rynki.png).
"""
import importlib
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for f in (HERE / "fonts").glob("*.[ot]tf"):
    font_manager.fontManager.addfont(str(f))
BG, FG, GREEN, RED, GREY, CARD, LINE = "#0B0D10", "#F2F2F2", "#00D084", "#FF3B30", "#8A919C", "#14181E", "#262B33"
TF = "Anton"

# Nazwa aktywa w tick_config → (symbol na planszy, nazwa, kategoria).
ASSET_CARDS = {
    "XAUUSD": ("XAUUSD", "Złoto", "metal"),
    "Bitcoin": ("BTCUSD", "Bitcoin", "kryptowaluta"),
    "EURUSD": ("EURUSD", "Euro / dolar", "forex"),
    "Brent": ("BRENT", "Ropa Brent", "surowiec"),
    "US500": ("US500", "S&P 500", "indeks akcji"),
    "USA 100": ("US100", "Nasdaq 100", "indeks akcji"),
}
MONTHS = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
          "sierpnia", "września", "października", "listopada", "grudnia"]


def odmiana(n, f1, f2, f5):
    if n == 1:
        return f1
    return f2 if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14) else f5


def tf_label(tf: str) -> str:
    """'15min' → '15 min', '1h' → '1 h', '1D' → '1 dzień'."""
    if tf.endswith("min"):
        return f"{tf[:-3]} min"
    if tf.endswith("D"):
        n = int(tf[:-1] or 1)
        return f"{n} {odmiana(n, 'dzień', 'dni', 'dni')}"
    if tf.endswith("h"):
        return f"{tf[:-1]} h"
    return tf


def period_text(start: str, end: str) -> str:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    if (s.month, s.day) == (1, 1) and (e.month, e.day) == (12, 31):
        n = e.year - s.year + 1
        if n == 1:
            return f"Cały rok {s.year}"
        return f"{n} {odmiana(n, '', 'pełne lata', 'pełnych lat')}: od początku {s.year} do końca {e.year} roku"
    return f"Od {s.day} {MONTHS[s.month - 1]} {s.year} do {e.day} {MONTHS[e.month - 1]} {e.year}"


def plansza(assets, timeframes, path, period):
    """assets: nazwy z tick_config (np. "Bitcoin"), timeframes: np. "15min"."""
    with plt.rc_context({"font.family": ["Inter", "DejaVu Sans"]}):
        _plansza(assets, timeframes, path, period)


def _plansza(assets, timeframes, path, period):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    cards = [ASSET_CARDS.get(a, (a, a, "")) for a in assets]
    tfs = [tf_label(t) for t in timeframes]

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1920); ax.set_ylim(1080, 0); ax.axis("off")

    def card(x, y, w, h, ec=LINE, fc=CARD, lw=1.6):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=18", fc=fc, ec=ec, lw=lw))

    ax.text(960, 45, "NA CZYM TESTUJĘ", color=FG, fontsize=58, family=TF, ha="center", va="top")
    ax.text(960, 168, period, color=GREY, fontsize=24, ha="center", va="top")

    CW, GAP, LW = 300, 20, 240
    n = len(cards)
    L = (1920 - (LW + GAP + n * (CW + GAP) - GAP)) / 2       # wyśrodkowanie całego bloku
    X0 = L + LW + GAP
    for j, (sym, nm, cat) in enumerate(cards):
        x = X0 + j * (CW + GAP)
        card(x, 240, CW, 195)
        ax.plot([x + 30, x + 70], [272, 272], color=GREEN, lw=4, solid_capstyle="round")
        ax.text(x + 30, 292, sym, color=FG, fontsize=40, family=TF, va="top")
        ax.text(x + 30, 365, nm, color=FG, fontsize=20, fontweight="bold", va="top")
        ax.text(x + 30, 400, cat, color=GREY, fontsize=16, va="top")

    k = len(tfs)
    # Do 3 interwałów jak dotąd (wiersz 105 px), przy więcej wiersze się zmniejszają.
    RH = min(105, (850 - 465 - (k - 1) * 20) / k)
    for i, tf in enumerate(tfs):
        y = 465 + i * (RH + 20)
        card(L, y, LW, RH)
        ax.text(L + LW / 2, y + RH / 2, tf, color=FG, fontsize=40 if RH >= 90 else 32, family=TF,
                ha="center", va="center")
        for j in range(n):
            x = X0 + j * (CW + GAP)
            card(x, y, CW, RH, fc=BG)
            ax.plot([x + CW / 2], [y + RH / 2], "o", ms=22, color=GREEN, mec=BG, mew=0, alpha=0.18)
            ax.plot([x + CW / 2], [y + RH / 2], "o", ms=11, color=GREEN)
    ax.text(L + LW / 2, 450, "INTERWAŁ", color=GREY, fontsize=16, ha="center", va="bottom", fontweight="bold")

    txt = (f"{n} {odmiana(n, 'rynek', 'rynki', 'rynków')}  ×  {k} {odmiana(k, 'interwał', 'interwały', 'interwałów')}"
           f"  =  {n * k} {odmiana(n * k, 'test', 'testy', 'testów')}")
    ax.text(960, 875, txt, color=FG, fontsize=44, family=TF, ha="center", va="top")
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    print("ok", path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)


def wszystkie_strategie():
    """Plansza rynków w folderze każdej strategii (bez wariantów _Control/_Standard)."""
    sys.path.insert(0, str(ROOT))
    import run_all_assets as cfg
    from narzedzia.odcinki import ODCINEK_ZRODLA, WARIANTY, folder_strategii

    period = period_text(cfg.START_DATE, cfg.END_DATE)
    for source in ODCINEK_ZRODLA:
        for file in sorted((ROOT / "strategies" / source).glob("*.py")):
            name = file.stem
            if name.startswith("_") or name.endswith(WARIANTY):
                continue
            module = importlib.import_module(f"strategies.{source}.{name}")
            assets = getattr(module, "ASSETS", cfg.ASSETS_TO_TEST)
            timeframes = getattr(module, "TIMEFRAMES", cfg.TIMEFRAMES_TO_TEST)
            plansza(assets, timeframes, folder_strategii(name) / "plansza_rynki.png", period)


if __name__ == "__main__":
    wszystkie_strategie()
    # Plansza ogólna odcinka TikTok (5 rynków × 5/15/30 min).
    plansza(["XAUUSD", "Bitcoin", "EURUSD", "Brent", "US500"], ["5min", "15min", "30min"],
            ROOT / "nagrania" / "TikTok" / "plansza_rynki.png",
            "5 pełnych lat: od początku 2021 do końca 2025 roku")
