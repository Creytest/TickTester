"""
Wykrywanie 12 formacji świecowych z planszy „Candlestick Patterns”
(TredWithRahul). Definicje: analizy/event_study_candles_zasady.md.

detect_patterns(bars) -> dict {nazwa: tablica bool}, True na ostatniej
świecy formacji (sygnał na jej zamknięciu). Bez zaglądania w przyszłość.

PATTERNS: nazwa -> (kierunek obiecany na planszy +1/-1, liczba świec).
"""

import numpy as np
import pandas as pd

AVG_PERIOD = 10          # średni korpus / zakres z 10 świec przed świecą
DOJI_FACTOR = 0.10       # korpus doji ≤ 10% śr. zakresu (TA-Lib BodyDoji)
VERY_SHORT_FACTOR = 0.10  # knot „prawie zerowy” ≤ 10% śr. zakresu
HAMMER_SHADOW = 2.0      # knot młota ≥ 2 × korpus
TWEEZER_ATR = 0.05       # dołki / szczyty różnią się o ≤ 5% ATR 14
SOLDIER_SHADOW = 0.25    # knot w kierunku ruchu ≤ 25% korpusu

# Kolejność = plansza (bullish | bearish w parach).
PATTERNS = {
    "Dragonfly Doji": (+1, 1),
    "Gravestone Doji": (-1, 1),
    "Hammer": (+1, 1),
    "Inverted Hammer": (-1, 1),
    "Tweezer Bottom": (+1, 2),
    "Tweezer Top": (-1, 2),
    "Morning Star": (+1, 3),
    "Evening Star": (-1, 3),
    "Bullish Engulfing": (+1, 2),
    "Bearish Engulfing": (-1, 2),
    "Three White Soldiers": (+1, 3),
    "Three Black Crows": (-1, 3),
}


def _prior_mean(x: np.ndarray, n: int) -> np.ndarray:
    """Średnia z n wartości PRZED każdą świecą (bez niej)."""
    return pd.Series(x).rolling(n).mean().shift(1).to_numpy()


def _shift(x: np.ndarray, k: int) -> np.ndarray:
    """x[t - k] na pozycji t (NaN / False na początku)."""
    out = np.empty_like(x)
    if x.dtype == bool:
        out[:k] = False
    else:
        out[:k] = np.nan
    out[k:] = x[:-k]
    return out


def detect_patterns(bars: pd.DataFrame, atr: np.ndarray) -> dict:
    o = bars["open"].to_numpy(dtype=float)
    h = bars["high"].to_numpy(dtype=float)
    l = bars["low"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)

    body = np.abs(c - o)
    rng = h - l
    top = np.maximum(o, c)
    bottom = np.minimum(o, c)
    upper = h - top
    lower = bottom - l
    green = c > o
    red = c < o

    avg_body = _prior_mean(body, AVG_PERIOD)
    avg_rng = _prior_mean(rng, AVG_PERIOD)
    ready = ~np.isnan(avg_body) & ~np.isnan(avg_rng) & (avg_rng > 0)

    with np.errstate(invalid="ignore"):
        doji = ready & (body <= DOJI_FACTOR * avg_rng)
        not_doji = ready & ~doji
        very_short_up = upper <= VERY_SHORT_FACTOR * avg_rng
        very_short_low = lower <= VERY_SHORT_FACTOR * avg_rng
        long_body = ready & (body > avg_body)
        small_body = ready & (body < avg_body)

    out = {}

    # 1 świeca
    out["Dragonfly Doji"] = doji & very_short_up & ~very_short_low
    out["Gravestone Doji"] = doji & very_short_low & ~very_short_up
    out["Hammer"] = (not_doji & small_body & (lower >= HAMMER_SHADOW * body)
                     & very_short_up)
    out["Inverted Hammer"] = (not_doji & small_body & (upper >= HAMMER_SHADOW * body)
                              & very_short_low)

    # 2 świece: [t-1, t]
    o1, c1, h1, l1 = _shift(o, 1), _shift(c, 1), _shift(h, 1), _shift(l, 1)
    body1 = _shift(body, 1)
    green1, red1 = _shift(green, 1), _shift(red, 1)
    not_doji1 = _shift(not_doji, 1)
    tol = TWEEZER_ATR * atr
    with np.errstate(invalid="ignore"):
        out["Tweezer Bottom"] = (red1 & green & not_doji1 & not_doji
                                 & (np.abs(l - l1) <= tol))
        out["Tweezer Top"] = (green1 & red & not_doji1 & not_doji
                              & (np.abs(h - h1) <= tol))
        out["Bullish Engulfing"] = (red1 & green & (o <= c1) & (c >= o1)
                                    & (body > body1))
        out["Bearish Engulfing"] = (green1 & red & (o >= c1) & (c <= o1)
                                    & (body > body1))

    # 3 świece: [t-2, t-1, t]
    o2, c2 = _shift(o, 2), _shift(c, 2)
    green2, red2 = _shift(green, 2), _shift(red, 2)
    long2 = _shift(long_body, 2)
    long1 = _shift(long_body, 1)
    small1 = _shift(small_body, 1)
    top1, bottom1 = _shift(top, 1), _shift(bottom, 1)
    mid2 = (o2 + c2) / 2
    with np.errstate(invalid="ignore"):
        out["Morning Star"] = (red2 & long2 & small1 & (bottom1 < c2)
                               & green & long_body & (c > mid2))
        out["Evening Star"] = (green2 & long2 & small1 & (top1 > c2)
                               & red & long_body & (c < mid2))

        upper1, upper2 = _shift(upper, 1), _shift(upper, 2)
        lower1, lower2 = _shift(lower, 1), _shift(lower, 2)
        body2 = _shift(body, 2)
        out["Three White Soldiers"] = (
            green2 & green1 & green & long2 & long1 & long_body
            & (c1 > c2) & (c > c1)
            & (o1 >= o2) & (o1 <= c2) & (o >= o1) & (o <= c1)
            & (upper2 <= SOLDIER_SHADOW * body2)
            & (upper1 <= SOLDIER_SHADOW * body1)
            & (upper <= SOLDIER_SHADOW * body)
        )
        out["Three Black Crows"] = (
            red2 & red1 & red & long2 & long1 & long_body
            & (c1 < c2) & (c < c1)
            & (o1 <= o2) & (o1 >= c2) & (o <= o1) & (o >= c1)
            & (lower2 <= SOLDIER_SHADOW * body2)
            & (lower1 <= SOLDIER_SHADOW * body1)
            & (lower <= SOLDIER_SHADOW * body)
        )

    return {name: np.asarray(out[name], dtype=bool) for name in PATTERNS}


def context_mask(bars: pd.DataFrame, length_sma: int = 20) -> dict:
    """
    Kontekst trendu dla każdej formacji: zamknięcie świecy tuż przed
    pierwszą świecą formacji poniżej SMA (bullish) / powyżej SMA (bearish).
    Zwraca {nazwa: tablica bool} wyrównaną do ostatniej świecy formacji.
    """
    c = bars["close"].to_numpy(dtype=float)
    sma = pd.Series(c).rolling(length_sma).mean().to_numpy()
    with np.errstate(invalid="ignore"):
        below = c < sma
        above = c > sma
    out = {}
    for name, (direction, n_candles) in PATTERNS.items():
        base = below if direction > 0 else above
        out[name] = _shift(base, n_candles)
    return out
