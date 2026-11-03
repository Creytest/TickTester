"""
Strong Pressure Signals (ProjectSyndicate, TradingView Community Scripts):
https://pl.tradingview.com/script/E0ietNMM-Strong-Pressure-Signals-ProjectSyndicate/

Port wskaźnika z ustawieniami domyślnymi. Przy nich wszystkie bramki
(klastry, sesje, RSI, gwiazdki, knot) są wyłączone, więc o wejściu
decyduje tylko "burst" poza EMA 20 ± 2 × ATR 14:

1. Burst w górę: high świecy powyżej górnej bandy. Wielkość = ile ATR
   ponad bandą.
2. Sygnał na zamknięciu świecy, gdy poprzednia świeca miała szczyt
   burstu (nie mniejszy niż przed nią), a obecna jest mniejsza.
   Szczyt co najmniej 1 ATR poza bandą (stack 3 przy kroku 0,5 ATR).
3. Burst w górę → SHORT, w dół → LONG. Wejście po zamknięciu świecy.
4. SL: 0,3 ATR za skrajnym punktem burstu (ta i poprzednia świeca),
   odległość ograniczona do 0,5–3 ATR.
5. TP1/TP2/TP3 ("Pressure Ladder"): najbliższe klastry z pivotów 12/4
   w kierunku zysku, co najmniej 0,6 odległości SL od wejścia; brak
   klastra → 1×, 2×, 3× odległość SL.
6. Jedna transakcja naraz, 20 świec odstępu między sygnałami,
   time stop po 200 świecach.

Wyjścia: autor rysuje trzy TP, ale nie podaje, ile pozycji zamykać na
każdym. Domyślnie po 1/3 na TP1, TP2, TP3, reszta na SL (TP_SPLIT).
Dashboard autora liczy co innego: transakcję, która dotknęła TP1 i
wróciła na SL, księguje jako wygraną +TP1 z CAŁEJ pozycji.

Klastry liczymy na całej historii (w TV tylko na ostatnich 3000
świecach wykresu — to limit wydajności, nie reguła strategii).
"""

import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema
from strategies.tiktok.LuxAlgo_SR_Breaks_MSTS import pivot_high, pivot_low
from strategies.tiktok.SR_Retest import atr as atr_rma


NAME = "Strong Pressure Signals"

# Autor: XAUUSD, interwały intraday (pasek MTF domyślnie 15 i 60 min).
TIMEFRAMES = ["15min", "1h", "4h"]

# Jedna transakcja naraz: sygnał przy otwartej pozycji jest pomijany.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Części pozycji zamykane na TP1, TP2, TP3.
TP_SPLIT = (1 / 3, 1 / 3, 1 / 3)

# 01 · Burst Engine
BASIS_LEN = 20
ATR_LEN = 14
BAND_MULT = 2.0
STEP_ATR = 0.5
MAX_LEVELS = 6
# 04 · Signal Filter
FADE_MIN = 3
COOLDOWN = 20
# 05 · Trade Levels
SL_BUF = 0.30
MAX_RISK = 3.0
MIN_RISK = 0.5
LADDER_MIN_R = 0.6
TP_R = (1.0, 2.0, 3.0)
MAX_HUNT = 200
# 02 · Pressure Clusters
LEFT_BARS = 12
RIGHT_BARS = 4
MAX_ZONES = 30
MAX_LIFE = 400
OVERLAP_THR = 35
CL_ATR_LEN = 200
BAND_ATR = 0.5
MIN_DEPTH = 0.15
RECLAIM_WIN = 6
BREAK_ATR = 0.9


# ============================================================
# Klastry ("Pressure Clusters") — tylko to, co wpływa na TP
# ============================================================

class _Zone:
    __slots__ = ("dir", "top", "bot", "mid", "born", "phase", "sw_bar", "dead")

    def __init__(self, side, top, bot, mid, born):
        self.dir, self.top, self.bot, self.mid, self.born = side, top, bot, mid, born
        self.phase, self.sw_bar, self.dead = 0, -1, False


def _overlap(t1, b1, t2, b2):
    ov = min(t1, t2) - max(b1, b2)
    min_h = min(t1 - b1, t2 - b2)
    return ov > 0 and min_h > 0 and ov / min_h >= OVERLAP_THR / 100.0


def _cluster_atr(bars):
    """atrRaw: ATR 200, a przed jego startem średni zakres świecy."""
    a = atr_rma(bars, CL_ATR_LEN)
    rng = (bars["high"] - bars["low"]).to_numpy(dtype=float)
    fallback = np.cumsum(rng) / np.arange(1, len(rng) + 1)
    return np.where(np.isnan(a), fallback, a)


# ============================================================
# Sygnały
# ============================================================

def _simulate(bars: pd.DataFrame) -> dict:
    """Kod wskaźnika świeca po świecy, w kolejności z Pine."""
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    n = len(bars)

    basis = ema(bars["close"], BASIS_LEN).to_numpy(dtype=float)
    atr = atr_rma(bars, ATR_LEN)
    upper = basis + BAND_MULT * atr
    lower = basis - BAND_MULT * atr
    with np.errstate(invalid="ignore", divide="ignore"):
        up_m0 = np.where(high - upper > 0, (high - upper) / atr, 0.0)
        dn_m0 = np.where(lower - low > 0, (lower - low) / atr, 0.0)
    up_m0 = np.nan_to_num(up_m0)
    dn_m0 = np.nan_to_num(dn_m0)

    atr_raw = _cluster_atr(bars)
    ph = pivot_high(bars["high"], LEFT_BARS, RIGHT_BARS).to_numpy(dtype=float)
    pl = pivot_low(bars["low"], LEFT_BARS, RIGHT_BARS).to_numpy(dtype=float)

    out = {
        "basis": basis, "upper": upper, "lower": lower,
        "dir": np.zeros(n, dtype=int),
        "stop": np.full(n, np.nan),
        "tp": np.full((n, 3), np.nan),
        "time_exit": np.zeros(n, dtype=bool),
    }

    zones: list[_Zone] = []
    last_sig = None
    active, side, t_bar = False, 0, -1
    t_stop = np.nan
    t_tp = [np.nan] * 3
    best = 0

    for i in range(n):
        band_h = atr_raw[i] * BAND_ATR

        # ---- klastry: nowe z pivotów (wsparcie, potem opór)
        for zside, lvl in ((1, pl[i]), (-1, ph[i])):
            if np.isnan(lvl):
                continue
            t, b = lvl + band_h / 2, lvl - band_h / 2
            if any(not z.dead and z.phase != 1 and _overlap(t, b, z.top, z.bot) for z in zones):
                continue
            zones.append(_Zone(zside, t, b, lvl, i - RIGHT_BARS))
        while len(zones) > MAX_ZONES:
            zones.pop(0)

        # ---- klastry: dotknięcie / sweep / reclaim / przełamanie
        for z in zones:
            if i - z.born >= MAX_LIFE:
                z.dead = True
                continue
            if z.dir == 1:
                if z.phase == 0:
                    if not (low[i] <= z.top and low[i] >= z.bot and close[i] > z.bot) \
                            and low[i] < z.bot - MIN_DEPTH * atr_raw[i]:
                        z.phase, z.sw_bar = 1, i
                elif z.phase == 1:
                    accepted = close[i] < z.bot - BREAK_ATR * atr_raw[i] or \
                        (i - z.sw_bar >= RECLAIM_WIN and close[i] < z.bot)
                    if close[i] > z.bot:
                        z.phase = 0
                    elif accepted:
                        z.dir, z.phase = -1, 0
            else:
                if z.phase == 0:
                    if not (high[i] >= z.bot and high[i] <= z.top and close[i] < z.top) \
                            and high[i] > z.top + MIN_DEPTH * atr_raw[i]:
                        z.phase, z.sw_bar = 1, i
                elif z.phase == 1:
                    accepted = close[i] > z.top + BREAK_ATR * atr_raw[i] or \
                        (i - z.sw_bar >= RECLAIM_WIN and close[i] > z.top)
                    if close[i] < z.top:
                        z.phase = 0
                    elif accepted:
                        z.dir, z.phase = 1, 0
        zones = [z for z in zones if not z.dead]

        if i < 2:
            continue

        # ---- burst i jego szczyt
        up_peak = up_m0[i - 1] > 0 and up_m0[i - 1] >= up_m0[i - 2] and up_m0[i - 1] > up_m0[i]
        dn_peak = dn_m0[i - 1] > 0 and dn_m0[i - 1] >= dn_m0[i - 2] and dn_m0[i - 1] > dn_m0[i]
        up_pk, dn_pk = up_m0[i - 1], dn_m0[i - 1]
        up_q = up_peak and min(MAX_LEVELS, 1 + int(up_pk / STEP_ATR)) >= FADE_MIN
        dn_q = dn_peak and min(MAX_LEVELS, 1 + int(dn_pk / STEP_ATR)) >= FADE_MIN
        fire = (-1 if up_pk >= dn_pk else 1) if (up_q and dn_q) else -1 if up_q else 1 if dn_q else 0

        # ---- rozliczenie transakcji jak w dashboardzie (do bramkowania)
        closed = False
        if active:
            if side == 1:
                hits = [high[i] >= t for t in t_tp]
                sl_hit = low[i] <= t_stop
            else:
                hits = [low[i] <= t for t in t_tp]
                sl_hit = high[i] >= t_stop
            stage = 3 if hits[2] else 2 if hits[1] else 1 if hits[0] else 0
            same_bar_sl = sl_hit and stage > 0
            if stage > best and not same_bar_sl:
                best = stage
            fin_tp3 = not same_bar_sl and best == 3
            fin_sl = sl_hit
            expire = not fin_tp3 and not fin_sl and i - t_bar >= MAX_HUNT
            if fin_tp3 or fin_sl or expire:
                closed = True
                active = False
                if expire:
                    out["time_exit"][i] = True

        # ---- nowy sygnał
        cooldown_ok = last_sig is None or i - last_sig >= COOLDOWN
        if fire != 0 and not active and not closed and not np.isnan(atr[i]) and cooldown_ok:
            last_sig = i
            is_long = fire == 1
            entry = close[i]
            if is_long:
                raw_stop = min(low[i], low[i - 1]) - atr[i] * SL_BUF
            else:
                raw_stop = max(high[i], high[i - 1]) + atr[i] * SL_BUF
            risk = min(max(abs(entry - raw_stop), atr[i] * MIN_RISK), atr[i] * MAX_RISK)
            stop = entry - risk if is_long else entry + risk
            sgn = 1 if is_long else -1
            r = [entry + sgn * risk * k for k in TP_R]

            # Pressure Ladder: klastry przeciwnej strony w kierunku zysku.
            cands = sorted(
                d for d in (
                    sgn * (z.mid - entry) for z in zones
                    if z.dir == (-1 if is_long else 1)
                )
                if d >= risk * LADDER_MIN_R
            )
            lv = [entry + sgn * d for d in cands[:3]] + [np.nan] * (3 - min(3, len(cands)))
            t1 = lv[0] if not np.isnan(lv[0]) else r[0]
            if not np.isnan(lv[1]):
                t2 = lv[1]
            else:
                t2 = max(r[1], t1 + risk * 0.5) if is_long else min(r[1], t1 - risk * 0.5)
            if not np.isnan(lv[2]):
                t3 = lv[2]
            else:
                t3 = max(r[2], t2 + risk * 0.5) if is_long else min(r[2], t2 - risk * 0.5)

            active, side, t_bar, best = True, sgn, i, 0
            t_stop, t_tp = stop, [t1, t2, t3]
            out["dir"][i] = sgn
            out["stop"][i] = stop
            out["tp"][i] = t_tp

    return out


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Wyjście: buy, sell, stop_loss, take_profit (TP1), take_profit_2,
    take_profit_3, exit_long / exit_short (time stop 200 świec).
    """
    sim = _simulate(bars)
    d = sim["dir"]
    result = pd.DataFrame(index=bars.index)
    result["buy"] = d == 1
    result["sell"] = d == -1
    result["stop_loss"] = sim["stop"]
    result["take_profit"] = sim["tp"][:, 0]
    result["take_profit_2"] = sim["tp"][:, 1]
    result["take_profit_3"] = sim["tp"][:, 2]
    # Time stop: zamknięcie na zamknięciu świecy (exit dla obu stron;
    # dotyczy tylko otwartej pozycji).
    result["exit_long"] = sim["time_exit"]
    result["exit_short"] = sim["time_exit"]
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """EMA 20 i bandy ± 2 ATR na cenie, TP1/SL jako kropki."""
    sim = _simulate(bars)
    idx = bars.index
    d = pd.Series(sim["dir"], index=idx)
    stop = pd.Series(sim["stop"], index=idx)
    return {
        "trend": None,
        "overlays": [
            (f"EMA {BASIS_LEN}", pd.Series(sim["basis"], index=idx), "#FF9800"),
            ("Banda górna", pd.Series(sim["upper"], index=idx), "#9598A1"),
            ("Banda dolna", pd.Series(sim["lower"], index=idx), "#9598A1"),
        ],
        "markers": [
            ("SL long", stop.where(d == 1), "#FF3B30", "below"),
            ("SL short", stop.where(d == -1), "#FF3B30", "above"),
        ],
    }
