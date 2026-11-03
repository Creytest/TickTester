"""
Auto Levels & Trendlines + Breakout Check (TradingView Community Scripts):
https://www.tradingview.com/script/7C36YesS-auto-levels-trendlines-breakout-check/

To NIE jest strategia: wskaźnik autora nie ma wejść, SL ani TP
("This is an analysis aid, not a trading recommendation"). Plik
zawiera port 1:1 logiki zdarzeń wskaźnika (Pine v6), z którego
korzysta event_study.py (badanie zdarzeń). Rysunek i tabela
są pominięte, bo nie wpływają na zdarzenia.

Reguły z kodu (ustawienia domyślne, DEFAULTS niżej):

1. Pivoty: ta.pivothigh / ta.pivotlow(5, 5), znane 5 świec później.
   ATR(14). Wszystko liczone na zamkniętych świecach i dopiero,
   gdy ATR ma wartość.
2. Strefy poziome: pivot dołącza do pierwszej (najstarszej)
   niezłamanej strefy, od której jest w ±0,35 ATR, jeśli strefa nie
   przekroczy wtedy 1,5 ATR grubości (dołączenie NIE dodaje dotyku).
   Inaczej nowa strefa pivot ± 0,10 ATR, 1 dotyk. Strona ustalana
   raz: close świecy, na której pivot się potwierdził, nad pivotem =
   wsparcie, inaczej opór. Max 20 stref: najstarsze wypadają
   (także złamane i kwalifikowane).
3. Dotyk strefy: high >= dół − 0,35 ATR i low <= góra + 0,35 ATR,
   zamknięcie po "swojej" stronie (wsparcie: close >= dół, opór:
   close <= góra), >= 5 świec od poprzedniego dotyku. Strefa
   kwalifikowana od 3 dotyków.
4. Linie trendu (po każdym nowym pivocie): ostatni pivot + jeden
   z 10 poprzednich tego typu, odległość <= 300 świec, różnica cen
   >= 0,5 ATR, żaden knot między nimi nie wychodzi za linię o więcej
   niż 0,25 ATR, >= 3 dotyki knotem (co >= 5 świec). Opór tylko
   spadający, wsparcie tylko rosnące. Wygrywa najwięcej dotyków,
   przy remisie dłuższa linia. Pomijane, gdy istnieje już
   niezłamana linia tego typu w ±0,25 ATR od nowego pivota.
   Max 6 linii (najstarsze wypadają).
5. Wybicie: zamknięcie za granicą o więcej niż 0,15 ATR (opór: nad
   górą strefy / nad linią, wsparcie: pod dołem / pod linią).
   Wybicie strefy z < 3 dotykami po cichu ją kasuje.
6. TRUE: 3 kolejne zamknięcia za granicą, licząc świecę wybicia
   (czyli 2 świece po wybiciu). FALSE: wcześniej zamknięcie z
   powrotem za granicą (bez bufora). Granica linii idzie dalej linią.
7. Po TRUE retest przez 10 świec: knot dotyka granicy → zamknięcie
   za nią = "confirmed by retest", z powrotem = "failed" (alert
   autora liczy "failed" jako false breakout).
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from strategies.tiktok.LuxAlgo_SR_Breaks_MSTS import pivot_high, pivot_low
from strategies.tiktok.SR_Retest import atr as atr_rma


NAME = "Auto Levels & Trendlines"

# Interwał i aktywa: autor ich nie podaje.
TIMEFRAMES = ["15min", "1h", "4h"]

DEFAULTS = {
    "swing_len": 5,
    "atr_len": 14,
    "min_gap": 5,
    # poziomy
    "show_levels": True,
    "min_touch_lv": 3,
    "tol_atr": 0.35,
    "pad_atr": 0.10,
    "max_width_atr": 1.5,
    "max_lv": 20,
    # linie
    "show_lines": True,
    "min_touch_tl": 3,
    "tl_tol_atr": 0.25,
    "max_cand": 10,
    "max_tl_bars": 300,
    "min_move_atr": 0.5,
    "allow_counter": False,
    "max_tl": 6,
    # wybicie
    "brk_atr": 0.15,
    "conf_bars": 3,
    "need_vol": False,
    "vol_mult": 1.5,
    "use_retest": True,
    "retest_bars": 10,
}

# Stany wybicia jak w Pine.
PENDING, TRUE, FALSE, RETEST_OK, RETEST_FAIL, LOW_VOLUME = 1, 2, 3, 4, 5, 6
STATE_NAMES = {
    PENDING: "awaiting",
    TRUE: "true",
    FALSE: "false",
    RETEST_OK: "retest_confirmed",
    RETEST_FAIL: "retest_failed",
    LOW_VOLUME: "low_volume",
}


@dataclass
class Level:
    price: float
    top: float
    bot: float
    side: int
    touches: int
    last_touch: int
    born: int
    broken: bool = False


@dataclass
class TLine:
    x1: int
    y1: float
    slope: float
    is_high: bool
    touches: int
    last_t: int
    broken: bool = False

    def value(self, x: int) -> float:
        return self.y1 + self.slope * (x - self.x1)


@dataclass
class Brk:
    kind: str  # "level" / "line"
    dir: int
    ref: float
    bar: int
    touches: int
    vol_ok: bool
    vol_ratio: float
    tl: TLine | None = None
    state: int = PENDING
    held: int = 1
    retest_left: int = 0
    log: list = field(default_factory=list)  # (bar, state)


def _add_pivot(levels, p, piv_bar, close, atr_v, prm):
    tol = prm["tol_atr"] * atr_v
    pad = prm["pad_atr"] * atr_v
    for lv in levels:
        if not lv.broken and lv.bot - tol <= p <= lv.top + tol:
            nt = max(lv.top, p + pad)
            nb = min(lv.bot, p - pad)
            if nt - nb <= prm["max_width_atr"] * atr_v:
                lv.top, lv.bot = nt, nb
                lv.price = (nt + nb) / 2
                return
    levels.append(
        Level(
            price=p,
            top=p + pad,
            bot=p - pad,
            side=1 if close > p else -1,
            touches=1,
            last_touch=piv_bar,
            born=piv_bar,
        )
    )


def _tl_eval(high, low, is_high, xa, ya, xb, yb, tol, gap):
    """f_tlEval: (ok, liczba dotyków, nachylenie)."""
    slope = (yb - ya) / (xb - xa)
    xs = np.arange(xa, xb + 1)
    yl = ya + slope * (xs - xa)
    if is_high:
        h = high[xa:xb + 1]
        if np.any(h > yl + tol):
            return False, 0, slope
        cand = xs[h >= yl - tol]
    else:
        lo = low[xa:xb + 1]
        if np.any(lo < yl - tol):
            return False, 0, slope
        cand = xs[lo <= yl + tol]

    n = 0
    last_t = xa - gap
    for x in cand:
        if x - last_t >= gap:
            n += 1
            last_t = x
    return True, n, slope


def _try_line(tls, py, px, is_high, high, low, atr_v, prm):
    sz = len(py)
    if sz < 2:
        return
    xb, yb = px[-1], py[-1]
    tol = prm["tl_tol_atr"] * atr_v
    for t in tls:
        if not t.broken and t.is_high == is_high and abs(t.value(xb) - yb) <= tol:
            return

    best_n, best_a, best_slope = 0, -1, 0.0
    low_k = max(0, sz - 1 - prm["max_cand"])
    for k in range(sz - 2, low_k - 1, -1):
        xa, ya = px[k], py[k]
        if xb - xa > prm["max_tl_bars"] or abs(yb - ya) < prm["min_move_atr"] * atr_v:
            continue
        slope = (yb - ya) / (xb - xa)
        dir_ok = prm["allow_counter"] or (slope < 0 if is_high else slope > 0)
        if not dir_ok:
            continue  # bez skutków ubocznych — tylko przyspieszenie
        ok, n, slope = _tl_eval(high, low, is_high, xa, ya, xb, yb, tol, prm["min_gap"])
        better = n > best_n
        if not better and n == best_n and best_a >= 0:
            better = (xb - xa) > (xb - px[best_a])
        if ok and n >= prm["min_touch_tl"] and better:
            best_n, best_a, best_slope = n, k, slope

    if best_a >= 0:
        tls.append(
            TLine(
                x1=px[best_a],
                y1=py[best_a],
                slope=best_slope,
                is_high=is_high,
                touches=best_n,
                last_t=xb,
            )
        )
        while len(tls) > prm["max_tl"]:
            tls.pop(0)


def breakout_events(bars: pd.DataFrame, **params) -> pd.DataFrame:
    """
    Wszystkie wybicia wskaźnika z historią statusu.

    Kolumny: kind (level/line), dir (1 w górę, -1 w dół), touches,
    ref (granica na świecy wybicia), breakout_bar, true_bar,
    false_bar (FALSE albo "failed" po retescie), retest_bar,
    final_state, vol_ratio oraz czasy *_time.
    Indeksy świec liczone od 0 w `bars`.
    """
    prm = {**DEFAULTS, **params}
    unknown = set(params) - set(DEFAULTS)
    if unknown:
        raise ValueError(f"Nieznane parametry: {sorted(unknown)}")

    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    volume = (
        bars["volume"].to_numpy(dtype=float)
        if "volume" in bars
        else np.full(len(bars), np.nan)
    )

    atr = atr_rma(bars, prm["atr_len"])
    vol_ma = pd.Series(volume).rolling(20).mean().to_numpy()
    ph = pivot_high(bars["high"], prm["swing_len"], prm["swing_len"]).to_numpy()
    pl = pivot_low(bars["low"], prm["swing_len"], prm["swing_len"]).to_numpy()

    levels: list[Level] = []
    tls: list[TLine] = []
    brks: list[Brk] = []
    done_brks: list[Brk] = []
    ph_y, ph_x, pl_y, pl_x = [], [], [], []
    sl = prm["swing_len"]
    min_gap = prm["min_gap"]

    for i in range(len(bars)):
        a = atr[i]
        if np.isnan(a):
            continue
        c = close[i]

        # ---------- nowe pivoty: poziomy i linie ----------
        if not np.isnan(ph[i]):
            xh = i - sl
            ph_y.append(ph[i])
            ph_x.append(xh)
            if len(ph_y) > 40:
                ph_y.pop(0)
                ph_x.pop(0)
            if prm["show_levels"]:
                _add_pivot(levels, ph[i], xh, c, a, prm)
                while len(levels) > prm["max_lv"]:
                    levels.pop(0)
            if prm["show_lines"]:
                _try_line(tls, ph_y, ph_x, True, high, low, a, prm)
        if not np.isnan(pl[i]):
            xl = i - sl
            pl_y.append(pl[i])
            pl_x.append(xl)
            if len(pl_y) > 40:
                pl_y.pop(0)
                pl_x.pop(0)
            if prm["show_levels"]:
                _add_pivot(levels, pl[i], xl, c, a, prm)
                while len(levels) > prm["max_lv"]:
                    levels.pop(0)
            if prm["show_lines"]:
                _try_line(tls, pl_y, pl_x, False, high, low, a, prm)

        # ---------- aktualizacja i wybicia ----------
        tol_t = prm["tol_atr"] * a
        tl_tol = prm["tl_tol_atr"] * a
        buf = prm["brk_atr"] * a
        vol_r = volume[i] / vol_ma[i] if vol_ma[i] > 0 else np.nan
        vol_ok = not np.isnan(vol_r) and vol_r >= prm["vol_mult"]
        h, lo = high[i], low[i]

        if prm["show_levels"]:
            for j in range(len(levels) - 1, -1, -1):
                lv = levels[j]
                if lv.broken:
                    continue
                entered = h >= lv.bot - tol_t and lo <= lv.top + tol_t
                held = c >= lv.bot if lv.side == 1 else c <= lv.top
                if entered and held and i > lv.born and i - lv.last_touch >= min_gap:
                    lv.touches += 1
                    lv.last_touch = i
                qual = lv.touches >= prm["min_touch_lv"]
                b_up = lv.side == -1 and c > lv.top + buf
                b_dn = lv.side == 1 and c < lv.bot - buf
                if b_up or b_dn:
                    if qual:
                        lv.broken = True
                        brks.append(
                            Brk(
                                kind="level",
                                dir=1 if b_up else -1,
                                ref=lv.top if b_up else lv.bot,
                                bar=i,
                                touches=lv.touches,
                                vol_ok=vol_ok,
                                vol_ratio=vol_r,
                                log=[(i, PENDING)],
                            )
                        )
                    else:
                        levels.pop(j)

        if prm["show_lines"]:
            for j in range(len(tls) - 1, -1, -1):
                t = tls[j]
                if t.broken:
                    continue
                yl = t.value(i)
                if t.is_high:
                    tch = h >= yl - tl_tol and c <= yl
                else:
                    tch = lo <= yl + tl_tol and c >= yl
                if tch and i > t.last_t and i - t.last_t >= min_gap:
                    t.touches += 1
                    t.last_t = i
                t_up = t.is_high and c > yl + buf
                t_dn = (not t.is_high) and c < yl - buf
                if t_up or t_dn:
                    t.broken = True
                    brks.append(
                        Brk(
                            kind="line",
                            dir=1 if t_up else -1,
                            ref=yl,
                            bar=i,
                            touches=t.touches,
                            vol_ok=vol_ok,
                            vol_ratio=vol_r,
                            tl=t,
                            log=[(i, PENDING)],
                        )
                    )

        # ---------- potwierdzenie wybić ----------
        for j in range(len(brks) - 1, -1, -1):
            b = brks[j]
            if i <= b.bar:
                continue
            ref = b.tl.value(i) if b.kind == "line" else b.ref
            back_in = c < ref if b.dir == 1 else c > ref
            prev = b.state
            done = False
            if b.state == PENDING:
                if back_in:
                    b.state = FALSE
                    done = True
                else:
                    b.held += 1
                    if b.held >= prm["conf_bars"]:
                        b.state = (
                            LOW_VOLUME
                            if prm["need_vol"] and not b.vol_ok
                            else TRUE
                        )
                        b.retest_left = prm["retest_bars"]
                        if b.state == LOW_VOLUME or not prm["use_retest"]:
                            done = True
            elif b.state == TRUE:
                touched = lo <= ref if b.dir == 1 else h >= ref
                if touched:
                    beyond = c > ref if b.dir == 1 else c < ref
                    b.state = RETEST_OK if beyond else RETEST_FAIL
                    done = True
                else:
                    b.retest_left -= 1
                    if b.retest_left <= 0:
                        done = True
            if b.state != prev:
                b.log.append((i, b.state))
            if done:
                done_brks.append(brks.pop(j))

    return _events_frame(done_brks + brks, bars.index)


def _events_frame(brks, index) -> pd.DataFrame:
    rows = []
    for b in brks:
        states = {state: bar for bar, state in b.log}
        true_bar = states.get(TRUE, states.get(LOW_VOLUME))
        false_bar = states.get(FALSE, states.get(RETEST_FAIL))
        retest_bar = states.get(RETEST_OK, states.get(RETEST_FAIL))
        rows.append(
            {
                "kind": b.kind,
                "dir": b.dir,
                "touches": b.touches,
                "ref": b.ref,
                "breakout_bar": b.bar,
                "true_bar": true_bar,
                "false_bar": false_bar,
                "retest_bar": retest_bar,
                "final_state": STATE_NAMES[b.state],
                "vol_ratio": b.vol_ratio,
            }
        )

    cols = [
        "kind", "dir", "touches", "ref", "breakout_bar", "true_bar",
        "false_bar", "retest_bar", "final_state", "vol_ratio",
    ]
    events = pd.DataFrame(rows, columns=cols)
    for col in ("breakout_bar", "true_bar", "false_bar", "retest_bar"):
        events[col] = events[col].astype("Int64")
        events[col.replace("_bar", "_time")] = [
            index[v] if pd.notna(v) else pd.NaT for v in events[col]
        ]
    return events.sort_values(["breakout_bar", "kind"]).reset_index(drop=True)
