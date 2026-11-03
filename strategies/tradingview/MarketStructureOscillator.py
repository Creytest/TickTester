"""
Market Structure Oscillator [BigBeluga] (TradingView Community Scripts):
https://pl.tradingview.com/script/mFMTYEYR-Market-Structure-Oscillator-BigBeluga/
© BigBeluga, oryginał na licencji CC BY-NC-SA 4.0
(https://creativecommons.org/licenses/by-nc-sa/4.0/); ten port jest
adaptacją i podlega tej samej licencji.

Port 1:1 części wskaźnika, która decyduje o kierunku (Pine v6,
indicator, ustawienia domyślne):

1. Swing high / swing low = ta.pivothigh / ta.pivotlow (5 / 5),
   potwierdzone 5 świec po szczycie / dołku.
2. Zamknięcie przebija ostatni swing high w górę (ta.crossover)
   → trend wzrostowy (pierwsze takie wybicie = CHoCH, kolejne = BoS).
   Zamknięcie przebija ostatni swing low w dół → trend spadkowy.
   Przebity poziom jest kasowany do czasu nowego pivota.
3. Oscylator momentum (ROC / odchylenie standardowe → sigmoid → EMA)
   i dywergencje NIE wpływają na kierunek — oscylator tylko dostaje
   znak od struktury (powyżej 50 w trendzie wzrostowym, poniżej 50
   w spadkowym). Liczymy go wyłącznie do wykresu.

Wskaźnik nie ma SL ani TP. Autor: "Use the CHoCH and BoS lines as
entry triggers, entering in the direction of the break". Nasza
interpretacja (założenie): zawsze w rynku — wybicie w górę otwiera
long, wybicie w dół zamyka long i otwiera short. Kolejne BoS w tym
samym kierunku nic nie zmieniają. Bez SL → 100% kapitału.

Autor nie podaje interwału ani rynku.
"""

import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema
from strategies.tiktok.LuxAlgo_SR_Breaks_MSTS import pivot_high, pivot_low


NAME = "Market Structure Oscillator"

TIMEFRAMES = ["15min", "1h", "4h"]

# Przeciwne wybicie odwraca pozycję, BoS w tę samą stronę nic nie robi.
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału z kapitalizacją.
EQUITY_FRACTION = 1.0

# Ustawienia domyślne skryptu.
MS_PIVOT_LEFT = 5
MS_PIVOT_RIGHT = 5
MOM_LENGTH = 14
SMOOTH_LENGTH = 10


# ============================================================
# Struktura rynku (jedyne źródło sygnałów)
# ============================================================

def _crossed(a_now, a_prev, b_now, b_prev, up: bool) -> bool:
    """ta.crossover / ta.crossunder; na w którejkolwiek wartości = False."""
    if np.isnan(b_now) or np.isnan(b_prev) or np.isnan(a_prev):
        return False
    if up:
        return a_now > b_now and a_prev <= b_prev
    return a_now < b_now and a_prev >= b_prev


def market_structure(bars: pd.DataFrame) -> dict:
    """
    Kod wskaźnika świeca po świecy, w kolejności z Pine.

    ta.crossover(close, latestHighSwing.price) porównuje z wartością
    poziomu z poprzedniej świecy tak, jak była w chwili wywołania
    (przed skasowaniem na "na" po wybiciu) — dlatego trzymamy
    osobno "poziom w chwili sprawdzenia" (hs_seen / ls_seen).
    """
    close = bars["close"].to_numpy(dtype=float)
    ph = pivot_high(bars["high"], MS_PIVOT_LEFT, MS_PIVOT_RIGHT).to_numpy()
    pl = pivot_low(bars["low"], MS_PIVOT_LEFT, MS_PIVOT_RIGHT).to_numpy()
    n = len(bars)

    out = {
        "bull_break": np.zeros(n, dtype=bool),
        "bear_break": np.zeros(n, dtype=bool),
        "bull_count": np.zeros(n, dtype=int),
        "bear_count": np.zeros(n, dtype=int),
        "trend_up": np.zeros(n, dtype=bool),
        "swing_high": np.full(n, np.nan),
        "swing_low": np.full(n, np.nan),
    }

    trend_up = False
    bull_count = bear_count = 0
    hs = ls = np.nan
    hs_prev_seen = ls_prev_seen = np.nan

    for i in range(n):
        if not np.isnan(ph[i]):
            hs = ph[i]
        if not np.isnan(pl[i]):
            ls = pl[i]

        out["swing_high"][i], out["swing_low"][i] = hs, ls
        c_prev = close[i - 1] if i >= 1 else np.nan

        hs_seen = hs
        if _crossed(close[i], c_prev, hs_seen, hs_prev_seen, up=True):
            trend_up = True
            bull_count += 1
            bear_count = 0
            out["bull_break"][i] = True
            hs = np.nan
        hs_prev_seen = hs_seen

        ls_seen = ls
        if _crossed(close[i], c_prev, ls_seen, ls_prev_seen, up=False):
            trend_up = False
            bear_count += 1
            bull_count = 0
            out["bear_break"][i] = True
            ls = np.nan
        ls_prev_seen = ls_seen

        out["trend_up"][i] = trend_up
        out["bull_count"][i], out["bear_count"][i] = bull_count, bear_count

    return out


# ============================================================
# Oscylator (tylko wykres)
# ============================================================

def oscillator(bars: pd.DataFrame, trend_up: np.ndarray) -> tuple[pd.Series, pd.Series]:
    """Zwraca (histogram filtrowany trendem, linia wygładzona bez filtra)."""
    close = bars["close"].astype(float)
    roc = close.diff(MOM_LENGTH)
    vol = close.diff().rolling(MOM_LENGTH).std(ddof=0)   # ta.stdev: populacyjne
    raw = (roc / vol).where(vol.notna() & (vol != 0), 0.0).fillna(0.0)
    sigmoid = 100.0 / (1.0 + np.exp(-raw))
    smooth = ema(sigmoid, SMOOTH_LENGTH)
    offset = (smooth - 50).abs()
    filtered = pd.Series(np.where(trend_up, 50 + offset, 50 - offset), index=bars.index)
    return filtered, smooth


# ============================================================
# Sygnały
# ============================================================

def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    buy: zamknięcie przebiło swing high (CHoCH albo BoS w górę).
    sell: zamknięcie przebiło swing low (CHoCH albo BoS w dół).
    Wejście po zamknięciu świecy wybicia.
    """
    ms = market_structure(bars)
    result = pd.DataFrame(index=bars.index)
    result["buy"] = ms["bull_break"]
    result["sell"] = ms["bear_break"]
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """Poziomy swingów na cenie, wybicia, oscylator w panelu."""
    ms = market_structure(bars)
    close = bars["close"]
    filtered, smooth = oscillator(bars, ms["trend_up"])
    choch_up = ms["bull_break"] & (ms["bull_count"] <= 1)
    choch_dn = ms["bear_break"] & (ms["bear_count"] <= 1)
    return {
        "trend": None,
        "overlays": [
            ("Swing high", pd.Series(ms["swing_high"], index=bars.index), "#35CFC5"),
            ("Swing low", pd.Series(ms["swing_low"], index=bars.index), "#FF5454"),
        ],
        "markers": [
            ("CHoCH w górę", close.where(choch_up), "#00D084", "below"),
            ("BoS w górę", close.where(ms["bull_break"] & ~choch_up), "#8FE3C0", "below"),
            ("CHoCH w dół", close.where(choch_dn), "#FF3B30", "above"),
            ("BoS w dół", close.where(ms["bear_break"] & ~choch_dn), "#FF9C95", "above"),
        ],
        "panel": {
            "title": f"Market Structure Oscillator ({MOM_LENGTH}, {SMOOTH_LENGTH})",
            "lines": [
                ("Histogram (filtr struktury)", filtered, "#35CFC5"),
                ("Linia wygładzona", smooth, "#F2C200"),
            ],
            "levels": (50,),
            "range": (0, 100),
        },
    }
