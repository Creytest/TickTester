"""
Grupa kontrolna dla Squeeze Breakout Signals [bitpunk]
(SqueezeBreakoutSignals.py).

Te same transakcje co strategia: tyle samo wejść, te same kierunki
(long / short), te same odległości SL i TP od ceny zamknięcia świecy
wejścia, liczone w średnim TR (SMA TR 20 z poprzedniej świecy — tak
jak zamrożony TR pudełka), 1% ryzyka i te same koszty — tylko momenty
wejścia są losowe. Jeśli strategia nie wypada lepiej od grupy
kontrolnej, kompresja i wybicie nic nie dodają ponad sam kierunek
i geometrię SL / TP.

Losowanie ma stałe ziarno (SEED), więc wynik jest powtarzalny.
Pozycje się nie nakładają: wyjście każdej losowej transakcji jest
szacowane na świecach (knot dotyka SL / TP) i następne wejście musi
być później. Wykres pokazuje pudełka wskaźnika, ale wejścia są
losowe — nie mają z nimi związku.
"""

import numpy as np
import pandas as pd

from strategies.tradingview import SqueezeBreakoutSignals as base


NAME = "Squeeze Breakout Signals [bitpunk] – grupa kontrolna"

TIMEFRAMES = base.TIMEFRAMES
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

SEED = 42
MAX_TRIES = 200


def random_entries(bars: pd.DataFrame, real: list[dict], seed: int = SEED):
    n = len(real)
    if n == 0:
        return []

    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    length = {**base.DEFAULTS, **base.PARAMS}["length"]
    *_, scale, _, _ = base._indicator_series(bars, length)
    prior = np.concatenate(([np.nan], scale[:-1]))   # scale[1] jak w Pine
    valid = np.flatnonzero(~np.isnan(prior) & (prior > 0))
    first = int(valid[0]) if len(valid) else 0
    last = len(bars) - 2
    if last <= first:
        return []

    rng = np.random.default_rng(seed)
    # Geometria każdej prawdziwej transakcji w średnim TR, w losowej kolejności.
    geo = [
        (e["dir"], (e["close"] - e["sl"]) * e["dir"] / e["scale"],
         (e["tp"] - e["close"]) * e["dir"] / e["scale"])
        for e in real
    ]
    order = rng.permutation(n)

    taken, busy = [], []   # busy: (wejście, wyjście)
    for k in order:
        d, sl_tr, tp_tr = geo[k]
        for _ in range(MAX_TRIES):
            j = int(rng.integers(first, last + 1))
            sl = close[j] - d * sl_tr * prior[j]
            tp = close[j] + d * tp_tr * prior[j]
            x = base.bar_exit(high, low, j, d, sl, tp)
            x = len(bars) if x is None else x
            if all(x < a or j > b for a, b in busy):
                busy.append((j, x))
                taken.append({"bar": j, "dir": d, "sl": sl, "tp": tp, "exit_bar": None})
                break
    return sorted(taken, key=lambda e: e["bar"])


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return base.signals_frame(bars, random_entries(bars, base.trades(bars)))


def indicators(bars: pd.DataFrame) -> dict:
    return base.indicators(bars)
