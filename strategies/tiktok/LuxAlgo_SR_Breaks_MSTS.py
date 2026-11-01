import numpy as np
import pandas as pd


NAME = "LuxAlgo S/R Breaks + Market Structure Trailing Stop"

# Wyjście wyłącznie na trailing stopie: sygnały przy otwartej
# pozycji (w obie strony) są pomijane, bez dokładania pozycji.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# 4h pominięte: za mało transakcji.
TIMEFRAMES = ["15min", "30min", "1h"]


# ============================================================
# FUNKCJE ZGODNE Z PINE SCRIPT
# ============================================================

def pivot_high(source: pd.Series, left: int, right: int) -> pd.Series:
    """
    Odpowiednik ta.pivothigh(left, right): wartość szczytu sprzed
    `right` świec, zwracana na świecy, na której jest potwierdzony.
    Szczyt musi być wyższy od świec po lewej i nie niższy od
    świec po prawej.
    """
    return _pivot(source, left, right, high=True)


def pivot_low(source: pd.Series, left: int, right: int) -> pd.Series:
    """Odpowiednik ta.pivotlow(left, right)."""
    return _pivot(source, left, right, high=False)


def _pivot(source: pd.Series, left: int, right: int, high: bool) -> pd.Series:
    values = source.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)
    size = left + right + 1

    if len(values) < size:
        return pd.Series(out, index=source.index)

    windows = np.lib.stride_tricks.sliding_window_view(values, size)
    center = windows[:, left]
    left_side = windows[:, :left]
    right_side = windows[:, left + 1:]

    if high:
        is_pivot = (
            (left_side < center[:, None]).all(axis=1)
            & (right_side <= center[:, None]).all(axis=1)
        )
    else:
        is_pivot = (
            (left_side > center[:, None]).all(axis=1)
            & (right_side >= center[:, None]).all(axis=1)
        )

    out[size - 1:] = np.where(is_pivot, center, np.nan)
    return pd.Series(out, index=source.index)


def ema(source: pd.Series, length: int) -> pd.Series:
    """Odpowiednik ta.ema(): start od średniej prostej z `length` świec."""
    values = source.to_numpy(dtype=float)
    out = np.full(len(values), np.nan)

    if len(values) < length:
        return pd.Series(out, index=source.index)

    alpha = 2.0 / (length + 1)
    out[length - 1] = values[:length].mean()

    for i in range(length, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]

    return pd.Series(out, index=source.index)


# ============================================================
# MARKET STRUCTURE TRAILING STOP [LuxAlgo]
# ============================================================

def market_structure_trailing_stop(
    bars: pd.DataFrame,
    length: int = 14,
    incr: float = 100.0,
    reset_on: str = "CHoCH",
) -> pd.Series:
    """
    Linia trailing stopu, przepisana świeca po świecy z Pine Script.

    NaN tak jak `na` w Pine: linia pojawia się dopiero po pierwszej
    zmianie struktury (CHoCH), a math.max/min z `na` daje `na`.
    """
    close = bars["close"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)

    ph = pivot_high(bars["high"], length, length).to_numpy()
    pl = pivot_low(bars["low"], length, length).to_numpy()

    ph_y = pl_y = np.nan
    ph_x = pl_x = 0
    ph_cross = pl_cross = False
    top = btm = np.nan
    max_close = min_close = np.nan
    ts = np.nan
    os = 0

    out = np.full(len(close), np.nan)

    for n in range(len(close)):
        ms = 0

        if not np.isnan(ph[n]):
            ph_y = ph[n]
            ph_x = n - length
            ph_cross = False

        if not np.isnan(pl[n]):
            pl_y = pl[n]
            pl_x = n - length
            pl_cross = False

        # Struktura wzrostowa: zamknięcie nad ostatnim szczytem.
        if close[n] > ph_y and not ph_cross:
            if reset_on == "CHoCH":
                ms = 1 if os == -1 else 0
            else:
                ms = 1

            ph_cross = True
            os = 1
            btm = low[ph_x + 1:n + 1].min()

        # Struktura spadkowa: zamknięcie pod ostatnim dołkiem.
        if close[n] < pl_y and not pl_cross:
            if reset_on == "CHoCH":
                ms = -1 if os == 1 else 0
            else:
                ms = -1

            pl_cross = True
            os = -1
            top = high[pl_x + 1:n + 1].max()

        prev_max = max_close
        prev_min = min_close

        if ms == 1:
            max_close = close[n]
        elif ms == -1:
            min_close = close[n]
        else:
            # np.maximum/np.minimum przenoszą NaN jak math.max w Pine.
            max_close = np.maximum(close[n], max_close)
            min_close = np.minimum(close[n], min_close)

        if ms == 1:
            ts = btm
        elif ms == -1:
            ts = top
        elif os == 1:
            ts = ts + (max_close - prev_max) * incr / 100
        else:
            ts = ts + (min_close - prev_min) * incr / 100

        out[n] = ts

    return pd.Series(out, index=bars.index, name="Trailing Stop")


# ============================================================
# SUPPORT AND RESISTANCE LEVELS WITH BREAKS [LuxAlgo]
# ============================================================

def support_resistance_breaks(
    bars: pd.DataFrame,
    left_bars: int = 15,
    right_bars: int = 15,
    volume_thresh: float = 20.0,
) -> pd.DataFrame:
    """
    Zielone B (wybicie oporu) i czerwone B (wybicie wsparcia)
    z filtrem wolumenu. Etykiety Bull Wick / Bear Wick pomijamy —
    autor wchodzi tylko na B.
    """
    open_ = bars["open"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    close = bars["close"].astype(float)

    # fixnan(pivothigh(...)[1]) — ostatni znany poziom.
    resistance = pivot_high(high, left_bars, right_bars).shift(1).ffill()
    support = pivot_low(low, left_bars, right_bars).shift(1).ffill()

    short_vol = ema(bars["volume"], 5)
    long_vol = ema(bars["volume"], 10)
    osc = 100 * (short_vol - long_vol) / long_vol

    # Odpowiedniki crossover() i crossunder().
    cross_up = (close > resistance) & (close.shift(1) <= resistance.shift(1))
    cross_down = (close < support) & (close.shift(1) >= support.shift(1))

    bull = cross_up & ~(open_ - low > close - open_) & (osc > volume_thresh)
    bear = cross_down & ~(open_ - close < high - open_) & (osc > volume_thresh)

    return pd.DataFrame(
        {
            "bull_break": bull.fillna(False).astype(bool),
            "bear_break": bear.fillna(False).astype(bool),
            "resistance": resistance,
            "support": support,
            "volume_osc": osc,
        },
        index=bars.index,
    )


# ============================================================
# STRATEGIA
# ============================================================

def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Wejście: long na zielonym B, short na czerwonym B
    (Support and Resistance Levels with Breaks, 15/15, wolumen 20).
    Wyjście: wyłącznie linia Market Structure Trailing Stop
    (14, 100%, CHoCH), aktualizowana na zamknięciu każdej świecy.

    Wolumen: liczba ticków w świecy (kolumna volume).

    Jeśli linia trailing stopu jest po złej stronie ceny (dla
    longa nad zamknięciem), sygnał jest pomijany — pozycja
    zamknęłaby się na pierwszym ticku i nie da się wyznaczyć
    wielkości pozycji przy 1% ryzyka.

    Wyjście:
        buy, sell, stop_loss, trail_long, trail_short.
    """
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(bars.columns)

    if missing:
        raise ValueError(f"Brak kolumn świec: {sorted(missing)}")

    close = bars["close"].astype(float)
    ts = market_structure_trailing_stop(bars)
    breaks = support_resistance_breaks(bars)

    buy = breaks["bull_break"] & (ts < close)
    sell = breaks["bear_break"] & (ts > close)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy.fillna(False).astype(bool)
    result["sell"] = sell.fillna(False).astype(bool)
    result["stop_loss"] = ts.where(result["buy"] | result["sell"])
    result["trail_long"] = ts
    result["trail_short"] = ts

    return result


def indicators(bars: pd.DataFrame) -> dict:
    """
    Linie do wykresów: trailing stop na cenie, oscylator wolumenu
    i wszystkie etykiety B jak w TradingView (również te, przy
    których linia trailing stopu była po złej stronie ceny).

    Opór i wsparcie: poziom obowiązujący na danej świecy, czyli
    ten, który zamknięcie musi przebić, żeby powstało B. Przy
    zmianie poziomu linia jest przerwana, jak w LuxAlgo.
    """
    breaks = support_resistance_breaks(bars)

    def segments(level: pd.Series) -> pd.Series:
        return level.where(level == level.shift(1))

    return {
        "trend": market_structure_trailing_stop(bars),
        "overlays": [
            ("Opór", segments(breaks["resistance"]), "#FF0000"),
            ("Wsparcie", segments(breaks["support"]), "#233DEE"),
        ],
        "panel": {
            "title": "Volume osc %",
            "lines": [("Volume osc", breaks["volume_osc"], "#7E57C2")],
            "levels": (20,),
        },
        "labels": [
            ("B long", breaks["bull_break"], "B", "#089981", "below"),
            ("B short", breaks["bear_break"], "B", "#F23645", "above"),
        ],
    }
