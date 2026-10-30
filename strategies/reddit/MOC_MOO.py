import numpy as np
import pandas as pd


NAME = "MOC to MOO"

# Autor grał akcjami Berkshire (BRK.A). Testujemy na S&P 500 (US500):
# ten sam efekt nocny, a akcji nie mamy w danych.
ASSETS = ["US500"]

# Wejście 16:00 i wyjście 9:30 NY wypadają na granicy świec 15m,
# więc mniejszy interwał nic nie zmienia.
TIMEFRAMES = ["15min"]

# Jedna pozycja na noc, tylko long.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału
# z kapitalizacją.
EQUITY_FRACTION = 1.0

# Czas danych = Nowy Jork + 7 h (GMT+2 / GMT+3 z DST USA).
ENTRY_TIME = "23:00"    # 16:00 NY — zamknięcie sesji (MOC)
EXIT_TIME = "16:30"     # 9:30 NY — otwarcie następnej sesji (MOO)


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def _bar_end_minutes(bars: pd.DataFrame) -> np.ndarray:
    """Minuta doby (w czasie danych), o której zamyka się każda świeca."""
    bar_len = int(pd.Series(bars.index).diff().min() / pd.Timedelta(minutes=1)) if len(bars) > 1 else 1
    start = (bars.index.hour * 60 + bars.index.minute).to_numpy()
    return (start + bar_len) % (24 * 60)


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Trading (HonestCamel1063): "MOC to MOO BRK.A every
    single day" — kupno na zamknięciu sesji (market on close),
    sprzedaż na otwarciu następnej (market on open). Codziennie,
    bez SL i TP.

    Wejście na pierwszym ticku po zamknięciu świecy kończącej się
    o 16:00 NY, wyjście na pierwszym ticku po świecy kończącej się
    o 9:30 NY. Piątek trzyma przez weekend do poniedziałku.

    Wyjście:
        buy, sell, exit_long, exit_short.
    """
    end = _bar_end_minutes(bars)
    weekday = bars.index.dayofweek.to_numpy()

    buy = (end == _to_minutes(ENTRY_TIME)) & (weekday < 5)
    exit_long = end == _to_minutes(EXIT_TIME)

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = False
    result["exit_long"] = exit_long
    result["exit_short"] = False
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """W panelu 1 = noc (od zamknięcia do otwarcia sesji), 0 = sesja."""
    end = _bar_end_minutes(bars)
    entry = _to_minutes(ENTRY_TIME)
    exit_ = _to_minutes(EXIT_TIME)
    # Świeca należy do nocy, jeśli kończy się po 16:00 albo
    # najpóźniej o 9:30 NY.
    night = (end > entry) | (end <= exit_)
    return {
        "trend": None,
        "panel": {
            "title": "Noc (MOC → MOO)",
            "lines": [("Noc", pd.Series(night.astype(float), index=bars.index), "#7E57C2")],
            "levels": (0, 1),
            "range": (-0.2, 1.2),
        },
    }
