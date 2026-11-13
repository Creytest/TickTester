import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema


NAME = "EMA 9 × VWAP"

# Autor pokazuje strategię na 30 minutach (day trading).
TIMEFRAMES = ["15min", "1h", "4h"]

# Tylko shorty. Brak SL i TP: przecięcie w górę zamyka shorta
# (exit_short), bez otwierania longa.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału
# z kapitalizacją.
EQUITY_FRACTION = 1.0


# Kotwica VWAP (nasze założenie, autor jej nie podaje):
#   "none"    — VWAP ciągły, bez resetu: liczony od pierwszej świecy
#               danych (początek rozgrzewki przed testem). Domyślnie
#               (Kamil, 2026-11-13): sesyjny VWAP na 4h ma 1–6 świec na
#               sesję, skacze za ceną i daje sztuczne przecięcia.
#   "session" — reset na początku każdej sesji (doba w czasie danych,
#               od 17:00 w Nowym Jorku), jak domyślny VWAP w TradingView.
#   "week"    — reset na początku tygodnia (poniedziałek 00:00 w czasie
#               danych = niedziela 17:00 NY), jak kotwica "Week" w TV.
#   "month"   — reset na początku miesiąca, jak kotwica "Month" w TV.
# Uwaga: ciągły VWAP z czasem robi się bardzo wolny (średnia z całej
# historii), więc wynik zależy od daty startu danych.
VWAP_ANCHOR = "none"

# Rozgrzewka = 300 świec, czyli 3 dni na 15 min i 50 dni na 4h. Przy
# ciągłym VWAP to także jego punkt startu, więc wyrównujemy rozgrzewkę
# do 50 dni na każdym interwale: VWAP startuje w tym samym dniu
# (START_DATE − 50 dni) na 15 min, 1h i 4h.
# Przy CHUNK_YEARS VWAP startuje od nowa w każdym kawałku.
WARMUP_DAYS = 50

_ANCHORS = ("none", "session", "week", "month")


def _anchor_groups(index: pd.DatetimeIndex, anchor: str) -> pd.Series:
    """Etykieta okresu kotwicy dla każdej świecy (zmiana = reset VWAP)."""
    naive = index.tz_localize(None) if index.tz is not None else index

    if anchor == "none":
        labels = np.zeros(len(index), dtype=np.int64)
    elif anchor == "session":
        labels = index.normalize()
    elif anchor == "week":
        # Tydzień od poniedziałku (W-SUN = tydzień kończy się w niedzielę).
        labels = naive.to_period("W-SUN")
    elif anchor == "month":
        labels = naive.to_period("M")
    else:
        raise ValueError(f"VWAP_ANCHOR musi być jednym z {_ANCHORS}, jest {anchor!r}")

    return pd.Series(np.asarray(labels), index=index)


def vwap(bars: pd.DataFrame, anchor: str | None = None) -> pd.Series:
    """
    Odpowiednik ta.vwap(hlc3) w TradingView: średnia hlc3 ważona
    wolumenem, liczona od początku okresu kotwicy (VWAP_ANCHOR).

    Sesja = doba w czasie danych (GMT+2 / GMT+3 z DST USA), czyli
    od 17:00 w Nowym Jorku — tak jak dzienna sesja FX w TV.
    Wolumen: liczba ticków w świecy.
    """
    anchor = VWAP_ANCHOR if anchor is None else anchor
    hlc3 = (bars["high"] + bars["low"] + bars["close"]).astype(float) / 3
    volume = bars["volume"].astype(float)
    groups = _anchor_groups(bars.index, anchor)

    weighted = (hlc3 * volume).groupby(groups).cumsum()
    total = volume.groupby(groups).cumsum()
    return (weighted / total).rename("VWAP")


def session_vwap(bars: pd.DataFrame) -> pd.Series:
    """VWAP z resetem na początku każdej sesji (kotwica "session")."""
    return vwap(bars, "session")


def generate_signals(bars: pd.DataFrame, length: int = 9) -> pd.DataFrame:
    """
    Short: EMA 9 przecina VWAP od góry (VWAP wg VWAP_ANCHOR,
    domyślnie ciągły).
    Wyjście: EMA 9 przecina VWAP od dołu. Brak SL i TP, brak longów.

    Wyjście:
        buy (zawsze False), sell, exit_short.
    """
    required = {"high", "low", "close", "volume"}
    missing = required - set(bars.columns)

    if missing:
        raise ValueError(f"Brak kolumn świec: {sorted(missing)}")

    fast = ema(bars["close"], length)
    line = vwap(bars)

    # Odpowiedniki ta.crossover() i ta.crossunder().
    cross_up = (fast > line) & (fast.shift(1) <= line.shift(1))
    sell = (fast < line) & (fast.shift(1) >= line.shift(1))

    result = pd.DataFrame(index=bars.index)
    result["buy"] = False
    result["sell"] = sell.fillna(False).astype(bool)
    result["exit_short"] = cross_up.fillna(False).astype(bool)
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """EMA 9 i VWAP na cenie, odległość EMA od VWAP w panelu."""
    fast = ema(bars["close"], 9)
    line = vwap(bars)
    spread = 100 * (fast - line) / line
    limit = 1.0

    if spread.notna().any():
        limit = float(np.nanmax(np.abs(spread.to_numpy()))) * 1.05 or 1.0

    # Przy kotwicy linia VWAP przerwana na każdym resecie, jak w TV.
    # Ciągły VWAP rysowany bez przerw.
    groups = _anchor_groups(bars.index, VWAP_ANCHOR)
    new_period = (groups != groups.shift(1)) & (VWAP_ANCHOR != "none")
    label = "VWAP" if VWAP_ANCHOR == "none" else f"VWAP ({VWAP_ANCHOR})"

    return {
        "trend": None,
        "overlays": [
            (label, line.where(~new_period), "#F2C200"),
            ("EMA 9", fast, "#FF3B30"),
        ],
        "panel": {
            "title": "EMA 9 − VWAP (%)",
            "lines": [("Różnica %", spread, "#7E57C2")],
            "levels": (0,),
            "range": (-limit, limit),
        },
    }
