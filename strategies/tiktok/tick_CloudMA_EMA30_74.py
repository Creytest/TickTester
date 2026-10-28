import numpy as np
import pandas as pd


NAME = "Cloud MA EMA 30/74 + SL na swingu"

# Przeciwny trójkąt zamyka pozycję i otwiera odwrotną.
# Ten sam kierunek nie wystąpi dwa razy z rzędu (przecięcia
# średnich naprzemiennie), więc SAME_SIGNAL nie ma znaczenia.
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"


def ema(source: pd.Series, length: int) -> pd.Series:
    """Odpowiednik ema() z Pine Script: start od średniej prostej."""
    values = source.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)

    if len(values) < length:
        return pd.Series(out, index=source.index)

    alpha = 2.0 / (length + 1)
    out[length - 1] = values[:length].mean()

    for i in range(length, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]

    return pd.Series(out, index=source.index)


def moving_averages(
    bars: pd.DataFrame,
    length_ma1: int = 30,
    length_ma2: int = 74,
) -> tuple[pd.Series, pd.Series]:
    """BEST Cloud ALL MA (Daveatt), ustawienia domyślne: EMA z close."""
    close = bars["close"].astype(float)
    return ema(close, length_ma1), ema(close, length_ma2)


def generate_signals(
    bars: pd.DataFrame,
    length_ma1: int = 30,
    length_ma2: int = 74,
) -> pd.DataFrame:
    """
    Long: zielony trójkąt — EMA 30 przecina w górę EMA 74.
    Short: czerwony trójkąt — EMA 30 przecina w dół EMA 74.

    SL: najniższy low (dla shorta najwyższy high) od świecy po
    poprzednim przeciwnym trójkącie do świecy sygnałowej, czyli
    skrajny punkt ruchu przed przecięciem — tak jak żółta linia
    na screenach autora. Brak TP. Przeciwny trójkąt odwraca
    pozycję.

    Wyjście:
        buy, sell, stop_loss.
    """
    required = {"open", "high", "low", "close"}
    missing = required - set(bars.columns)

    if missing:
        raise ValueError(f"Brak kolumn OHLC: {sorted(missing)}")

    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)

    ma1, ma2 = moving_averages(bars, length_ma1, length_ma2)
    prev1 = ma1.shift(1)
    prev2 = ma2.shift(1)

    # cond_buy = MA1 > MA2 and crossover(MA1, MA2), analogicznie short.
    buy = ((ma1 > ma2) & (prev1 <= prev2)).to_numpy()
    sell = ((ma1 < ma2) & (prev1 >= prev2)).to_numpy()

    stop_loss = np.full(len(bars), np.nan)
    buy_idx = np.flatnonzero(buy)
    sell_idx = np.flatnonzero(sell)

    for i in buy_idx:
        # Poprzedni czerwony trójkąt przed tą świecą.
        k = np.searchsorted(sell_idx, i) - 1
        if k >= 0:
            stop_loss[i] = low[sell_idx[k] + 1:i + 1].min()

    for i in sell_idx:
        k = np.searchsorted(buy_idx, i) - 1
        if k >= 0:
            stop_loss[i] = high[buy_idx[k] + 1:i + 1].max()

    # Bez poprzedniego sygnału albo przy SL po złej stronie
    # zamknięcia nie da się policzyć 1% ryzyka — pomijamy.
    valid_long = buy & (stop_loss < close)
    valid_short = sell & (stop_loss > close)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = valid_long
    result["sell"] = valid_short
    result["stop_loss"] = np.where(
        valid_long | valid_short, stop_loss, np.nan
    )
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """EMA 30 i EMA 74 na cenie, różnica średnich w panelu."""
    ma1, ma2 = moving_averages(bars)
    spread = 100 * (ma1 - ma2) / ma2
    # Symetryczna skala panelu wokół zera.
    limit = 1.0

    if spread.notna().any():
        limit = float(np.nanmax(np.abs(spread.to_numpy()))) * 1.05 or 1.0

    return {
        "trend": None,
        "overlays": [
            ("EMA 30", ma1, "#00D084"),
            ("EMA 74", ma2, "#FF3B30"),
        ],
        "panel": {
            "title": "EMA 30 − EMA 74 (%)",
            "lines": [("Różnica EMA %", spread, "#7E57C2")],
            "levels": (0,),
            "range": (-limit, limit),
        },
    }
