"""
Auto Levels & Trendlines + Breakout Check (TradingView Community Scripts):
https://www.tradingview.com/script/7C36YesS-auto-levels-trendlines-breakout-check/

Wskaźnik autora nie ma wejść, SL ani TP ("This is an analysis aid,
not a trading recommendation"). Plik zawiera port 1:1 logiki zdarzeń
wskaźnika (Pine v6), z którego korzystają:
- event_study.py (badanie zdarzeń, bez transakcji),
- run_all_assets.py: strategia z NASZYMI założeniami (wejście na
  TRUE, wyjście po HOLD_BARS świecach) + grupa kontrolna
  AutoLevelsTrendlines_Control, porównanie: compare_control.py.
Tabela wskaźnika jest pominięta; strefy, linie i etykiety są
rysowane na wykresie HTML (indicators()).

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

# ------------------------------------------------------------
# Wersja do backtestu (NASZE założenia — autor nie podaje zasad
# handlu, nazywa skrypt "analysis aid"):
# - wejście na sygnale TRUE (alert "true breakout"): long przy
#   wybiciu w górę, short w dół, na pierwszym ticku po zamknięciu
#   świecy, na której wybicie zostało uznane za TRUE (3. zamknięcie
#   za granicą, licząc świecę wybicia),
# - wyjście po HOLD_BARS świecach (na pierwszym ticku po zamknięciu
#   świecy wejścia + HOLD_BARS), bez SL i TP,
# - jedna pozycja naraz: sygnały w trakcie pozycji są pomijane,
# - bez SL → 100% kapitału z kapitalizacją.
# Grupa kontrolna: AutoLevelsTrendlines_Control.py (te same wejścia
# co do liczby i kierunku, ale w losowych momentach).
# ------------------------------------------------------------
HOLD_BARS = 10

OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"
EQUITY_FRACTION = 1.0

# Ustawienia wskaźnika inne niż domyślne autora, np. {"conf_bars": 2}.
PARAMS = {}

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
    qual_bar: int | None = None  # pierwsza świeca z >= min dotyków
    end_bar: int | None = None   # złamanie albo wypadnięcie z listy


@dataclass
class TLine:
    x1: int
    y1: float
    slope: float
    is_high: bool
    touches: int
    last_t: int
    created: int = 0             # świeca, na której linia powstała
    broken: bool = False
    end_bar: int | None = None

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


def _add_pivot(levels, p, piv_bar, close, atr_v, prm, history):
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
    lv = Level(
        price=p,
        top=p + pad,
        bot=p - pad,
        side=1 if close > p else -1,
        touches=1,
        last_touch=piv_bar,
        born=piv_bar,
    )
    levels.append(lv)
    history.append(lv)


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


def _try_line(tls, py, px, is_high, high, low, atr_v, prm, bar, history):
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
                created=bar,
            )
        )
        history.append(tls[-1])
        while len(tls) > prm["max_tl"]:
            old = tls.pop(0)
            if old.end_bar is None:
                old.end_bar = bar


def breakout_events(bars: pd.DataFrame, **params) -> pd.DataFrame:
    """
    Wszystkie wybicia wskaźnika z historią statusu.

    Kolumny: kind (level/line), dir (1 w górę, -1 w dół), touches,
    ref (granica na świecy wybicia), breakout_bar, true_bar,
    false_bar (FALSE albo "failed" po retescie), retest_bar,
    final_state, vol_ratio oraz czasy *_time.
    Indeksy świec liczone od 0 w `bars`.
    """
    brks, _, _ = _run(bars, params)
    return _events_frame(brks, bars.index)


def _run(bars: pd.DataFrame, params: dict):
    """Pełny przebieg wskaźnika: (wybicia, historia stref, historia linii)."""
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
    lv_hist: list[Level] = []
    tl_hist: list[TLine] = []

    def trim_levels(bar):
        while len(levels) > prm["max_lv"]:
            old = levels.pop(0)
            if old.end_bar is None:
                old.end_bar = bar
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
                _add_pivot(levels, ph[i], xh, c, a, prm, lv_hist)
                trim_levels(i)
            if prm["show_lines"]:
                _try_line(tls, ph_y, ph_x, True, high, low, a, prm, i, tl_hist)
        if not np.isnan(pl[i]):
            xl = i - sl
            pl_y.append(pl[i])
            pl_x.append(xl)
            if len(pl_y) > 40:
                pl_y.pop(0)
                pl_x.pop(0)
            if prm["show_levels"]:
                _add_pivot(levels, pl[i], xl, c, a, prm, lv_hist)
                trim_levels(i)
            if prm["show_lines"]:
                _try_line(tls, pl_y, pl_x, False, high, low, a, prm, i, tl_hist)

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
                if qual and lv.qual_bar is None:
                    lv.qual_bar = i
                b_up = lv.side == -1 and c > lv.top + buf
                b_dn = lv.side == 1 and c < lv.bot - buf
                if b_up or b_dn:
                    if qual:
                        lv.broken = True
                        lv.end_bar = i
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
                    t.end_bar = i
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

    return done_brks + brks, lv_hist, tl_hist


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


# ============================================================
# STRATEGIA (nasze założenia, patrz HOLD_BARS u góry)
# ============================================================

_CACHE = {}


def _cached_run(bars: pd.DataFrame):
    """generate_signals i indicators liczą to samo — liczymy raz."""
    key = (
        len(bars),
        bars.index[0] if len(bars) else None,
        bars.index[-1] if len(bars) else None,
        float(bars["close"].sum()) if len(bars) else 0.0,
        tuple(sorted(PARAMS.items())),
    )
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = _run(bars, PARAMS)
    return _CACHE[key]


def true_signals(bars: pd.DataFrame) -> list[tuple[int, int]]:
    """(świeca TRUE, kierunek) dla każdego wybicia uznanego za TRUE."""
    brks, _, _ = _cached_run(bars)
    out = []
    for b in brks:
        for bar, state in b.log:
            if state == TRUE:
                out.append((bar, b.dir))
    return sorted(out)


def take_entries(signals, hold: int) -> list[tuple[int, int]]:
    """Jedna pozycja naraz: kolejne wejście dopiero po świecy wyjścia."""
    taken = []
    busy_until = -1
    for bar, direction in signals:
        if bar > busy_until:
            taken.append((bar, direction))
            busy_until = bar + hold
    return taken


def signals_frame(bars: pd.DataFrame, entries, hold: int) -> pd.DataFrame:
    n = len(bars)
    buy = np.zeros(n, dtype=bool)
    sell = np.zeros(n, dtype=bool)
    exit_long = np.zeros(n, dtype=bool)
    exit_short = np.zeros(n, dtype=bool)
    for bar, direction in entries:
        (buy if direction == 1 else sell)[bar] = True
        if bar + hold < n:
            (exit_long if direction == 1 else exit_short)[bar + hold] = True
    return pd.DataFrame(
        {"buy": buy, "sell": sell, "exit_long": exit_long, "exit_short": exit_short},
        index=bars.index,
    )


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    entries = take_entries(true_signals(bars), HOLD_BARS)
    return signals_frame(bars, entries, HOLD_BARS)


def indicators(bars: pd.DataFrame) -> dict:
    """
    Strefy (prostokąty), linie trendu i etykiety jak na wykresie
    autora: W wybicie (⚡ w TV), ✓ TRUE, ✗ FALSE / nieudany retest.
    Strefa rysowana od pivota, od którego powstała (jak box w Pine),
    do złamania albo wypadnięcia z listy 20 stref; tylko strefy,
    które doszły do min. liczby dotyków. Panel: ATR(14).
    """
    brks, lv_hist, tl_hist = _cached_run(bars)
    idx = bars.index
    last = len(bars) - 1

    zones = []
    for lv in lv_hist:
        if lv.qual_bar is None:
            continue
        end = lv.end_bar if lv.end_bar is not None else last
        if lv.broken:
            color = "rgba(150,150,150,0.18)"
        elif lv.side == -1:
            color = "rgba(239,83,80,0.22)"
        else:
            color = "rgba(38,166,154,0.22)"
        zones.append((idx[lv.born], idx[end], lv.top, lv.bot, color))

    lines = []
    for t in tl_hist:
        end = t.end_bar if t.end_bar is not None else last
        if t.broken:
            color = "rgba(150,150,150,0.8)"
        else:
            color = "#ffa726" if t.is_high else "#42a5f5"
        lines.append((idx[t.x1], t.y1, idx[end], t.value(end), color))

    def mask(bars_list):
        m = np.zeros(len(bars), dtype=bool)
        m[list(bars_list)] = True
        return pd.Series(m, index=idx)

    labels = []
    for direction, where in ((1, "below"), (-1, "above")):
        sel = [b for b in brks if b.dir == direction]
        brk_bars = [b.bar for b in sel]
        true_bars = [bar for b in sel for bar, st in b.log if st == TRUE]
        false_bars = [
            bar for b in sel for bar, st in b.log if st in (FALSE, RETEST_FAIL)
        ]
        arrow = "▲" if direction == 1 else "▼"
        labels += [
            (f"Wybicie {arrow}", mask(brk_bars), "W", "#ffca28", where),
            (f"TRUE {arrow}", mask(true_bars), "✓", "#4caf50", where),
            (f"FALSE {arrow}", mask(false_bars), "✗", "#ef5350", where),
        ]

    atr_series = pd.Series(atr_rma(bars, DEFAULTS["atr_len"]), index=idx)
    return {
        "trend": None,
        "zones": zones,
        "lines": lines,
        "labels": labels,
        "panel": {
            "title": "ATR(14)",
            "lines": [("ATR(14)", atr_series, "#B0BEC5")],
            "levels": (),
            "range": (0, float(np.nanpercentile(atr_series, 99.5)) * 1.3 or 1.0),
        },
    }
