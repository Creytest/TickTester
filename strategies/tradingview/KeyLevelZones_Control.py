"""
Grupa kontrolna dla Key Level Zones (KeyLevelZones.py).

Te same transakcje co strategia: tyle samo wejść, te same kierunki
(long / short), to samo wyjście po HOLD_BARS świecach, 100% kapitału
i te same koszty — tylko momenty wejścia są losowe. Jeśli strategia
nie wypada lepiej od grupy kontrolnej, dotknięcie strefy nic nie
dodaje ponad sam kierunek i czas trzymania.

Losowanie ma stałe ziarno (SEED), więc wynik jest powtarzalny.
Wykres pokazuje strefy wskaźnika, ale wejścia są losowe.
"""

import numpy as np
import pandas as pd

from strategies.tradingview import KeyLevelZones as base


NAME = "Key Level Zones – grupa kontrolna"

TIMEFRAMES = base.TIMEFRAMES
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"
EQUITY_FRACTION = 1.0

SEED = 42


def random_entries(bars: pd.DataFrame, entries, hold: int, seed: int = SEED):
    """
    Tyle samo wejść co `entries`, z tymi samymi kierunkami w losowej
    kolejności, w losowych świecach od pierwszego dnia ze strefami,
    bez nakładania się pozycji: odstęp między wejściami >= hold + 1.
    """
    n = len(entries)
    if n == 0:
        return []

    days = base._cached_days(bars)
    first = int(bars.index.searchsorted(days[0]["t0"])) if days else 0
    last = len(bars) - 1 - hold
    step = hold + 1
    room = last - first - (n - 1) * step
    if room < 0:
        raise ValueError("Za mało świec na losowe wejścia bez nakładania.")

    rng = np.random.default_rng(seed)
    offsets = np.sort(rng.integers(0, room + 1, size=n))
    bars_at = first + offsets + np.arange(n) * step
    dirs = np.array([d for _, d in entries])
    rng.shuffle(dirs)
    return list(zip(bars_at.tolist(), dirs.tolist()))


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    hold = base.HOLD_BARS
    real = base.take_entries(base._entries(bars), hold)
    return base.signals_frame(bars, random_entries(bars, real, hold), hold)


def indicators(bars: pd.DataFrame) -> dict:
    return base.indicators(bars)
