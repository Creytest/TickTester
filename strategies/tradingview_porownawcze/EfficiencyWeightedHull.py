"""
Efficiency Weighted Hull [BackQuant] (TradingView Community Scripts):
https://www.tradingview.com/script/2A4GKtHB-Efficiency-Weighted-Hull-BackQuant/
© BackQuant, oryginał na licencji MPL 2.0 (https://mozilla.org/MPL/2.0/);
ten plik jest portem i podlega tej samej licencji.

Port 1:1 wskaźnika (Pine v6, indicator, ustawienia domyślne):

1. fast = WMA(close, round(34 / 2) = 17), slow = WMA(close, 34),
   rootLen = round(√34) = 6.
2. Kaufman Efficiency Ratio(20) = |close − close[20]| / suma
   |zmian 1-świecowych| z 20 świec, obcięte do [0, 1] (path = 0 → 0).
3. Kompensacja = minComp + (1 − minComp) × ER ^ power (domyślnie
   minComp = 0, power = 1, więc kompensacja = ER).
4. hullRaw = fast + kompensacja × (fast − slow);
   Efficiency Hull = WMA(hullRaw, 6).
   (Standardowy Hull = WMA(2 × fast − slow, 6) — autor liczy go
   tylko do Data Window; tu służy jako punkt odniesienia.)
5. slope = Hull − Hull[2]; noise = EMA(|Hull − Hull[1]|, 20);
   próg = noise × 0,20.
6. Stan trendu: na pierwszej świecy znak slope (slope jeszcze nie
   istnieje, więc w Pine wychodzi -1, bez sygnału). Potem slope > próg
   → bull, slope < −próg → bear, w martwej strefie stan bez zmian.
7. bullFlip = stan −1 → 1, bearFlip = 1 → −1 (alerty autora).
   Trend Strength, wstążka, gradient, glow i kolor świec to tylko
   wygląd — nie wpływają na stan ani alerty.

Wskaźnik nie ma SL, TP ani reguł handlu. Nasza interpretacja
(założenie, wybór Kamila 2026-11-04): zawsze w rynku — bullFlip
otwiera long i zamyka short, bearFlip odwrotnie. Sygnał na zamknięciu
świecy, wejście na otwarciu następnej. Pierwsza pozycja od pierwszego
flipu (stan początkowy nie otwiera transakcji). Bez SL → 100% kapitału.

Punkt odniesienia: EfficiencyWeightedHull_Standard.py — ta sama
strategia na standardowym Hullu (te same długości i martwa strefa).
Grupa kontrolna: EfficiencyWeightedHull_Control.py — tyle samo
odwróceń w losowych momentach. Porównanie: analizy/compare_control.py.

Autor nie podaje interwału ani rynku.
"""

import math

import numpy as np
import pandas as pd


NAME = "Efficiency Weighted Hull"

TIMEFRAMES = ["15min", "1h", "4h"]

# Stan wskaźnika zmienia się naprzemiennie, więc przeciwny flip = odwrócenie.
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału z kapitalizacją.
EQUITY_FRACTION = 1.0

# Ustawienia domyślne skryptu.
HULL_LENGTH = 34
ER_LENGTH = 20
ER_POWER = 1.0
MIN_COMPENSATION = 0.0
TREND_LOOKBACK = 2
NOISE_LENGTH = 20
DEAD_ZONE = 0.20

BULL_COLOR = "#00ff00"
BEAR_COLOR = "#ff0000"


# ============================================================
# Funkcje Pine
# ============================================================

def pine_round(x: float) -> int:
    """math.round z Pine: połówki od zera (Python round() zaokrągla do parzystej)."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def wma(values: np.ndarray, length: int) -> np.ndarray:
    """ta.wma: wagi 1..length (najnowsza świeca największa); na, jeśli w oknie jest na."""
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    if len(values) < length:
        return out
    weights = np.arange(1, length + 1, dtype=float)
    # convolve odwraca jądro, więc podajemy wagi od najmłodszej.
    out[length - 1:] = np.convolve(values, weights[::-1], mode="valid") / weights.sum()
    return out


def sma(values: np.ndarray, length: int) -> np.ndarray:
    """ta.sma: na, jeśli w oknie jest na."""
    return pd.Series(values, dtype=float).rolling(length).mean().to_numpy()


def ema(values: np.ndarray, length: int) -> np.ndarray:
    """ta.ema: start od SMA z pierwszych `length` wartości bez na (jak w Pine)."""
    values = np.asarray(values, dtype=float)
    out = np.full(len(values), np.nan)
    valid = np.flatnonzero(~np.isnan(values))
    if len(valid) < length:
        return out
    start = valid[0]
    seed = start + length - 1
    if np.isnan(values[start:seed + 1]).any():
        # Dziury w środku serii nie występują w tym wskaźniku.
        raise ValueError("ema(): na w środku serii")
    alpha = 2.0 / (length + 1)
    out[seed] = values[start:seed + 1].mean()
    for i in range(seed + 1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def shift(values: np.ndarray, k: int) -> np.ndarray:
    """x[k] z Pine (na na początku)."""
    out = np.full(len(values), np.nan)
    if k < len(values):
        out[k:] = values[:len(values) - k]
    return out


def trend_state(line: np.ndarray) -> dict:
    """Stan trendu, flipy i próg z nachylenia linii (kroki 5–7)."""
    slope = line - shift(line, TREND_LOOKBACK)
    noise = ema(np.abs(line - shift(line, 1)), NOISE_LENGTH)
    threshold = noise * DEAD_ZONE

    n = len(line)
    state = np.zeros(n, dtype=int)
    s = 0
    for i in range(n):
        if s == 0:
            # slope >= 0.0 z na daje false → -1 (pierwsza świeca).
            s = 1 if slope[i] >= 0.0 else -1
        elif slope[i] > threshold[i]:
            s = 1
        elif slope[i] < -threshold[i]:
            s = -1
        state[i] = s

    prev = np.concatenate(([0], state[:-1]))
    return {
        "slope": slope,
        "threshold": threshold,
        "state": state,
        "bull": (state == 1) & (prev == -1),
        "bear": (state == -1) & (prev == 1),
    }


# ============================================================
# Obliczenia wskaźnika
# ============================================================

def compute(bars: pd.DataFrame) -> dict:
    """Wszystkie serie wskaźnika w kolejności z Pine + stan dla standardowego Hulla."""
    src = bars["close"].to_numpy(dtype=float)

    half_len = max(1, pine_round(HULL_LENGTH / 2.0))
    root_len = max(1, pine_round(math.sqrt(HULL_LENGTH)))

    displacement = np.abs(src - shift(src, ER_LENGTH))
    path = sma(np.abs(src - shift(src, 1)), ER_LENGTH) * ER_LENGTH
    with np.errstate(invalid="ignore", divide="ignore"):
        efficiency = np.where(path > 0.0, np.minimum(displacement / path, 1.0), 0.0)

    adjusted = np.power(efficiency, ER_POWER)
    compensation = MIN_COMPENSATION + (1.0 - MIN_COMPENSATION) * adjusted

    fast = wma(src, half_len)
    slow = wma(src, HULL_LENGTH)

    hull_raw = fast + compensation * (fast - slow)
    efficiency_hull = wma(hull_raw, root_len)

    standard_hull = wma(2.0 * fast - slow, root_len)
    base = wma(slow, root_len)

    return {
        "efficiency": efficiency,
        "compensation": compensation,
        "fast": fast,
        "slow": slow,
        "hull_raw": hull_raw,
        "hull": efficiency_hull,
        "standard_hull": standard_hull,
        "base": base,
        "ewh": trend_state(efficiency_hull),
        "std": trend_state(standard_hull),
    }


_CACHE = {}


def cached(bars: pd.DataFrame) -> dict:
    key = (id(bars), len(bars), bars.index[0], bars.index[-1])
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = compute(bars)
    return _CACHE[key]


# ============================================================
# Sygnały
# ============================================================

def signals_from(bars: pd.DataFrame, which: str) -> pd.DataFrame:
    """buy = bullFlip, sell = bearFlip (na zamknięciu świecy)."""
    t = cached(bars)[which]
    return pd.DataFrame({"buy": t["bull"], "sell": t["bear"]}, index=bars.index)


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return signals_from(bars, "ewh")


def indicators_for(bars: pd.DataFrame, which: str, signals: pd.DataFrame = None) -> dict:
    """Linia Hulla w kolorze stanu, Base, flipy (albo podane sygnały), ER i kompensacja w panelu."""
    c = cached(bars)
    idx = bars.index
    line = pd.Series(c["hull"] if which == "ewh" else c["standard_hull"], index=idx)
    state = pd.Series(c[which]["state"], index=idx)
    # Odcinek łączy się z poprzednią świecą, żeby linia nie miała dziur.
    bull = line.where((state == 1) | (state.shift(-1) == 1))
    bear = line.where((state == -1) | (state.shift(-1) == -1))
    other_name = "Standard Hull" if which == "ewh" else "Efficiency Weighted Hull"
    other = pd.Series(c["standard_hull"] if which == "ewh" else c["hull"], index=idx)

    if signals is None:
        buy, sell = c[which]["bull"], c[which]["bear"]
        buy_name, sell_name = "Bullish flip", "Bearish flip"
    else:
        buy, sell = signals["buy"].to_numpy(), signals["sell"].to_numpy()
        buy_name, sell_name = "Losowy long", "Losowy short"

    return {
        "trend": None,
        "overlays": [
            ("Hull (bullish)", bull, BULL_COLOR),
            ("Hull (bearish)", bear, BEAR_COLOR),
            (other_name, other, "#8A8F98"),
            ("Adaptive Base", pd.Series(c["base"], index=idx), "#5C6370"),
        ],
        "markers": [
            (buy_name, bars["low"].where(buy), "#00D084", "below"),
            (sell_name, bars["high"].where(sell), "#FF3B30", "above"),
        ],
        "panel": {
            "title": "Efficiency Ratio i Hull Compensation",
            "lines": [
                ("Efficiency Ratio", pd.Series(c["efficiency"], index=idx), "#F2F2F2"),
                ("Hull Compensation", pd.Series(c["compensation"], index=idx), "#00D084"),
            ],
            "levels": (0, 1),
            "range": (0, 1.05),
        },
    }


def indicators(bars: pd.DataFrame) -> dict:
    return indicators_for(bars, "ewh")
