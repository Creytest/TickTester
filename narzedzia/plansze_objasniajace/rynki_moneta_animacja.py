"""Animacja „47 rynków kontra moneta” do odcinka „Czy trend istnieje?”.

Pokazuje badanie z analizy/event_study_trend.py --szeroki w 4 scenach (osobne MP4, 1920×1080, 30 kl./s):
    1_rynki.mp4   — siatka rynków pojawia się grupami (indeksy, waluty, surowce, obligacje),
    2_moneta.mp4  — jeden rynek (złoto) i 1000 wykresów z monety za nim, potem wynik reguły na tle pasa przypadku,
    3_siatka.mp4  — każdy rynek zapala się: zielony = lepiej niż moneta, szary = jak przypadek, czerwony = gorzej,
    4_razem.mp4   — rynki zjeżdżają do jednego wyniku, pas przypadku się zwęża, na końcu wynik wspólny.
Do tego 4 PNG (ostatnia klatka każdej sceny) do odsłaniania po kolei w montażu.

Wszystkie liczby biorą się z summary.csv (reguła Murphy'ego, trend średni). Szare linie w scenie 2
to ilustracja tej samej metody co w badaniu: prawdziwe ruchy złota z losowym kierunkiem (moneta).

Użycie (najpierw badanie):
    python analizy/event_study_trend.py --szeroki
    python narzedzia/plansze_objasniajace/rynki_moneta_animacja.py
Podgląd bez danych (47 rynków z wymyślonymi wynikami):
    python narzedzia/plansze_objasniajace/rynki_moneta_animacja.py --sztuczne
Tylko PNG, bez wideo: dopisz --png.

Wideo wymaga ffmpeg: w PATH albo `pip install imageio-ffmpeg`.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tiktok_plansze import BG, FG, GREEN, RED, GREY, DIM, TITLE_FONT  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FFMpegWriter  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from narzedzia.plansze import count_text  # noqa: E402
from analizy import event_study_trend as ets  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WYNIKI = ROOT / "nagrania" / "Trend" / "wyniki_event_study_szeroki"
OUT = ROOT / "nagrania" / "Trend" / "wyniki_animacja_rynki"
FPS = 30
DEFINICJA, STOPIEN = "murphy", ets.MAIN_DEGREE
N_MONET = 1000
PUNKTY = 160                      # punktów na mini wykres
W, H = 16.0, 9.0                  # współrzędne sceny (16:9)
COLS = 8
POOLED = ets.POOLED_NAME
GRUPY = list(ets.SZEROKI)
SKROT = {"Obligacje USA 20+ (TLT)": "TLT (USA 20+)", "Obligacje USA 7-10 (IEF)": "IEF (USA 7-10)",
         "Obligacje USA 1-3 (SHY)": "SHY (USA 1-3)", "Obligacje korporacyjne (LQD)": "LQD (korporacyjne)",
         "Obligacje USA 10 lat (futures)": "USA 10 lat", "Obligacje USA 30 lat (futures)": "USA 30 lat"}
GRUPA_TXT = {"Indeksy": ("indeks", "indeksy", "indeksów"), "Waluty": ("para walut", "pary walut", "par walut"),
             "Surowce": ("surowiec", "surowce", "surowców"), "Obligacje": ("obligacje", "obligacje", "obligacji")}


def pl(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def ease(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return t * t * (3 - 2 * t)


# ============================================================
# DANE
# ============================================================

class Rynek:
    def __init__(self, name, grupa, close, row):
        self.name, self.grupa = name, grupa
        self.close = close
        self.wynik = float(row["wygrane_pct"])
        self.pas = (float(row["moneta_pas_dol_pct"]), float(row["moneta_pas_gora_pct"]))
        self.moneta = float(row["moneta_srednia_pct"])
        self.n = int(row["zdarzenia"])
        lg = np.log(close.to_numpy())
        idx = np.linspace(0, len(lg) - 1, PUNKTY).astype(int)
        y = lg[idx]
        self.mini = (y - y.min()) / max(y.max() - y.min(), 1e-9)

    @property
    def stan(self) -> int:
        return 1 if self.wynik > self.pas[1] else -1 if self.wynik < self.pas[0] else 0


def dane_sztuczne():
    rng = np.random.default_rng(5)
    dates = pd.bdate_range("2000-01-01", "2025-12-31")
    rynki, pule = [], {}
    for grupa, nazwy in ets.SZEROKI.items():
        for name in nazwy:
            close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0002, 0.01, len(dates)))), index=dates)
            n = int(rng.integers(60, 160))
            half = 1.96 * np.sqrt(0.25 / n) * 100
            row = {"wygrane_pct": 50 + rng.normal(0.8, half / 2), "moneta_srednia_pct": 50.0,
                   "moneta_pas_dol_pct": 50 - half, "moneta_pas_gora_pct": 50 + half, "zdarzenia": n}
            row["wygrane_pct"] += rng.normal(0, half / 2)   # podgląd: część rynków poza pasem
            rynki.append(Rynek(name, grupa, close, row))
    for nazwa, part in [(f"{g} (razem)", [r for r in rynki if r.grupa == g]) for g in GRUPY] + [(POOLED, rynki)]:
        n = sum(r.n for r in part)
        half = 1.96 * np.sqrt(0.25 / n) * 100
        pule[nazwa] = {"wygrane_pct": sum(r.wynik * r.n for r in part) / n, "moneta_srednia_pct": 50.0,
                       "moneta_pas_dol_pct": 50 - half, "moneta_pas_gora_pct": 50 + half, "zdarzenia": n}
    return rynki, pule


def dane_prawdziwe():
    path = WYNIKI / "summary.csv"
    if not path.exists():
        sys.exit(f"Brak {path}. Najpierw: python analizy/event_study_trend.py --szeroki")
    s = pd.read_csv(path)
    s = s[(s["definicja"] == DEFINICJA) & (s["stopien"] == STOPIEN)].set_index("rynek")
    grupa_of = {name: g for g, nazwy in ets.SZEROKI.items() for name in nazwy}
    rynki = []
    for name, close, _ in ets.series_list(False, True):   # pliki są już na dysku po badaniu
        if name in s.index:
            rynki.append(Rynek(name, grupa_of[name], close, s.loc[name]))
    pule = {k: s.loc[k] for k in s.index if k in ets.pooled_names()}
    if POOLED not in pule:
        sys.exit("W summary.csv brak wiersza „Wszystkie rynki” — uruchom badanie z --szeroki.")
    return rynki, pule


# ============================================================
# UKŁAD SIATKI
# ============================================================

def uklad(rynki):
    """Każda grupa zaczyna nowy rząd. Zwraca prostokąty (x, y, w, h) w kolejności rynków."""
    rows = sum(-(-sum(r.grupa == g for r in rynki) // COLS) for g in GRUPY)
    x0, x1, y_top, y_bot = 0.5, W - 0.5, 7.55, 0.35
    tw, th = (x1 - x0) / COLS, (y_top - y_bot) / max(rows, 1)
    rects, row = [], 0
    for g in GRUPY:
        part = [r for r in rynki if r.grupa == g]
        for k, _ in enumerate(part):
            rr, cc = row + k // COLS, k % COLS
            rects.append((x0 + cc * tw, y_top - (rr + 1) * th, tw, th))
        row += -(-len(part) // COLS)
    return rects, th


def nowa_scena():
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_facecolor(BG)
    ax.axis("off")
    return fig, ax


class Kafelki:
    """Mini wykresy rynków na jednej osi (szybsze niż 47 osobnych osi)."""

    def __init__(self, ax, rynki, rects, th):
        self.rynki, self.rects = rynki, rects
        self.lines, self.labels = [], []
        fs = 13 if th > 0.9 else 11
        for r in rynki:
            ln, = ax.plot([], [], color=FG, lw=1.6, alpha=0, solid_capstyle="round")
            tx = ax.text(0, 0, SKROT.get(r.name, r.name), color=GREY, fontsize=fs, ha="center", va="center", alpha=0)
            self.lines.append(ln)
            self.labels.append(tx)

    def ustaw(self, i, rect=None, alpha=1.0, color=FG, lw=1.6):
        x, y, w, h = rect or self.rects[i]
        xs = x + w * (0.08 + 0.84 * np.linspace(0, 1, PUNKTY))
        ys = y + h * (0.36 + 0.56 * self.rynki[i].mini)
        self.lines[i].set_data(xs, ys)
        self.lines[i].set_alpha(alpha)
        self.lines[i].set_color(color)
        self.lines[i].set_linewidth(lw)
        self.labels[i].set_position((x + w / 2, y + h * 0.17))
        self.labels[i].set_alpha(alpha)


def kolor(stan: int):
    return GREEN if stan == 1 else RED if stan == -1 else GREY


# ============================================================
# ZAPIS
# ============================================================

def ffmpeg_ok() -> bool:
    try:
        import imageio_ffmpeg
        matplotlib.rcParams["animation.ffmpeg_path"] = imageio_ffmpeg.get_ffmpeg_exe()
        return True
    except ImportError:
        return shutil.which("ffmpeg") is not None


def render(fig, update, sekundy: float, nazwa: str, video: bool) -> None:
    n = int(round(sekundy * FPS))
    if video:
        writer = FFMpegWriter(fps=FPS, codec="libx264", bitrate=12000, extra_args=["-pix_fmt", "yuv420p"])
        with writer.saving(fig, str(OUT / f"{nazwa}.mp4"), dpi=100):
            for k in range(n):
                update(k / FPS)
                writer.grab_frame(facecolor=BG)
        print(f"  {OUT / (nazwa + '.mp4')}")
    update(sekundy)
    fig.savefig(OUT / f"{nazwa}.png", facecolor=BG)
    print(f"  {OUT / (nazwa + '.png')}")
    plt.close(fig)


# ============================================================
# SCENY
# ============================================================

def scena_rynki(rynki, video):
    fig, ax = nowa_scena()
    rects, th = uklad(rynki)
    kaf = Kafelki(ax, rynki, rects, th)
    tytul = ax.text(W / 2, 8.3, "", color=FG, fontsize=60, fontfamily=TITLE_FONT, ha="center", va="center")
    start = {g: 0.4 + 1.6 * k for k, g in enumerate(GRUPY)}       # grupa za grupą
    koniec = start[GRUPY[-1]] + 1.6

    def update(t):
        widoczne = 0
        for i, r in enumerate(rynki):
            part = [q for q in rynki if q.grupa == r.grupa]
            k = part.index(r)
            t0 = start[r.grupa] + 1.1 * k / max(len(part), 1)
            a = ease((t - t0) / 0.35)
            kaf.ustaw(i, alpha=a)
            widoczne += a > 0.5
        teraz = [g for g in GRUPY if t >= start[g]]
        if t >= koniec or not teraz:
            tytul.set_text(count_text(len(rynki), "rynek", "rynki", "rynków").upper() if t >= koniec else "")
        else:
            g = teraz[-1]
            tytul.set_text(count_text(sum(r.grupa == g for r in rynki), *GRUPA_TXT[g]).upper())

    render(fig, update, koniec + 2.0, "1_rynki", video)


def coin_paths(close: pd.Series, n: int, seed: int = 3):
    """Te same dzienne ruchy, kierunek z monety (dryf zostaje — jak w badaniu)."""
    lg = np.log(close.to_numpy())
    r = np.diff(lg)
    mu = r.mean()
    rng = np.random.default_rng(seed)
    signs = rng.choice([-1.0, 1.0], size=(n, len(r)))
    paths = lg[0] + np.concatenate([np.zeros((n, 1)), np.cumsum(mu + signs * (r - mu), axis=1)], axis=1)
    idx = np.linspace(0, len(lg) - 1, 300).astype(int)
    return lg[idx], paths[:, idx]


def zakres(*wartosci):
    """Oś co najmniej 40–60%, poszerzana co 5 pkt, gdy pas albo wynik wychodzi poza nią."""
    lo = min(40.0, 5 * np.floor(min(wartosci) / 5))
    hi = max(60.0, 5 * np.ceil(max(wartosci) / 5))
    return lo, hi


def pas_os(ax, y, lo_pct=40.0, hi_pct=60.0, x0=2.0, x1=14.0):
    """Oś procentów z kreskami co 5 pkt. Zwraca funkcję procent → x."""
    def fx(p):
        return x0 + (x1 - x0) * (p - lo_pct) / (hi_pct - lo_pct)
    ax.plot([x0, x1], [y, y], color=DIM, lw=2)
    for p in np.arange(lo_pct, hi_pct + 0.1, 5 if hi_pct - lo_pct <= 30 else 10):
        ax.plot([fx(p)] * 2, [y - 0.08, y + 0.08], color=DIM, lw=2)
        ax.text(fx(p), y - 0.32, f"{p:.0f}%", color=GREY, fontsize=18, ha="center", va="center")
    return fx


def scena_moneta(rynki, video):
    r = next((q for q in rynki if q.name in ("Złoto", "Sztuczny Surowce 1")), rynki[0])
    real, paths = coin_paths(r.close, N_MONET)
    fig, ax = nowa_scena()
    ax.text(W / 2, 8.35, r.name.upper(), color=FG, fontsize=60, fontfamily=TITLE_FONT, ha="center", va="center")
    licznik = ax.text(W / 2, 7.55, "", color=GREY, fontsize=30, ha="center", va="center")
    lo, hi = min(paths.min(), real.min()), max(paths.max(), real.max())   # wszystkie 1000 w kadrze
    bx0, bx1, by0, by1 = 1.0, W - 1.0, 2.6, 7.0
    xs = np.linspace(bx0, bx1, len(real))

    def fy(v):
        return by0 + (by1 - by0) * (v - lo) / (hi - lo)

    lc = LineCollection([], colors=GREY, linewidths=1.0, alpha=0.06, zorder=1)
    ax.add_collection(lc)
    segs = [np.column_stack([xs, fy(p)]) for p in paths]
    ax.plot(xs, fy(real), color=FG, lw=3.2, zorder=3)

    fx = pas_os(ax, 1.25, *zakres(*r.pas, r.wynik))
    band = Rectangle((fx(r.pas[0]), 1.05), fx(r.pas[1]) - fx(r.pas[0]), 0.4, color=GREY, alpha=0.0, zorder=2)
    ax.add_patch(band)
    dot, = ax.plot([], [], "o", ms=26, color=kolor(r.stan), zorder=4)
    txt_band = ax.text(fx(r.moneta), 1.85, "", color=GREY, fontsize=26, ha="center", va="center")
    txt_dot = ax.text(fx(r.wynik), 0.45, "", color=kolor(r.stan), fontsize=30, fontfamily=TITLE_FONT,
                      ha="center", va="center")
    t_cloud, t_band, t_dot = 0.8, 6.5, 8.0

    def update(t):
        k = int(N_MONET * ease((t - t_cloud) / (t_band - t_cloud - 0.8)) ** 1.6)
        lc.set_segments(segs[:k])
        licznik.set_text(f"{k} wykresów z monety" if k else "prawdziwy wykres")
        a = ease((t - t_band) / 0.6)
        band.set_alpha(0.45 * a)
        txt_band.set_text(f"moneta: {pl(r.pas[0])}–{pl(r.pas[1])}%" if a > 0 else "")
        if t >= t_dot:
            dot.set_data([fx(r.wynik)], [1.25])
            txt_dot.set_text(f"trend: {pl(r.wynik)}%")
        else:
            dot.set_data([], [])
            txt_dot.set_text("")

    render(fig, update, t_dot + 3.0, "2_moneta", video)


def scena_siatka(rynki, video):
    fig, ax = nowa_scena()
    rects, th = uklad(rynki)
    kaf = Kafelki(ax, rynki, rects, th)
    zl = ax.text(W / 2 - 4.2, 8.3, "", color=GREEN, fontsize=44, fontfamily=TITLE_FONT, ha="center", va="center")
    sz = ax.text(W / 2, 8.3, "", color=GREY, fontsize=44, fontfamily=TITLE_FONT, ha="center", va="center")
    cz = ax.text(W / 2 + 4.2, 8.3, "", color=RED, fontsize=44, fontfamily=TITLE_FONT, ha="center", va="center")
    t0, krok = 0.6, 4.5 / max(len(rynki), 1)

    def update(t):
        licz = {1: 0, 0: 0, -1: 0}
        for i, r in enumerate(rynki):
            on = t >= t0 + i * krok
            kaf.ustaw(i, color=kolor(r.stan) if on else FG, lw=2.2 if on else 1.6)
            kaf.labels[i].set_color(kolor(r.stan) if on and r.stan else GREY)
            if on:
                licz[r.stan] += 1
        zl.set_text(f"LEPIEJ: {licz[1]}")
        sz.set_text(f"JAK MONETA: {licz[0]}")
        cz.set_text(f"GORZEJ: {licz[-1]}")

    render(fig, update, t0 + 4.5 + 2.5, "3_siatka", video)


def scena_razem(rynki, pule, video):
    fig, ax = nowa_scena()
    rects, th = uklad(rynki)
    kaf = Kafelki(ax, rynki, rects, th)
    p = pule[POOLED]
    wynik, lo_p, hi_p = float(p["wygrane_pct"]), float(p["moneta_pas_dol_pct"]), float(p["moneta_pas_gora_pct"])
    n_all = int(p["zdarzenia"])
    stan = 1 if wynik > hi_p else -1 if wynik < lo_p else 0
    AX_Y = 4.3
    srodek = (W / 2 - 1.2, AX_Y - 0.6, 2.4, 1.2)
    t_move, t_axis, t_dot = 0.3, 3.0, 6.5

    tytul = ax.text(W / 2, 8.3, "", color=FG, fontsize=60, fontfamily=TITLE_FONT, ha="center", va="center")
    sygnaly = ax.text(W / 2, 7.4, "", color=GREY, fontsize=32, ha="center", va="center")
    fx = None
    elems = {}

    def build_axis():
        nonlocal fx
        half1 = np.median([(r.pas[1] - r.pas[0]) / 2 for r in rynki])
        c = (lo_p + hi_p) / 2
        fx = pas_os(ax, AX_Y, *zakres(c - half1, c + half1, wynik))
        elems["half1"] = half1
        elems["band"] = Rectangle((0, AX_Y - 0.25), 0, 0.5, color=GREY, alpha=0.45, zorder=2)
        ax.add_patch(elems["band"])
        elems["band_txt"] = ax.text(W / 2, AX_Y + 0.75, "", color=GREY, fontsize=28, ha="center", va="center")
        elems["dot"], = ax.plot([], [], "o", ms=30, color=kolor(stan), zorder=4)
        elems["wynik"] = ax.text(W / 2, 2.3, "", color=kolor(stan), fontsize=64, fontfamily=TITLE_FONT,
                                 ha="center", va="center")
        elems["moneta"] = ax.text(W / 2, 1.35, "", color=GREY, fontsize=34, ha="center", va="center")

    built = [False]

    def update(t):
        a = ease((t - t_move) / 2.2)
        for i, (x, y, w, h) in enumerate(rects):
            tx, ty, tw, tht = srodek
            rect = (x + (tx - x) * a, y + (ty - y) * a, w + (tw - w) * a, h + (tht - h) * a)
            kaf.ustaw(i, rect=rect, alpha=max(1 - a, 0.0) if a < 1 else 0.0, color=GREY if a > 0 else FG)
            kaf.labels[i].set_alpha(max(1 - 3 * a, 0.0))
        tytul.set_text("WSZYSTKIE RYNKI RAZEM" if a > 0.5 else "")
        n_now = int(n_all * a)
        sygnaly.set_text(count_text(n_now, "sygnał", "sygnały", "sygnałów") if a > 0 else "")
        if t >= t_axis:
            if not built[0]:
                build_axis()
                built[0] = True
            b = ease((t - t_axis) / 2.5)
            half = elems["half1"] + ((hi_p - lo_p) / 2 - elems["half1"]) * b
            c = (lo_p + hi_p) / 2
            elems["band"].set_x(fx(c - half))
            elems["band"].set_width(fx(c + half) - fx(c - half))
            elems["band_txt"].set_text(
                "pas przypadku: jeden rynek" if b < 0.5 else f"pas przypadku: {count_text(len(rynki), 'rynek', 'rynki', 'rynków')}")
        if t >= t_dot:
            elems["dot"].set_data([fx(wynik)], [AX_Y])
            elems["wynik"].set_text(f"TREND: {pl(wynik)}%")
            elems["moneta"].set_text(f"moneta: {pl(lo_p)}–{pl(hi_p)}%")

    render(fig, update, t_dot + 3.5, "4_razem", video)


def main():
    sztuczne = "--sztuczne" in sys.argv
    video = "--png" not in sys.argv
    if video and not ffmpeg_ok():
        sys.exit("Brak ffmpeg. Zainstaluj: pip install imageio-ffmpeg (albo dopisz --png).")
    rynki, pule = dane_sztuczne() if sztuczne else dane_prawdziwe()
    global OUT
    if sztuczne:
        OUT = OUT / "sztuczne"
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{len(rynki)} rynków. Zapis do {OUT}:")
    scena_rynki(rynki, video)
    scena_moneta(rynki, video)
    scena_siatka(rynki, video)
    scena_razem(rynki, pule, video)


if __name__ == "__main__":
    main()
