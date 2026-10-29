import numpy as np
import pandas as pd

from strategies.tiktok.LuxAlgo_SR_Breaks_MSTS import pivot_high, pivot_low


NAME = "SSL + IFVG"

# Autor gra na 1 minucie (Nasdaq futures, NQ).
TIMEFRAMES = ["1min"]

# Pozycja kończy się na SL albo TP. Sygnały przy otwartej
# pozycji (w obie strony) są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

PIVOT_LEFT = 3
PIVOT_RIGHT = 3
BIAS_BARS = 30     # bias po sweepie trwa 30 świec
FVG_BARS = 30      # pod uwagę bierzemy FVG z ostatnich 30 świec


def ssl_ifvg(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Mechaniczna wersja ICT „sweep SSL + IFVG” z filmu.

    Sweep SSL: low świecy schodzi pod ostatni pivot low (3 świece
    w lewo, 3 w prawo — znany 3 świece po dołku), a zamknięcie
    wraca nad niego. Od tej świecy przez 30 świec bias = long.
    Zamknięcie pod dołkiem to zwykłe przebicie, nie sweep.
    Zamknięcie pod low świecy sweepu kasuje bias (sweep się nie
    udał, cena idzie niżej).

    FVG spadkowy: high świecy n jest pod low świecy n-2 (knoty
    1. i 3. świecy się nie stykają). Luka: od high[n] do low[n-2].

    IFVG: zamknięcie nad górną krawędzią spadkowego FVG z ostatnich
    30 świec, jeszcze nieodwróconego. Przy biasie long to sygnał
    long, SL pod dolną krawędzią luki. Odwrócony FVG znika.

    Short lustrzanie: sweep BSL (high nad pivot high, zamknięcie
    pod nim) i zamknięcie pod dolną krawędzią wzrostowego FVG,
    SL nad jego górną krawędzią.

    Wyjście: kolumny long, short, stop (SL sygnału), bias (1 long,
    -1 short, 0 brak), ssl, bsl
    (aktywne poziomy płynności), sweep_ssl, sweep_bsl, bear_top,
    bear_bottom, bull_top, bull_bottom (ostatni aktywny FVG),
    pivot_high, pivot_low (cena pivota na świecy szczytu — tylko
    do rysowania).
    """
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    size = len(close)

    ph = pivot_high(bars["high"], PIVOT_LEFT, PIVOT_RIGHT).to_numpy()
    pl = pivot_low(bars["low"], PIVOT_LEFT, PIVOT_RIGHT).to_numpy()

    long = np.zeros(size, dtype=bool)
    short = np.zeros(size, dtype=bool)
    stop = np.full(size, np.nan)
    ssl_out = np.full(size, np.nan)
    bsl_out = np.full(size, np.nan)
    sweep_ssl = np.zeros(size, dtype=bool)
    sweep_bsl = np.zeros(size, dtype=bool)
    bear_top = np.full(size, np.nan)
    bear_bottom = np.full(size, np.nan)
    bull_top = np.full(size, np.nan)
    bull_bottom = np.full(size, np.nan)

    ssl = bsl = np.nan
    long_until = short_until = -1
    sweep_low = sweep_high = np.nan
    bias = np.zeros(size)
    bear_fvgs = []   # (świeca, góra, dół)
    bull_fvgs = []

    for n in range(size):
        # ---------------- Płynność i sweep ----------------
        if not np.isnan(pl[n]):
            ssl = pl[n]
        if not np.isnan(ph[n]):
            bsl = ph[n]

        ssl_out[n] = ssl
        bsl_out[n] = bsl

        if not np.isnan(ssl) and low[n] < ssl:
            if close[n] > ssl:
                sweep_ssl[n] = True
                long_until, short_until = n + BIAS_BARS, -1
                sweep_low = low[n]
            ssl = np.nan

        if not np.isnan(bsl) and high[n] > bsl:
            if close[n] < bsl:
                sweep_bsl[n] = True
                short_until, long_until = n + BIAS_BARS, -1
                sweep_high = high[n]
            bsl = np.nan

        if n <= long_until and close[n] < sweep_low:
            long_until = -1
        if n <= short_until and close[n] > sweep_high:
            short_until = -1

        bias[n] = 1 if n <= long_until else -1 if n <= short_until else 0

        # ---------------- Nowe FVG ----------------
        if n >= 2 and high[n] < low[n - 2]:
            bear_fvgs.append((n, low[n - 2], high[n]))
        if n >= 2 and low[n] > high[n - 2]:
            bull_fvgs.append((n, low[n], high[n - 2]))

        bear_fvgs = [f for f in bear_fvgs if n - f[0] <= FVG_BARS]
        bull_fvgs = [f for f in bull_fvgs if n - f[0] <= FVG_BARS]

        # ---------------- Inwersja ----------------
        # Luka utworzona na tej świecy nie może się na niej odwrócić.
        inverted = [f for f in bear_fvgs if f[0] < n and close[n] > f[1]]
        if inverted:
            bear_fvgs = [f for f in bear_fvgs if f not in inverted]
            if n <= long_until:
                newest = max(inverted, key=lambda f: f[0])
                long[n] = True
                stop[n] = newest[2]

        inverted = [f for f in bull_fvgs if f[0] < n and close[n] < f[2]]
        if inverted:
            bull_fvgs = [f for f in bull_fvgs if f not in inverted]
            if n <= short_until and not long[n]:
                newest = max(inverted, key=lambda f: f[0])
                short[n] = True
                stop[n] = newest[1]

        if bear_fvgs:
            bear_top[n], bear_bottom[n] = bear_fvgs[-1][1:]
        if bull_fvgs:
            bull_top[n], bull_bottom[n] = bull_fvgs[-1][1:]

    pivot_high_at = np.full(size, np.nan)
    pivot_low_at = np.full(size, np.nan)
    confirmed = np.flatnonzero(~np.isnan(ph))
    pivot_high_at[confirmed - PIVOT_RIGHT] = ph[confirmed]
    confirmed = np.flatnonzero(~np.isnan(pl))
    pivot_low_at[confirmed - PIVOT_RIGHT] = pl[confirmed]

    return pd.DataFrame(
        {
            "long": long,
            "short": short,
            "stop": stop,
            "bias": bias,
            "ssl": ssl_out,
            "bsl": bsl_out,
            "sweep_ssl": sweep_ssl,
            "sweep_bsl": sweep_bsl,
            "bear_top": bear_top,
            "bear_bottom": bear_bottom,
            "bull_top": bull_top,
            "bull_bottom": bull_bottom,
            "pivot_high": pivot_high_at,
            "pivot_low": pivot_low_at,
        },
        index=bars.index,
    )


def generate_signals(bars: pd.DataFrame, rr_ratio: float = 2.0) -> pd.DataFrame:
    """
    Long: IFVG przy biasie long po sweepie SSL. Short: IFVG przy
    biasie short po sweepie BSL. Wejście na pierwszym ticku po
    zamknięciu świecy sygnałowej.

    SL pod dolną krawędzią odwróconej luki (dla shorta nad górną),
    jak czerwone pole na filmie. TP = 2 × ryzyko od zamknięcia.
    Pozycja: 1% kapitału ryzykowany przy SL.

    Wyjście:
        buy, sell, stop_loss, take_profit.
    """
    setup = ssl_ifvg(bars)
    close = bars["close"].astype(float)
    sl = setup["stop"]

    buy = setup["long"]
    sell = setup["short"]

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    result["stop_loss"] = np.where(buy | sell, sl, np.nan)
    result["take_profit"] = np.where(
        buy,
        close + (close - sl) * rr_ratio,
        np.where(sell, close - (sl - close) * rr_ratio, np.nan),
    )
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """
    Płynność: SSL żółta, BSL pomarańczowa. FVG, które mogą dać
    sygnał (spadkowy przy biasie long — fioletowy, wzrostowy przy
    biasie short — turkusowy), górna i dolna krawędź. Pivoty jako
    kropki, „S” przy sweepie. Panel: bias (1 long, -1 short).
    """
    setup = ssl_ifvg(bars)
    long_bias = setup["bias"] > 0
    short_bias = setup["bias"] < 0

    return {
        "trend": None,
        "overlays": [
            ("SSL (płynność pod dołkiem)", _split(setup["ssl"]), "#FFC107"),
            ("BSL (płynność nad szczytem)", _split(setup["bsl"]), "#FF6D00"),
            ("FVG spadkowy", _split(setup["bear_top"].where(long_bias)), "#B388FF"),
            ("FVG spadkowy — dół", _split(setup["bear_bottom"].where(long_bias)), "#B388FF"),
            ("FVG wzrostowy", _split(setup["bull_top"].where(short_bias)), "#1DE9B6"),
            ("FVG wzrostowy — dół", _split(setup["bull_bottom"].where(short_bias)), "#1DE9B6"),
        ],
        "markers": [
            ("Pivot high", setup["pivot_high"], "#FF6D00", "above"),
            ("Pivot low", setup["pivot_low"], "#FFC107", "below"),
        ],
        "labels": [
            ("Sweep SSL", setup["sweep_ssl"], "S", "#FFC107", "below"),
            ("Sweep BSL", setup["sweep_bsl"], "S", "#FF6D00", "above"),
        ],
        "panel": {
            "title": "Bias (1 long, -1 short)",
            "lines": [("Bias", setup["bias"], "#7E57C2")],
            "levels": (0,),
            "range": (-1.2, 1.2),
        },
    }


def _split(level: pd.Series) -> pd.Series:
    """Przerwa w linii przy zmianie poziomu — bez pionowych skoków."""
    level = level.copy()
    level[level.ne(level.shift(1)) & level.shift(1).notna()] = np.nan
    return level
