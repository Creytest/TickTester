"""Plansze 'jak działa strategia' dla strategii z Reddita (odcinek 2).

Każda plansza: JEDEN PNG 1920x1080 z 3 segmentami obok siebie (1 setup, 2 wejście, 3 wyjście),
jak przy TikToku. W montażu prawe segmenty są zasłonięte i odsłaniane po kolei.
Świece są ilustracyjne (nie dane rynkowe), ale wskaźniki (RSI, EMA, ATR, ADX) są liczone z tych świec
zgodnie z regułami w strategies/reddit/. IBS Mean Reversion ma osobny skrypt (ibs_plansza.py).

Uruchomienie:  python reddit_plansze.py [folder_wyjściowy] [nazwa ...]
(domyślnie każda plansza do nagrania/Reddit/<Strategia>/plansza_zasady.png)
"""
import sys
from math import sin
from pathlib import Path

from matplotlib.patches import Rectangle

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tiktok_plansze import (BG, FG, GREEN, RED, GREY, DIM, PANEL, BLUE, YELLOW, Seg, figure, path,  # noqa: E402
                            bars_from, ylim_of, ema, rsi, cross_up, cross_dn, HERE)
import matplotlib.pyplot as plt  # noqa: E402

ARGS = sys.argv[1:]
OUT = Path(ARGS.pop(0)) if ARGS and not ARGS[0].isidentifier() else None
REDDIT = HERE.parents[1] / "nagrania" / "Reddit"


def save(fig, folder):
    p = OUT / f"{folder}.png" if OUT else REDDIT / folder / "plansza_zasady.png"
    p.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(p, facecolor=BG)
    plt.close(fig)
    print("ok", folder)


def atr(B, p=14):
    out, prev = [], None
    for i, (o, h, l, c) in enumerate(B):
        tr = h - l if i == 0 else max(h - l, abs(h - B[i - 1][3]), abs(l - B[i - 1][3]))
        prev = tr if prev is None else (prev * (p - 1) + tr) / p
        out.append(prev)
    return out


def adx(B, p=14):
    """ADX Wildera (jak ta.dmi w TradingView)."""
    pdm, ndm, tr = [0.0], [0.0], [B[0][1] - B[0][2]]
    for i in range(1, len(B)):
        up, dn = B[i][1] - B[i - 1][1], B[i - 1][2] - B[i][2]
        pdm.append(up if up > dn and up > 0 else 0.0)
        ndm.append(dn if dn > up and dn > 0 else 0.0)
        tr.append(max(B[i][1] - B[i][2], abs(B[i][1] - B[i - 1][3]), abs(B[i][2] - B[i - 1][3])))

    def rma(x):
        out, v = [], None
        for i, a in enumerate(x):
            v = sum(x[:i + 1]) / (i + 1) if i < p else (v * (p - 1) + a) / p
            out.append(v)
        return out

    st, sp, sn = rma(tr), rma(pdm), rma(ndm)
    dx = []
    for t, a, b in zip(st, sp, sn):
        pdi, ndi = 100 * a / t, 100 * b / t
        dx.append(100 * abs(pdi - ndi) / (pdi + ndi) if pdi + ndi else 0.0)
    return rma(dx)


def dot(s, x, y, col):
    s.ax.plot([x], [y], "o", ms=13, color=col, mec=FG, mew=2, zorder=8)


def risk_boxes(s, x1, x2, entry, sl, tp, long=True):
    s.ax.add_patch(Rectangle((x1, min(entry, sl)), x2 - x1, abs(entry - sl), facecolor=RED, alpha=0.14, lw=0, zorder=1))
    s.ax.add_patch(Rectangle((x1, min(entry, tp)), x2 - x1, abs(tp - entry), facecolor=GREEN, alpha=0.14, lw=0, zorder=1))
    s.level(tp, x1 - 1, x2, GREEN, "TP", ls="-")
    s.level(sl, x1 - 1, x2, RED, "SL", ls="-")


# ───────────────────────── RSI 90% ─────────────────────────
def rsi_90():
    H, n = 30, 50
    # RSI: wyjście nad 30, wyraźnie wyżej (~50), powrót pod 30 i drugie przecięcie w górę
    cl = path([(0, 110), (H, 108), (H + 5, 98), (H + 11, 105), (H + 18, 93), (H + 21, 97), (H + 26, 103),
               (H + 33, 112), (H + 39, 118), (H + 42, 117.4), (H + 48, 113)], H + n, 0.35)
    Ball = bars_from(cl, wick=0.55)
    r = rsi(cl, 14)
    B, r = Ball[H:], r[H:]
    ups = [i for i in range(1, n) if cross_up(r, [30] * n, i)]
    dn = next(i for i in range((ups[-1] if ups else 1) + 1, n) if cross_dn(r, [70] * n, i))
    A1, A2 = ups[0], ups[1] if len(ups) > 1 else ups[0]
    n = dn + 4
    lo, hi = ylim_of(B, n, pad=0.1)

    def panel(s, upto, marks):
        s.sx.add_patch(Rectangle((-0.8, 0), n + 0.3, 30, facecolor=GREEN, alpha=0.08, lw=0, zorder=1))
        s.sx.add_patch(Rectangle((-0.8, 70), n + 0.3, 30, facecolor=RED, alpha=0.08, lw=0, zorder=1))
        s.level(30, -0.8, n - 0.5, GREEN, "30", ax=s.sx, lw=1.8, size=15)
        s.level(70, -0.8, n - 0.5, RED, "70", ax=s.sx, lw=1.8, size=15)
        s.line(r, upto, YELLOW, lw=2.6, ax=s.sx)
        for x, col in marks:
            s.sx.plot([x], [r[x]], "o", ms=10, color=col, mec=FG, mew=1.6, zorder=8)

    fig = figure()
    kw = dict(sub_ylim=(0, 100), sub_name="RSI 14")
    s = Seg(fig, 0, "1. RSI WRACA NAD 30 = LONG", "Wyjście z wyprzedania.\nWejście za 1/10 kapitału.", n, (lo, hi), **kw)
    s.candles(B, A1 + 1, {A1: GREEN})
    s.entry(A1, B[A1][3], GREEN, "1/10")
    panel(s, A1 + 1, [(A1, GREEN)])

    s = Seg(fig, 1, "2. KOLEJNY SYGNAŁ = DOKŁADKA", "Każde następne przecięcie 30\ndokłada 1/10. Najwyżej 10 wejść.", n, (lo, hi), **kw)
    s.candles(B, A2 + 1, {A1: GREEN, A2: GREEN})
    dot(s, A1 + 0.5, B[A1][3], GREEN)
    s.entry(A2, B[A2][3], GREEN, "+1/10")
    panel(s, A2 + 1, [(A1, GREEN), (A2, GREEN)])

    s = Seg(fig, 2, "3. RSI SPADA POD 70 = ODWRÓCENIE", "Zamknięcie całej pozycji i short.\nBez SL i TP.", n, (lo, hi), **kw)
    s.candles(B, n, {A1: GREEN, A2: GREEN, dn: RED})
    dot(s, A1 + 0.5, B[A1][3], GREEN)
    dot(s, A2 + 0.5, B[A2][3], GREEN)
    s.exit(dn + 0.5, B[dn][3], RED, "short")
    panel(s, n, [(A1, GREEN), (A2, GREEN), (dn, RED)])
    save(fig, "RSI_90")


# ───────────────────────── Second Entry ─────────────────────────
def second_entry():
    H, n = 30, 40
    cl = path([(0, 92), (H, 100), (H + 8, 108), (H + 11, 105.2), (H + 13, 107.3), (H + 16, 104.6), (H + 17, 105.4),
               (H + 18, 106.6), (H + 26, 113), (H + 39, 116)], H + n, 0.15)
    over = {}
    Ball = bars_from(cl, wick=0.45, over=over)
    e = ema(cl, 21)
    B, e = Ball[H:], e[H:]
    # nogi cofnięcia: szukamy H1 (pierwsze wyższe high po cofnięciu) i świecy sygnałowej po drugiej nodze
    top = 8
    H1 = next(i for i in range(top + 2, n) if B[i][1] > B[i - 1][1])
    SIG = next(i for i in range(H1 + 2, n) if B[i][1] < B[i - 1][1] and B[i + 1][1] > B[i][1])
    o, h, l, c = B[SIG]
    B[SIG] = (min(o, c) - 0.1, h, l, h - 0.2)  # świeca sygnałowa: wzrostowa, zamknięcie w górnej połowie
    if SIG + 1 < n:
        o2, h2, l2, c2 = B[SIG + 1]
        B[SIG + 1] = (B[SIG][3], max(h2, B[SIG][1] + 0.6), l2, c2)
    entry, sl = B[SIG][1], B[SIG][2]
    tp = entry + (entry - sl)
    ENT = SIG + 1
    EXIT = next(i for i in range(ENT, n) if B[i][1] >= tp)
    n = EXIT + 3
    leg1 = min(range(top, H1 + 1), key=lambda i: B[i][2])
    leg2 = min(range(H1, SIG + 1), key=lambda i: B[i][2])
    lo, hi = ylim_of(B, n, extra=[e[0]], pad=0.1)

    fig = figure()
    s = Seg(fig, 0, "1. TREND: EMA 21 ROŚNIE", "Cena cofa się po szczycie.\nPierwsze odbicie (1) pomijamy.", n, (lo, hi))
    s.candles(B, H1 + 1, {H1: DIM})
    s.line(e, H1 + 1, BLUE, label="EMA 21")
    s.tag(leg1, B[leg1][2], "1", FG, True, size=22)

    s = Seg(fig, 1, "2. DRUGIE ODBICIE = BUY STOP", "Dołek drugiej nogi (2) wyżej niż pierwszej.\nZlecenie nad high świecy sygnałowej.", n, (lo, hi))
    s.candles(B, SIG + 1, {H1: DIM, SIG: GREEN})
    s.line(e, SIG + 1, BLUE)
    s.tag(leg1, B[leg1][2], "1", FG, True, size=22)
    s.tag(leg2, B[leg2][2], "2", GREEN, True, size=22)
    s.level(entry, SIG - 0.5, SIG + 3, GREEN, "buy stop", lw=2)

    s = Seg(fig, 2, "3. SL POD ŚWIECĄ, TP 1:1", "SL pod low świecy sygnałowej.\nTP = tyle samo co ryzyko.", n, (lo, hi))
    s.candles(B, n, {SIG: GREEN})
    s.line(e, n, BLUE)
    risk_boxes(s, ENT - 0.5, EXIT + 0.5, entry, sl, tp)
    dot(s, ENT - 0.5, entry, GREEN)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "SecondEntry")


# ───────────────────────── Renko EMA 9/20 ─────────────────────────
def renko():
    # kierunki cegieł (+1 / -1); cegła = 1 punkt, odwrócenie o 2 cegły
    dirs = [1] * 14 + [-1] * 4 + [1] * 2 + [-1] * 2 + [1] * 10 + [-1] * 3 + [1] * 2 + [-1] * 4 + [1] * 8
    B, p, prev = [], 100.0, 1
    for i, d in enumerate(dirs):
        o = p if d == prev else p + d  # odwrócenie: cegła zaczyna się o jedną cegłę dalej
        c = o + d
        wick = 0.35 + 0.25 * abs(sin(i * 1.9)) if d != prev or i % 4 == 0 else 0.0
        h, l = (max(o, c), min(o, c) - wick) if d > 0 else (max(o, c) + wick, min(o, c))
        B.append((o, h, l, c))
        p, prev = c, d
    cl = [b[3] for b in B]
    e9, e20 = ema(cl, 9), ema(cl, 20)
    H = 14
    B, e9, e20 = B[H:], e9[H:], e20[H:]
    n = len(B)
    # sygnał: po dotknięciu EMA 20 knotem cegła wzrostowa zamyka się nad EMA 9
    touch = next(i for i in range(1, n) if B[i][2] <= e20[i] and e9[i] > e20[i])
    SIG = next(i for i in range(touch + 1, n) if B[i][3] > B[i][0] and B[i][0] <= e9[i] < B[i][3])
    o, h, l, c = B[SIG]
    knot = min(b[2] for b in B[touch:SIG + 1])
    entry, sl = c, knot - 0.1
    tp = entry + (1 + (min(o, c) - knot))
    EXIT = next(i for i in range(SIG + 1, n) if B[i][1] >= tp)
    n = EXIT + 3
    lo, hi = ylim_of(B, n, pad=0.1)
    lo -= (hi - lo) * 0.06

    def bricks(s, upto, hl=None):
        hl = hl or {}
        for i in range(upto):
            o, h, l, c = B[i]
            col = hl.get(i, GREEN if c > o else RED)
            if l < min(o, c) or h > max(o, c):
                s.ax.plot([i, i], [l, h], color=col, lw=2.2, zorder=3)
            s.ax.add_patch(Rectangle((i - 0.45, min(o, c)), 0.9, abs(c - o), facecolor=col if i in hl else BG,
                                     edgecolor=col, lw=2.2, zorder=4))

    fig = figure()
    s = Seg(fig, 0, "1. WYKRES RENKO + EMA 9 I 20", "Cegła rysuje się dopiero po ruchu o stałą\nliczbę punktów. Trend: EMA 9 nad EMA 20.", n, (lo, hi))
    bricks(s, touch)
    s.line(e9, touch, YELLOW, label="EMA 9")
    s.line(e20, touch, BLUE, label="EMA 20")

    s = Seg(fig, 1, "2. COFNIĘCIE I CEGŁA PRZEZ EMA 9", "Knot dotyka EMA 20, potem cegła\nzamyka się nad EMA 9 = long. Short lustrzanie.", n, (lo, hi))
    bricks(s, SIG + 1, {SIG: GREEN})
    s.line(e9, SIG + 1, YELLOW)
    s.line(e20, SIG + 1, BLUE)
    s.tag(touch, B[touch][2], "dotknięcie", FG, True, size=16, off=0.5)
    s.entry(SIG, entry, GREEN, "long")

    s = Seg(fig, 2, "3. SL ZA KNOTEM, TP = CEGŁA + KNOT", "TP w odległości cegły i knota (1:1).\nWariant autora: połowa tego (1:0,5).", n, (lo, hi))
    bricks(s, n, {SIG: GREEN})
    s.line(e9, n, YELLOW)
    s.line(e20, n, BLUE)
    risk_boxes(s, SIG + 0.5, EXIT + 0.5, entry, sl, tp)
    dot(s, SIG + 0.5, entry, GREEN)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "Renko_EMA9_20")


# ───────────────────────── EMA 9/19 Scalping ─────────────────────────
def ema9_19():
    H, n = 40, 34
    cl = path([(0, 96), (H - 10, 98), (H, 100.5), (H + 12, 107.5), (H + 16, 105.6), (H + 17, 105.8),
               (H + 24, 111), (H + 33, 114)], H + n, 0.2)
    Ball = bars_from(cl, wick=0.4)
    e9, e19 = ema(cl, 9), ema(cl, 19)
    B, e9, e19 = Ball[H:], e9[H:], e19[H:]
    # dotknięcie EMA 9 z góry po co najmniej 3 zamknięciach nad obiema średnimi
    T = next(i for i in range(4, n) if B[i][2] <= e9[i - 1] and all(B[k][3] > max(e9[k], e19[k]) for k in range(i - 3, i)))
    entry = e9[T - 1]
    o, h, l, c = B[T]
    B[T] = (o, h, min(l, entry - 0.25), max(c, entry + 0.1))
    sl = e19[T] - 0.1 * atr(Ball)[H + T]
    tp = entry + 2 * (entry - sl)
    EXIT = next(i for i in range(T + 1, n) if B[i][1] >= tp)
    n = EXIT + 3
    lo, hi = ylim_of(B, n, extra=[sl], pad=0.1)
    lo -= (hi - lo) * 0.06

    fig = figure()
    s = Seg(fig, 0, "1. TREND: CENA NAD EMA 9 I 19", "3 zamknięcia nad obiema średnimi,\nEMA 9 nad EMA 19. Short lustrzanie.", n, (lo, hi))
    s.candles(B, T)
    s.line(e9, T, YELLOW, label="EMA 9")
    s.line(e19, T, BLUE, label="EMA 19")

    s = Seg(fig, 1, "2. DOTKNIĘCIE EMA 9 = LONG", "Wejście od razu przy dotknięciu,\nbez czekania na zamknięcie świecy.", n, (lo, hi))
    s.candles(B, T + 1, {T: GREEN})
    s.line(e9, T + 1, YELLOW)
    s.line(e19, T + 1, BLUE)
    s.entry(T - 0.5, entry, GREEN, "long")

    s = Seg(fig, 2, "3. SL ZA EMA 19, TP 2:1", "Po zysku równym ryzyku SL na wejście.\nTylko 9:30–10:00 czasu NY.", n, (lo, hi))
    s.candles(B, n, {T: GREEN})
    s.line(e9, n, YELLOW)
    s.line(e19, n, BLUE)
    risk_boxes(s, T + 0.5, EXIT + 0.5, entry, sl, tp)
    dot(s, T, entry, GREEN)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "EMA9_19_Scalping")


# ───────────────────────── MOC to MOO ─────────────────────────
def moc_moo():
    # dwie sesje po 13 świec (pół godziny), przerwa nocna = pusty odstęp
    s1 = path([(0, 100), (6, 101.5), (12, 101.0)], 13, 0.35)
    s2 = path([(0, 101.9), (6, 101.2), (12, 102.4)], 13, 0.35)
    B1 = bars_from(s1, wick=0.3)
    B2 = bars_from(s2, first_open=101.9, wick=0.3)
    GAP = 6
    B = B1 + [None] * GAP + B2
    CLOSE, OPEN = 12, 13 + GAP
    n = len(B)
    lo, hi = ylim_of([b for b in B if b], 26, pad=0.35)

    def draw(s, upto, hl):
        for i in range(upto):
            if B[i] is None:
                continue
            o, h, l, c = B[i]
            col = hl.get(i, GREY)
            s.ax.plot([i, i], [l, h], color=col, lw=2.2 if i in hl else 1.8, zorder=3)
            s.ax.add_patch(Rectangle((i - 0.32, min(o, c)), 0.64, max(abs(c - o), s.dy * 0.15), facecolor=col,
                                     edgecolor=col, zorder=4))

    def night(s):
        s.ax.add_patch(Rectangle((CLOSE + 0.6, lo), GAP - 0.2, hi - lo, facecolor=PANEL, lw=0, zorder=0))
        s.ax.text(CLOSE + 0.5 + GAP / 2, hi - s.dy, "noc", color=GREY, fontsize=17, ha="center", va="top", zorder=6)

    fig = figure()
    s = Seg(fig, 0, "1. KUPNO NA ZAMKNIĘCIU", "Market on Close: kupno o 16:00 czasu NY,\nna ostatniej cenie sesji.", n, (lo, hi), right=2)
    draw(s, CLOSE + 1, {CLOSE: GREEN})
    s.entry(CLOSE, B[CLOSE][3], GREEN, "16:00")

    s = Seg(fig, 1, "2. TRZYMAMY PRZEZ NOC", "Cały zysk albo strata to luka\nmiędzy zamknięciem a otwarciem.", n, (lo, hi), right=2)
    night(s)
    draw(s, CLOSE + 1, {CLOSE: GREEN})
    dot(s, CLOSE + 0.5, B[CLOSE][3], GREEN)
    s.level(B[CLOSE][3], CLOSE + 0.5, OPEN, GREEN, lw=2)

    s = Seg(fig, 2, "3. SPRZEDAŻ NA OTWARCIU", "Market on Open: sprzedaż o 9:30 czasu NY.\nI tak codziennie. Tylko long, bez SL.", n, (lo, hi), right=2)
    night(s)
    draw(s, n, {CLOSE: GREEN, OPEN: FG})
    dot(s, CLOSE + 0.5, B[CLOSE][3], GREEN)
    s.level(B[CLOSE][3], CLOSE + 0.5, OPEN, GREEN, lw=2)
    col = GREEN if B[OPEN][0] > B[CLOSE][3] else RED
    s.ax.plot([OPEN - 0.5], [B[OPEN][0]], marker="X", ms=17, color=col, mec=FG, mew=1.6, zorder=8)
    s.ax.text(OPEN - 0.5, B[OPEN][1] + s.dy, "9:30", color=col, fontsize=17, fontweight="bold", ha="center", zorder=8)
    s.note("Autor: akcje BRK.A. Test: indeks US500.", y=lo)
    save(fig, "MOC_MOO")


# ───────────────────────── Gold Thursday–Friday ─────────────────────────
def gold_thu_fri():
    days = ["pn", "wt", "śr", "cz", "pt"]
    W = [(100.0, 101.4, 99.2, 100.8), (100.8, 101.2, 99.6, 100.1), (100.1, 101.6, 99.8, 101.2),
         (101.2, 102.0, 100.6, 101.6), (101.6, 103.0, 101.0, 102.5)]
    W2 = [(102.5, 103.1, 101.3, 101.8), (101.8, 102.4, 100.9, 102.1), (102.1, 102.6, 101.2, 101.5),
          (101.5, 102.1, 100.7, 101.9), (101.9, 102.3, 100.6, 101.1)]
    B = W + W2
    n = len(B)
    THU, FRI = 3, 4
    lo, hi = ylim_of(B, n, pad=0.3)

    def draw(s, upto, hl):
        for i in range(upto):
            o, h, l, c = B[i]
            col = hl.get(i, DIM)
            s.ax.plot([i, i], [l, h], color=col, lw=2.6, zorder=3)
            s.ax.add_patch(Rectangle((i - 0.3, min(o, c)), 0.6, abs(c - o), facecolor=col, edgecolor=col, zorder=4))
            s.ax.text(i, lo + s.dy * 0.6, days[i % 5], color=FG if i in hl else GREY, fontsize=17, ha="center", zorder=6)

    fig = figure()
    s = Seg(fig, 0, "1. CZWARTEK: KUPNO", "Kupno złota na zamknięciu czwartku.", n, (lo, hi), right=1)
    draw(s, THU + 1, {THU: GREEN})
    s.entry(THU, B[THU][3], GREEN, "")

    s = Seg(fig, 1, "2. PIĄTEK: SPRZEDAŻ", "Sprzedaż na zamknięciu piątku.\nPozycja trwa jeden dzień.", n, (lo, hi), right=1)
    draw(s, FRI + 1, {THU: GREEN, FRI: FG})
    dot(s, THU + 0.5, B[THU][3], GREEN)
    s.exit(FRI + 0.5, B[FRI][3], GREEN, "")

    s = Seg(fig, 2, "3. I TAK CO TYDZIEŃ", "Reszta tygodnia bez pozycji.\nTylko long, bez SL, cały kapitał.", n, (lo, hi), right=1)
    draw(s, n, {THU: GREEN, FRI: FG, THU + 5: GREEN, FRI + 5: FG})
    for t, f in ((THU, FRI), (THU + 5, FRI + 5)):
        dot(s, t + 0.5, B[t][3], GREEN)
        s.exit(f + 0.5, B[f][3], GREEN if B[f][3] > B[t][3] else RED, "")
    save(fig, "Gold_ThuFri")


# ───────────────────────── New ATH + ATR trailing ─────────────────────────
def ath_atr():
    H, n = 20, 52
    cl = path([(0, 96), (H, 104), (H + 6, 110), (H + 14, 102), (H + 22, 106), (H + 28, 112.5), (H + 36, 119),
               (H + 40, 116.5), (H + 44, 120.5), (H + 51, 111)], H + n, 0.5)
    Ball = bars_from(cl, wick=0.6)
    a = atr(Ball)
    B, a = Ball[H:], a[H:]
    ath = max(b[1] for b in Ball[:H + 10])
    PK = max(range(0, 10), key=lambda i: B[i][1])
    SIG = next(i for i in range(PK + 3, n) if B[i][3] > ath)
    ts, hh, stops = None, B[SIG][1], [None] * n
    for i in range(SIG, n):
        hh = max(hh, B[i][1])
        ts = max(ts or -1e9, hh - 3 * a[i])
        stops[i] = ts
    EXIT = next(i for i in range(SIG + 1, n) if B[i][2] <= stops[i - 1])
    n = EXIT + 2
    lo, hi = ylim_of(B, n, pad=0.1)

    fig = figure()
    s = Seg(fig, 0, "1. SZCZYT WSZECH CZASÓW", "Najwyższa cena w całej historii\naktywa (u nas: w całych danych).", n, (lo, hi))
    s.candles(B, SIG)
    s.level(ath, PK, SIG + 1, FG, "ATH")

    s = Seg(fig, 1, "2. ZAMKNIĘCIE NAD ATH = LONG", "Kupujemy nowy szczyt.\nTylko long.", n, (lo, hi))
    s.candles(B, SIG + 1, {SIG: GREEN})
    s.level(ath, PK, SIG + 1, FG)
    s.entry(SIG, B[SIG][3], GREEN, "long")

    s = Seg(fig, 2, "3. TRAILING STOP 3 × ATR", "Najwyższa cena od wejścia minus 3 ATR.\nStop idzie tylko w górę. Brak TP.", n, (lo, hi))
    s.candles(B, n, {SIG: GREEN, EXIT: RED})
    s.level(ath, PK, SIG, FG, lw=1.4)
    xs, ys = [], []
    for i in range(SIG + 1, EXIT + 1):
        xs += [i - 0.5, i + 0.5]; ys += [stops[i - 1]] * 2
    s.ax.plot(xs, ys, color=RED, lw=3, zorder=5)
    dot(s, SIG + 0.5, B[SIG][3], GREEN)
    s.exit(EXIT, stops[EXIT - 1], RED, "wyjście")
    s.note("1% kapitału ryzyka do pierwszego stopu", y=lo)
    save(fig, "ATH_ATR")


# ───────────────────────── IBS gold futures ─────────────────────────
def ibs_gold():
    n = 40
    IB = 12  # pierwsza godzina (świece po 5 min)
    cl = path([(0, 100), (3, 101.6), (6, 99.4), (9, 101.2), (11, 100.4), (14, 101.0), (17, 102.6), (22, 103.6),
               (27, 103.0), (32, 104.4), (39, 104.6)], n, 0.25)
    B = bars_from(cl, wick=0.35)
    ibh, ibl = max(b[1] for b in B[:IB]), min(b[2] for b in B[:IB])
    BRK = next(i for i in range(IB, n) if B[i][1] > ibh or B[i][2] < ibl)
    entry, sl = ibh, ibl - 0.05
    tp = entry + (ibh - ibl)
    EXIT = next((i for i in range(BRK + 1, n) if B[i][1] >= tp), None)
    if EXIT is None:
        o, h, l, c = B[-3]
        EXIT = n - 3
        B[EXIT] = (o, tp + 0.2, l, c)
    n = EXIT + 3
    lo, hi = ylim_of(B, n, extra=[tp, sl], pad=0.1)

    def box(s, x2):
        s.ax.add_patch(Rectangle((-0.5, ibl), IB, ibh - ibl, facecolor=BLUE, alpha=0.12, edgecolor=BLUE, lw=1.6, zorder=1))
        s.level(ibh, -0.5, x2, BLUE, lw=1.8)
        s.level(ibl, -0.5, x2, BLUE, lw=1.8)

    fig = figure()
    s = Seg(fig, 0, "1. PIERWSZA GODZINA (IB)", "Zakres od 8:20 do 9:20 czasu NY:\nnajwyższa i najniższa cena.", n, (lo, hi))
    box(s, IB - 0.5)
    s.candles(B, IB)
    s.ax.text((IB - 1) / 2, ibh + s.dy, "IB", color=BLUE, fontsize=22, fontweight="bold", ha="center", va="bottom", zorder=7)

    s = Seg(fig, 1, "2. PIERWSZE WYBICIE = WEJŚCIE", "Wybicie w górę = long, w dół = short.\nJedna transakcja dziennie.", n, (lo, hi))
    box(s, BRK + 2)
    s.candles(B, BRK + 1, {BRK: GREEN})
    s.entry(BRK - 0.5, entry, GREEN, "long")

    s = Seg(fig, 2, "3. SL ZA IB, TP = SZEROKOŚĆ IB", "SL tick za drugą stroną zakresu.\nNajpóźniej wyjście o 13:30 czasu NY.", n, (lo, hi))
    box(s, BRK)
    s.candles(B, n, {BRK: GREEN})
    risk_boxes(s, BRK, EXIT + 0.5, entry, sl, tp)
    dot(s, BRK, entry, GREEN)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "IBS_GoldFutures")


# ───────────────────────── Holy Grail (Raschke) ─────────────────────────
def holy_grail():
    H, n = 40, 40
    cl = path([(0, 100), (H - 20, 99), (H - 6, 103), (H + 12, 117), (H + 14, 117.6), (H + 19, 111.4),
               (H + 21, 111.0), (H + 24, 115.0), (H + 30, 121), (H + 39, 124)], H + n, 0.3)
    Ball = bars_from(cl, wick=0.5)
    e, ax_ = ema(cl, 20), adx(Ball)
    B, e, ax_ = Ball[H:], e[H:], ax_[H:]
    PEAK = max(range(8, 20), key=lambda i: B[i][1])
    T = next(i for i in range(PEAK + 1, n) if B[i][2] <= e[i])
    # buy stop co świecę przesuwany na high ostatniej świecy; wejście, gdy cena go przebije
    ENT = next(i for i in range(T + 1, n) if B[i][1] > B[i - 1][1])
    SIG = ENT - 1
    o, h, l, c = B[SIG]  # świeca sygnałowa czytelniejsza: wyraźny korpus, high nadal pod high świecy wejścia
    B[SIG] = (c - 0.6, min(c + 0.3, B[ENT][1] - 0.2), c - 0.9, c)
    entry = B[SIG][1]
    sl = min(b[2] for b in B[PEAK:ENT + 1]) - 0.1
    tp = B[PEAK][1]
    EXIT = next(i for i in range(ENT, n) if B[i][1] >= tp)
    n = EXIT + 3
    lo, hi = ylim_of(B, n, extra=[e[0]], pad=0.1)
    lo -= (hi - lo) * 0.08
    amax = max(ax_[:n]) * 1.15

    def panel(s, upto):
        s.level(30, -0.8, n - 0.5, FG, "30", ax=s.sx, lw=1.8, size=15)
        s.line(ax_, upto, YELLOW, lw=2.6, ax=s.sx)

    fig = figure()
    kw = dict(sub_ylim=(0, amax), sub_name="ADX 14")
    s = Seg(fig, 0, "1. SILNY TREND: ADX > 30", "ADX powyżej 30 i rośnie.\nCena nad EMA 20 = szukamy longów.", n, (lo, hi), **kw)
    s.candles(B, PEAK + 1)
    s.line(e, PEAK + 1, BLUE, label="EMA 20")
    panel(s, PEAK + 1)

    s = Seg(fig, 1, "2. COFNIĘCIE DO EMA 20", "Cena dotyka EMA 20. Buy stop\nnad high świecy. Short lustrzanie.", n, (lo, hi), **kw)
    s.candles(B, SIG + 1, {SIG: GREEN})
    s.line(e, SIG + 1, BLUE)
    s.tag(T, B[T][2], "dotknięcie", FG, True, size=16, off=2.2)
    s.level(entry, SIG - 0.5, SIG + 2.5, GREEN, "buy stop", lw=2)
    panel(s, SIG + 1)

    s = Seg(fig, 2, "3. SL POD DOŁKIEM, TP NA SZCZYCIE", "SL pod dołkiem cofnięcia.\nTP na szczycie sprzed cofnięcia.", n, (lo, hi), **kw)
    s.candles(B, n, {SIG: GREEN})
    s.line(e, n, BLUE)
    risk_boxes(s, ENT - 0.5, EXIT + 0.5, entry, sl, tp)
    dot(s, ENT - 0.5, entry, GREEN)
    panel(s, n)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "HolyGrail")


ALL = [rsi_90, second_entry, renko, ema9_19, moc_moo, gold_thu_fri, ath_atr, ibs_gold, holy_grail]

if __name__ == "__main__":
    wybrane = [fn for fn in ALL if not ARGS or fn.__name__ in ARGS]
    for fn in wybrane:
        fn()
