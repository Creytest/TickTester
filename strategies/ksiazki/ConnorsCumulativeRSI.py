"""
Cumulative RSI (Larry Connors, „Short Term Trading Strategies That Work”, 2008).

Zasady:
1. Zamknięcie powyżej SMA 200 (tylko long, tylko w trendzie wzrostowym).
2. Cumulative RSI = RSI(2) z dziś + RSI(2) z wczoraj.
3. Wejście: cumulative RSI < ENTRY_LEVEL (wariant 35 albo 50), kupno
   na zamknięciu świecy dziennej (u nas: pierwszy tick po zamknięciu).
4. Wyjście: RSI(2) > EXIT_LEVEL (65), też po zamknięciu.

Bez SL i TP (autor ich nie ma), więc 100% kapitału z kapitalizacją.
Autor: świece dzienne, akcje i indeksy USA (S&P 500) — najpierw US500.

Wariant z progiem 50: ConnorsCumulativeRSI_50.py.
Grupa kontrolna: ConnorsCumulativeRSI_Control.py.
"""

import pandas as pd

from strategies.tiktok.RSI6_80_20 import rsi


NAME = "Connors Cumulative RSI (35)"

# Autor testuje na świecach dziennych.
TIMEFRAMES = ["1D"]

OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"
EQUITY_FRACTION = 1.0

RSI_LENGTH = 2
CUMULATIVE_DAYS = 2
SMA_LENGTH = 200
ENTRY_LEVEL = 35
EXIT_LEVEL = 65


def cumulative_rsi(bars: pd.DataFrame) -> pd.Series:
    """Suma RSI(2) z ostatnich CUMULATIVE_DAYS świec."""
    value = rsi(bars["close"], RSI_LENGTH)
    return value.rolling(CUMULATIVE_DAYS).sum()


def signals(bars: pd.DataFrame, entry_level: float = ENTRY_LEVEL,
            exit_level: float = EXIT_LEVEL) -> pd.DataFrame:
    close = bars["close"].astype(float)
    sma = close.rolling(SMA_LENGTH).mean()

    buy = (close > sma) & (cumulative_rsi(bars) < entry_level)
    exit_long = rsi(close, RSI_LENGTH) > exit_level

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy.fillna(False).astype(bool)
    result["sell"] = False
    result["exit_long"] = exit_long.fillna(False).astype(bool)
    return result


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """Wyjście: buy, sell, exit_long."""
    return signals(bars, ENTRY_LEVEL, EXIT_LEVEL)


def trades_in_bars(sig: pd.DataFrame) -> list[tuple[int, int]]:
    """
    Transakcje tak, jak je wykona silnik (jedna pozycja naraz):
    (świeca sygnału wejścia, świeca sygnału wyjścia). Ostatnia
    otwarta pozycja bez wyjścia jest pomijana.
    """
    buy = sig["buy"].to_numpy()
    exit_long = sig["exit_long"].to_numpy()
    trades, entry = [], None
    for i in range(len(buy)):
        if entry is None:
            if buy[i]:
                entry = i
        elif exit_long[i]:
            trades.append((entry, i))
            entry = None
    return trades


def indicators(bars: pd.DataFrame, entry_level: float = ENTRY_LEVEL,
               exit_level: float = EXIT_LEVEL) -> dict:
    close = bars["close"].astype(float)
    return {
        "trend": None,
        "overlays": [
            (f"SMA {SMA_LENGTH}", close.rolling(SMA_LENGTH).mean(), "#4C8DFF"),
        ],
        "panel": {
            "title": f"Cumulative RSI ({CUMULATIVE_DAYS} dni RSI {RSI_LENGTH})",
            "lines": [("Cumulative RSI", cumulative_rsi(bars), "#7E57C2")],
            "levels": (entry_level,),
            "range": (0, 200),
        },
        "panel2": {
            "title": f"RSI {RSI_LENGTH}",
            "lines": [("RSI 2", rsi(close, RSI_LENGTH), "#FFC107")],
            "levels": (exit_level,),
            "range": (0, 100),
        },
    }
