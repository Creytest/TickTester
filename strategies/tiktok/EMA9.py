import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema


NAME = "EMA9"

# Autor pokazuje strategię na 30 minutach (day trading).
TIMEFRAMES = ["30min"]

# Brak SL i TP: zamknięcie po drugiej stronie EMA 9 zamyka
# pozycję i otwiera odwrotną — zawsze gramy z EMA 9.
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału
# z kapitalizacją.
EQUITY_FRACTION = 1.0


def generate_signals(bars: pd.DataFrame, length: int = 9) -> pd.DataFrame:
    """
    Long: zamknięcie przebija EMA 9 w górę (poprzednie było
    pod lub na EMA). Short: zamknięcie przebija EMA 9 w dół.

    Brak SL i TP — przeciwne wybicie zamyka pozycję i od razu
    otwiera odwrotną.

    Wyjście:
        buy, sell.
    """
    close = bars["close"].astype(float)
    fast = ema(close, length)

    # Odpowiedniki ta.crossover(close, ema) i ta.crossunder().
    buy = (close > fast) & (close.shift(1) <= fast.shift(1))
    sell = (close < fast) & (close.shift(1) >= fast.shift(1))

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy.fillna(False).astype(bool)
    result["sell"] = sell.fillna(False).astype(bool)
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """EMA 9 na cenie, odległość zamknięcia od EMA w panelu."""
    close = bars["close"].astype(float)
    fast = ema(close, 9)
    spread = 100 * (close - fast) / fast
    limit = 1.0

    if spread.notna().any():
        limit = float(np.nanmax(np.abs(spread.to_numpy()))) * 1.05 or 1.0

    return {
        "trend": None,
        "overlays": [("EMA 9", fast, "#F2C200")],
        "panel": {
            "title": "Close − EMA 9 (%)",
            "lines": [("Różnica %", spread, "#7E57C2")],
            "levels": (0,),
            "range": (-limit, limit),
        },
    }
