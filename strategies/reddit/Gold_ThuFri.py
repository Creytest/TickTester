import numpy as np
import pandas as pd


NAME = "Gold Thursday-Friday"

ASSETS = ["XAUUSD"]

# Silnik wchodzi i wychodzi na pierwszym ticku po zamknięciu świecy
# sygnałowej. Świece 5 min pozwalają zrobić to 5 minut przed końcem
# dnia — po ostatniej świecy piątku następny tick byłby dopiero
# w poniedziałek.
TIMEFRAMES = ["5min"]

# Jedna pozycja na tydzień, tylko long.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Bez SL nie ma 1% ryzyka — pozycja to 100% kapitału
# z kapitalizacją.
EQUITY_FRACTION = 1.0

# Czas danych = Nowy Jork + 7 h. Dzień złota kończy się o 17:00 NY
# (24:00 w danych); wejście i wyjście 5 minut wcześniej.
CLOSE_TIME = "23:55"    # 16:55 NY
ENTRY_DAY = 3           # czwartek (poniedziałek = 0)
EXIT_DAY = 4            # piątek


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
    Reddit r/Daytrading (draderdim): "Buy Gold on Thursday close
    and sell on Friday close. Backtested more than 20 years."

    Kupno na zamknięciu czwartku, sprzedaż na zamknięciu piątku.
    Bez SL i TP. Gdy piątek jest wolny (np. Wielki Piątek),
    wyjście na zamknięciu następnego dnia handlowego.

    Wyjście:
        buy, sell, exit_long, exit_short.
    """
    at_close = _bar_end_minutes(bars) == _to_minutes(CLOSE_TIME)
    weekday = bars.index.dayofweek.to_numpy()

    result = pd.DataFrame(index=bars.index)
    result["buy"] = at_close & (weekday == ENTRY_DAY)
    result["sell"] = False
    result["exit_long"] = at_close & (weekday != ENTRY_DAY)
    result["exit_short"] = False
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """W panelu dzień tygodnia: 1 = poniedziałek … 5 = piątek."""
    day = pd.Series(bars.index.dayofweek + 1, index=bars.index, dtype=float)
    return {
        "trend": None,
        "panel": {
            "title": "Dzień tygodnia",
            "lines": [("Dzień (1 = pn, 5 = pt)", day, "#7E57C2")],
            "levels": (ENTRY_DAY + 1, EXIT_DAY + 1),
            "level_colors": ("#00D084", "#FF3B30"),
            "range": (0.5, 5.5),
        },
    }
