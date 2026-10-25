
import numpy as np
import pandas as pd


NAME = "RSI 6 (80/20) RR 2:1"

# Zachowanie przy otwartej pozycji, jak w oryginale Pine Script:
# strategy.entry w drugą stronę odwraca pozycję, a ponowne
# strategy.exit z tym samym id przestawia SL i TP.
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "update_exits"


def rsi(close: pd.Series, length: int) -> pd.Series:
    """
    Odpowiednik ta.rsi() z Pine Script: średnie RMA (Wildera),
    pierwsza wartość to średnia prosta z `length` zmian.
    """
    change = close.astype(float).diff().to_numpy()
    up = np.maximum(change, 0.0)
    down = np.maximum(-change, 0.0)

    def rma(values: np.ndarray) -> np.ndarray:
        out = np.full(len(values), np.nan)
        alpha = 1.0 / length

        # Pierwsza zmiana jest na drugiej świecy (indeks 1).
        if len(values) <= length:
            return out

        out[length] = values[1:length + 1].mean()

        for i in range(length + 1, len(values)):
            out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]

        return out

    up_rma = rma(up)
    down_rma = rma(down)

    with np.errstate(divide="ignore", invalid="ignore"):
        values = 100.0 - 100.0 / (1.0 + up_rma / down_rma)

    values = np.where(down_rma == 0, 100.0, values)
    values = np.where((up_rma == 0) & (down_rma != 0), 0.0, values)
    values = np.where(np.isnan(up_rma), np.nan, values)

    return pd.Series(values, index=close.index, name="RSI")


def generate_signals(
    bars: pd.DataFrame,
    rsi_length: int = 6,
    upper_band: float = 80.0,
    lower_band: float = 20.0,
    rr_ratio: float = 2.0,
) -> pd.DataFrame:
    """
    RSI Reversal Strategy 6 (80/20) RR 2:1.

    Long: RSI przecina w górę 20 (ta.crossover).
    Short: RSI przecina w dół 80 (ta.crossunder).
    SL na low / high świecy sygnałowej, TP = 2 × ryzyko,
    liczone od ceny zamknięcia świecy sygnałowej.

    Wejście:
        DataFrame z kolumnami open, high, low, close.

    Wyjście:
        buy, sell, stop_loss, take_profit.
    """

    required = {"open", "high", "low", "close"}
    missing = required - set(bars.columns)

    if missing:
        raise ValueError(f"Brak kolumn OHLC: {sorted(missing)}")

    if rsi_length < 1:
        raise ValueError("rsi_length musi być dodatnie.")

    if rr_ratio <= 0:
        raise ValueError("rr_ratio musi być dodatnie.")

    result = pd.DataFrame(index=bars.index)
    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)

    value = rsi(close, rsi_length)
    previous = value.shift(1)

    # Odpowiedniki ta.crossover() i ta.crossunder().
    long_signal = (value > lower_band) & (previous <= lower_band)
    short_signal = (value < upper_band) & (previous >= upper_band)

    result["buy"] = long_signal.fillna(False).astype(bool)
    result["sell"] = short_signal.fillna(False).astype(bool)

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

    # Zamknięcie na samym low / high daje ryzyko 0 — nie da się
    # policzyć wielkości pozycji przy 1% ryzyka, więc pomijamy.
    invalid_long = result["buy"] & ~(long_distance > 0)
    invalid_short = result["sell"] & ~(short_distance > 0)

    result.loc[invalid_long | invalid_short, ["buy", "sell"]] = False

    return result


def indicators(bars: pd.DataFrame) -> dict:
    """Linie do wykresów: RSI w dolnym panelu."""
    return {
        "trend": None,
        "panel": {
            "title": "RSI 6",
            "lines": [("RSI", rsi(bars["close"], 6), "#7E57C2")],
            "levels": (20, 80),
        },
    }
