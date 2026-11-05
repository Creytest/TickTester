"""
Grupa kontrolna dla Efficiency Weighted Hull (EfficiencyWeightedHull.py).

Tyle samo odwróceń co strategia, naprzemiennie long / short (pierwszy
long, jak pierwszy flip strategii), zawsze w rynku, 100% kapitału
i te same koszty — tylko momenty odwróceń są losowe (od pierwszej
świecy z gotowym wskaźnikiem do końca danych). Jeśli strategia nie
wypada lepiej od grupy kontrolnej, flipy Hulla nie dają przewagi
ponad samo bycie w rynku z taką samą liczbą transakcji.

Losowanie ma stałe ziarno (SEED), więc wynik jest powtarzalny.
Wykres pokazuje Hulla, ale znaczniki to losowe wejścia.
"""

import numpy as np
import pandas as pd

from strategies.tradingview_porownawcze import EfficiencyWeightedHull as base


NAME = "Efficiency Weighted Hull – grupa kontrolna"

TIMEFRAMES = base.TIMEFRAMES
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"
EQUITY_FRACTION = 1.0

SEED = 42


def random_flips(bars: pd.DataFrame, seed: int = SEED) -> pd.DataFrame:
    real = base.signals_from(bars, "ewh")
    count = int(real["buy"].sum() + real["sell"].sum())

    n = len(bars)
    buy = np.zeros(n, dtype=bool)
    sell = np.zeros(n, dtype=bool)
    if count == 0:
        return pd.DataFrame({"buy": buy, "sell": sell}, index=bars.index)

    hull = base.cached(bars)["hull"]
    first = int(np.flatnonzero(~np.isnan(hull))[0])
    # Ostatnia świeca odpada: sygnał na niej nie zdąży się wykonać.
    candidates = np.arange(first, n - 1)
    if len(candidates) < count:
        raise ValueError("Za mało świec na losowe odwrócenia.")

    rng = np.random.default_rng(seed)
    at = np.sort(rng.choice(candidates, size=count, replace=False))
    buy[at[0::2]] = True
    sell[at[1::2]] = True
    return pd.DataFrame({"buy": buy, "sell": sell}, index=bars.index)


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return random_flips(bars)


def indicators(bars: pd.DataFrame) -> dict:
    return base.indicators_for(bars, "ewh", signals=random_flips(bars))
