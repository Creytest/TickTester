"""
Grupa kontrolna dla Connors Cumulative RSI, wariant 50.
Zasady losowania jak w ConnorsCumulativeRSI_Control.py.
"""

import pandas as pd

from strategies.ksiazki import ConnorsCumulativeRSI as base
from strategies.ksiazki import ConnorsCumulativeRSI_Control as control


NAME = "Connors Cumulative RSI (50) – grupa kontrolna"

TIMEFRAMES = base.TIMEFRAMES
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"
EQUITY_FRACTION = 1.0

ENTRY_LEVEL = 50


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return control.control_signals(bars, ENTRY_LEVEL)


def indicators(bars: pd.DataFrame) -> dict:
    return base.indicators(bars, ENTRY_LEVEL, base.EXIT_LEVEL)
