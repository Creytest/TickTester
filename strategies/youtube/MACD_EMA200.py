import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema
from strategies.reddit.RSI_MACD import _crosses


NAME = "MACD + 200 EMA (86%)"

# Autor: "works in almost every single market", interwału nie podaje
# — standardowy test 15m/1h/4h.

# Pozycja kończy się na SL albo TP. Sygnały przy otwartej pozycji
# są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Z SL — standardowe 1% ryzyka na transakcję.

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
EMA_LENGTH = 200
RR_RATIO = 1.5      # "a 1.5 profit ratio for my profit target"


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    line = ema(close, MACD_FAST) - ema(close, MACD_SLOW)
    return line, ema(line.dropna(), MACD_SIGNAL).reindex(close.index)


def generate_signals(bars: pd.DataFrame, rr_ratio: float = RR_RATIO) -> pd.DataFrame:
    """
    YouTube, TradingLab, "BEST MACD Trading Strategy [86% Win Rate]"
    (2021): "we buy if the macd lines cross below the zero line mark,
    and the current price also above the 200 day moving average ...
    set a stop loss below the 200 day moving average ... a 1.5 profit
    ratio for my profit target". Short "the exact opposite".

    Long: linia MACD (12, 26, 9) przecina sygnałową w górę, obie pod
    zerem, zamknięcie nad EMA 200.
    Short: przecięcie w dół, obie nad zerem, zamknięcie pod EMA 200.
    SL na EMA 200 ze świecy sygnałowej, TP = 1,5 × odległość do SL.

    Wersja podstawowa z filmu. "Advanced confirmation" (drugi dotyk
    wsparcia/oporu) autor wyznacza na oko — nie testujemy.

    Wyjście:
        buy, sell, stop_loss, take_profit.
    """
    close = bars["close"].astype(float)
    trend = ema(close, EMA_LENGTH)
    line, signal = macd(close)
    up, down = _crosses(line, signal)

    line_v = line.to_numpy(dtype=float)
    signal_v = signal.to_numpy(dtype=float)
    close_v = close.to_numpy(dtype=float)
    trend_v = trend.to_numpy(dtype=float)

    buy = up & (line_v < 0) & (signal_v < 0) & (close_v > trend_v)
    sell = down & (line_v > 0) & (signal_v > 0) & (close_v < trend_v)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    result["stop_loss"] = np.where(buy | sell, trend_v, np.nan)
    result["take_profit"] = np.where(
        buy,
        close_v + (close_v - trend_v) * rr_ratio,
        np.where(sell, close_v - (trend_v - close_v) * rr_ratio, np.nan),
    )
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """EMA 200 na cenie, MACD i linia sygnałowa w panelu z poziomem zera."""
    close = bars["close"].astype(float)
    trend = ema(close, EMA_LENGTH)
    line, signal = macd(close)
    limit = 1.0

    both = pd.concat([line, signal])
    if both.notna().any():
        limit = float(np.nanmax(np.abs(both.to_numpy()))) * 1.05 or 1.0

    return {
        "trend": None,
        "overlays": [(f"EMA {EMA_LENGTH}", trend, "#F2C200")],
        "panel": {
            "title": f"MACD ({MACD_FAST}, {MACD_SLOW}, {MACD_SIGNAL})",
            "lines": [
                ("MACD", line, "#2962FF"),
                ("Sygnał", signal, "#FF6D00"),
            ],
            "levels": (0,),
            "range": (-limit, limit),
        },
    }
