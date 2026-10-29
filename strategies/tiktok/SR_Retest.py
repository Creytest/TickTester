import numpy as np
import pandas as pd

from strategies.tiktok.LuxAlgo_SR_Breaks_MSTS import pivot_high, pivot_low


NAME = "SR Retest"

# Autor gra na 5 minutach.
TIMEFRAMES = ["5min"]

# Pozycja kończy się na SL albo TP. Sygnały przy otwartej
# pozycji (w obie strony) są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

PIVOT_LEFT = 3
PIVOT_RIGHT = 3
LOOKBACK = 50       # pivoty z ostatnich 50 świec
MIN_TOUCHES = 2     # ile pivotów musi tworzyć poziom
TOLERANCE = 0.25    # odległość pivotów w ATR(14)
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
    Mechaniczna wersja ręcznie rysowanych S/R z filmu.

    Opór: co najmniej 2 pivoty high (3 świece w lewo, 3 w prawo)
    z ostatnich 50 świec, leżące w odległości do 0,25 ATR(14) od
    siebie. Poziom to najwyższy z nich. Pivot jest znany dopiero
    3 świece po szczycie, więc nie podglądamy przyszłości.
    Wsparcie odwrotnie, z pivotów low.

    Wybicie: zamknięcie nad oporem. Retest: w ciągu 5 kolejnych
    świec low dotyka poziomu, a świeca zamyka się nad nim — to
    sygnał long. Bez retestu w 5 świec sygnał przepada. Short
    lustrzanie przez wsparcie.

    Wyjście: kolumny resistance, support (aktywny poziom, także
    w oknie retestu), break_up, break_down, retest_up,
    retest_down, pivot_high, pivot_low (cena pivota na świecy
    szczytu — tylko do rysowania).
    """
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    size = len(close)
    tol = TOLERANCE * atr(bars)

    ph = pivot_high(bars["high"], PIVOT_LEFT, PIVOT_RIGHT).to_numpy()
    pl = pivot_low(bars["low"], PIVOT_LEFT, PIVOT_RIGHT).to_numpy()

    resistance = np.full(size, np.nan)
    support = np.full(size, np.nan)
    break_up = np.zeros(size, dtype=bool)
    break_down = np.zeros(size, dtype=bool)
    retest_up = np.zeros(size, dtype=bool)
    retest_down = np.zeros(size, dtype=bool)

    def side(pivots, sign):
        """
        Jedna strona (sign=1 opór, -1 wsparcie). Zwraca funkcję
        kroku, która trzyma własny stan między świecami.
        """
        state = {"points": [], "retest": np.nan, "until": -1}
        level_out = resistance if sign > 0 else support
        break_out = break_up if sign > 0 else break_down
        retest_out = retest_up if sign > 0 else retest_down
        price = high if sign > 0 else low

        def step(n):
            points = state["points"]

            # Pivot potwierdzony na tej świecy (szczyt 3 świece wcześniej).
            if not np.isnan(pivots[n]):
                points.append((n - PIVOT_RIGHT, pivots[n]))

            points[:] = [p for p in points if p[0] >= n - LOOKBACK]

            # Okno retestu po wybiciu.
            if n <= state["until"]:
                level = state["retest"]
                level_out[n] = level
                touched = low[n] <= level if sign > 0 else high[n] >= level
                held = close[n] > level if sign > 0 else close[n] < level

                if touched and held:
                    retest_out[n] = True
                    state["until"] = -1
                return

            if np.isnan(tol[n]) or len(points) < MIN_TOUCHES:
                return

            # Najnowszy pivot, który ma w pobliżu inne pivoty.
            level = np.nan
            members = []

            for bar, value in reversed(points):
                near = [p for p in points if abs(p[1] - value) <= tol[n]]

                if len(near) >= MIN_TOUCHES:
                    members = near
                    values = [p[1] for p in near]
                    level = max(values) if sign > 0 else min(values)
                    break

            if np.isnan(level):
                return

            # Poziom już przebity zamknięciem przed tą świecą — nieważny.
            first = min(p[0] for p in members)
            past = close[first:n]

            if len(past) and (
                past.max() > level if sign > 0 else past.min() < level
            ):
                points[:] = [p for p in points if p not in members]
                return

            level_out[n] = level

            if (close[n] > level) if sign > 0 else (close[n] < level):
                break_out[n] = True
                state["retest"] = level
                state["until"] = n + RETEST_BARS
                # Przebite pivoty nie tworzą już poziomu.
                points[:] = [p for p in points if p not in members]

        return step

    step_up = side(ph, 1)
    step_down = side(pl, -1)

    for n in range(size):
        step_up(n)
        step_down(n)

    pivot_high_at = np.full(size, np.nan)
    pivot_low_at = np.full(size, np.nan)
    confirmed = np.flatnonzero(~np.isnan(ph))
    pivot_high_at[confirmed - PIVOT_RIGHT] = ph[confirmed]
    confirmed = np.flatnonzero(~np.isnan(pl))
    pivot_low_at[confirmed - PIVOT_RIGHT] = pl[confirmed]

    return pd.DataFrame(
        {
            "resistance": resistance,
            "support": support,
            "break_up": break_up,
            "break_down": break_down,
            "retest_up": retest_up,
            "retest_down": retest_down,
            "pivot_high": pivot_high_at,
            "pivot_low": pivot_low_at,
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
    pivoty jako kropki (pomarańczowe high, turkusowe low),
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
            ("Pivot high", sr["pivot_high"], "#FF9100", "above"),
            ("Pivot low", sr["pivot_low"], "#00BFA5", "below"),
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
