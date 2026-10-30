import pandas as pd

from strategies.tiktok.RSI6_80_20 import rsi


NAME = "RSI 90%"

# Każdy sygnał to wejście za 1/10 kapitału; kolejne sygnały w tę
# samą stronę dokładają (najwyżej 10 wejść). Przeciwny sygnał
# zamyka wszystko i otwiera pozycję w drugą stronę.
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "add"
PYRAMIDING = 10
EQUITY_FRACTION = 0.1

# Autor nie podał ustawień — domyślne RSI z TradingView.
RSI_LENGTH = 14
OVERSOLD = 30
OVERBOUGHT = 70


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Daytrading (nuclearpunch90, „90% win rate strategy
    with huge problem”), jak wbudowana „RSI Strategy” z TV:

    Long: RSI przecina w górę 30 (wyjście z wyprzedania).
    Short: RSI przecina w dół 70 (wyjście z wykupienia).
    Sygnał w stronę otwartej pozycji dokłada 1/10 kapitału,
    przeciwny zamyka całość i odwraca pozycję. Bez SL i TP.

    Wyjście:
        buy, sell.
    """
    value = rsi(bars["close"], RSI_LENGTH)
    prev = value.shift(1)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = ((value > OVERSOLD) & (prev <= OVERSOLD)).fillna(False)
    result["sell"] = ((value < OVERBOUGHT) & (prev >= OVERBOUGHT)).fillna(False)
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """RSI 14 w panelu z poziomami 30 i 70."""
    return {
        "trend": None,
        "panel": {
            "title": f"RSI {RSI_LENGTH}",
            "lines": [("RSI", rsi(bars["close"], RSI_LENGTH), "#7E57C2")],
            "levels": (OVERSOLD, OVERBOUGHT),
            "level_colors": ("#00D084", "#FF3B30"),
            "range": (0, 100),
        },
    }
