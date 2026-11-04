"""
Key Level Zones | Pivots & Daily Weekly Monthly High Low (Forex City Pro)
https://www.tradingview.com/script/MVfnGVle-FCP-Key-Level-Zones-Pivots-Daily-Weekly-Monthly-High-Low/

Port 1:1 liczenia stref (Pine v6, indicator, ustawienia domyślne).
To NIE jest strategia: wskaźnik nie ma wejść, wyjść, SL ani TP,
a autor pisze, że strefa "is a place to pay attention to, not a signal
to buy or sell". Moduł tylko wyznacza strefy; pomiar reakcji ceny
robi analizy/event_study_key_levels.py.

Reguły z kodu:
1. Poziomy HL: high, low i środek (mid) poprzedniego dnia, tygodnia
   i miesiąca (request.security z high[1] / low[1], lookahead_on).
2. Pivoty Traditional z poprzedniego dnia, tygodnia i miesiąca:
   P, R1–R3, S1–S3 (R4/S4 i R5/S5 domyślnie wyłączone).
3. Tolerancja = 0,5 × ATR(14) z interwału 4h, wartość z ostatniej
   ZAMKNIĘTEJ świecy 4h (ta.atr(14)[1], lookahead_on).
4. Każdy poziom HL porównany z każdym pivotem: odległość ≤ tolerancja
   → kandydat [min, max]. Dwa pivoty albo dwa HL nie tworzą strefy.
5. Kandydaci posortowani po dolnej krawędzi; nakładający się
   (l <= hi) łączeni w jedną strefę.
6. Liczba poziomów = wszystkie poziomy (HL i pivoty) w [lo, hi].
   2 = turkus, 3 = złoto, 4+ = czerwień.
7. Rysunek: strefa węższa niż 0,08 × tolerancji poszerzana do tej
   wysokości, szersza niż 0,1 × ATR przycinana wokół środka.
   Liczba poziomów się nie zmienia.
8. Strefy liczone na pierwszej świecy dnia (przy domyślnych
   ustawieniach dzień jest najkrótszym okresem), ważne do końca dnia.
   Pierwszy dzień historii pomijany (bar_index > 0).

Interwał wykresu nie ma znaczenia: na każdym interwale ≤ D strefy
są identyczne (tolerancja z ATR 4h, nie z wykresu).

Granice okresów liczone w czasie danych (Tickstory GMT+2 z DST USA
= NY + 7 h, dzień zaczyna się o 17:00 NY jak na TV dla FX).
Tydzień od poniedziałku. Dla BTC TradingView liczy dzień od 00:00 UTC,
u nas od 00:00 GMT+2 — przybliżenie.

Wersja do backtestu (NASZE założenia, autor nie podaje zasad handlu,
"not a signal to buy or sell"), wzorem Auto Levels & Trendlines:
- sygnał = pierwsze dotknięcie strefy w dniu, w którym obowiązuje
  (strefa, w której cena jest już na otwarciu dnia, jest pomijana),
- kierunek = odbicie: cena przyszła z góry → long, z dołu → short,
- wejście na pierwszym ticku po zamknięciu świecy dotknięcia,
  wyjście po HOLD_BARS świecach, bez SL i TP, 100% kapitału,
- jedna pozycja naraz; świeca z dotknięciami w obu kierunkach pomijana.
Grupa kontrolna: KeyLevelZones_Control.py (te same liczby wejść,
kierunki i czas trzymania, losowe momenty), porównanie: analizy/compare_control.py.
Badanie zdarzeń bez transakcji: analizy/event_study_key_levels.py.

Autor nie podaje konkretnego interwału ("Intraday and swing traders who
plan around daily and weekly key levels") ani rynku.
"""

import numpy as np
import pandas as pd


NAME = "Key Level Zones"

TIMEFRAMES = ["15min", "1h", "4h"]

HOLD_BARS = 10
# 2 = wszystkie strefy, 3 = tylko złote i czerwone, 4 = tylko czerwone.
MIN_LEVELS = 2

OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"
EQUITY_FRACTION = 1.0

COLORS = {2: "rgba(47,227,198,0.30)", 3: "rgba(255,216,77,0.30)", 4: "rgba(255,97,82,0.30)"}

# Ustawienia domyślne skryptu.
TOL_ATR = 0.5
MAX_HEIGHT_ATR = 0.1
ATR_LENGTH = 14
ATR_TIMEFRAME = "4h"

USE_DAY_HL = True
USE_WEEK_HL = True
USE_MONTH_HL = True
USE_MID_HL = True

USE_DAY_PP = True
USE_WEEK_PP = True
USE_MONTH_PP = True
# Poziomy pivotów: 0 = P, 1 = R1/S1, ..., 5 = R5/S5.
INCLUDE_TIER = {0: True, 1: True, 2: True, 3: True, 4: False, 5: False}

PP_NAMES = ["P", "R1", "S1", "R2", "S2", "R3", "S3", "R4", "S4", "R5", "S5"]

HL_SOURCE = 0
PIVOT_SOURCE = 1


# ============================================================
# Dane źródłowe
# ============================================================

def period_key(index: pd.DatetimeIndex, kind: str) -> pd.DatetimeIndex:
    """Początek dnia / tygodnia (pn) / miesiąca dla każdej świecy."""
    day = index.normalize()
    if kind == "D":
        return day
    if kind == "W":
        return day - pd.to_timedelta(index.dayofweek, unit="D")
    if kind == "M":
        return index.to_period("M").to_timestamp()
    raise ValueError(kind)


def previous_period_hlc(bars: pd.DataFrame, kind: str) -> pd.DataFrame:
    """
    High, low i close POPRZEDNIEGO okresu (poprzedniej istniejącej
    świecy D/W/M, jak barmerge.gaps_off), indeksowane początkiem
    bieżącego okresu.
    """
    keys = period_key(bars.index, kind)
    hlc = bars.groupby(keys).agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
    return hlc.shift(1)


def traditional_pivots(h: float, l: float, c: float) -> list:
    """ta.pivot_point_levels("Traditional"): P, R1, S1, ..., R5, S5."""
    p = (h + l + c) / 3
    return [
        p,
        2 * p - l, 2 * p - h,
        p + (h - l), p - (h - l),
        h + 2 * (p - l), l - 2 * (h - p),
        p * 3 + (h - 3 * l), p * 3 - (3 * h - l),
        p * 4 + (h - 4 * l), p * 4 - (4 * h - l),
    ]


def atr_series(bars: pd.DataFrame, timeframe: str = ATR_TIMEFRAME, length: int = ATR_LENGTH) -> pd.Series:
    """ta.atr(length) na świecach timeframe (RMA zasiane SMA, jak w Pine)."""
    htf = bars.resample(timeframe).agg({"high": "max", "low": "min", "close": "last"}).dropna()
    prev_close = htf["close"].shift(1)
    tr = pd.concat(
        [htf["high"] - htf["low"], (htf["high"] - prev_close).abs(), (htf["low"] - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    tr.iloc[0] = htf["high"].iloc[0] - htf["low"].iloc[0]

    values = tr.to_numpy()
    atr = np.full(len(values), np.nan)
    if len(values) >= length:
        atr[length - 1] = values[:length].mean()
        alpha = 1.0 / length
        for i in range(length, len(values)):
            atr[i] = alpha * values[i] + (1 - alpha) * atr[i - 1]
    return pd.Series(atr, index=htf.index)


def atr_before(atr: pd.Series, t0: pd.Timestamp, timeframe: str = ATR_TIMEFRAME) -> float:
    """ATR z ostatniej świecy HTF zaczętej przed świecą HTF zawierającą t0 (ta.atr()[1])."""
    start = t0.floor(timeframe)
    pos = atr.index.searchsorted(start, side="left") - 1
    return float(atr.iloc[pos]) if pos >= 0 else np.nan


# ============================================================
# Strefy
# ============================================================

def gather_levels(day_start, hl: dict, pivots: dict) -> list:
    """
    f_gather(): lista (cena, źródło, nazwa) w kolejności z Pine.
    hl / pivots: {"D": DataFrame z previous_period_hlc, ...}
    """
    levels = []
    keys = {
        "D": day_start,
        "W": period_key(pd.DatetimeIndex([day_start]), "W")[0],
        "M": period_key(pd.DatetimeIndex([day_start]), "M")[0],
    }

    for kind, tag, enabled in (("D", "PD", USE_DAY_HL), ("W", "PW", USE_WEEK_HL), ("M", "PM", USE_MONTH_HL)):
        if not enabled or keys[kind] not in hl[kind].index:
            continue
        row = hl[kind].loc[keys[kind]]
        if np.isnan(row["high"]) or np.isnan(row["low"]):
            continue
        levels.append((row["high"], HL_SOURCE, tag + "H"))
        levels.append((row["low"], HL_SOURCE, tag + "L"))
        if USE_MID_HL:
            levels.append(((row["high"] + row["low"]) / 2, HL_SOURCE, tag + "M"))

    for kind, tag, enabled in (("D", "D ", USE_DAY_PP), ("W", "W ", USE_WEEK_PP), ("M", "M ", USE_MONTH_PP)):
        if not enabled or keys[kind] not in pivots[kind].index:
            continue
        row = pivots[kind].loc[keys[kind]]
        if np.isnan(row["high"]):
            continue
        for i, level in enumerate(traditional_pivots(row["high"], row["low"], row["close"])):
            tier = 0 if i == 0 else (i + 1) // 2
            if INCLUDE_TIER[tier]:
                levels.append((level, PIVOT_SOURCE, tag + PP_NAMES[i]))

    return levels


def build_zones(levels: list, atr: float) -> list:
    """f_build() + f_emit(): lista słowników lo, hi, top, bot, members, names."""
    if not levels or np.isnan(atr):
        return []

    tol = TOL_ATR * atr
    pairs = []
    for pi, si, _ in levels:
        if si != HL_SOURCE:
            continue
        for pj, sj, _ in levels:
            if sj == PIVOT_SOURCE and abs(pi - pj) <= tol:
                pairs.append((min(pi, pj), max(pi, pj)))
    if not pairs:
        return []

    pairs.sort(key=lambda pair: pair[0])
    merged = []
    lo, hi = pairs[0]
    for l, h in pairs[1:]:
        if l <= hi:
            hi = max(hi, h)
        else:
            merged.append((lo, hi))
            lo, hi = l, h
    merged.append((lo, hi))

    zones = []
    for lo, hi in merged:
        inside = [name for price, _, name in levels if lo <= price <= hi]
        pad = max(0.0, (tol * 0.08 - (hi - lo)) / 2)
        top, bot = hi + pad, lo - pad
        max_h = MAX_HEIGHT_ATR * atr
        if MAX_HEIGHT_ATR > 0 and top - bot > max_h:
            mid = (hi + lo) / 2
            top, bot = mid + max_h / 2, mid - max_h / 2
        zones.append(
            {"lo": lo, "hi": hi, "top": top, "bot": bot, "members": len(inside), "names": " · ".join(inside)}
        )
    return zones


def daily_zones(bars: pd.DataFrame) -> list:
    """
    Strefy dla każdego dnia z bars (świece intraday, np. 1 min).
    Zwraca listę słowników: day_start (pierwsza świeca dnia), day_end
    (pierwsza świeca następnego dnia), atr, levels, zones.
    """
    hl = {kind: previous_period_hlc(bars, kind) for kind in ("D", "W", "M")}
    atr = atr_series(bars)

    day_keys = period_key(bars.index, "D")
    first_bar = pd.Series(bars.index, index=day_keys).groupby(level=0).first()

    result = []
    starts = list(first_bar.index)
    for k, day in enumerate(starts):
        if k == 0:
            continue  # bar_index > 0
        t0 = first_bar.loc[day]
        day_atr = atr_before(atr, t0)
        levels = gather_levels(day, hl, hl)
        result.append(
            {
                "day": day,
                "t0": t0,
                "t_end": first_bar.iloc[k + 1] if k + 1 < len(starts) else bars.index[-1] + pd.Timedelta("1min"),
                "atr": day_atr,
                "levels": levels,
                "zones": build_zones(levels, day_atr),
            }
        )
    return result


# ============================================================
# Backtest (nasze założenia — patrz opis na górze)
# ============================================================

_CACHE = {}


def _cached_days(bars: pd.DataFrame) -> list:
    key = (id(bars), len(bars), bars.index[0], bars.index[-1])
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = daily_zones(bars)
    return _CACHE[key]


def touch_signals(bars: pd.DataFrame) -> list:
    """
    (świeca pierwszego dotknięcia, kierunek odbicia, strefa) dla każdej
    strefy z >= MIN_LEVELS poziomami. Kierunek: +1 = cena przyszła
    z góry (wsparcie), -1 = z dołu (opór).
    """
    o = bars["open"].to_numpy()
    h = bars["high"].to_numpy()
    l = bars["low"].to_numpy()
    index = bars.index

    out = []
    for day in _cached_days(bars):
        i0 = index.searchsorted(day["t0"])
        i_end = index.searchsorted(day["t_end"])
        for zone in day["zones"]:
            if zone["members"] < MIN_LEVELS:
                continue
            top, bot = zone["top"], zone["bot"]
            if bot <= o[i0] <= top:
                continue
            from_above = o[i0] > top
            hit = l[i0:i_end] <= top if from_above else h[i0:i_end] >= bot
            if hit.any():
                out.append((i0 + int(np.argmax(hit)), 1 if from_above else -1, zone))
    return sorted(out, key=lambda item: (item[0], item[1]))


def _entries(bars: pd.DataFrame) -> list:
    """Sygnały bez świec z dotknięciami w obu kierunkach."""
    by_bar = {}
    for bar, direction, _ in touch_signals(bars):
        by_bar.setdefault(bar, set()).add(direction)
    return [(bar, dirs.pop()) for bar, dirs in sorted(by_bar.items()) if len(dirs) == 1]


def take_entries(signals, hold: int) -> list:
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
    cols = {name: np.zeros(n, dtype=bool) for name in ("buy", "sell", "exit_long", "exit_short")}
    for bar, direction in entries:
        cols["buy" if direction == 1 else "sell"][bar] = True
        if bar + hold < n:
            cols["exit_long" if direction == 1 else "exit_short"][bar + hold] = True
    return pd.DataFrame(cols, index=bars.index)


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return signals_frame(bars, take_entries(_entries(bars), HOLD_BARS), HOLD_BARS)


def indicators(bars: pd.DataFrame) -> dict:
    """Strefy w kolorach autora (od początku do końca dnia), etykiety dotknięć, panel ATR(14, 4h)."""
    zones = []
    for day in _cached_days(bars):
        for zone in day["zones"]:
            color = COLORS[min(zone["members"], 4)]
            zones.append((day["t0"], day["t_end"], zone["top"], zone["bot"], color))

    idx = bars.index
    labels = []
    for direction, where, text in ((1, "below", "▲"), (-1, "above", "▼")):
        mask = np.zeros(len(bars), dtype=bool)
        for bar, d, _ in touch_signals(bars):
            if d == direction:
                mask[bar] = True
        labels.append((f"Dotknięcie strefy {text}", pd.Series(mask, index=idx), text, "#8A8F98", where))

    atr = atr_series(bars)
    atr_line = atr.reindex(idx, method="ffill")
    return {
        "trend": None,
        "zones": zones,
        "labels": labels,
        "panel": {
            "title": "ATR(14) z 4h",
            "lines": [("ATR(14, 4h)", atr_line, "#B0BEC5")],
            "levels": (),
            "range": (0, float(np.nanpercentile(atr_line, 99.5)) * 1.3 or 1.0),
        },
    }
