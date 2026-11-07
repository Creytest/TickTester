import numpy as np
import pandas as pd


NAME = "Elephant Bar + MA200 + Volume Spike"

# Autor nie podaje interwału — domyślne 15m/1h/4h z run_all_assets.

# Pozycja kończy się na SL albo TP. Sygnały przy otwartej pozycji
# są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Od autora: "200 period moving average". Typ średniej nie jest
# podany — bierzemy SMA (ta.sma, domyślna "MA" w TradingView).
MA_LENGTH = 200

# Nasze założenia (autor nie definiuje pojęć):
# Elephant bar — świeca wzrostowa wyraźnie większa od poprzednich:
# zakres (high − low) ≥ 2 × średni zakres z 20 poprzednich świec
# i korpus ≥ 70% zakresu (mało knotów).
AVG_LENGTH = 20
RANGE_MULT = 2.0
BODY_RATIO = 0.7

# Volume spike — wolumen ≥ 2 × średni wolumen z 20 poprzednich
# świec. Wolumen w TickTesterze to liczba ticków w świecy
# (dane Dukascopy nie mają wolumenu giełdowego).
VOLUME_MULT = 2.0

# Wyjście (autor nie podaje): SL pod low świecy sygnałowej,
# TP = 2 × ryzyko, 1% kapitału ryzykowany przy SL.
RR_RATIO = 2.0


def sma(values: pd.Series, length: int) -> pd.Series:
    """Odpowiednik ta.sma()."""
    return values.astype(float).rolling(length, min_periods=length).mean()


def elephant_setup(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Daytrading (Trade-Clearly): "a bullish elephant bar off
    the 200 period moving average where it has a volume spike".

    Warunki na jednej świecy:
    1. Bullish elephant bar: close > open, zakres ≥ 2 × średni zakres
       20 poprzednich świec, korpus ≥ 70% zakresu.
    2. "Off the MA200": low świecy ≤ SMA 200 < close — świeca
       wybija się w górę od średniej (dotyka jej albo przebija
       z dołu i zamyka nad nią).
    3. Volume spike: wolumen ≥ 2 × średni wolumen 20 poprzednich
       świec.

    Średnie zakresu i wolumenu liczone bez bieżącej świecy, żeby
    duża świeca nie podnosiła własnego progu.
    """
    open_ = bars["open"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    close = bars["close"].astype(float)
    volume = bars["volume"].astype(float)

    ma = sma(close, MA_LENGTH)
    bar_range = high - low
    body = close - open_
    avg_range = sma(bar_range, AVG_LENGTH).shift(1)
    avg_volume = sma(volume, AVG_LENGTH).shift(1)

    elephant = (
        (body > 0)
        & (bar_range >= RANGE_MULT * avg_range)
        & (body >= BODY_RATIO * bar_range)
    )
    off_ma = (low <= ma) & (close > ma)
    spike = volume >= VOLUME_MULT * avg_volume

    return pd.DataFrame(
        {
            "ma": ma,
            "elephant": elephant.fillna(False),
            "off_ma": off_ma.fillna(False),
            "spike": spike.fillna(False),
            "signal": (elephant & off_ma & spike).fillna(False),
        },
        index=bars.index,
    )


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Long na pierwszym ticku po zamknięciu świecy sygnałowej.
    Tylko long — autor pisze wyłącznie o świecy wzrostowej.

    SL: low świecy sygnałowej. TP: zamknięcie + 2 × (zamknięcie − low).

    Wyjście:
        buy, sell, stop_loss, take_profit.
    """
    setup = elephant_setup(bars)
    low = bars["low"].astype(float)
    close = bars["close"].astype(float)

    buy = setup["signal"] & (close > low)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = False
    result["stop_loss"] = np.where(buy, low, np.nan)
    result["take_profit"] = np.where(buy, close + (close - low) * RR_RATIO, np.nan)
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """
    Na cenie: SMA 200, etykiety E na świecach sygnałowych.
    Panel: wolumen (liczba ticków) i próg volume spike.
    """
    setup = elephant_setup(bars)
    volume = bars["volume"].astype(float)
    threshold = VOLUME_MULT * sma(volume, AVG_LENGTH).shift(1)
    top = float(np.nanmax(volume.to_numpy())) if volume.notna().any() else 1.0

    return {
        "trend": None,
        "overlays": [
            (f"SMA {MA_LENGTH}", setup["ma"], "#4C8DFF"),
        ],
        "labels": [
            ("Elephant bar", setup["signal"], "E", "#00D084", "below"),
        ],
        "panel": {
            "title": "Wolumen (liczba ticków)",
            "lines": [
                ("Wolumen", volume, "#7E57C2"),
                (f"Próg spike ({VOLUME_MULT:g} × średnia {AVG_LENGTH})", threshold, "#FF9100"),
            ],
            "levels": (),
            "range": (0, top * 1.05 or 1.0),
        },
    }
