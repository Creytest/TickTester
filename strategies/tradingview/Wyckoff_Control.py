"""
Grupa kontrolna dla Wyckoff (LunqFX) (Wyckoff.py).

Te same transakcje co strategia: tyle samo wejść, te same kierunki
(long / short), te same odległości SL i TP w ATR(50) od ceny
zamknięcia świecy wejścia, to samo wygaśnięcie (wyjście po
max_leg + 1 świecach), 1% ryzyka i te same koszty — tylko momenty
wejścia są losowe. Jeśli strategia nie wypada lepiej od grupy
kontrolnej, schemat Wyckoffa nic nie dodaje ponad sam kierunek
i geometrię SL / TP.

Losowanie ma stałe ziarno (SEED), więc wynik jest powtarzalny.
Pozycje się nie nakładają: wyjście każdej losowej transakcji jest
szacowane na świecach (knot dotyka SL / TP albo wygaśnięcie) i następne
wejście musi być później. Wykres pokazuje schematy wskaźnika, ale
wejścia są losowe — nie mają z nimi związku.
"""

import numpy as np
import pandas as pd

from strategies.tradingview import Wyckoff as base
from strategies.tiktok.SR_Retest import atr as atr_rma


NAME = "Wyckoff (LunqFX) – grupa kontrolna"

TIMEFRAMES = base.TIMEFRAMES
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

SEED = 42
MAX_TRIES = 200


def _bar_exit(high, low, j, d, sl, tp, expiry):
    """Pierwsza świeca po j, na której knot dotyka SL lub TP (albo wygaśnięcie)."""
    end = min(j + expiry, len(high) - 1)
    if end <= j:
        return end
    h, lo = high[j + 1:end + 1], low[j + 1:end + 1]
    hit = (lo <= sl) | (h >= tp) if d == 1 else (h >= sl) | (lo <= tp)
    k = np.flatnonzero(hit)
    return j + 1 + int(k[0]) if len(k) else end


def random_entries(bars: pd.DataFrame, real: list[dict], seed: int = SEED):
    n = len(real)
    if n == 0:
        return []

    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    atr = atr_rma(bars, base.ATR_LEN)
    valid = np.flatnonzero(~np.isnan(atr))
    first = int(valid[0]) if len(valid) else 0
    last = len(bars) - 2
    if last <= first:
        return []

    expiry = {**base.DEFAULTS, **base.PARAMS}["max_leg"] + 1
    rng = np.random.default_rng(seed)
    # Geometria każdej prawdziwej transakcji w ATR, w losowej kolejności.
    geo = [
        (e["dir"], (e["close"] - e["sl"]) * e["dir"] / e["atr"],
         (e["tp"] - e["close"]) * e["dir"] / e["atr"])
        for e in real
    ]
    order = rng.permutation(n)

    taken, busy = [], []   # busy: (wejście, wyjście)
    for k in order:
        d, sl_atr, tp_atr = geo[k]
        for _ in range(MAX_TRIES):
            j = int(rng.integers(first, last + 1))
            sl = close[j] - d * sl_atr * atr[j]
            tp = close[j] + d * tp_atr * atr[j]
            x = _bar_exit(high, low, j, d, sl, tp, expiry)
            if all(x < a or j > b for a, b in busy):
                busy.append((j, x))
                taken.append({
                    "bar": j, "dir": d, "sl": sl, "tp": tp,
                    "exit_bar": j + expiry if j + expiry < len(bars) else None,
                })
                break
    return sorted(taken, key=lambda e: e["bar"])


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return base.signals_frame(bars, random_entries(bars, base.trades(bars)))


def indicators(bars: pd.DataFrame) -> dict:
    return base.indicators(bars)
