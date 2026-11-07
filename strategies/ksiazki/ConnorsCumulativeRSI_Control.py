"""
Grupa kontrolna dla Connors Cumulative RSI (wariant 35).

Te same transakcje co strategia: tyle samo wejść i te same czasy
trzymania (w losowej kolejności), long, 100% kapitału, te same
koszty — tylko momenty wejścia są losowe (bez filtra SMA 200
i bez RSI). Jeśli strategia nie wypada lepiej, Cumulative RSI nic
nie dodaje ponad „kupuj i trzymaj kilka dni”.

Losowanie ma stałe ziarno (SEED), więc wynik jest powtarzalny.
"""

import numpy as np
import pandas as pd

from strategies.ksiazki import ConnorsCumulativeRSI as base


NAME = "Connors Cumulative RSI (35) – grupa kontrolna"

TIMEFRAMES = base.TIMEFRAMES
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"
EQUITY_FRACTION = 1.0

ENTRY_LEVEL = base.ENTRY_LEVEL
SEED = 42


def random_trades(n_bars: int, holds: list[int], first: int, seed: int = SEED):
    """
    Tyle samo transakcji o tych samych długościach (w świecach),
    w losowej kolejności i w losowych miejscach od świecy `first`,
    bez nakładania się (po wyjściu co najmniej 1 świeca przerwy).
    """
    if not holds:
        return []
    rng = np.random.default_rng(seed)
    holds = list(holds)
    rng.shuffle(holds)
    need = sum(h + 1 for h in holds)
    room = (n_bars - 1) - first - need
    if room < 0:
        raise ValueError("Za mało świec na losowe transakcje bez nakładania.")
    gaps = np.sort(rng.integers(0, room + 1, size=len(holds)))
    trades, used = [], 0
    for gap, hold in zip(gaps, holds):
        entry = first + int(gap) + used
        trades.append((entry, entry + hold))
        used += hold + 1
    return trades


def control_signals(bars: pd.DataFrame, entry_level: float) -> pd.DataFrame:
    real = base.trades_in_bars(base.signals(bars, entry_level, base.EXIT_LEVEL))
    holds = [exit_bar - entry_bar for entry_bar, exit_bar in real]
    trades = random_trades(len(bars), holds, first=base.SMA_LENGTH)

    buy = np.zeros(len(bars), dtype=bool)
    exit_long = np.zeros(len(bars), dtype=bool)
    for entry_bar, exit_bar in trades:
        buy[entry_bar] = True
        exit_long[exit_bar] = True

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = False
    result["exit_long"] = exit_long
    return result


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return control_signals(bars, ENTRY_LEVEL)


def indicators(bars: pd.DataFrame) -> dict:
    return base.indicators(bars, ENTRY_LEVEL, base.EXIT_LEVEL)
