import numpy as np
import pandas as pd

from strategies.tiktok.tick_CloudMA_EMA30_74 import ema


NAME = "EMA 9 × VWAP"

# Autor pokazuje strategię na 30 minutach (day trading).
TIMEFRAMES = ["30min"]

# Tylko shorty. Brak SL i TP: przecięcie w górę zamyka shorta
# (exit_short), bez otwierania longa.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału
# z kapitalizacją.
EQUITY_FRACTION = 1.0


def session_vwap(bars: pd.DataFrame) -> pd.Series:
    """
    Odpowiednik ta.vwap(hlc3) z kotwicą "Session" w TradingView:
    średnia hlc3 ważona wolumenem, liczona od początku sesji.

    Sesja = doba w czasie danych (GMT+2 / GMT+3 z DST USA), czyli
    od 17:00 w Nowym Jorku — tak jak dzienna sesja FX w TV.
    Wolumen: liczba ticków w świecy.
    """
    hlc3 = (bars["high"] + bars["low"] + bars["close"]).astype(float) / 3
    volume = bars["volume"].astype(float)
    session = bars.index.normalize()

    weighted = (hlc3 * volume).groupby(session).cumsum()
    total = volume.groupby(session).cumsum()
    return (weighted / total).rename("VWAP")


def generate_signals(bars: pd.DataFrame, length: int = 9) -> pd.DataFrame:
    """
    Short: EMA 9 przecina VWAP od góry.
    Wyjście: EMA 9 przecina VWAP od dołu. Brak SL i TP, brak longów.

    Wyjście:
        buy (zawsze False), sell, exit_short.
    """
    required = {"high", "low", "close", "volume"}
    missing = required - set(bars.columns)

    if missing:
        raise ValueError(f"Brak kolumn świec: {sorted(missing)}")

    fast = ema(bars["close"], length)
    vwap = session_vwap(bars)

    # Odpowiedniki ta.crossover() i ta.crossunder().
    cross_up = (fast > vwap) & (fast.shift(1) <= vwap.shift(1))
    sell = (fast < vwap) & (fast.shift(1) >= vwap.shift(1))

    result = pd.DataFrame(index=bars.index)
    result["buy"] = False
    result["sell"] = sell.fillna(False).astype(bool)
    result["exit_short"] = cross_up.fillna(False).astype(bool)
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """EMA 9 i VWAP na cenie, odległość EMA od VWAP w panelu."""
    fast = ema(bars["close"], 9)
    vwap = session_vwap(bars)
    spread = 100 * (fast - vwap) / vwap
    limit = 1.0

    if spread.notna().any():
        limit = float(np.nanmax(np.abs(spread.to_numpy()))) * 1.05 or 1.0

    # VWAP przerwany na początku każdej sesji, jak w TradingView.
    day = pd.Series(bars.index.normalize(), index=bars.index)
    new_session = day != day.shift(1)

    return {
        "trend": None,
        "overlays": [
            ("VWAP", vwap.where(~new_session), "#F2C200"),
            ("EMA 9", fast, "#FF3B30"),
        ],
        "panel": {
            "title": "EMA 9 − VWAP (%)",
            "lines": [("Różnica %", spread, "#7E57C2")],
            "levels": (0,),
            "range": (-limit, limit),
        },
    }
