import numpy as np
import pandas as pd


NAME = "SR Retest"

# Autor gra na 5 minutach.
TIMEFRAMES = ["5min"]

# Pozycja kończy się na SL albo TP. Sygnały przy otwartej
# pozycji (w obie strony) są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

LOOKBACK = 20       # poziom szukany w ostatnich 20 świecach
MIN_TOUCHES = 2     # ile knotów musi dotknąć poziomu
TOLERANCE = 0.25    # dotknięcie = knot do 0,25 ATR(14) od poziomu
RETEST_BARS = 5     # na retest czekamy najwyżej 5 świec


def atr(bars: pd.DataFrame, length: int = 14) -> np.ndarray:
    """Odpowiednik ta.atr(): RMA (Wildera) z true range."""
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)

    prev = np.concatenate(([np.nan], close[:-1]))
    tr = np.fmax(high - low, np.fmax(np.abs(high - prev), np.abs(low - prev)))
    out = np.full(len(tr), np.nan)

    if len(tr) < length:
        return out

    out[length - 1] = tr[:length].mean()
    alpha = 1.0 / length

    for i in range(length, len(tr)):
        out[i] = alpha * tr[i] + (1 - alpha) * out[i - 1]

    return out


def support_resistance(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Mechaniczna wersja ręcznie rysowanych S/R z filmu (kadr:
    kilka knotów zatrzymuje się na jednej poziomej linii, świeca
    zamyka się nad nią, następna wraca knotem do linii = long).

    Opór na świecy n: najwyższe high z ostatnich 20 świec (bez n).
    Liczy się jako opór, gdy co najmniej 2 świece z tego okna mają
    high nie niżej niż 0,25 ATR(14) pod nim (dotknięcia knotem),
    i między dotknięciami jest choć jedna świeca, która do poziomu
    nie doszła (cena odbiła i wróciła) — inaczej każdy spokojny
    trend świeca po świecy robiłby „opór”. To nie jest double top:
    liczba dotknięć jest dowolna (≥ 2), a gramy wybicie.
    Wsparcie odwrotnie, z low.

    Wybicie: zamknięcie nad oporem. Retest: w ciągu 5 kolejnych
    świec low dochodzi do poziomu (z tą samą tolerancją 0,25 ATR co
    dotknięcia oporu), a świeca zamyka się nad nim — to sygnał long.
    Zamknięcie z powrotem pod poziomem kasuje wybicie (nieudane
    wybicie, a nie retest). Bez retestu w 5 świec sygnał przepada.
    Short lustrzanie przez wsparcie.

    Wyjście: kolumny resistance, support (aktywny poziom, także
    w oknie retestu), break_up, break_down, retest_up,
    retest_down, touch_high, touch_low (cena knota na świecach,
    które utworzyły wybity poziom — tylko do rysowania).
    """
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    size = len(close)
    tol = TOLERANCE * atr(bars)

    resistance = np.full(size, np.nan)
    support = np.full(size, np.nan)
    break_up = np.zeros(size, dtype=bool)
    break_down = np.zeros(size, dtype=bool)
    retest_up = np.zeros(size, dtype=bool)
    retest_down = np.zeros(size, dtype=bool)
    touch_high = np.full(size, np.nan)
    touch_low = np.full(size, np.nan)

    def side(sign):
        """
        Jedna strona (sign=1 opór, -1 wsparcie). Zwraca funkcję
        kroku, która trzyma własny stan między świecami.
        """
        state = {"retest": np.nan, "until": -1}
        wick = high if sign > 0 else -low   # wsparcie liczymy na -low
        level_out = resistance if sign > 0 else support
        break_out = break_up if sign > 0 else break_down
        retest_out = retest_up if sign > 0 else retest_down
        touch_out = touch_high if sign > 0 else touch_low

        def step(n):
            # Okno retestu po wybiciu.
            if n <= state["until"]:
                level = state["retest"]
                level_out[n] = level
                near = tol[n] if not np.isnan(tol[n]) else 0.0
                touched = (
                    low[n] <= level + near if sign > 0 else high[n] >= level - near
                )
                held = close[n] > level if sign > 0 else close[n] < level

                if touched and held:
                    retest_out[n] = True
                    state["until"] = -1
                elif not held:
                    # Zamknięcie z powrotem po drugiej stronie poziomu =
                    # wybicie nieudane, nie czekamy dalej na retest.
                    state["until"] = -1
                return

            if n < LOOKBACK or np.isnan(tol[n]):
                return

            window = wick[n - LOOKBACK:n]
            top = window.max()
            touches = np.flatnonzero(window >= top - tol[n])

            # Dotknięcia muszą być rozdzielone świecą bez dotknięcia.
            if len(touches) < MIN_TOUCHES or not (np.diff(touches) > 1).any():
                return

            level = top * sign
            level_out[n] = level

            if (close[n] > level) if sign > 0 else (close[n] < level):
                break_out[n] = True
                state["retest"] = level
                state["until"] = n + RETEST_BARS
                idx = n - LOOKBACK + touches
                touch_out[idx] = window[touches] * sign

        return step

    step_up = side(1)
    step_down = side(-1)

    for n in range(size):
        step_up(n)
        step_down(n)

    return pd.DataFrame(
        {
            "resistance": resistance,
            "support": support,
            "break_up": break_up,
            "break_down": break_down,
            "retest_up": retest_up,
            "retest_down": retest_down,
            "touch_high": touch_high,
            "touch_low": touch_low,
        },
        index=bars.index,
    )


def generate_signals(bars: pd.DataFrame, rr_ratio: float = 2.0) -> pd.DataFrame:
    """
    Long: retest przebitego oporu. Short: retest przebitego
    wsparcia. Wejście na pierwszym ticku po zamknięciu świecy
    retestu.

    Autor nie podaje wyjścia — przyjmujemy SL pod low świecy
    retestu (dla shorta nad high), TP = 2 × ryzyko od zamknięcia,
    jak przy SFP+Volume. Pozycja: 1% kapitału ryzykowany przy SL.

    Wyjście:
        buy, sell, stop_loss, take_profit.
    """
    sr = support_resistance(bars)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    close = bars["close"].astype(float)

    # Zamknięcie na samym low / high daje ryzyko 0 — pomijamy.
    buy = sr["retest_up"] & (close > low)
    sell = sr["retest_down"] & (close < high)

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
    Opór (fioletowy) i wsparcie (niebieskie) jako linie na cenie,
    dotknięcia wybitego poziomu jako kropki (pomarańczowe high,
    turkusowe low),
    etykiety B przy wybiciu. Panel: ATR(14).
    """
    sr = support_resistance(bars)
    atr_values = pd.Series(atr(bars), index=bars.index)
    top = float(np.nanmax(atr_values.to_numpy())) if atr_values.notna().any() else 1.0

    return {
        "trend": None,
        "overlays": [
            ("Opór", _split(sr["resistance"]), "#D500F9"),
            ("Wsparcie", _split(sr["support"]), "#2979FF"),
        ],
        "markers": [
            ("Dotknięcie oporu", sr["touch_high"], "#FF9100", "above"),
            ("Dotknięcie wsparcia", sr["touch_low"], "#00BFA5", "below"),
        ],
        "labels": [
            ("Wybicie oporu", sr["break_up"], "B", "#D500F9", "above"),
            ("Wybicie wsparcia", sr["break_down"], "B", "#2979FF", "below"),
        ],
        "panel": {
            "title": "ATR (14)",
            "lines": [("ATR", atr_values, "#7E57C2")],
            "levels": (),
            "range": (0, top * 1.05 or 1.0),
        },
    }


def _split(level: pd.Series) -> pd.Series:
    """Przerwa w linii przy zmianie poziomu — bez pionowych skoków."""
    level = level.copy()
    level[level.ne(level.shift(1)) & level.shift(1).notna()] = np.nan
    return level
