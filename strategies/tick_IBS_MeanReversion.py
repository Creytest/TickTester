import numpy as np
import pandas as pd


NAME = "IBS Mean Reversion"

# Autor testuje na świecach dziennych.
TIMEFRAMES = ["1D"]

# Tylko long. Wyjście sygnałem exit_long, bez SL i TP.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału
# z kapitalizacją, jak u autora (cały kapitał w SPY).
EQUITY_FRACTION = 1.0


def ibs(bars: pd.DataFrame) -> pd.Series:
    """
    Internal Bar Strength: (close - low) / (high - low), od 0
    (zamknięcie na low) do 1 (zamknięcie na high). Świeca bez
    zakresu (high = low) daje NaN.
    """
    span = (bars["high"] - bars["low"]).astype(float)
    return ((bars["close"] - bars["low"]) / span.where(span > 0)).astype(float)


def band(bars: pd.DataFrame) -> pd.Series:
    """
    Próg wejścia: najwyższy high z 10 świec minus 2,5 × średni
    zakres (średnia z 25 świec high minus średnia z 25 świec low).
    """
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    avg_range = high.rolling(25).mean() - low.rolling(25).mean()
    return high.rolling(10).max() - 2.5 * avg_range


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Daytrading (vaanam-dev, za Quantified Strategies):

    Long: zamknięcie pod progiem (10-dniowy high − 2,5 × średni
    25-dniowy zakres) i IBS < 0,3.
    Wyjście: zamknięcie nad high poprzedniej świecy.

    Wejście i wyjście na pierwszym ticku po zamknięciu świecy
    dziennej. Bez SL i TP — autor ich nie ma.

    Wyjście:
        buy, sell, exit_long.
    """
    close = bars["close"].astype(float)
    high = bars["high"].astype(float)

    buy = (close < band(bars)) & (ibs(bars) < 0.3)
    exit_long = close > high.shift(1)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy.fillna(False).astype(bool)
    result["sell"] = False
    result["exit_long"] = exit_long.fillna(False).astype(bool)
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """Próg wejścia na cenie, IBS w panelu z poziomem 0,3."""
    return {
        "trend": None,
        "overlays": [("Próg wejścia", band(bars), "#2979FF")],
        "panel": {
            "title": "IBS",
            "lines": [("IBS", ibs(bars), "#7E57C2")],
            "levels": (0.3,),
            "range": (0, 1),
        },
    }
