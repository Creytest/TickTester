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
    return _compute(bars)[
        ["buy", "sell", "entry_stop", "stop_loss", "take_profit"]
    ]


def _compute(bars: pd.DataFrame) -> pd.DataFrame:
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
    # Pierwsze odbicie (H1 / L1) setupów, które dały sygnał — tylko do
    # wykresu, nie gramy go.
    first = {1: np.zeros(n, dtype=bool), -1: np.zeros(n, dtype=bool)}
    # Linie korekt (zygzak po skrajnych cenach) — też tylko do wykresu:
    # pierwsza = szczyt przed cofnięciem → dołek 1. nogi → high H1,
    # druga = high H1 → dołek 2. nogi → high świecy sygnałowej.
    leg_lines = {
        key: np.full(n, np.nan)
        for key in ("first_leg", "second_leg_long", "second_leg_short")
    }

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
                    top_bar, leg1_bar = i - 1, i
                continue

            if state == "leg1":
                if higher:
                    if h[i] > top:
                        # Nowy szczyt — cofnięcie się skończyło.
                        state = "idle"
                    else:
                        state, leg2_low = "h1", np.inf
                        h1_bar = i
                elif l[i] < leg1_low:
                    leg1_low, leg1_bar = l[i], i
                continue

            if state == "h1":
                # Po H1 czekamy na niższe high (druga noga).
                if h[i] > top:
                    state = "idle"
                    continue
                if lower:
                    state = "leg2"
                    leg2_low, leg2_bar = l[i], i
                else:
                    continue

            elif state == "leg2":
                if higher:
                    # H2 — zlecenie z poprzedniej świecy weszło albo
                    # setup przepadł; zaczynamy od nowa.
                    state = "idle"
                    continue
                if l[i] < leg2_low:
                    leg2_low, leg2_bar = l[i], i

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
                first[side][h1_bar] = True
                _zigzag(
                    leg_lines["first_leg"],
                    [(top_bar, top), (leg1_bar, leg1_low), (h1_bar, h[h1_bar])],
                    side,
                )
                _zigzag(
                    leg_lines["second_leg_long" if side == 1 else "second_leg_short"],
                    [(h1_bar, h[h1_bar]), (leg2_bar, leg2_low), (i, h[i])],
                    side,
                )
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
    result["first_long"] = first[1]
    result["first_short"] = first[-1]
    for key, line in leg_lines.items():
        result[key] = line
    return result


def _zigzag(line: np.ndarray, points: list, side: int) -> None:
    """Wpisuje do line odcinki między punktami (świeca, cena)."""
    for (b0, p0), (b1, p1) in zip(points, points[1:]):
        if b1 > b0:
            line[b0:b1 + 1] = np.linspace(p0, p1, b1 - b0 + 1) * side
        else:
            line[b0] = p0 * side


def indicators(bars: pd.DataFrame) -> dict:
    """
    EMA 21 na cenie, zlecenia stop (H2 / L2) jako kropki.
    Etykieta „1” = pierwsze odbicie (H1 / L1, pomijane),
    „2” = świeca sygnałowa drugiego odbicia (H2 / L2).
    Szara linia = pierwsza korekta (szczyt → dołek 1. nogi → H1),
    zielona / czerwona = druga korekta (H1 → dołek 2. nogi → świeca
    sygnałowa). Tylko setupy, które dały sygnał.
    Panel: zmiana EMA 21 na świecę (> 0 = trend wzrostowy, < 0 = spadkowy).
    """
    signals = _compute(bars)
    average = ema(bars["close"], EMA_LENGTH)
    slope = average.diff()
    top = float(np.nanmax(np.abs(slope.to_numpy()))) if slope.notna().any() else 1.0
    return {
        "trend": None,
        "overlays": [
            (f"EMA {EMA_LENGTH}", average, "#FF9800"),
            ("Pierwsza korekta", signals["first_leg"], "#9E9E9E"),
            ("Druga korekta (long)", signals["second_leg_long"], "#00D084"),
            ("Druga korekta (short)", signals["second_leg_short"], "#FF3B30"),
        ],
        "markers": [
            ("Buy stop (H2)", signals["entry_stop"].where(signals["buy"]), "#00D084", "above"),
            ("Sell stop (L2)", signals["entry_stop"].where(signals["sell"]), "#FF3B30", "below"),
        ],
        "labels": [
            ("Pierwsze odbicie (H1, pomijamy)", signals["first_long"], "1", "#9E9E9E", "above"),
            ("Pierwsze odbicie (L1, pomijamy)", signals["first_short"], "1", "#9E9E9E", "below"),
            ("Drugie odbicie (H2)", signals["buy"], "2", "#00D084", "above"),
            ("Drugie odbicie (L2)", signals["sell"], "2", "#FF3B30", "below"),
        ],
        "panel": {
            "title": f"Nachylenie EMA {EMA_LENGTH}",
            "lines": [("Zmiana EMA", slope, "#7E57C2")],
            "levels": (0,),
            "range": (-top * 1.05 or -1.0, top * 1.05 or 1.0),
        },
    }
