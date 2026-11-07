"""
Cumulative RSI (Connors) — wariant z progiem wejścia 50.

Te same zasady co ConnorsCumulativeRSI.py, tylko wejście przy
cumulative RSI < 50 (więcej transakcji, płytsze cofnięcia).
"""

import pandas as pd

from strategies.ksiazki import ConnorsCumulativeRSI as base


NAME = "Connors Cumulative RSI (50)"

TIMEFRAMES = base.TIMEFRAMES
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"
EQUITY_FRACTION = 1.0

ENTRY_LEVEL = 50
EXIT_LEVEL = base.EXIT_LEVEL


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return base.signals(bars, ENTRY_LEVEL, EXIT_LEVEL)


def indicators(bars: pd.DataFrame) -> dict:
    return base.indicators(bars, ENTRY_LEVEL, EXIT_LEVEL)
