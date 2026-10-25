
import numpy as np
import pandas as pd


NAME = "BigBeluga Two-Pole + Stochastic 7,3,3"

# Sygnały przy otwartej pozycji są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"


def generate_signals(
    bars: pd.DataFrame,
    length: int = 34,
    damping: float = 0.9,
    period_k: int = 7,
    smooth_k: int = 3,
    period_d: int = 3,
    rr_ratio: float = 2.0,
) -> pd.DataFrame:
    """
    BigBeluga Two-Pole Trend Filter + Stochastic 7,3,3.

    Wejście:
        DataFrame z kolumnami open, high, low, close.

    Wyjście:
        buy, sell, stop_loss, take_profit.
    """

    required = {"open", "high", "low", "close"}
    missing = required - set(bars.columns)

    if missing:
        raise ValueError(f"Brak kolumn OHLC: {sorted(missing)}")

    if length < 1 or period_k < 1 or smooth_k < 1 or period_d < 1:
        raise ValueError("Długości wskaźników muszą być dodatnie.")

    if not 0.1 <= damping <= 1.0:
        raise ValueError("damping musi należeć do zakresu 0.1–1.0.")

    if rr_ratio <= 0:
        raise ValueError("rr_ratio musi być dodatnie.")

    result = pd.DataFrame(index=bars.index)
    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)

    # Two-Pole Trend Filter — rekurencja zgodna z Pine Script.
    omega = 2.0 * np.pi / length
    alpha = damping * omega
    beta = omega ** 2

    f1 = np.zeros(len(bars), dtype=float)
    f2 = np.zeros(len(bars), dtype=float)
    prices = close.to_numpy()

    for i in range(len(bars)):
        previous_f1 = f1[i - 1] if i > 0 else 0.0
        previous_f2 = f2[i - 1] if i > 0 else 0.0

        f1[i] = previous_f1 + alpha * (prices[i] - previous_f1)
        f2[i] = previous_f2 + beta * (f1[i] - previous_f2)

    trend_filter = pd.Series(f2, index=bars.index)

    up = trend_filter > trend_filter.shift(2)
    down = trend_filter < trend_filter.shift(2)

    # Stochastic 7,3,3.
    lowest_low = low.rolling(period_k, min_periods=period_k).min()
    highest_high = high.rolling(period_k, min_periods=period_k).max()
    price_range = highest_high - lowest_low

    raw_k = 100.0 * (close - lowest_low) / price_range
    raw_k = raw_k.where(price_range != 0)

    k = raw_k.rolling(smooth_k, min_periods=smooth_k).mean()
    d = k.rolling(period_d, min_periods=period_d).mean()

    # Odpowiedniki ta.crossover() i ta.crossunder().
    cross_up = (k > d) & (k.shift(1) <= d.shift(1))
    cross_down = (k < d) & (k.shift(1) >= d.shift(1))

    long_signal = up & cross_up & (k < 20)
    short_signal = down & cross_down & (k > 80)

    result["buy"] = long_signal.fillna(False).astype(bool)
    result["sell"] = short_signal.fillna(False).astype(bool)

    # SL i TP wyznaczone z ceny zamknięcia świecy sygnałowej.
    long_sl = low
    long_distance = close - long_sl
    long_tp = close + long_distance * rr_ratio

    short_sl = high
    short_distance = short_sl - close
    short_tp = close - short_distance * rr_ratio

    result["stop_loss"] = np.nan
    result["take_profit"] = np.nan

    valid_long = result["buy"] & (long_distance > 0)
    valid_short = result["sell"] & (short_distance > 0)

    result.loc[valid_long, "stop_loss"] = long_sl[valid_long]
    result.loc[valid_long, "take_profit"] = long_tp[valid_long]

    result.loc[valid_short, "stop_loss"] = short_sl[valid_short]
    result.loc[valid_short, "take_profit"] = short_tp[valid_short]

    # Nie przekazujemy sygnału, jeśli odległość do SL jest zerowa.
    invalid_long = result["buy"] & ~(long_distance > 0)
    invalid_short = result["sell"] & ~(short_distance > 0)

    result.loc[invalid_long | invalid_short, ["buy", "sell"]] = False

    return result


def indicators(bars: pd.DataFrame) -> dict:
    """Linie do wykresów: Two-Pole na cenie, Stochastic w panelu."""
    close = bars["close"].astype(float).to_numpy()

    length = 34
    damping = 0.9

    omega = 2.0 * np.pi / length
    alpha = damping * omega
    beta = omega ** 2

    f1 = 0.0
    f2 = 0.0
    f2_values = []

    for price in close:
        f1 = f1 + alpha * (price - f1)
        f2 = f2 + beta * (f1 - f2)
        f2_values.append(f2)

    trend = pd.Series(f2_values, index=bars.index, name="Two-Pole Filter")

    lowest_low = bars["low"].rolling(7, min_periods=7).min()
    highest_high = bars["high"].rolling(7, min_periods=7).max()
    price_range = highest_high - lowest_low

    raw_k = (
        100.0 * (bars["close"] - lowest_low) / price_range
    ).where(price_range != 0)

    k = raw_k.rolling(3, min_periods=3).mean()
    d = k.rolling(3, min_periods=3).mean()

    return {
        "trend": trend,
        "panel": {
            "title": "Stochastic",
            "lines": [("%K", k, "blue"), ("%D", d, "darkorange")],
            "levels": (20, 80),
        },
    }
