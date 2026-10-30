import numpy as np
import pandas as pd

from strategies.tiktok.SR_Retest import atr


NAME = "New ATH + ATR trailing"

# Tylko long. Pozycja kończy się wyłącznie na trailing stopie,
# nowe szczyty przy otwartej pozycji są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Autor podał "2-3 ATR" — bierzemy górną granicę. Domyślne ATR
# z TradingView (14).
ATR_LENGTH = 14
ATR_MULT = 3.0

# Najwyższa cena (Bid) w danych sprzed rozgrzewki. Ustawia ją
# plot_tick_backtest_xauusd.main przed backtestem, żeby szczyt był
# naprawdę historyczny, a nie tylko z wczytanego okresu.
# None: szczyt liczony tylko z wczytanych świec.
HISTORY_HIGH = None


def all_time_high(bars: pd.DataFrame) -> pd.Series:
    """Szczyt wszech czasów sprzed danej świecy (bez niej)."""
    previous = bars["high"].astype(float).cummax().shift(1)

    if HISTORY_HIGH is not None:
        previous = previous.fillna(-np.inf).clip(lower=HISTORY_HIGH)

    return previous


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Daytrading (DecentStudent2888): "Buy new all time
    highs. Set trailing stop at 2-3 ATR".

    Wejście: zamknięcie powyżej dotychczasowego szczytu wszech czasów.
    Wyjście: trailing stop = najwyższe high od wejścia − 3 × ATR(14),
    przesuwany tylko w górę.

    Stop zależy od chwili wejścia, więc pozycję śledzimy tu na
    świecach, tak jak silnik na tickach: stop z zamknięcia świecy
    obowiązuje od następnej, a świece są z cen Bid, więc low świecy
    poniżej stopu oznacza wyjście w silniku.

    Wyjście:
        buy, sell, stop_loss, trail_long.
    """
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    distance = ATR_MULT * atr(bars, ATR_LENGTH)
    new_high = close > all_time_high(bars).to_numpy(dtype=float)

    trail = np.full(len(bars), np.nan)
    stop = np.nan

    for i in range(len(bars)):
        # Wyjście na stopie z poprzedniej świecy.
        if not np.isnan(stop) and low[i] <= stop:
            stop = np.nan

        if np.isnan(stop):
            if new_high[i] and not np.isnan(distance[i]):
                stop = high[i] - distance[i]
        else:
            stop = max(stop, high[i] - distance[i])

        trail[i] = stop

    buy = new_high & ~np.isnan(distance)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = False
    result["stop_loss"] = np.where(buy, trail, np.nan)
    result["trail_long"] = trail
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """Na cenie: szczyt wszech czasów i trailing stop. W panelu ATR."""
    signals = generate_signals(bars)
    atr_line = pd.Series(atr(bars, ATR_LENGTH), index=bars.index)
    return {
        "trend": None,
        "overlays": [
            ("Szczyt wszech czasów", all_time_high(bars), "#4C8DFF"),
            ("Trailing stop 3 ATR", signals["trail_long"], "#FF3B30"),
        ],
        "panel": {
            "title": f"ATR({ATR_LENGTH})",
            "lines": [
                (f"ATR {ATR_LENGTH}", atr_line, "#7E57C2"),
            ],
            "levels": (),
            "range": (0, float(np.nanmax(atr_line)) * 1.1 if atr_line.notna().any() else 1.0),
        },
    }
