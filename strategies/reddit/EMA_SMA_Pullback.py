import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema


NAME = "EMA/SMA Pullback"

# Autor nie podaje interwału ani rynku ("średnie zależą od aktywa
# i interwału") — standardowy test 15m/1h/4h.

# Tylko long. Sygnał kupna przy otwartej pozycji nic nie zmienia,
# pozycję zamyka wyłącznie reguła wyjścia autora.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Autor wspomina o stopach, ale ich nie opisuje — bez SL nie ma
# 1% ryzyka, pozycja to 100% kapitału z kapitalizacją.
EQUITY_FRACTION = 1.0

# Przykład autora: EMA(10) i SMA(20) ("SMA of about double the EMA period").
EMA_LENGTH = 10
SMA_LENGTH = 20


def _averages(bars: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    close = bars["close"].astype(float)
    fast = ema(close, EMA_LENGTH)
    slow = close.rolling(SMA_LENGTH).mean()
    return fast, slow


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Daytrading, "Crazy simple strategies", komentarz
    The-Goat-Trader: "fast EMA and slow SMA of about double the EMA
    period. So like EMA(10) and SMA(20).
    1. Price > ema > sma
    2. ema & sma are both trending up (or flat)
    3. Price closes between them — buy
    4. Sell when price is above ema and closes higher than previous high"

    Punkty 1–2 to stan na poprzedniej świecy, punkt 3 to sygnał.
    Wszystkie trzy na tej samej świecy wykluczają się: EMA rośnie
    tylko wtedy, gdy zamknięcie jest nad poprzednią EMA, więc
    świeca z rosnącą EMA nie może zamknąć się pod nią (to samo
    z "Price > ema" i "closes between them").

    Kupno (na zamknięciu świecy):
        poprzednia świeca: zamknięcie > EMA 10 > SMA 20 (punkt 1),
        EMA i SMA nie niższe niż świecę wcześniej (punkt 2),
        ta świeca: SMA < zamknięcie < EMA (cofnięcie, punkt 3).
    Wyjście (na zamknięciu świecy):
        zamknięcie > EMA i zamknięcie > high poprzedniej świecy.

    Bez SL i TP, bez shortów (autor opisuje tylko long).

    Wyjście:
        buy, sell, exit_long, exit_short.
    """
    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    fast, slow = _averages(bars)

    # Stan przed cofnięciem (poprzednia świeca).
    above = (close > fast) & (fast > slow)
    rising = (fast >= fast.shift(1)) & (slow >= slow.shift(1))
    setup = (above & rising).shift(1, fill_value=False)

    between = (close < fast) & (close > slow)

    buy = setup & between
    exit_long = (close > fast) & (close > high.shift(1))

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy.fillna(False).astype(bool)
    result["sell"] = False
    result["exit_long"] = exit_long.fillna(False).astype(bool)
    result["exit_short"] = False
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """EMA 10 i SMA 20 na cenie, odległość EMA od SMA w panelu."""
    fast, slow = _averages(bars)
    spread = 100 * (fast - slow) / slow
    limit = 1.0

    if spread.notna().any():
        limit = float(np.nanmax(np.abs(spread.to_numpy()))) * 1.05 or 1.0

    return {
        "trend": None,
        "overlays": [
            (f"EMA {EMA_LENGTH}", fast, "#00D084"),
            (f"SMA {SMA_LENGTH}", slow, "#FF3B30"),
        ],
        "panel": {
            "title": f"EMA {EMA_LENGTH} − SMA {SMA_LENGTH} (%)",
            "lines": [("Różnica EMA − SMA %", spread, "#7E57C2")],
            "levels": (0,),
            "range": (-limit, limit),
        },
    }
