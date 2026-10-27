import numpy as np
import pandas as pd

from strategies.tick_LuxAlgo_SR_Breaks_MSTS import pivot_high, pivot_low


NAME = "SFP+Volume"

# Autor testuje tylko na 30 minutach.
TIMEFRAMES = ["30min"]

# Pozycja kończy się na SL albo TP. Sygnały przy otwartej
# pozycji (w obie strony) są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"


# ============================================================
# SWING FAILURE PATTERN [LuxAlgo]
# ============================================================

def swing_failure_pattern(bars: pd.DataFrame, length: int = 5) -> pd.DataFrame:
    """
    Przepisane świeca po świecy z Pine Script, ustawienia domyślne:
    Swings 5, Validation 'None' (bez filtra wolumenu z LTF).

    Bearish SFP: knot powyżej ostatniego swing high, open i close
    pod nim. Linia potwierdzenia: najniższy low między swingiem
    a świecą SFP. ▼ — pierwsze zamknięcie pod tą linią, zanim
    zamknięcie wróci nad swing high (wtedy wzór jest unieważniony).
    Bullish SFP i ▲ odwrotnie.

    Wyjście: kolumny sfp_bear, sfp_bull (etykieta SFP),
    confirm_bear (▼), confirm_bull (▲), oppos_bear, oppos_bull
    (aktywna linia potwierdzenia na danej świecy).
    """
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    size = len(close)

    # ta.pivothigh(len, 1): szczyt sprzed jednej świecy.
    ph = pivot_high(bars["high"], length, 1).to_numpy()
    pl = pivot_low(bars["low"], length, 1).to_numpy()

    sfp_bear = np.zeros(size, dtype=bool)
    sfp_bull = np.zeros(size, dtype=bool)
    confirm_bear = np.zeros(size, dtype=bool)
    confirm_bull = np.zeros(size, dtype=bool)
    oppos_bear = np.full(size, np.nan)
    oppos_bull = np.full(size, np.nan)

    # Ostatni swing i aktywny wzór (piv w Pine) dla obu stron.
    swh_prc, swh_bix = np.nan, 0
    swl_prc, swl_bix = np.nan, 0
    h_swing = h_oppos = np.nan
    h_bix = 0
    h_active = h_confirmed = False
    l_swing = l_oppos = np.nan
    l_bix = 0
    l_active = l_confirmed = False

    for n in range(size):
        # ---------------- Bearish ----------------
        if not np.isnan(ph[n]):
            swh_bix = n - 1
            swh_prc = ph[n]

        sw, bx = swh_prc, swh_bix
        if high[n] > sw and open_[n] < sw and close[n] < sw:
            # Najniższy low świec między swingiem a SFP.
            oppos = sw
            if n - bx - 1 >= 1:
                oppos = min(sw, low[bx + 1:n].min())

            sfp_bear[n] = True
            h_swing, h_bix, h_oppos = sw, bx, oppos
            h_active, h_confirmed = True, False

        if h_active and not h_confirmed:
            oppos_bear[n] = h_oppos
            if close[n] < h_oppos:
                h_confirmed = True
                confirm_bear[n] = True

        if n - h_bix > 500 or close[n] > h_swing:
            h_active = False

        # ---------------- Bullish ----------------
        if not np.isnan(pl[n]):
            swl_bix = n - 1
            swl_prc = pl[n]

        sw, bx = swl_prc, swl_bix
        if low[n] < sw and open_[n] > sw and close[n] > sw:
            oppos = sw
            if n - bx - 1 >= 1:
                oppos = max(sw, high[bx + 1:n].max())

            sfp_bull[n] = True
            l_swing, l_bix, l_oppos = sw, bx, oppos
            l_active, l_confirmed = True, False

        if l_active and not l_confirmed:
            oppos_bull[n] = l_oppos
            if close[n] > l_oppos:
                l_confirmed = True
                confirm_bull[n] = True

        if n - l_bix > 500 or close[n] < l_swing:
            l_active = False

    return pd.DataFrame(
        {
            "sfp_bear": sfp_bear,
            "sfp_bull": sfp_bull,
            "confirm_bear": confirm_bear,
            "confirm_bull": confirm_bull,
            "oppos_bear": oppos_bear,
            "oppos_bull": oppos_bull,
        },
        index=bars.index,
    )


# ============================================================
# VOLUME DELTA CANDLES [LuxAlgo]
# ============================================================

def volume_delta(bars: pd.DataFrame) -> pd.Series:
    """
    Delta wolumenu: wolumen świec 1-minutowych wzrostowych minus
    spadkowych (kolumna delta z build_bars, wolumen tickowy).
    Ustawienia domyślne LuxAlgo: LTF auto = interwał / 1500,
    nie mniej niż 1 minuta — dla 30 min to 1 minuta.

    Wypełnienie świecy jest zielone przy delcie dodatniej,
    czerwone przy ujemnej (niezależnie od koloru samej świecy).
    """
    return bars["delta"].astype(float)


# ============================================================
# STRATEGIA
# ============================================================

def generate_signals(bars: pd.DataFrame, rr_ratio: float = 2.0) -> pd.DataFrame:
    """
    Short: ▼ (potwierdzony bearish SFP) na świecy z czerwoną
    deltą (delta < 0). Long: ▲ na świecy z zieloną deltą.

    SL na high świecy sygnałowej (dla longa low), TP = 2 × ryzyko,
    liczone od ceny zamknięcia świecy sygnałowej — jak na filmie
    autora. Wielkość pozycji: 1% kapitału ryzykowany przy SL.

    Wyjście:
        buy, sell, stop_loss, take_profit.
    """
    required = {"open", "high", "low", "close", "delta"}
    missing = required - set(bars.columns)

    if missing:
        raise ValueError(f"Brak kolumn świec: {sorted(missing)}")

    sfp = swing_failure_pattern(bars)
    delta = volume_delta(bars)

    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    close = bars["close"].astype(float)

    # Zamknięcie na samym high / low daje ryzyko 0 — nie da się
    # policzyć wielkości pozycji przy 1% ryzyka, więc pomijamy.
    buy = sfp["confirm_bull"] & (delta > 0) & (close > low)
    sell = sfp["confirm_bear"] & (delta < 0) & (close < high)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    result["stop_loss"] = np.where(buy, low, np.where(sell, high, np.nan))
    result["take_profit"] = np.where(
        buy,
        close + (close - low) * rr_ratio,
        np.where(sell, close - (high - close) * rr_ratio, np.nan),
    )
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """
    Etykiety SFP i ▼/▲ jak w TradingView, linie potwierdzenia
    na cenie, delta wolumenu w panelu.
    """
    sfp = swing_failure_pattern(bars)
    delta = volume_delta(bars)
    norm = 100 * delta / bars["volume"].astype(float)

    # Wypełnienie korpusu jak Volume Delta Candles (full bar):
    # pasek o wysokości |delta| / wolumen korpusu, zielony przy
    # delcie dodatniej (od dołu korpusu), czerwony przy ujemnej
    # (od góry). Ramka i knot zostają w kolorze ceny.
    open_ = bars["open"].astype(float)
    close = bars["close"].astype(float)
    body = (open_ - close).abs()
    low_body = np.minimum(open_, close)
    high_body = np.maximum(open_, close)
    share = (delta / bars["volume"].astype(float)).abs()
    positive = delta > 0

    fill = {
        "base": low_body.where(positive, high_body),
        "value": (low_body + share * body).where(
            positive, high_body - share * body
        ),
        "color": pd.Series(
            np.where(positive, "#089981", "#F23645"), index=bars.index
        ),
    }

    return {
        "trend": None,
        "candle_fill": fill,
        "overlays": [
            ("Potwierdzenie short", sfp["oppos_bear"], "#F23645"),
            ("Potwierdzenie long", sfp["oppos_bull"], "#089981"),
        ],
        "panel": {
            "title": "Volume Delta % (delta / wolumen)",
            "lines": [("Delta %", norm, "#7E57C2")],
            "levels": (0,),
            "range": (-100, 100),
        },
        "labels": [
            ("SFP short", sfp["sfp_bear"], "SFP", "#F23645", "above"),
            ("SFP long", sfp["sfp_bull"], "SFP", "#089981", "below"),
            ("▼", sfp["confirm_bear"], "▼", "#F23645", "above"),
            ("▲", sfp["confirm_bull"], "▲", "#089981", "below"),
        ],
    }
