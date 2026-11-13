"""Plansze 'jak działa strategia' dla 9 strategii z TikToka (zestaw 1).

Każda plansza: JEDEN PNG 1920x1080 z 3 segmentami obok siebie (1 setup, 2 wejście, 3 wyjście).
W montażu prawe segmenty są zasłonięte i odsłaniane po kolei. Świece są ilustracyjne (nie dane rynkowe),
ale wskaźniki (EMA, VWAP, RSI, Stochastic, Two-Pole) są liczone z tych świec zgodnie z regułami strategii.

Uruchomienie:  python tiktok_plansze.py [folder_wyjściowy]
(domyślnie każda plansza do nagrania/TikTok/<Strategia>/plansza_zasady.png)
Fonty Anton i Inter są ładowane z podfolderu fonts/ (nie trzeba ich instalować).
"""
import sys
from math import sin, cos, pi
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle, Polygon

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
TIKTOK = HERE.parents[1] / "nagrania" / "TikTok"
# Nazwa planszy → folder strategii w nagrania/TikTok/.
STRATEGIE = {
    "01_luxalgo_sr_breaks_msts": "LuxAlgo_SR_Breaks_MSTS",
    "02_cloud_ma_ema30_74": "CloudMA_EMA30_74",
    "03_sfp_volume": "SFP_Volume",
    "04_ema9_vwap": "EMA9_VWAP",
    "05_ema9": "EMA9",
    "06_rsi6_80_20": "RSI6_80_20",
    "07_bigbeluga_two_pole_stoch": "BigBeluga_Stoch_80percent",
    "08_sr_retest": "SR_Retest",
    "09_ssl_ifvg": "SSL_IFVG",
}
for f in (HERE / "fonts").glob("*.[ot]tf"):
    font_manager.fontManager.addfont(str(f))

BG, FG, GREEN, RED = "#0B0D10", "#F2F2F2", "#00D084", "#FF3B30"
GREY, DIM, PANEL = "#6B7280", "#3A3F47", "#14181E"
BLUE, YELLOW = "#4C8DFF", "#F5C542"
TV_GREEN, TV_RED = "#4CAF50", "#FF5252"   # kolory trójkątów Cloud MA z TradingView
plt.rcParams["font.family"] = ["Inter", "DejaVu Sans"]
TITLE_FONT = "Anton" if any(f.name == "Anton" for f in font_manager.fontManager.ttflist) else "DejaVu Sans"

X0, STEP, W = 0.025, 0.325, 0.30


# ───────────────────────── dane ilustracyjne ─────────────────────────
def path(knots, n, noise=0.6):
    """Zamknięcia: interpolacja liniowa między punktami (indeks, cena) + deterministyczny szum."""
    out = []
    for i in range(n):
        for (a, va), (b, vb) in zip(knots, knots[1:]):
            if a <= i <= b:
                v = va + (vb - va) * (i - a) / (b - a)
                break
        else:
            v = knots[-1][1]
        out.append(v + noise * sin(i * 2.3) * cos(i * 0.7))
    return out


def bars_from(closes, first_open=None, wick=0.5, over=None):
    """OHLC z zamknięć: open = poprzednie zamknięcie, knoty o zmiennej długości. over = {i: (o,h,l,c)}."""
    B = []
    prev = closes[0] if first_open is None else first_open
    for i, c in enumerate(closes):
        o = prev
        w1 = wick * (0.6 + 0.5 * abs(sin(i * 1.7)))
        w2 = wick * (0.6 + 0.5 * abs(cos(i * 1.3)))
        B.append((o, max(o, c) + w1, min(o, c) - w2, c))
        prev = c
    for i, ohlc in (over or {}).items():
        B[i] = ohlc
        if i + 1 < len(B) and (i + 1) not in (over or {}):
            o, h, l, c = B[i + 1]
            B[i + 1] = (ohlc[3], max(h, ohlc[3]), min(l, ohlc[3]), c)
    return B


def ema(x, p):
    k, out = 2 / (p + 1), []
    for v in x:
        out.append(v if not out else out[-1] + k * (v - out[-1]))
    return out


def rsi(closes, p):
    out, ag, al = [50.0], 0.0, 0.0
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0), max(-ch, 0)
        if i <= p:
            ag += g / p; al += l / p
        else:
            ag = (ag * (p - 1) + g) / p; al = (al * (p - 1) + l) / p
        out.append(50.0 if i < p else 100 - 100 / (1 + ag / al) if al else 100.0)
    return out


def sma(x, p):
    return [sum(x[max(0, i - p + 1):i + 1]) / len(x[max(0, i - p + 1):i + 1]) for i in range(len(x))]


def stoch(B, pk=7, sk=3, sd=3):
    raw = []
    for i in range(len(B)):
        w = B[max(0, i - pk + 1):i + 1]
        hh, ll = max(b[1] for b in w), min(b[2] for b in w)
        raw.append(100 * (B[i][3] - ll) / (hh - ll) if hh > ll else 50)
    k = sma(raw, sk)
    return k, sma(k, sd)


def two_pole(closes, length=34, damping=0.9):
    om = 2 * pi / length
    a, b = damping * om, om ** 2
    f1, f2, out = closes[0], closes[0], []
    for c in closes:
        f1 = f1 + a * (c - f1)
        f2 = f2 + b * (f1 - f2)
        out.append(f2)
    return out


def ylim_of(B, nv, extra=(), pad=0.12):
    """Zakres osi Y z widocznych świec (i dodatkowych poziomów) z marginesem."""
    lo = min([b[2] for b in B[:nv]] + list(extra))
    hi = max([b[1] for b in B[:nv]] + list(extra))
    r = hi - lo
    return lo - r * pad, hi + r * pad


def cross_up(a, b, i):
    return a[i] > b[i] and a[i - 1] <= b[i - 1]


def cross_dn(a, b, i):
    return a[i] < b[i] and a[i - 1] >= b[i - 1]


# ───────────────────────── rysowanie ─────────────────────────
def fit_text(fig, x, y, s, max_w, size, **kw):
    t = fig.text(x, y, s, fontsize=size, **kw)
    r = fig.canvas.get_renderer()
    while t.get_window_extent(r).width > max_w * fig.bbox.width and size > 10:
        size -= 1
        t.set_fontsize(size)
    return t


class Seg:
    """Jeden segment planszy: nagłówek, wykres ceny i opcjonalny panel wskaźnika."""

    def __init__(self, fig, j, title, sub, n, ylim, sub_ylim=None, sub_name=None, right=8):
        self.x0 = x0 = X0 + j * STEP
        fit_text(fig, x0 + W / 2, 0.94, title, W, 40, color=FG, ha="center", va="top", family=TITLE_FONT)
        fit_text(fig, x0 + W / 2, 0.855, sub, W, 19, color=GREY, ha="center", va="top", linespacing=1.45)
        xl = (-1, n + right)
        if sub_ylim:
            self.ax = fig.add_axes([x0, 0.31, W, 0.44])
            self.sx = fig.add_axes([x0, 0.07, W, 0.20])
            self.sx.set_facecolor(BG); self.sx.axis("off"); self.sx.set_xlim(*xl); self.sx.set_ylim(*sub_ylim)
            self.sx.add_patch(Rectangle((-0.8, sub_ylim[0]), n + 0.3, sub_ylim[1] - sub_ylim[0],
                                        facecolor=PANEL, edgecolor="none", zorder=0))
            if sub_name:
                self.sx.text(-0.5, sub_ylim[1], sub_name, color=GREY, fontsize=16, va="top", zorder=5)
        else:
            self.ax = fig.add_axes([x0, 0.07, W, 0.68])
            self.sx = None
        self.ax.set_facecolor(BG); self.ax.axis("off")
        self.ax.set_xlim(*xl); self.ax.set_ylim(*ylim)
        self.n = n
        yr = ylim[1] - ylim[0]
        self.dy = yr * 0.035

    # świece
    def candles(self, B, upto, hl=None, start=0):
        hl = hl or {}
        for i in range(start, upto):
            o, h, l, c = B[i]
            col = hl.get(i, GREY)
            lw = 2.6 if i in hl else 1.8
            self.ax.plot([i, i], [l, h], color=col, lw=lw, solid_capstyle="round", zorder=3)
            lo, hi = min(o, c), max(o, c)
            self.ax.add_patch(Rectangle((i - 0.32, lo), 0.64, max(hi - lo, self.dy * 0.15),
                                        facecolor=col, edgecolor=col, lw=lw, zorder=4))

    def line(self, y, upto, col, lw=3, start=0, ax=None, ls="-", label=None, z=5):
        ax = ax or self.ax
        xs = list(range(start, upto))
        ax.plot(xs, y[start:upto], color=col, lw=lw, ls=ls, zorder=z, solid_capstyle="round")
        if label:
            ax.text(upto - 1 + 0.6, y[upto - 1], label, color=col, fontsize=17, fontweight="bold", va="center", zorder=6)

    def level(self, y, x1, x2, col, label=None, ls=(0, (6, 4)), lw=2.4, ax=None, size=17, above=None):
        ax = ax or self.ax
        ax.plot([x1, x2], [y, y], color=col, lw=lw, ls=ls, zorder=2)
        if label:
            if above is None:
                ax.text(x2 + 0.4, y, label, color=col, fontsize=size, fontweight="bold", va="center", zorder=6)
            else:
                ax.text(x1, y + (self.dy if above else -self.dy), label, color=col, fontsize=size,
                        fontweight="bold", va="bottom" if above else "top", zorder=6)

    def tag(self, x, y, text, col, below, size=18, ax=None, off=1.0):
        ax = ax or self.ax
        ax.text(x, y + (-self.dy * off if below else self.dy * off), text, color=col, fontsize=size, fontweight="bold",
                ha="center", va="top" if below else "bottom", zorder=7)

    def tri(self, x, y, col, up, ax=None):
        ax = ax or self.ax
        d, s = self.dy, 0.42
        y0 = y - d * 0.6 if up else y + d * 0.6
        pts = [(x - s, y0 - d), (x + s, y0 - d), (x, y0)] if up else [(x - s, y0 + d), (x + s, y0 + d), (x, y0)]
        ax.add_patch(Polygon(pts, closed=True, facecolor=col, edgecolor=col, zorder=7))

    def signal_tri(self, x, y, col, up, w_px=80, gap_px=7):
        """Duży trójkąt sygnału jak we wskaźniku Cloud MA na TradingView:
        pełny, czubkiem przy przecięciu średnich, pod nim (long) albo nad nim (short)."""
        ax = self.ax
        bb = ax.get_window_extent()
        (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
        ux, uy = (x1 - x0) / bb.width, (y1 - y0) / bb.height
        hw, h, g = w_px / 2 * ux, w_px * 0.87 * uy, gap_px * uy
        if up:
            pts = [(x - hw, y - g - h), (x + hw, y - g - h), (x, y - g)]
        else:
            pts = [(x - hw, y + g + h), (x + hw, y + g + h), (x, y + g)]
        ax.add_patch(Polygon(pts, closed=True, facecolor=col, edgecolor="none", zorder=7))

    def entry(self, x, y, col, text="wejście", below=False):
        self.ax.plot([x + 0.5], [y], "o", ms=13, color=col, mec=FG, mew=2, zorder=8)
        self.ax.text(x + 1.3, y, text, color=col, fontsize=17, fontweight="bold", va="center", zorder=8)

    def exit(self, x, y, col, text):
        self.ax.plot([x], [y], marker="X", ms=17, color=col, mec=FG, mew=1.6, zorder=8)
        self.ax.text(x + 0.9, y, text, color=col, fontsize=17, fontweight="bold", va="center", zorder=8)

    def note(self, text, col=GREY, y=None, size=16):
        yl = self.ax.get_ylim()
        self.ax.text(-0.6, yl[0] if y is None else y, text, color=col, fontsize=size, va="bottom", zorder=6)


def figure():
    return plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)


def save(fig, name):
    path = OUT / f"{name}.png" if OUT else TIKTOK / STRATEGIE[name] / "plansza_zasady.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=BG)
    plt.close(fig)
    print("ok", name)


# ───────────────────────── 01 LuxAlgo S/R Breaks + MSTS ─────────────────────────
def luxalgo():
    n = 44
    cl = path([(0, 100), (6, 108.5), (11, 99), (15, 104), (18, 100), (21, 105), (22, 111.5), (26, 115),
               (28, 112.5), (32, 119), (34, 116.5), (37, 122), (40, 119), (42, 113), (43, 112)], n, 0.5)
    B = bars_from(cl, wick=0.7)
    SIG, PIV = 22, 6
    R = max(b[1] for b in B[:SIG])
    o, h, l, c = B[SIG]
    B[SIG] = (o, c + 0.5, o - 0.4, c)
    # Market Structure Trailing Stop (poglądowo): startuje z ostatniego dołka, przeskakuje na wyższe dołki
    ts = [None] * n
    stop = min(b[2] for b in B[15:SIG + 1])
    for i in range(SIG, n):
        if i >= 3 and B[i - 2][2] < B[i - 3][2] and B[i - 2][2] < B[i - 1][2] and B[i - 2][2] > stop:
            stop = B[i - 2][2]
        ts[i] = stop
    EXIT = next(i for i in range(SIG + 1, n) if B[i][3] < ts[i - 1])
    n = EXIT + 1
    lo, hi = ylim_of(B, n, pad=0.15)

    fig = figure()
    s = Seg(fig, 0, "1. OPÓR", "Wskaźnik S/R Breaks rysuje poziom\nna ostatnim szczycie", n, (lo, hi))
    s.candles(B, SIG)
    s.level(R, PIV, SIG + 1.5, FG, "opór")
    s.tag(PIV, B[PIV][1], "szczyt", GREY, False, size=16)

    s = Seg(fig, 1, "2. ZIELONE B = LONG", "Zamknięcie nad oporem przy wysokim wolumenie.\nShort: czerwone B przy wybiciu wsparcia",
            n, (lo, hi))
    s.candles(B, SIG + 1, {SIG: GREEN})
    s.level(R, PIV, SIG + 1.5, FG)
    s.ax.text(SIG, B[SIG][2] - s.dy * 1.0, "B", color=BG, fontsize=18, fontweight="bold", ha="center", va="top", zorder=8,
              bbox=dict(boxstyle="round,pad=0.25", fc=GREEN, ec=GREEN))
    s.entry(SIG, B[SIG][3], GREEN)

    s = Seg(fig, 2, "3. WYJŚCIE NA TRAILING STOPIE", "Linia Market Structure Trailing Stop idzie za ceną.\nZamknięcie pod nią = wyjście. Brak TP.",
            n, (lo, hi))
    s.candles(B, n, {SIG: GREEN, EXIT: RED})
    xs, ys = [], []
    for i in range(SIG, EXIT + 1):
        xs += [i - 0.5, i + 0.5]; ys += [ts[i - 1] if i > SIG else ts[SIG]] * 2
    s.ax.plot(xs, ys, color=RED, lw=3, zorder=5)
    s.ax.text(SIG + 1.5, ts[SIG] - s.dy * 0.6, "SL przy wejściu", color=RED, fontsize=16, fontweight="bold", va="top", zorder=7)
    s.ax.plot([SIG + 0.5], [B[SIG][3]], "o", ms=13, color=GREEN, mec=FG, mew=2, zorder=8)
    s.exit(EXIT + 0.5, B[EXIT][3], RED, "wyjście")
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "01_luxalgo_sr_breaks_msts")


# ───────────────────────── 02 Cloud MA EMA 30/74 ─────────────────────────
def cloud_ma():
    H, n = 120, 64
    N = H + n
    cl = path([(0, 130), (60, 122), (H, 108), (H + 14, 99), (H + 24, 106), (H + 34, 118), (H + 42, 121),
               (H + 52, 110), (H + 63, 100)], N, 0.9)
    Ball = bars_from(cl, wick=0.9)
    e30, e74 = ema(cl, 30), ema(cl, 74)
    B, e30, e74 = Ball[H:], e30[H:], e74[H:]
    up = next(i for i in range(1, n) if cross_up(e30, e74, i))
    dn = next(i for i in range(up + 1, n) if cross_dn(e30, e74, i))
    lows = [b[2] for b in B[:up + 1]]
    sw = lows.index(min(lows))
    SL = B[sw][2]
    lo, hi = ylim_of(B, n, pad=0.08)

    def cloud(s, upto):
        xs = list(range(upto))
        s.ax.fill_between(xs, e30[:upto], e74[:upto], where=[a >= b for a, b in zip(e30[:upto], e74[:upto])],
                          color=GREEN, alpha=0.16, lw=0, zorder=1, interpolate=True)
        s.ax.fill_between(xs, e30[:upto], e74[:upto], where=[a < b for a, b in zip(e30[:upto], e74[:upto])],
                          color=RED, alpha=0.16, lw=0, zorder=1, interpolate=True)
        s.line(e30, upto, FG, lw=2.6, label="EMA 30" if upto == n else None)
        s.line(e74, upto, BLUE, lw=2.6, label="EMA 74" if upto == n else None)

    fig = figure()
    s = Seg(fig, 0, "1. CHMURA EMA 30 / 74", "EMA 30 pod EMA 74 = czerwona chmura.\nSL = najniższy dołek od poprzedniego sygnału", n, (lo, hi))
    s.candles(B, up)
    cloud(s, up)
    s.ax.text(up + 0.3, e30[up - 1] - s.dy * 0.5, "EMA 30", color=FG, fontsize=16, fontweight="bold", ha="left", va="top")
    s.ax.text(up + 0.3, e74[up - 1] + s.dy * 0.5, "EMA 74", color=BLUE, fontsize=16, fontweight="bold", ha="left", va="bottom")
    s.level(SL, sw, up + 1, YELLOW, "najniższy dołek", ls="-", lw=2.2)

    s = Seg(fig, 1, "2. PRZECIĘCIE W GÓRĘ = LONG", "Zielony trójkąt: EMA 30 przecina EMA 74.\nShort: czerwony trójkąt, przecięcie w dół", n, (lo, hi))
    s.candles(B, up + 1, {up: GREEN})
    cloud(s, up + 1)
    s.signal_tri(up, e30[up], TV_GREEN, True)
    s.entry(up, B[up][3], GREEN)
    s.level(SL, sw, up + 1, YELLOW, ls="-", lw=2.2)

    s = Seg(fig, 2, "3. SL NA DOŁKU, ODWRÓCENIE", "SL na najniższym dołku. Brak TP.\nPrzeciwny trójkąt zamyka longa i otwiera shorta", n, (lo, hi))
    s.candles(B, n, {up: GREEN, dn: RED})
    cloud(s, n)
    s.signal_tri(up, e30[up], TV_GREEN, True)
    s.signal_tri(dn, e30[dn], TV_RED, False)
    s.ax.plot([up + 0.5], [B[up][3]], "o", ms=13, color=GREEN, mec=FG, mew=2, zorder=8)
    s.level(SL, sw, dn, RED, None, ls="-", lw=2.6)
    s.tag(sw + 4, SL, "SL", RED, True)
    s.ax.text(dn - 1.2, B[dn][2] - s.dy * 1.5, "zamknij long\n+ short", color=RED, fontsize=16, fontweight="bold",
              ha="right", va="top", zorder=8)
    save(fig, "02_cloud_ma_ema30_74")


# ───────────────────────── 03 SFP + Volume ─────────────────────────
def sfp():
    n = 38
    cl = path([(0, 101), (9, 110), (11, 109), (16, 102.5), (21, 107.5), (22, 108)] + [(23, 106.5), (27, 101),
               (29, 102.5), (33, 95), (35, 93), (37, 94)], n, 0.45)
    SIG, PIV = 23, 10
    over = {PIV: (109.4, 111.2, 108.8, 110.4), SIG: (108, 113.2, 106.2, 106.6)}
    B = bars_from(cl, wick=0.6, over=over)
    SH = B[PIV][1]
    entry = B[SIG][3]
    sl = B[SIG][1]
    tp = entry - 2 * (sl - entry)
    EXIT = next(i for i in range(SIG + 1, n) if B[i][2] <= tp)
    B[EXIT] = (B[EXIT][0], B[EXIT][1], tp - 0.6, min(B[EXIT][3], tp + 0.3))
    n = EXIT + 1
    # Volume Delta: znak = przewaga kupna/sprzedaży, udział = |delta| / wolumen (0–1).
    # Zwykle zgodny z kierunkiem świecy, ale nie zawsze (świece 6, 15, 19).
    sign = [(1 if b[3] >= b[0] else -1) * (-1 if i in (6, 15, 19) else 1) for i, b in enumerate(B)]
    share = [0.15 + 0.55 * abs(sin(i * 1.9)) for i in range(len(B))]
    sign[SIG], share[SIG] = -1, 0.9
    # mniej świec na planszy = szersze korpusy i czytelniejsze wypełnienie
    K = 4   # zostaje 5 świec przed szczytem (definicja pivota: 5 przed, 1 po)
    B, sign, share = B[K:], sign[K:], share[K:]
    SIG, PIV, EXIT, n = SIG - K, PIV - K, EXIT - K, n - K
    lo, hi = ylim_of(B, n, pad=0.1)

    def vcandles(s, upto, hl=()):
        """Świece jak Volume Delta Candles: pusty korpus z ramką w kolorze ceny,
        w środku pasek |delta|/wolumen: zielony od dołu (kupno), czerwony od góry (sprzedaż)."""
        for i in range(upto):
            o, h, l, c = B[i]
            a = 1.0 if (i in hl or not hl) else 0.45
            pc = GREEN if c >= o else RED
            lw = 2.6 if i in hl else 1.8
            lo_b, hi_b = min(o, c), max(o, c)
            body = max(hi_b - lo_b, s.dy * 0.15)
            s.ax.plot([i, i], [l, lo_b], color=pc, lw=lw, alpha=a, zorder=3, solid_capstyle="round")
            s.ax.plot([i, i], [lo_b + body, h], color=pc, lw=lw, alpha=a, zorder=3, solid_capstyle="round")
            s.ax.add_patch(Rectangle((i - 0.38, lo_b), 0.76, body, facecolor=BG, edgecolor=pc, lw=lw, alpha=a, zorder=4))
            fc = GREEN if sign[i] > 0 else RED
            fh = share[i] * body
            y0 = lo_b if sign[i] > 0 else lo_b + body - fh
            s.ax.add_patch(Rectangle((i - 0.38, y0), 0.76, fh, facecolor=fc, edgecolor="none", alpha=a, zorder=5))

    fig = figure()
    s = Seg(fig, 0, "1. ŚWIECE WOLUMENOWE", "Kolor wypełnienia = przewaga kupna lub sprzedaży,\nwysokość wypełnienia = siła tej przewagi",
            n, (lo, hi))
    vcandles(s, SIG)
    s.level(SH, PIV, SIG + 1.5, FG, "swing high")
    s.ax.text(SIG + 1.9, SH - s.dy * 0.9, "szczyt: 5 świec przed nim\ni 1 świeca po nim niżej",
              color=GREY, fontsize=15, va="top", linespacing=1.4, zorder=6)

    s = Seg(fig, 1, "2. SFP + PRZEWAGA SPRZEDAŻY", "Knot nad szczytem, zamknięcie pod nim (SFP)\ni przewaga sprzedaży = short. Long lustrzanie.",
            n, (lo, hi))
    vcandles(s, SIG + 1, (SIG,))
    s.level(SH, PIV, SIG + 1.5, FG)
    s.tag(SIG, B[SIG][1], "SFP", RED, False, off=0.4)
    s.entry(SIG, entry, RED, "short")

    s = Seg(fig, 2, "3. SL NA HIGH, TP 2:1", "Wyjście tylko na SL albo TP.\nNowe sygnały w trakcie pozycji są ignorowane.",
            n, (lo, hi))
    vcandles(s, n, (SIG,))
    s.ax.add_patch(Rectangle((SIG + 0.5, entry), EXIT - SIG, sl - entry, facecolor=RED, alpha=0.14, lw=0, zorder=1))
    s.ax.add_patch(Rectangle((SIG + 0.5, tp), EXIT - SIG, entry - tp, facecolor=GREEN, alpha=0.14, lw=0, zorder=1))
    s.level(sl, SIG - 0.5, EXIT + 0.5, RED, "SL", ls="-")
    s.level(entry, SIG + 0.5, EXIT + 0.5, FG, "wejście", ls=(0, (2, 3)), lw=2)
    s.level(tp, SIG - 0.5, EXIT + 0.5, GREEN, "TP 2:1", ls="-")
    s.ax.plot([SIG + 0.5], [entry], "o", ms=13, color=RED, mec=FG, mew=2, zorder=8)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "03_sfp_volume")


# ───────────────────────── 04 EMA 9 × VWAP ─────────────────────────
def ema9_vwap():
    H, n = 6, 42
    N = H + n
    cl = path([(0, 101), (H, 101), (H + 12, 110), (H + 18, 109), (H + 30, 97), (H + 30, 96), (H + 36, 108), (H + 41, 110)], N, 0.5)
    Ball = bars_from(cl, wick=0.6)
    e9 = ema(cl, 9)[H:]
    B = Ball[H:]
    vol = [1.0 + 0.4 * abs(sin(i * 1.3)) for i in range(n)]
    num = den = 0.0
    vw = []
    for b, v in zip(B, vol):
        num += (b[1] + b[2] + b[3]) / 3 * v; den += v
        vw.append(num / den)
    dn = next(i for i in range(2, n) if cross_dn(e9, vw, i))
    up = next(i for i in range(dn + 1, n) if cross_up(e9, vw, i))
    n = up + 1
    lo, hi = ylim_of(B, n, pad=0.1)

    def lines(s, upto, lab=False):
        s.line(e9, upto, FG, lw=2.6, label="EMA 9" if lab else None)
        s.line(vw, upto, YELLOW, lw=2.6, label="VWAP" if lab else None)

    fig = figure()
    s = Seg(fig, 0, "1. EMA 9 I VWAP", "", n, (lo, hi))
    s.candles(B, dn)
    lines(s, dn)
    s.ax.text(dn - 0.5, e9[dn - 1] + s.dy * 0.6, "EMA 9", color=FG, fontsize=16, fontweight="bold", va="bottom")
    s.ax.text(dn - 0.5, vw[dn - 1] - s.dy * 0.6, "VWAP", color=YELLOW, fontsize=16, fontweight="bold", va="top")

    s = Seg(fig, 1, "2. EMA 9 POD VWAP = SHORT", "EMA 9 przecina VWAP od góry.\nLongów w tej strategii nie ma.", n, (lo, hi))
    s.candles(B, dn + 1, {dn: RED})
    lines(s, dn + 1)
    s.entry(dn, B[dn][3], RED, "short")

    s = Seg(fig, 2, "3. EMA 9 NAD VWAP = WYJŚCIE", "Brak SL i TP.\nPozycja = 100% kapitału.", n, (lo, hi))
    s.candles(B, n, {dn: RED, up: GREEN})
    lines(s, n)
    s.ax.text(n - 0.4, e9[n - 1] + s.dy * 0.5, "EMA 9", color=FG, fontsize=16, fontweight="bold", va="bottom")
    s.ax.text(n - 0.4, vw[n - 1] - s.dy * 0.5, "VWAP", color=YELLOW, fontsize=16, fontweight="bold", va="top")
    s.ax.plot([dn + 0.5], [B[dn][3]], "o", ms=13, color=RED, mec=FG, mew=2, zorder=8)
    s.exit(up + 0.5, B[up][3], FG, "wyjście")
    save(fig, "04_ema9_vwap")


# ───────────────────────── 05 EMA9 ─────────────────────────
def ema9():
    H, n = 10, 38
    N = H + n
    cl = path([(0, 110), (H, 108), (H + 12, 99), (H + 14, 99.5), (H + 26, 109), (H + 28, 108.5), (H + 37, 101)], N, 0.6)
    Ball = bars_from(cl, wick=0.6)
    e = ema(cl, 9)
    B, e = Ball[H:], e[H:]
    c = [b[3] for b in B]
    up = next(i for i in range(1, n) if cross_up(c, e, i))
    dn = next(i for i in range(up + 1, n) if cross_dn(c, e, i))
    lo, hi = ylim_of(B, n, pad=0.1)

    fig = figure()
    s = Seg(fig, 0, "1. EMA 9", "Cena pod średnią = przewaga sprzedających.\nClaim: „Never trade against 9 EMA”", n, (lo, hi))
    s.candles(B, up)
    s.line(e, up, YELLOW, lw=2.8, label="EMA 9")

    s = Seg(fig, 1, "2. ZAMKNIĘCIE NAD EMA 9 = LONG", "Zamknięcie świecy przebija EMA 9 w górę.\nShort: przebicie w dół.", n, (lo, hi))
    s.candles(B, up + 1, {up: GREEN})
    s.line(e, up + 1, YELLOW, lw=2.8)
    s.entry(up, c[up], GREEN, "long")

    s = Seg(fig, 2, "3. PRZEBICIE W DÓŁ = ODWRÓCENIE", "Long zamknięty, od razu short.\nBrak SL i TP, pozycja = 100% kapitału.", n, (lo, hi))
    s.candles(B, n, {up: GREEN, dn: RED})
    s.line(e, n, YELLOW, lw=2.8, label="EMA 9")
    s.ax.plot([up + 0.5], [c[up]], "o", ms=13, color=GREEN, mec=FG, mew=2, zorder=8)
    s.ax.plot([dn + 0.5], [c[dn]], "o", ms=13, color=RED, mec=FG, mew=2, zorder=8)
    s.ax.text(dn + 1.4, B[dn][1] + s.dy * 0.5, "zamknij long\n+ short", color=RED, fontsize=16, fontweight="bold",
              ha="left", va="bottom", zorder=8)
    save(fig, "05_ema9")


# ───────────────────────── 06 RSI 6 (80/20) ─────────────────────────
def rsi6():
    H, n = 8, 34
    N = H + n
    cl = path([(0, 110), (H, 110), (H + 4, 109), (H + 11, 100), (H + 12, 99.6), (H + 13, 101.3), (H + 20, 106),
               (H + 22, 105), (H + 30, 110), (H + 33, 111)], N, 0.35)
    Ball = bars_from(cl, wick=0.45)
    r = rsi(cl, 6)[H:]
    B = Ball[H:]
    SIG = next(i for i in range(H and 1, n) if r[i] > 20 and r[i - 1] <= 20)
    o, h, l, c = B[SIG]
    B[SIG] = (o, h, min(l, o - 0.9), c)
    entry, sl = c, B[SIG][2]
    tp = entry + 2 * (entry - sl)
    EXIT = next(i for i in range(SIG + 1, n) if B[i][1] >= tp)
    B[EXIT] = (B[EXIT][0], tp + 0.4, B[EXIT][2], max(B[EXIT][3], tp - 0.2))
    n = EXIT + 1
    lo, hi = ylim_of(B, n, pad=0.12)
    sub = (-5, 110)

    def rpanel(s, upto, hl=False):
        for lv, col in ((80, RED), (20, GREEN)):
            s.level(lv, -0.8, n - 0.5, col, None, ls=(0, (4, 4)), lw=1.6, ax=s.sx)
            s.sx.text(n + 0.3, lv, str(lv), color=col, fontsize=16, fontweight="bold", va="center")
        s.line(r, upto, BLUE, lw=2.8, ax=s.sx)
        if hl:
            s.sx.plot([SIG], [r[SIG]], "o", ms=12, color=GREEN, mec=FG, mew=2, zorder=8)

    fig = figure()
    s = Seg(fig, 0, "1. RSI 6 SPADA POD 20", "Krótki RSI (6) szybko wchodzi\nw strefę wyprzedania", n, (lo, hi), sub, "RSI 6")
    s.candles(B, SIG)
    rpanel(s, SIG)
    s.sx.add_patch(Rectangle((-0.8, sub[0]), n + 0.3, 20 - sub[0], facecolor=GREEN, alpha=0.08, lw=0, zorder=1))

    s = Seg(fig, 1, "2. POWRÓT NAD 20 = LONG", "RSI 6 przecina 20 w górę.\nShort: RSI 6 przecina 80 w dół.", n, (lo, hi), sub, "RSI 6")
    s.candles(B, SIG + 1, {SIG: GREEN})
    rpanel(s, SIG + 1, True)
    s.entry(SIG, entry, GREEN, "long")

    s = Seg(fig, 2, "3. SL NA LOW ŚWIECY, TP 2:1", "Przeciwny sygnał odwraca pozycję,\nsygnał w tę samą stronę przestawia SL i TP.",
            n, (lo, hi), sub, "RSI 6")
    s.candles(B, n, {SIG: GREEN})
    s.ax.add_patch(Rectangle((SIG + 0.5, sl), EXIT - SIG, entry - sl, facecolor=RED, alpha=0.14, lw=0, zorder=1))
    s.ax.add_patch(Rectangle((SIG + 0.5, entry), EXIT - SIG, tp - entry, facecolor=GREEN, alpha=0.14, lw=0, zorder=1))
    s.level(tp, SIG - 0.5, EXIT + 0.5, GREEN, "TP 2:1", ls="-")
    s.level(entry, SIG + 0.5, EXIT + 0.5, FG, "wejście", ls=(0, (2, 3)), lw=2)
    s.level(sl, SIG - 0.5, EXIT + 0.5, RED, "SL", ls="-")
    s.ax.plot([SIG + 0.5], [entry], "o", ms=13, color=GREEN, mec=FG, mew=2, zorder=8)
    rpanel(s, n, True)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "06_rsi6_80_20")


# ───────────────────────── 07 BigBeluga Two-Pole + Stochastic 7,3,3 ─────────────────────────
def bigbeluga():
    H, n = 70, 36
    N = H + n
    cl = path([(0, 101), (H - 12, 101), (H, 103), (H + 14, 112), (H + 19, 108.4), (H + 21, 107.7), (H + 22, 107.9), (H + 24, 110.5),
               (H + 30, 118), (H + 35, 119)], N, 0.55)
    Ball = bars_from(cl, wick=0.55)
    tpf = two_pole(cl)[H:]
    k, d = stoch(Ball)
    SIG = next(i for i in range(10, n) if cross_up(k[H:], d[H:], i) and k[H + i] < 20 and tpf[i] > tpf[i - 2])
    o, h, l, c = Ball[H + SIG]
    Ball[H + SIG] = (o, h, min(l, c - 1.4), c)          # wyraźniejszy knot = czytelny SL
    k, d = stoch(Ball)
    assert cross_up(k[H:], d[H:], SIG) and k[H + SIG] < 20
    B, k, d = Ball[H:], k[H:], d[H:]
    entry, sl = B[SIG][3], B[SIG][2]
    tp = entry + 2 * (entry - sl)
    EXIT = next(i for i in range(SIG + 1, n) if B[i][1] >= tp)
    B[EXIT] = (B[EXIT][0], tp + 0.4, B[EXIT][2], max(B[EXIT][3], tp - 0.3))
    n = EXIT + 1
    lo, hi = ylim_of(B, n, extra=tpf[:n], pad=0.1)
    sub = (-8, 118)

    def spanel(s, upto, hl=False):
        for lv in (80, 20):
            s.level(lv, -0.8, n - 0.5, GREY, None, ls=(0, (4, 4)), lw=1.4, ax=s.sx)
            s.sx.text(n + 0.3, lv, str(lv), color=GREY, fontsize=16, va="center")
        s.line(k, upto, BLUE, lw=2.6, ax=s.sx)
        s.line(d, upto, YELLOW, lw=2.2, ax=s.sx)
        s.sx.text(0.31, 0.985, "%K", color=BLUE, fontsize=16, fontweight="bold", va="top", zorder=6, transform=s.sx.transAxes)
        s.sx.text(0.385, 0.985, "%D", color=YELLOW, fontsize=16, fontweight="bold", va="top", zorder=6, transform=s.sx.transAxes)
        if hl:
            s.sx.plot([SIG], [k[SIG]], "o", ms=12, color=GREEN, mec=FG, mew=2, zorder=8)

    fig = figure()
    s = Seg(fig, 0, "1. FILTR TRENDU ROŚNIE", "Two-Pole Trend Filter (34) wyżej niż\n2 świece temu: szukamy tylko longów",
            n, (lo, hi), sub, "Stochastic 7,3,3")
    s.candles(B, SIG)
    s.line(tpf, SIG, GREEN, lw=3.2)
    s.ax.text(SIG - 0.5, tpf[SIG - 1] - s.dy * 0.8, "Two-Pole", color=GREEN, fontsize=16, fontweight="bold", va="top")
    spanel(s, SIG)

    s = Seg(fig, 1, "2. %K PRZECINA %D POD 20 = LONG", "Short odwrotnie: filtr spada,\n%K przecina %D w dół nad 80.",
            n, (lo, hi), sub, "Stochastic 7,3,3")
    s.candles(B, SIG + 1, {SIG: GREEN})
    s.line(tpf, SIG + 1, GREEN, lw=3.2)
    spanel(s, SIG + 1, True)
    s.entry(SIG, entry, GREEN, "long")

    s = Seg(fig, 2, "3. SL NA LOW ŚWIECY, TP 2:1", "Przy otwartej pozycji\nnowe sygnały są ignorowane.",
            n, (lo, hi), sub, "Stochastic 7,3,3")
    s.candles(B, n, {SIG: GREEN})
    s.line(tpf, n, GREEN, lw=3.2)
    s.ax.add_patch(Rectangle((SIG + 0.5, sl), EXIT - SIG, entry - sl, facecolor=RED, alpha=0.14, lw=0, zorder=1))
    s.ax.add_patch(Rectangle((SIG + 0.5, entry), EXIT - SIG, tp - entry, facecolor=GREEN, alpha=0.14, lw=0, zorder=1))
    s.level(tp, SIG - 0.5, EXIT + 0.5, GREEN, "TP", ls="-")
    s.level(sl, SIG - 0.5, EXIT + 0.5, RED, "SL", ls="-")
    s.ax.plot([SIG + 0.5], [entry], "o", ms=13, color=GREEN, mec=FG, mew=2, zorder=8)
    spanel(s, n, True)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "07_bigbeluga_two_pole_stoch")


# ───────────────────────── 08 SR Retest ─────────────────────────
def sr_retest():
    # Jak na kadrze z filmu: rajd, konsolidacja z kilkoma knotami na jednym poziomie,
    # zamknięcie nad oporem, następna świeca wraca knotem do linii = long.
    B = [(103.4, 104.6, 103.1, 104.3), (104.3, 105.7, 104.0, 105.4),
         (105.4, 107.3, 105.1, 107.0), (107.0, 109.0, 106.6, 108.4), (108.4, 109.9, 107.5, 109.3),   # 4: dotknięcie
         (109.3, 109.6, 107.2, 107.6), (107.6, 108.6, 106.9, 108.1), (108.1, 110.0, 107.7, 108.0),   # 7: dotknięcie
         (108.0, 108.5, 106.5, 106.8), (106.8, 108.2, 106.4, 107.9), (107.9, 109.95, 107.4, 108.3),  # 10: dotknięcie
         (108.3, 108.6, 107.6, 107.9), (107.9, 111.6, 107.7, 111.3),                                   # 12: wybicie
         (111.3, 111.7, 110.0, 111.1)]                                                                 # 13: retest
    TOUCH, BRK, RT = (4, 7, 10), 12, 13
    R = 110.0
    entry, sl = B[RT][3], B[RT][2] - 0.2
    tp = entry + 2 * (entry - sl)
    for c in (112.3, 113.0, 114.2, 115.1, 116.6):
        o = B[-1][3]
        B.append((o, max(o, c) + 0.3, min(o, c) - 0.35, c))
    EXIT = next(i for i in range(RT + 1, len(B)) if B[i][1] >= tp)
    B[EXIT] = (B[EXIT][0], tp + 0.4, B[EXIT][2], max(B[EXIT][3], tp - 0.3))
    n = EXIT + 1
    lo, hi = ylim_of(B, n, pad=0.12)

    fig = figure()
    s = Seg(fig, 0, "1. OPÓR Z KNOTÓW",
            "Min. 2 knoty w ostatnich 20 świecach na tym samym\npoziomie (do 0,25 ATR), z odbiciem pomiędzy", n, (lo, hi))
    s.candles(B, BRK)
    s.level(R, TOUCH[0] - 0.5, BRK + 1, FG, "opór")
    for p in TOUCH:
        s.ax.plot([p], [B[p][1] + s.dy * 0.8], "o", ms=9, color=FG, zorder=7)

    s = Seg(fig, 1, "2. WYBICIE I RETEST = LONG", "Zamknięcie nad oporem, knot wraca do poziomu\nw ciągu 5 świec. Short lustrzanie.", n, (lo, hi))
    s.candles(B, RT + 1, {BRK: FG, RT: GREEN})
    s.level(R, TOUCH[0] - 0.5, RT + 2, FG)
    s.tag(BRK, B[BRK][1], "wybicie", FG, False, size=16, off=0.6)
    s.ax.text(RT + 0.7, B[RT][2] - s.dy * 0.3, "retest", color=GREEN, fontsize=16, fontweight="bold", va="top", zorder=8)
    s.ax.plot([RT + 0.5], [entry], "o", ms=13, color=GREEN, mec=FG, mew=2, zorder=8)
    s.ax.text(RT + 1.2, entry + s.dy * 0.9, "long", color=GREEN, fontsize=17, fontweight="bold", va="bottom", zorder=8)

    s = Seg(fig, 2, "3. SL I TP: NASZE ZAŁOŻENIE", "Autor nie podał wyjścia.\nSL za świecą retestu, TP 2:1.", n, (lo, hi))
    s.candles(B, n, {BRK: FG, RT: GREEN})
    s.level(R, TOUCH[0] - 0.5, RT, FG, ls=(0, (6, 4)), lw=1.6)
    s.ax.add_patch(Rectangle((RT + 0.5, sl), EXIT - RT, entry - sl, facecolor=RED, alpha=0.14, lw=0, zorder=1))
    s.ax.add_patch(Rectangle((RT + 0.5, entry), EXIT - RT, tp - entry, facecolor=GREEN, alpha=0.14, lw=0, zorder=1))
    s.level(tp, RT - 0.5, EXIT + 0.5, GREEN, "TP", ls="-")
    s.level(sl, RT - 0.5, EXIT + 0.5, RED, "SL", ls="-")
    s.ax.plot([RT + 0.5], [entry], "o", ms=13, color=GREEN, mec=FG, mew=2, zorder=8)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "08_sr_retest")


# ───────────────────────── 09 SSL + IFVG ─────────────────────────
def ssl_ifvg():
    n = 38
    cl = path([(0, 106), (5, 100.6), (8, 106), (10, 106.8), (11, 105.6), (12, 102.4), (13, 101.4), (15, 100.9),
               (16, 101.5), (18, 102.6), (19, 103), (20, 106.0), (24, 108), (26, 107.4), (33, 113.5), (37, 114)], n, 0.3)
    PIV, SWP, ENT = 5, 15, 20
    over = {PIV: (101.6, 101.9, 100.0, 100.7),
            10: (106.6, 107.3, 105.9, 106.0), 11: (106.0, 106.2, 102.9, 103.2), 12: (103.2, 103.6, 101.6, 102.0),
            SWP: (100.8, 101.9, 98.6, 101.5), ENT: (103.0, 106.6, 102.8, 106.3)}
    B = bars_from(cl, wick=0.4, over=over)
    PL = B[PIV][2]
    g_top, g_bot = B[10][2], B[12][1]  # spadkowy FVG: high[12] < low[10]
    entry, sl = B[ENT][3], g_bot - 0.2
    tp = entry + 2 * (entry - sl)
    EXIT = next(i for i in range(ENT + 1, n) if B[i][1] >= tp)
    B[EXIT] = (B[EXIT][0], tp + 0.4, B[EXIT][2], max(B[EXIT][3], tp - 0.3))
    n = EXIT + 1
    lo, hi = ylim_of(B, n, pad=0.12)

    def gap(s, x2, col=RED, a=0.22):
        s.ax.add_patch(Rectangle((10.5, g_bot), x2 - 10.5, g_top - g_bot, facecolor=col, alpha=a, edgecolor=col, lw=1.2, zorder=1))

    fig = figure()
    s = Seg(fig, 0, "1. SWEEP DOŁKA (SSL)", "Cena wybija dołek i wraca nad niego.\nPrzez 30 świec szukamy tylko longów.", n, (lo, hi))
    s.candles(B, SWP + 1, {SWP: GREEN})
    s.level(PL, PIV - 0.5, SWP + 1.5, FG, "dołek")
    s.tag(SWP, B[SWP][2], "sweep", GREEN, True, size=16)

    s = Seg(fig, 1, "2. ZAMKNIĘCIE NAD LUKĄ = LONG", "Spadkowy FVG zostaje odwrócony (IFVG).\nShort lustrzanie po sweepie szczytu.", n, (lo, hi))
    s.candles(B, ENT + 1, {SWP: GREEN, ENT: GREEN})
    s.level(PL, PIV - 0.5, SWP + 1.5, DIM)
    gap(s, ENT + 0.5)
    s.ax.text((10.5 + ENT) / 2 + 1.2, (g_top + g_bot) / 2, "spadkowy FVG", color=RED, fontsize=16, fontweight="bold",
              ha="center", va="center", zorder=8)
    s.entry(ENT, entry, GREEN, "long")

    s = Seg(fig, 2, "3. SL POD LUKĄ, TP 2:1", "SL pod dolną krawędzią luki.\nTP = 2 × ryzyko od zamknięcia.", n, (lo, hi))
    s.candles(B, n, {SWP: GREEN, ENT: GREEN})
    gap(s, ENT + 0.5, GREY, 0.12)
    s.ax.add_patch(Rectangle((ENT + 0.5, sl), EXIT - ENT, entry - sl, facecolor=RED, alpha=0.14, lw=0, zorder=1))
    s.ax.add_patch(Rectangle((ENT + 0.5, entry), EXIT - ENT, tp - entry, facecolor=GREEN, alpha=0.14, lw=0, zorder=1))
    s.level(tp, ENT - 0.5, EXIT + 0.5, GREEN, "TP", ls="-")
    s.level(sl, 10.5, EXIT + 0.5, RED, "SL", ls="-")
    s.ax.plot([ENT + 0.5], [entry], "o", ms=13, color=GREEN, mec=FG, mew=2, zorder=8)
    s.note("1% kapitału ryzyka do SL", y=lo)
    save(fig, "09_ssl_ifvg")


ALL = [luxalgo, cloud_ma, sfp, ema9_vwap, ema9, rsi6, bigbeluga, sr_retest, ssl_ifvg]

if __name__ == "__main__":
    if OUT:
        OUT.mkdir(parents=True, exist_ok=True)
    for fn in ALL:
        fn()
