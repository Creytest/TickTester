import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema
from strategies.tiktok.SR_Retest import atr


NAME = "EMA 9/19 scalping"

# Od autora: wykres 1-minutowy.
TIMEFRAMES = ["1min"]

# Pozycja kończy się na SL, TP albo break even. Sygnały przy
# otwartej pozycji są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Od autora: EMA 9 i EMA 19, TP 1:2–1:3 (bierzemy 2), SL na
# wejściu, gdy zysk dojdzie do 1:1.
FAST = 9
SLOW = 19
RR_RATIO = 2.0
BREAK_EVEN_RR = 1.0

# Od autora: "I only trade the first 30 minutes of the NY open"
# (9:30–10:00 NY = 16:30–17:00 w czasie danych, NY + 7 h).
# Autor dodaje "But it does work in all sessions at all times" —
# SESSION_ONLY = False sprawdza tę wersję.
SESSION_ONLY = True
SESSION_START = "16:30"
SESSION_END = "17:00"

# Nasze założenia (autor nie podaje liczb):
# "consistently above both EMAs" — 3 ostatnie zamknięcia nad obiema
# EMA (short: pod obiema).
TREND_BARS = 3
# "just below the 19 EMA" — 0,1 × ATR(14) za EMA 19.
SL_BUFFER_ATR = 0.1
# "If it's too wide, skip the trade" — autor ma SL 5–15 pkt NQ,
# czyli ok. 1–1,5 × ATR(14) z 1 minuty. Pomijamy SL > 1,5 × ATR.
MAX_SL_ATR = 1.5
# Filtr "momentum" przy dotyku autor ocenia na oko — pomijamy.


def _minutes(index: pd.DatetimeIndex) -> np.ndarray:
    return (index.hour * 60 + index.minute).to_numpy()


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def setup(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Poziomy zlecenia na następną świecę, liczone na zamknięciu
    bieżącej.

    Dotyk EMA 9: EMA liczona na żywo w trakcie świecy równa się
    cenie dokładnie wtedy, gdy cena równa się EMA 9 z zamknięcia
    poprzedniej świecy (EMA_t = EMA_t-1 + α·(cena − EMA_t-1)).
    Wejście na dotyku = poziom EMA 9 z tej świecy, bez przybliżeń.

    EMA 19 w chwili dotyku liczymy tak samo: EMA19 + α19·(EMA9 − EMA19).
    """
    close = bars["close"].astype(float)
    fast = ema(close, FAST)
    slow = ema(close, SLOW)
    vol = pd.Series(atr(bars, 14), index=bars.index)

    above = (close > fast) & (close > slow)
    below = (close < fast) & (close < slow)
    trend_up = above.astype(int).rolling(TREND_BARS).sum() == TREND_BARS
    trend_down = below.astype(int).rolling(TREND_BARS).sum() == TREND_BARS

    alpha_slow = 2.0 / (SLOW + 1)
    slow_at_touch = slow + alpha_slow * (fast - slow)
    buffer = SL_BUFFER_ATR * vol

    return pd.DataFrame(
        {
            "fast": fast,
            "slow": slow,
            "atr": vol,
            "trend_up": trend_up & (fast > slow),
            "trend_down": trend_down & (fast < slow),
            "sl_long": slow_at_touch - buffer,
            "sl_short": slow_at_touch + buffer,
        },
        index=bars.index,
    )


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Daytrading, „I'm Getting a Lot of Questions About My
    Strategy – Here's the Breakdown”:

    Trend: cena stale nad obiema EMA → tylko longi, pod obiema →
    tylko shorty. Wejście: retest EMA 9 — rynkowo, gdy świeca jej
    dotknie, bez czekania na zamknięcie. SL tuż za EMA 19, zbyt
    szeroki SL = brak transakcji. TP 1:2, przy 1:1 SL na wejście.
    Tylko pierwsze 30 minut sesji NY (SESSION_ONLY).

    Na zamknięciu świecy ze spełnionym trendem wystawiamy zlecenie
    na dotyk EMA 9, ważne przez następną świecę (entry_touch).

    Wyjście:
        buy, sell, entry_touch, stop_loss, take_profit, break_even.
    """
    s = setup(bars)
    level = s["fast"]
    risk_long = level - s["sl_long"]
    risk_short = s["sl_short"] - level
    max_risk = MAX_SL_ATR * s["atr"]

    buy = s["trend_up"] & (risk_long > 0) & (risk_long <= max_risk)
    sell = s["trend_down"] & (risk_short > 0) & (risk_short <= max_risk)

    if SESSION_ONLY:
        # Świeca, w której może dojść do dotyku, to następna.
        step = bars.index.to_series().diff().median()
        if pd.isna(step):
            step = pd.Timedelta("1min")
        minute = _minutes(bars.index + step)
        start, end = _to_minutes(SESSION_START), _to_minutes(SESSION_END)
        in_session = (minute >= start) & (minute < end)
        buy &= in_session
        sell &= in_session

    buy = buy.fillna(False)
    sell = sell.fillna(False)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    result["entry_touch"] = np.where(buy | sell, level, np.nan)
    result["stop_loss"] = np.where(
        buy, s["sl_long"], np.where(sell, s["sl_short"], np.nan)
    )
    result["take_profit"] = np.where(
        buy,
        level + RR_RATIO * risk_long,
        np.where(sell, level - RR_RATIO * risk_short, np.nan),
    )
    result["break_even"] = np.where(
        buy,
        level + BREAK_EVEN_RR * risk_long,
        np.where(sell, level - BREAK_EVEN_RR * risk_short, np.nan),
    )
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """Na cenie EMA 9 i EMA 19. Panel: ATR(14)."""
    s = setup(bars)
    top = float(np.nanmax(s["atr"].to_numpy())) if s["atr"].notna().any() else 1.0
    return {
        "trend": None,
        "overlays": [
            (f"EMA {FAST}", s["fast"], "#00D084"),
            (f"EMA {SLOW}", s["slow"], "#FF3B30"),
        ],
        "panel": {
            "title": "ATR (14)",
            "lines": [("ATR", s["atr"], "#7E57C2")],
            "levels": (),
            "range": (0, top * 1.05 or 1.0),
        },
    }
