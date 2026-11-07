import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema


NAME = "Second Entry (H2/L2)"

# Autor gra na wykresie 2000 ticków (futures). W danych Dukascopy
# tick to zmiana kwotowania, nie transakcja — świece czasowe.
TIMEFRAMES = ["1min", "5min"]

# Pozycja kończy się na SL albo TP. Sygnały przy otwartej pozycji
# są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Od autora: EMA 21, TP 1:1, SL za świecą sygnałową.
EMA_LENGTH = 21
RR_RATIO = 1.0


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Daytrading (thefakeab), „From 45% to 75% Win Rate”:
    „Entry: pullback + second entry setup (higher low in uptrend /
    lower high in downtrend). Stop: just beyond the signal bar.
    Target: usually 1:1 RR”, EMA 21 jako kierunek.

    „Second entry” to setup H2 / L2 Ala Brooksa (autor: „I started by
    reading the second entry books”). Dla longów (shorty lustrzanie):

    1. Trend: EMA 21 rośnie.
    2. Cofnięcie zaczyna świeca z high niższym niż poprzednie.
    3. H1: pierwsza świeca cofnięcia z high wyższym niż poprzednie —
       pierwsza próba (wg autora „fake-out”, nie gramy).
    4. Po H1 kolejna świeca z niższym high = druga noga cofnięcia.
       Jej dołek musi być wyżej niż dołek pierwszej nogi
       („higher low”).
    5. Świeca sygnałowa: wzrostowa, zamknięcie w górnej połowie
       (definicja Brooksa). Buy stop nad jej high, ważny przez
       następną świecę; bez wypełnienia ponawiany, dopóki setup trwa.
    6. SL pod low świecy sygnałowej, TP 1:1 od ceny zlecenia.

    Setup kasuje: nowy szczyt nad początkiem cofnięcia przed H2,
    dołek drugiej nogi pod dołkiem pierwszej, koniec trendu
    (EMA przestaje rosnąć) albo przebicie high świecy (H2) — wtedy
    zlecenie albo weszło, albo setup przepadł.

    Pominięte (uznaniowe u autora): gra w konsolidacji, linie
    trendu, S/R, „runner” po TP.

    Wyjście:
        buy, sell, entry_stop, stop_loss, take_profit.
    """
    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    average = ema(bars["close"], EMA_LENGTH).to_numpy(dtype=float)
    n = len(bars)

    buy = np.zeros(n, dtype=bool)
    sell = np.zeros(n, dtype=bool)
    entry = np.full(n, np.nan)
    stop_loss = np.full(n, np.nan)
    take_profit = np.full(n, np.nan)

    for side in (1, -1):
        # Shorty: ceny odwrócone (−low jako high), jedna logika.
        if side == 1:
            h, l, o, c, m = high, low, open_, close, average
        else:
            h, l, o, c, m = -low, -high, -open_, -close, -average

        state = "idle"      # idle → leg1 → leg2
        top = leg1_low = leg2_low = np.nan

        for i in range(1, n):
            if np.isnan(m[i]) or np.isnan(m[i - 1]):
                continue

            trend = m[i] > m[i - 1]
            higher = h[i] > h[i - 1]
            lower = h[i] < h[i - 1]

            if not trend:
                state = "idle"
                continue

            if state == "idle":
                if lower:
                    state, top, leg1_low = "leg1", h[i - 1], l[i]
                continue

            if state == "leg1":
                if higher:
                    if h[i] > top:
                        # Nowy szczyt — cofnięcie się skończyło.
                        state = "idle"
                    else:
                        state, leg2_low = "h1", np.inf
                else:
                    leg1_low = min(leg1_low, l[i])
                continue

            if state == "h1":
                # Po H1 czekamy na niższe high (druga noga).
                if h[i] > top:
                    state = "idle"
                    continue
                if lower:
                    state = "leg2"
                    leg2_low = l[i]
                else:
                    continue

            elif state == "leg2":
                if higher:
                    # H2 — zlecenie z poprzedniej świecy weszło albo
                    # setup przepadł; zaczynamy od nowa.
                    state = "idle"
                    continue
                leg2_low = min(leg2_low, l[i])

            if leg2_low <= leg1_low:
                # Brak "higher low".
                state = "idle"
                continue

            # Świeca sygnałowa: wzrostowa, zamknięcie w górnej połowie.
            if c[i] > o[i] and c[i] >= (h[i] + l[i]) / 2 and h[i] > l[i]:
                risk = h[i] - l[i]
                if side == 1:
                    buy[i] = True
                else:
                    sell[i] = True
                entry[i] = h[i] * side
                stop_loss[i] = l[i] * side
                take_profit[i] = (h[i] + RR_RATIO * risk) * side

    # Gdyby long i short wypadły na tej samej świecy — pomijamy.
    both = buy & sell
    buy[both] = sell[both] = False
    entry[both] = stop_loss[both] = take_profit[both] = np.nan

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    result["entry_stop"] = entry
    result["stop_loss"] = stop_loss
    result["take_profit"] = take_profit
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """
    EMA 21 na cenie, zlecenia stop (H2 / L2) jako kropki.
    Panel: zmiana EMA 21 na świecę (> 0 = trend wzrostowy, < 0 = spadkowy).
    """
    signals = generate_signals(bars)
    average = ema(bars["close"], EMA_LENGTH)
    slope = average.diff()
    top = float(np.nanmax(np.abs(slope.to_numpy()))) if slope.notna().any() else 1.0
    return {
        "trend": None,
        "overlays": [
            (f"EMA {EMA_LENGTH}", average, "#FF9800"),
        ],
        "markers": [
            ("Buy stop (H2)", signals["entry_stop"].where(signals["buy"]), "#00D084", "above"),
            ("Sell stop (L2)", signals["entry_stop"].where(signals["sell"]), "#FF3B30", "below"),
        ],
        "panel": {
            "title": f"Nachylenie EMA {EMA_LENGTH}",
            "lines": [("Zmiana EMA", slope, "#7E57C2")],
            "levels": (0,),
            "range": (-top * 1.05 or -1.0, top * 1.05 or 1.0),
        },
    }
