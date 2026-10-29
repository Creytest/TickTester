import numpy as np
import pandas as pd


NAME = "IBS - gold futures"

# Autor grał na kontraktach na złoto (COMEX GC). Testujemy na
# złocie spot (XAUUSD) — w ciągu dnia porusza się jak kontrakt.
ASSETS = ["XAUUSD"]

# Wybicie liczy się od pierwszego ticku poza IB, więc najkrótszy
# interwał: wejście najpóźniej minutę po wybiciu.
TIMEFRAMES = ["1min"]

# Jedna transakcja dziennie, kończy się na SL, TP albo na koniec
# sesji. Sygnały przy otwartej pozycji są pomijane.
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Czas danych = Nowy Jork + 7 h (GMT+2 / GMT+3 z DST USA).
# Sesja dzienna COMEX złota: 8:20–13:30 czasu nowojorskiego.
IB_START = "15:20"      # 8:20 NY — otwarcie sesji
IB_END = "16:20"        # 9:20 NY — koniec pierwszej godziny (Initial Balance)
SESSION_END = "20:30"   # 13:30 NY — zamknięcie sesji, wyjście z pozycji

TICK = 0.01             # tick złota: SL o tick za drugą stroną IB


def _minutes(bars: pd.DataFrame) -> np.ndarray:
    """Minuta doby (w czasie danych) początku każdej świecy."""
    return (bars.index.hour * 60 + bars.index.minute).to_numpy()


def _to_minutes(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def initial_balance(bars: pd.DataFrame) -> tuple[pd.Series, pd.Series, np.ndarray]:
    """
    High i low pierwszej godziny sesji (IB) danego dnia, podane na
    świecach od końca IB do końca sesji (poza nimi NaN).

    Wyjście:
        ib_high, ib_low, maska świec po IB w trakcie sesji.
    """
    minute = _minutes(bars)
    bar_len = int(pd.Series(bars.index).diff().min() / pd.Timedelta(minutes=1)) if len(bars) > 1 else 1
    day = bars.index.normalize()

    in_ib = (minute >= _to_minutes(IB_START)) & (minute < _to_minutes(IB_END))
    # Świeca należy do sesji po IB, jeśli zamyka się najpóźniej
    # o SESSION_END.
    after_ib = (minute >= _to_minutes(IB_END)) & (minute + bar_len <= _to_minutes(SESSION_END))

    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    day_high = high.where(in_ib).groupby(day).transform("max")
    day_low = low.where(in_ib).groupby(day).transform("min")

    ib_high = day_high.where(after_ib)
    ib_low = day_low.where(after_ib)
    return ib_high, ib_low, after_ib


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Reddit r/Daytrading (SubDayTrader, futures na złoto):

    Initial Balance = high i low pierwszej godziny sesji.
    Pierwsze wybicie dnia nad high IB → long, SL tick pod low IB,
    TP = high IB + szerokość IB. Pierwsze wybicie pod low IB →
    short, odwrotnie. Jedno wejście dziennie. Bez SL/TP do końca
    sesji → wyjście na zamknięciu sesji.

    Wejście na pierwszym ticku po zamknięciu świecy z wybiciem.
    Świeca, która wybija IB w obie strony naraz, jest pomijana
    (nie wiadomo, które wybicie było pierwsze).

    Wyjście:
        buy, sell, stop_loss, take_profit, exit_long, exit_short.
    """
    ib_high, ib_low, after_ib = initial_balance(bars)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    day = bars.index.normalize()

    up = (high > ib_high).to_numpy()
    down = (low < ib_low).to_numpy()
    broken = pd.Series(up | down, index=bars.index)

    # Tylko pierwsze wybicie w danym dniu.
    first = broken & (broken.astype(int).groupby(day).cumsum() == 1)
    first = first.to_numpy()

    # Ostatnia świeca sesji (zamyka się o SESSION_END) zamyka pozycję.
    # Poza sesją wyjście też jest włączone — nic nie zostaje na noc.
    exit_all = ~after_ib | (np.roll(~after_ib, -1) & after_ib)

    # Wybicie na ostatniej świecy sesji nie otwiera już pozycji.
    buy = first & up & ~down & ~exit_all
    sell = first & down & ~up & ~exit_all
    width = (ib_high - ib_low).to_numpy()

    stop_loss = np.full(len(bars), np.nan)
    take_profit = np.full(len(bars), np.nan)
    stop_loss[buy] = ib_low.to_numpy()[buy] - TICK
    take_profit[buy] = ib_high.to_numpy()[buy] + width[buy]
    stop_loss[sell] = ib_high.to_numpy()[sell] + TICK
    take_profit[sell] = ib_low.to_numpy()[sell] - width[sell]

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    result["stop_loss"] = stop_loss
    result["take_profit"] = take_profit
    result["exit_long"] = exit_all
    result["exit_short"] = exit_all
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """High i low Initial Balance na cenie, od końca IB do końca sesji."""
    ib_high, ib_low, _ = initial_balance(bars)
    return {
        "trend": None,
        "overlays": [
            ("IB high", ib_high, "#00D084"),
            ("IB low", ib_low, "#FF3B30"),
        ],
    }
