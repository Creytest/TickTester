"""
Punkt odniesienia dla Efficiency Weighted Hull (EfficiencyWeightedHull.py).

Ta sama strategia (zawsze w rynku, odwrócenie na flipie, 100% kapitału,
te same koszty), ale stan trendu liczony ze STANDARDOWEGO Hulla:
WMA(2 × WMA(close, 17) − WMA(close, 34), 6), z tą samą martwą strefą
(slope z 2 świec, próg = 0,20 × EMA(|zmiana 1-świecowa|, 20)).
Autor liczy standardowego Hulla w tym samym skrypcie (Data Window).

Jeśli wersja z Efficiency Ratio nie wypada lepiej od tej, adaptacyjna
kompensacja nic nie dodaje ponad zwykłego Hulla.
"""

import pandas as pd

from strategies.tradingview import EfficiencyWeightedHull as base


NAME = "Efficiency Weighted Hull – standardowy Hull"

TIMEFRAMES = base.TIMEFRAMES
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"
EQUITY_FRACTION = 1.0


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return base.signals_from(bars, "std")


def indicators(bars: pd.DataFrame) -> dict:
    return base.indicators_for(bars, "std")
