import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema


NAME = "Holy Grail (Raschke)"

# Książka gra na świecach dziennych — 1D jako wariant autorski
# obok naszych interwałów.
TIMEFRAMES = ["15min", "1h", "4h", "1D"]

# Pozycja kończy się na SL albo TP. Zlecenia przy otwartej
# pozycji są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Ustawienia z książki: ADX 14 powyżej 30, EMA 20.
ADX_LENGTH = 14
ADX_LEVEL = 30
EMA_LENGTH = 20


def rma(values: np.ndarray, length: int) -> np.ndarray:
    """Odpowiednik ta.rma(): średnia Wildera, start od SMA."""
    out = np.full(len(values), np.nan)
    valid = np.flatnonzero(~np.isnan(values))

    if len(valid) < length:
        return out

    first = valid[0]
    out[first + length - 1] = values[first:first + length].mean()
    alpha = 1.0 / length

    for i in range(first + length, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]

    return out


def adx(bars: pd.DataFrame, length: int = ADX_LENGTH) -> pd.Series:
    """Odpowiednik ta.dmi(length, length) — linia ADX."""
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)

    up = np.diff(high, prepend=np.nan)
    down = -np.diff(low, prepend=np.nan)
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    plus_dm[0] = minus_dm[0] = np.nan

    prev = np.concatenate(([np.nan], close[:-1]))
    tr = np.fmax(high - low, np.fmax(np.abs(high - prev), np.abs(low - prev)))
    tr[0] = np.nan

    atr = rma(tr, length)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus = 100 * rma(plus_dm, length) / atr
        minus = 100 * rma(minus_dm, length) / atr
        dx = 100 * np.abs(plus - minus) / (plus + minus)
    dx = np.where(np.isfinite(dx), dx, np.nan)

    return pd.Series(rma(dx, length), index=bars.index)


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Connors & Raschke, "Street Smarts" (1995), rozdział 10
    "The Holy Grail". Dla longów (shorty odwrotnie):

    1. ADX(14) powyżej 30 i rośnie — silny trend. Kierunek: zamknięcie
       nad EMA 20 (long) albo pod nią (short).
    2-3. Cena dotyka EMA 20 → buy stop nad high poprzedniej świecy.
       Niewypełnione zlecenie przesuwamy co świecę na high ostatniej
       świecy; gdy świeca zamknie się pod dołkiem cofnięcia, setup
       przepada.
    4. SL na dołku cofnięcia, TP na ostatnim szczycie przed
       cofnięciem. Bez trailingu i częściowego wyjścia (w książce
       opcjonalne).
    5. Po wybiciu SL nowy buy stop po pierwotnej cenie wejścia.
    6. Po udanej transakcji ADX musi znów przejść w górę przez 30,
       zanim zagramy kolejne cofnięcie.

    Wypełnienia, SL i TP śledzimy tu na świecach (Bid), żeby stosować
    reguły 5 i 6; silnik wykonuje zlecenia na tickach.

    Wyjście:
        buy, sell, entry_stop, stop_loss, take_profit.
    """
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    average = ema(bars["close"], EMA_LENGTH).to_numpy(dtype=float)
    strength = adx(bars).to_numpy(dtype=float)
    n = len(bars)

    buy = np.zeros(n, dtype=bool)
    sell = np.zeros(n, dtype=bool)
    entry = np.full(n, np.nan)
    stop_loss = np.full(n, np.nan)
    take_profit = np.full(n, np.nan)

    # Ceny shortów odwracamy (−low jako high), żeby jedna logika
    # obsługiwała oba kierunki.
    def view(side, i):
        if side == 1:
            return high[i], low[i], close[i], average[i]
        return -low[i], -high[i], -close[i], -average[i]

    state = "idle"
    side = 0
    swing = pull = trigger = sl = tp = original = np.nan
    order = False   # zlecenie złożone na poprzedniej świecy

    for i in range(1, n):
        if np.isnan(strength[i]) or np.isnan(average[i]) or np.isnan(strength[i - 1]):
            continue

        # Pozycja: wyjście na SL (ostrożnie: przed TP) albo TP.
        if state == "trade":
            h, l, c, m = view(side, i)
            if l <= sl:
                state, order = "reentry", True
                trigger = original
                pull = l
            elif h >= tp:
                state, order = "wait", False

        # Zlecenie z poprzedniej świecy.
        elif state in ("pending", "reentry") and order:
            h, l, c, m = view(side, i)
            if h >= trigger:
                state, order = "trade", False
                sl, original = pull, trigger
            elif c < pull:
                # Dalszy spadek pod dołek cofnięcia — setup przepada.
                state, order = "idle", False
            else:
                pull = min(pull, l)
                if state == "pending":
                    trigger = h

        # Reguła 6: po udanej transakcji ADX znów w górę przez 30.
        if state == "wait":
            if strength[i - 1] <= ADX_LEVEL < strength[i]:
                state = "idle"
            else:
                continue

        if state == "idle":
            if strength[i] > ADX_LEVEL and strength[i] > strength[i - 1]:
                side = 1 if close[i] > average[i] else -1
                h, l, c, m = view(side, i)
                state, swing = "armed", h
            else:
                continue

        if state == "armed":
            h, l, c, m = view(side, i)
            swing = max(swing, h)
            if l <= m:
                # Dotknięcie EMA 20 — szczyt przed cofnięciem to TP.
                state, order = "pending", True
                trigger, pull, tp = h, l, swing

        if state in ("pending", "reentry") and order:
            # Zlecenie ma sens tylko pod TP.
            if trigger < tp:
                price = trigger * side
                if side == 1:
                    buy[i] = True
                else:
                    sell[i] = True
                entry[i] = price
                stop_loss[i] = pull * side
                take_profit[i] = tp * side
            else:
                state, order = "idle", False

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    result["entry_stop"] = entry
    result["stop_loss"] = stop_loss
    result["take_profit"] = take_profit
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """EMA 20 na cenie, zlecenia stop jako kropki, ADX(14) w panelu."""
    signals = generate_signals(bars)
    return {
        "trend": None,
        "overlays": [
            (f"EMA {EMA_LENGTH}", ema(bars["close"], EMA_LENGTH), "#FF9800"),
        ],
        "markers": [
            ("Buy stop", signals["entry_stop"].where(signals["buy"]), "#00D084", "above"),
            ("Sell stop", signals["entry_stop"].where(signals["sell"]), "#FF3B30", "below"),
        ],
        "panel": {
            "title": f"ADX({ADX_LENGTH})",
            "lines": [(f"ADX {ADX_LENGTH}", adx(bars), "#7E57C2")],
            "levels": (ADX_LEVEL,),
            "range": (0, 80),
        },
    }
