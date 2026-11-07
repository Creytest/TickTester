import numpy as np
import pandas as pd

from narzedzia.renko import calibrate_brick_size, renko_bricks
from strategies.tiktok.CloudMA_EMA30_74 import ema


NAME = "Renko EMA 9/20"

# Świece to cegły Renko (BUILD_BARS). Interwał służy tylko do
# rozgrzewki (300 × 5 min) i krzywej kapitału.
TIMEFRAMES = ["5min"]

# Pozycja kończy się na SL albo TP. Sygnały przy otwartej pozycji
# są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Od autora: EMA 9 i 20, TP = cegła + knot (1:1, „70% WR”) albo
# połowa (1:0,5, „80% WR”).
FAST = 9
SLOW = 20
TP_FRACTION = 1.0

# Od autora: EURUSD = 4R (cTrader: cegła 4 pipsy).
BRICK_SIZE = {"EURUSD": 0.0004}
# Pozostałe aktywa — autor dobiera cegłę „trial and error”, by nie
# drukowała więcej niż 1 cegły na minutę. Nasza reguła: cegła, przy
# której w pierwszych 30 dniach danych powstaje średnio 1 cegła na
# 5 minut handlu.
TARGET_BRICK_MINUTES = 5
CALIBRATION_DAYS = 30

# Ustawiane przez narzedzia/plot_tick_backtest_xauusd.main.
ASSET = None
TICK = 0.0

# Wielkość cegły raz na aktywo (test w kawałkach używa tej samej).
_size_cache = {}


def brick_size(ticks: pd.DataFrame) -> float:
    if ASSET in BRICK_SIZE:
        return BRICK_SIZE[ASSET]
    if ASSET in _size_cache:
        return _size_cache[ASSET]
    size = calibrate_brick_size(
        ticks["timestamp"].to_numpy(),
        ticks["bid"].to_numpy(dtype=float),
        TARGET_BRICK_MINUTES,
        CALIBRATION_DAYS,
    )
    if ASSET is not None:
        _size_cache[ASSET] = size
    print(f"Renko {ASSET}: cegła {size:.6g}")
    return size


def BUILD_BARS(ticks: pd.DataFrame) -> pd.DataFrame:
    """Cegły Renko z knotami z cen Bid (narzedzia/renko.py)."""
    return renko_bricks(
        ticks["timestamp"].to_numpy(),
        ticks["bid"].to_numpy(dtype=float),
        brick_size(ticks),
    )


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Daytrading (PauloMinozo), „Renko setup 70%-80% win rate”:
    „Long when box is crossing 9-20 EMA. Target is the same size of
    the box + wick […] Stop below wick. Same logic for shorting.”
    W komentarzu: czeka na cofnięcie do EMA 20, potem cegła znów
    przecina EMA 9 — wejście po zamknięciu cegły.

    Long (short lustrzanie):
    1. Trend: EMA 9 > EMA 20 (z zamknięć cegieł).
    2. Cofnięcie: od ostatniego zamknięcia nad EMA 9 knot którejś
       cegły dotknął EMA 20.
    3. Cegła wzrostowa otwiera się pod EMA 9 (albo na niej) i zamyka
       nad nią — wejście na ticku zamknięcia cegły.
    4. SL tick pod knotem, TP = zamknięcie + (cegła + knot) × TP_FRACTION.

    Cegły zamknięte tym samym tickiem co następna (luka) pomijamy —
    autor: „those are missed opportunities”.

    Wyjście:
        buy, sell, stop_loss, take_profit.
    """
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    fast = ema(bars["close"], FAST).to_numpy(dtype=float)
    slow = ema(bars["close"], SLOW).to_numpy(dtype=float)
    final = (
        bars["final"].to_numpy(dtype=bool)
        if "final" in bars.columns
        else np.ones(len(bars), dtype=bool)
    )
    n = len(bars)

    buy = np.zeros(n, dtype=bool)
    sell = np.zeros(n, dtype=bool)
    stop_loss = np.full(n, np.nan)
    take_profit = np.full(n, np.nan)

    touched_up = touched_down = False

    for i in range(n):
        if np.isnan(fast[i]) or np.isnan(slow[i]):
            continue

        # Cofnięcie w trendzie wzrostowym: knot do EMA 20.
        if close[i] > fast[i]:
            pullback_up = touched_up
            touched_up = False
        else:
            pullback_up = False
        if low[i] <= slow[i]:
            touched_up = True

        if close[i] < fast[i]:
            pullback_down = touched_down
            touched_down = False
        else:
            pullback_down = False
        if high[i] >= slow[i]:
            touched_down = True

        if not final[i]:
            continue

        up_brick = close[i] > open_[i]
        down_brick = close[i] < open_[i]

        if (
            up_brick and fast[i] > slow[i]
            and open_[i] <= fast[i] < close[i]
            and (pullback_up or low[i] <= slow[i])
        ):
            buy[i] = True
            stop_loss[i] = low[i] - TICK
            take_profit[i] = close[i] + (close[i] - low[i]) * TP_FRACTION

        elif (
            down_brick and fast[i] < slow[i]
            and open_[i] >= fast[i] > close[i]
            and (pullback_down or high[i] >= slow[i])
        ):
            sell[i] = True
            stop_loss[i] = high[i] + TICK
            take_profit[i] = close[i] - (high[i] - close[i]) * TP_FRACTION

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    result["stop_loss"] = stop_loss
    result["take_profit"] = take_profit
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """EMA 9 i 20 na cegłach. Panel: różnica EMA 9 − EMA 20."""
    fast = ema(bars["close"], FAST)
    slow = ema(bars["close"], SLOW)
    diff = fast - slow
    top = float(np.nanmax(np.abs(diff.to_numpy()))) if diff.notna().any() else 1.0
    return {
        "trend": None,
        "overlays": [
            (f"EMA {FAST}", fast, "#FFD600"),
            (f"EMA {SLOW}", slow, "#2979FF"),
        ],
        "panel": {
            "title": f"EMA {FAST} − EMA {SLOW}",
            "lines": [("Różnica", diff, "#7E57C2")],
            "levels": (0,),
            "range": (-top * 1.05 or -1.0, top * 1.05 or 1.0),
        },
    }
