"""Wykres z rzutów monetą kontra prawdziwe złoto (odcinek „Czy trend istnieje?”).

Pomysł Kamila: 50 prawdziwych rzutów monetą (orzeł / reszka) zamienia 50 prawdziwych
dni złota w wykres bez pamięci. Każdy dzień zachowuje swoją wielkość ruchu i kształt
świecy, a kierunek bierze z monety (orzeł = dzień w górę, reszka = dzień w dół).
To ta sama grupa kontrolna co w analizy/event_study_trend.py („moneta”), tylko w skali,
którą widz zobaczy na własne oczy.

KROK 1 — przed rzucaniem (okres wybiera program, nie Ty):
    python narzedzia/plansze_objasniajace/moneta_wykres.py losuj
  Losuje 50 kolejnych dni XAUUSD (2004–2025) i zapisuje je w nagrania/Trend/moneta/okres.json.
  Nie zaglądaj do pliku przed nagraniem.

KROK 2 — po rzutach (O = orzeł, R = reszka, w kolejności rzutów, 50 znaków):
    python narzedzia/plansze_objasniajace/moneta_wykres.py rzuty OORRORO...
  Rysuje do nagrania/Trend/moneta/:
    quiz_A_B.png        — dwa wykresy obok siebie, A i B (który jest prawdziwy, losuje program),
    wykres_A.png, wykres_B.png — każdy osobno (1920×1080),
    odpowiedz.png       — te same wykresy z podpisami i datami okresu,
    odpowiedz.txt       — który to złoto (do montażu; nie otwierać przed quizem).

Test bez danych: dopisz --sztuczne (dni złota zastąpione losowym wykresem).

Jak powstaje dzień z monety: świeca dnia jest opisana względem poprzedniego zamknięcia
(otwarcie, high, low, close jako zmiany w logarytmach). Gdy moneta mówi inny kierunek niż
prawdziwy dzień, cała świeca odbija się lustrzanie (zmiany ze znakiem minus, high ↔ low).
Wielkość ruchu, knoty i luka na otwarciu zostają takie jak w prawdziwym dniu.
"""
from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tiktok_plansze import BG, FG, GREEN, RED, GREY, TITLE_FONT  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

N_DNI = 50
OD, DO = "2004-01-01", "2025-12-31"
OUT = Path(__file__).resolve().parents[2] / "nagrania" / "Trend" / "moneta"
OKRES = OUT / "okres.json"
LITERY = ("A", "B")


# ============================================================
# DANE
# ============================================================

def dni_zlota(sztuczne: bool) -> pd.DataFrame:
    if sztuczne:
        rng = np.random.default_rng(7)
        n = 3000
        idx = pd.bdate_range("2010-01-01", periods=n)
        c = 1200 * np.exp(np.cumsum(rng.normal(0.0003, 0.01, n)))
        o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.002, n))
        h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.004, n)))
        lo = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.004, n)))
        return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c}, index=idx)
    from narzedzia.swiece_dzienne import wczytaj
    return wczytaj("XAUUSD", od=OD, do=DO)


def losuj(sztuczne: bool) -> None:
    bars = dni_zlota(sztuczne)
    # N_DNI dni + 1 dzień przed nimi (jego zamknięcie = start obu wykresów)
    start = secrets.randbelow(len(bars) - N_DNI - 1)
    okres = {
        "od": str(bars.index[start + 1].date()),
        "do": str(bars.index[start + N_DNI].date()),
        "dzien_startowy": str(bars.index[start].date()),
        "prawdziwy_wykres": secrets.choice(LITERY),
        "sztuczne": sztuczne,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    OKRES.write_text(json.dumps(okres, indent=2), encoding="utf-8")
    print(f"Okres wylosowany i zapisany w {OKRES}. Nie zaglądaj do pliku przed nagraniem.")


# ============================================================
# WYKRES Z MONETY
# ============================================================

def z_monety(real: pd.DataFrame, rzuty: str) -> pd.DataFrame:
    """Te same dni, kierunek z monety. real ma N_DNI+1 wierszy (pierwszy = dzień startowy)."""
    prev = real["close"].to_numpy()[:-1]
    days = real.iloc[1:]
    lg = {k: np.log(days[k].to_numpy() / prev) for k in ("open", "high", "low", "close")}
    up_real = lg["close"] >= 0
    up_coin = np.array([r == "O" for r in rzuty])
    flip = up_real != up_coin
    s = np.where(flip, -1.0, 1.0)
    o, c = lg["open"] * s, lg["close"] * s
    h = np.where(flip, -lg["low"], lg["high"])
    lo = np.where(flip, -lg["high"], lg["low"])
    out, close = [], real["close"].iloc[0]
    for i in range(N_DNI):
        out.append([close * np.exp(o[i]), close * np.exp(h[i]), close * np.exp(lo[i]), close * np.exp(c[i])])
        close = out[-1][3]
    return pd.DataFrame(out, columns=["open", "high", "low", "close"])


# ============================================================
# RYSOWANIE
# ============================================================

def rysuj_swiece(ax, df: pd.DataFrame, ylim) -> None:
    for i, (o, h, lo, c) in enumerate(df[["open", "high", "low", "close"]].to_numpy()):
        col = GREEN if c >= o else RED
        ax.plot([i, i], [lo, h], color=col, lw=2.2, solid_capstyle="round", zorder=2)
        ax.add_patch(Rectangle((i - 0.33, min(o, c)), 0.66, max(abs(c - o), (ylim[1] - ylim[0]) * 0.002),
                               facecolor=col, edgecolor=col, zorder=3))
    ax.set_xlim(-1.2, len(df) + 0.2)
    ax.set_ylim(*ylim)
    ax.set_facecolor(BG)
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def wspolna_skala(*dfs):
    lo = min(d["low"].min() for d in dfs)
    hi = max(d["high"].max() for d in dfs)
    pad = (hi - lo) * 0.06
    return lo - pad, hi + pad


def nowa_figura():
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)
    return fig


def zapisz(fig, nazwa: str) -> None:
    path = OUT / nazwa
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    print(f"  {path}")


def plansza_jeden(df, ylim, litera, podpis=None):
    fig = nowa_figura()
    ax = fig.add_axes([0.05, 0.08, 0.9, 0.74])
    rysuj_swiece(ax, df, ylim)
    fig.text(0.05, 0.9, litera, color=FG, fontsize=80, fontfamily=TITLE_FONT, va="center")
    if podpis:
        fig.text(0.95, 0.9, podpis[0], color=podpis[1], fontsize=40, fontfamily=TITLE_FONT, ha="right", va="center")
    return fig


def plansza_dwa(wykresy, ylim, tytul, podpisy=None, stopka=None):
    fig = nowa_figura()
    fig.text(0.5, 0.92, tytul, color=FG, fontsize=58, fontfamily=TITLE_FONT, ha="center", va="center")
    for k, (litera, df) in enumerate(wykresy):
        x0 = 0.04 + k * 0.48
        ax = fig.add_axes([x0, 0.12, 0.44, 0.66])
        rysuj_swiece(ax, df, ylim)
        fig.text(x0 + 0.22, 0.81, litera, color=FG, fontsize=54, fontfamily=TITLE_FONT, ha="center", va="center")
        if podpisy:
            txt, col = podpisy[k]
            fig.text(x0 + 0.22, 0.07, txt, color=col, fontsize=30, fontfamily=TITLE_FONT, ha="center", va="center")
    if stopka:
        fig.text(0.5, 0.025, stopka, color=GREY, fontsize=18, ha="center", va="center")
    return fig


def rzuty(rzuty_txt: str) -> None:
    if not OKRES.exists():
        sys.exit("Najpierw: moneta_wykres.py losuj (okres musi być wylosowany PRZED rzutami).")
    rz = rzuty_txt.upper().replace(" ", "").replace(",", "")
    if len(rz) != N_DNI or set(rz) - {"O", "R"}:
        sys.exit(f"Podaj dokładnie {N_DNI} rzutów: O = orzeł, R = reszka (podano {len(rz)}).")
    okres = json.loads(OKRES.read_text(encoding="utf-8"))
    bars = dni_zlota(okres.get("sztuczne", False))
    real = bars.loc[okres["dzien_startowy"]:okres["do"]]
    if len(real) != N_DNI + 1:
        sys.exit(f"Okres w {OKRES} ma {len(real)} świec zamiast {N_DNI + 1} — wylosuj od nowa.")
    moneta = z_monety(real, rz)
    zloto = real.iloc[1:].reset_index(drop=True)
    ylim = wspolna_skala(zloto, moneta)

    prawdziwy = okres["prawdziwy_wykres"]
    po_literze = {prawdziwy: zloto, ("B" if prawdziwy == "A" else "A"): moneta}
    wykresy = [(l, po_literze[l]) for l in LITERY]

    (OUT / "rzuty.txt").write_text(rz + "\n", encoding="utf-8")
    print("Zapisano:")
    zapisz(plansza_dwa(wykresy, ylim, "KTÓRY TO PRAWDZIWE ZŁOTO?"), "quiz_A_B.png")
    for l, df in wykresy:
        zapisz(plansza_jeden(df, ylim, l), f"wykres_{l}.png")
    podpisy = [("PRAWDZIWE ZŁOTO", GREEN) if l == prawdziwy else ("RZUTY MONETĄ", RED) for l in LITERY]
    orly = rz.count("O")
    stopka = (f"Złoto: {okres['od']} – {okres['do']} ({N_DNI} dni). Moneta: te same dni, "
              f"kierunek z {N_DNI} rzutów ({orly} orłów, {N_DNI - orly} reszek).")
    zapisz(plansza_dwa(wykresy, ylim, "ODPOWIEDŹ", podpisy, stopka), "odpowiedz.png")
    (OUT / "odpowiedz.txt").write_text(
        f"Prawdziwe złoto: wykres {prawdziwy}\n{stopka}\n", encoding="utf-8")
    print(f"  {OUT / 'odpowiedz.txt'}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--sztuczne"]
    sztuczne = "--sztuczne" in sys.argv
    if args[:1] == ["losuj"]:
        losuj(sztuczne)
    elif args[:1] == ["rzuty"] and len(args) >= 2:
        rzuty("".join(args[1:]))
    else:
        print(__doc__)
