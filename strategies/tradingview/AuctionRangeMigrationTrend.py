"""
Auction Range Migration Trend [SchizoQuant] (TradingView Community Scripts):
https://www.tradingview.com/script/QTeLijEz-Auction-Range-Migration-Trend-SchizoQuant/
© SchizoQuant, oryginał na licencji MPL 2.0 (https://mozilla.org/MPL/2.0/);
ten plik jest portem i podlega tej samej licencji.

Port 1:1 wskaźnika (Pine v6, indicator, ustawienia domyślne):

1. ATR(14) (RMA z true range); safeATR = max(ATR albo high-low, mintick).
2. Migracja: ruch środka świecy (high+low)/2 i ruch zamknięcia,
   oba / safeATR, ważone 0,35 / 0,65.
3. Overlap: część wspólna z poprzednią świecą / większy z dwóch
   zakresów (0..1); rangeExpansion = 1 - overlap.
4. Nowe terytorium: zamknięcie nad poprzednim high (+) lub pod
   poprzednim low (-), / safeATR, max 1; waga 0,45.
5. auctionDrive = migracja * (1 + 0,5 * expansion) + terytorium * 0,45,
   obcięte do ±2.
6. trendScore = 0,6 * EMA20(drive) + 0,4 * EMA13(głos ±1/0),
   głos = drive > 0,03 → +1, < -0,03 → -1.
7. Próg = 0,19 + 0,25 * max(0, (EMA2(overlap) - 0,30) / 0,70).
8. Stan: na pierwszej gotowej świecy (bar_index >= 20) kierunek
   = znak trendScore, BEZ sygnału. Potem LONG, gdy stan spadkowy
   i trendScore > próg; SHORT, gdy stan wzrostowy i trendScore < -próg.
   Tylko na zamkniętych świecach.

"Auction Migration Path" to wyłącznie rysunek (nie wpływa na sygnały).

Wskaźnik nie ma SL, TP ani reguł wyjścia. Nasza interpretacja
(założenie): zawsze w rynku — LONG otwiera long i zamyka short,
SHORT odwrotnie. Wejście na otwarciu następnej świecy. Pozycja
od pierwszego sygnału (stan początkowy bez sygnału nie otwiera
transakcji, jak na wykresie autora). Bez SL → 100% kapitału.

Autor nie podaje interwału ani rynku.
"""

import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema
from strategies.tiktok.SR_Retest import atr


NAME = "Auction Range Migration Trend"

TIMEFRAMES = ["15min", "1h", "4h"]

# Sygnały naprzemienne (stan wskaźnika), więc przeciwny = odwrócenie.
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału z kapitalizacją.
EQUITY_FRACTION = 1.0

# Najmniejsza zmiana ceny (syminfo.mintick). Ustawiana przez
# plot_tick_backtest_xauusd.py z TICK_SIZE w tick_config.py.
TICK = 0.01

# Ustawienia domyślne skryptu.
ATR_LENGTH = 14
CENTER_INFLUENCE = 0.35
TERRITORY_INFLUENCE = 0.45
SHOCK_LIMIT = 2.0
DRIVE_LENGTH = 20
PERSISTENCE_LENGTH = 13
MINIMUM_MIGRATION = 0.03
PERSISTENCE_INFLUENCE = 0.40
REVERSAL_THRESHOLD = 0.19
OVERLAP_LENGTH = 2
OVERLAP_PROTECTION = 0.25


# ============================================================
# Obliczenia wskaźnika
# ============================================================

def compute(bars: pd.DataFrame) -> dict:
    """Wszystkie serie wskaźnika w kolejności z Pine."""
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    idx = bars.index
    n = len(bars)
    tick = TICK

    def prev(a):
        # nz(x[1], x): na pierwszej świecy bieżąca wartość.
        return np.concatenate((a[:1], a[:-1]))

    atr_value = atr(bars, ATR_LENGTH)
    safe_atr = np.maximum(np.where(np.isnan(atr_value), high - low, atr_value), tick)

    range_center = (high + low) * 0.5
    center_movement = (range_center - prev(range_center)) / safe_atr
    closing_movement = (close - prev(close)) / safe_atr
    directional_migration = (
        center_movement * CENTER_INFLUENCE
        + closing_movement * (1.0 - CENTER_INFLUENCE)
    )

    prev_high, prev_low = prev(high), prev(low)
    overlap_distance = np.maximum(np.minimum(high, prev_high) - np.maximum(low, prev_low), 0.0)
    current_range = np.maximum(high - low, tick)
    previous_range = np.maximum(prev_high - prev_low, tick)
    overlap_ratio = np.minimum(overlap_distance / np.maximum(current_range, previous_range), 1.0)
    range_expansion = 1.0 - overlap_ratio

    bullish_territory = np.where(close > prev_high, np.minimum((close - prev_high) / safe_atr, 1.0), 0.0)
    bearish_territory = np.where(close < prev_low, np.minimum((prev_low - close) / safe_atr, 1.0), 0.0)
    accepted_territory = bullish_territory - bearish_territory

    raw_drive = (
        directional_migration * (1.0 + range_expansion * 0.50)
        + accepted_territory * TERRITORY_INFLUENCE
    )
    auction_drive = np.clip(raw_drive, -SHOCK_LIMIT, SHOCK_LIMIT)

    migration_pressure = ema(pd.Series(auction_drive, index=idx), DRIVE_LENGTH).to_numpy()
    vote = np.where(auction_drive > MINIMUM_MIGRATION, 1.0,
                    np.where(auction_drive < -MINIMUM_MIGRATION, -1.0, 0.0))
    persistence = ema(pd.Series(vote, index=idx), PERSISTENCE_LENGTH).to_numpy()
    trend_score = (
        migration_pressure * (1.0 - PERSISTENCE_INFLUENCE)
        + persistence * PERSISTENCE_INFLUENCE
    )

    average_overlap = ema(pd.Series(overlap_ratio, index=idx), OVERLAP_LENGTH).to_numpy()
    congestion = np.maximum(0.0, (average_overlap - 0.30) / 0.70)
    threshold = REVERSAL_THRESHOLD + congestion * OVERLAP_PROTECTION

    # Ścieżka aukcji (tylko rysunek).
    path_speed = 0.12 + 0.38 * range_expansion
    path = np.empty(n)
    for i in range(n):
        path[i] = range_center[i] if i == 0 else path[i - 1] + path_speed[i] * (range_center[i] - path[i - 1])

    # Stan SQ: 0 → znak trendScore bez sygnału, potem odwrócenia.
    warmup = max(ATR_LENGTH, DRIVE_LENGTH, PERSISTENCE_LENGTH, OVERLAP_LENGTH)
    state = np.zeros(n, dtype=int)
    long_signal = np.zeros(n, dtype=bool)
    short_signal = np.zeros(n, dtype=bool)
    sq = 0
    for i in range(n):
        ready = i >= warmup and not np.isnan(atr_value[i]) and not np.isnan(trend_score[i])
        if ready:
            if sq == 0:
                sq = 1 if trend_score[i] >= 0.0 else -1
            elif sq == -1 and trend_score[i] > threshold[i]:
                sq = 1
                long_signal[i] = True
            elif sq == 1 and trend_score[i] < -threshold[i]:
                sq = -1
                short_signal[i] = True
        state[i] = sq

    return {
        "trend_score": trend_score,
        "threshold": threshold,
        "state": state,
        "long": long_signal,
        "short": short_signal,
        "path": path,
        "ready_from": warmup,
    }


# ============================================================
# Sygnały
# ============================================================

def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """buy = trójkąt LONG, sell = trójkąt SHORT (po zamknięciu świecy)."""
    c = compute(bars)
    result = pd.DataFrame(index=bars.index)
    result["buy"] = c["long"]
    result["sell"] = c["short"]
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """Ścieżka aukcji w kolorze stanu, LONG/SHORT, trendScore z progiem w panelu."""
    c = compute(bars)
    idx = bars.index
    path = pd.Series(c["path"], index=idx)
    path.iloc[:c["ready_from"]] = np.nan
    state = pd.Series(c["state"], index=idx)
    # Odcinek łączy się z poprzednią świecą, żeby linia nie miała dziur.
    bull = path.where((state == 1) | (state.shift(-1) == 1))
    bear = path.where((state == -1) | (state.shift(-1) == -1))
    score = pd.Series(c["trend_score"], index=idx)
    thr = pd.Series(c["threshold"], index=idx)
    return {
        "trend": None,
        "overlays": [
            ("Auction path (wzrost)", bull, "#39FF14"),
            ("Auction path (spadek)", bear, "#8A2BE2"),
        ],
        "markers": [
            ("LONG", bars["low"].where(c["long"]), "#00D084", "below"),
            ("SHORT", bars["high"].where(c["short"]), "#FF3B30", "above"),
        ],
        "panel": {
            "title": "Auction Trend Score i próg odwrócenia",
            "lines": [
                ("Trend score", score, "#F2F2F2"),
                ("+próg", thr, "#00D084"),
                ("-próg", -thr, "#FF3B30"),
            ],
            "levels": (0,),
        },
    }
