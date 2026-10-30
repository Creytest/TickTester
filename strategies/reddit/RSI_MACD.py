import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema
from strategies.tiktok.RSI6_80_20 import rsi


NAME = "RSI MA + MACD"

# Bez SL i TP — sygnał przeciwny zamyka pozycję i otwiera odwrotną.
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału
# z kapitalizacją.
EQUITY_FRACTION = 1.0

# Autor nie podał ustawień — domyślne z TradingView.
RSI_LENGTH = 14
RSI_MA_LENGTH = 14          # średnia z RSI ("RSI crossing its 14 moving average")
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
WINDOW = 5                  # MACD musi się przeciąć najpóźniej 5 świec po RSI


def rsi_and_ma(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    value = rsi(close, RSI_LENGTH)
    return value, value.rolling(RSI_MA_LENGTH).mean()


def macd(close: pd.Series) -> tuple[pd.Series, pd.Series]:
    line = ema(close, MACD_FAST) - ema(close, MACD_SLOW)
    return line, ema(line.dropna(), MACD_SIGNAL).reindex(close.index)


def _crosses(a: pd.Series, b: pd.Series) -> tuple[np.ndarray, np.ndarray]:
    """Przecięcie a nad b (w górę) i pod b (w dół) na zamknięciu świecy."""
    diff = (a - b).to_numpy(dtype=float)
    prev = np.roll(diff, 1)
    prev[0] = np.nan
    up = (diff > 0) & (prev <= 0)
    down = (diff < 0) & (prev >= 0)
    return up, down


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Trading (m0nk_3y_gw): "RSI crossing its 14 moving
    average, AND then MACD also crossing within ~5 bars".

    Long: RSI 14 przecina w górę swoją SMA 14, a potem (na tej samej
    albo jednej z 5 kolejnych świec) linia MACD przecina w górę
    sygnałową. Short odwrotnie. Liczy się ostatnie przecięcie RSI —
    jeśli RSI wróci pod średnią, czekamy na nowe.

    Autor nie podał wyjścia: pozycję zamyka i odwraca sygnał
    przeciwny. Bez SL i TP.

    Wyjście:
        buy, sell.
    """
    close = bars["close"].astype(float)
    value, average = rsi_and_ma(close)
    line, signal = macd(close)

    rsi_up, rsi_down = _crosses(value, average)
    macd_up, macd_down = _crosses(line, signal)

    buy = np.zeros(len(bars), dtype=bool)
    sell = np.zeros(len(bars), dtype=bool)
    last_dir, last_bar = 0, -10**9

    for i in range(len(bars)):
        if rsi_up[i]:
            last_dir, last_bar = 1, i
        elif rsi_down[i]:
            last_dir, last_bar = -1, i

        if i - last_bar > WINDOW:
            continue
        if macd_up[i] and last_dir == 1:
            buy[i] = True
        elif macd_down[i] and last_dir == -1:
            sell[i] = True

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """
    Panel 1: RSI 14 i jego SMA 14, kropki na przecięciach (zielona
    w górę, czerwona w dół). Panel 2: MACD i linia sygnałowa (EMA 9
    z MACD), kropki na ich przecięciach.
    """
    close = bars["close"].astype(float)
    value, average = rsi_and_ma(close)
    line, signal = macd(close)

    rsi_up, rsi_down = _crosses(value, average)
    macd_up, macd_down = _crosses(line, signal)

    return {
        "trend": None,
        "panel": {
            "title": f"RSI {RSI_LENGTH}",
            "lines": [
                ("RSI", value, "#7E57C2"),
                (f"SMA {RSI_MA_LENGTH} z RSI", average, "#FFC107"),
            ],
            "points": [
                ("RSI przecina SMA w górę", value.where(rsi_up), "#00D084"),
                ("RSI przecina SMA w dół", value.where(rsi_down), "#FF3B30"),
            ],
            "levels": (30, 50, 70),
            "level_colors": ("#00D084", "#8A8F98", "#FF3B30"),
            "range": (0, 100),
        },
        "panel2": {
            "title": f"MACD {MACD_FAST},{MACD_SLOW},{MACD_SIGNAL}",
            "lines": [
                ("MACD", line, "#4C8DFF"),
                (f"Sygnał (EMA {MACD_SIGNAL})", signal, "#FF9800"),
            ],
            "points": [
                ("MACD przecina sygnał w górę", line.where(macd_up), "#00D084"),
                ("MACD przecina sygnał w dół", line.where(macd_down), "#FF3B30"),
            ],
            "levels": (0,),
        },
    }
