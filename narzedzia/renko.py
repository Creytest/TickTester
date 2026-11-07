import numpy as np
import pandas as pd


def _first_cross(bid: np.ndarray, start: int, upper: float, lower: float) -> int:
    """
    Indeks pierwszego ticku od start z bid >= upper albo bid <= lower,
    -1 jeśli żaden. Szuka w rosnących oknach, jak _find_exit.
    """
    n = len(bid)
    pos = start
    window = 4096

    while pos < n:
        stop = min(n, pos + window)
        part = bid[pos:stop]
        hit = (part >= upper) | (part <= lower)
        if hit.any():
            return pos + int(hit.argmax())
        pos = stop
        window *= 2

    return -1


def renko_bricks(
    timestamps: np.ndarray,
    bid: np.ndarray,
    size: float,
    with_details: bool = True,
):
    """
    Cegły Renko (klasyczne, odwrócenie o 2 cegły) z cen Bid, z knotami.

    Kolejna cegła wzrostowa powstaje, gdy Bid dojdzie do górnej krawędzi
    ostatniej cegły + size, spadkowa — gdy spadnie do dolnej − size.
    Cegła zamyka się na konkretnym ticku (close_time). Knot to skrajna
    cena Bid w trakcie tworzenia cegły (od ticku po poprzedniej cegle):
    przy cegle wzrostowej dołek pod jej otwarciem, przy spadkowej szczyt
    nad otwarciem.

    Jeden tick może zamknąć kilka cegieł naraz (luka). Tylko ostatnia
    z nich ma final=True — na pozostałe nie da się zareagować.

    with_details=False zwraca samą liczbę cegieł (do kalibracji).
    """
    n = len(bid)
    if n == 0:
        return pd.DataFrame() if with_details else 0

    anchor = np.floor(bid[0] / size) * size
    top = bottom = anchor
    pos = 0
    count = 0
    rows = []

    while pos < n:
        k = _first_cross(bid, pos, top + size, bottom - size)
        if k == -1:
            break

        price = bid[k]
        up = price >= top + size
        steps = int((price - top) // size) if up else int((bottom - price) // size)
        steps = max(steps, 1)

        if with_details:
            segment = bid[pos:k + 1]
            seg_low = float(segment.min())
            seg_high = float(segment.max())
            ticks_in = k + 1 - pos

            for j in range(steps):
                if up:
                    open_ = top + j * size
                    close = open_ + size
                    low = min(open_, seg_low) if j == 0 else open_
                    high = close
                else:
                    open_ = bottom - j * size
                    close = open_ - size
                    high = max(open_, seg_high) if j == 0 else open_
                    low = close
                rows.append(
                    (
                        timestamps[k],
                        open_, high, low, close,
                        float(ticks_in if j == 0 else 0),
                        j == steps - 1,
                    )
                )

        count += steps

        if up:
            top = top + steps * size
            bottom = top - size
        else:
            bottom = bottom - steps * size
            top = bottom + size

        pos = k + 1

    if not with_details:
        return count

    frame = pd.DataFrame(
        rows,
        columns=["close_time", "open", "high", "low", "close", "volume", "final"],
    )
    frame["close_time"] = pd.to_datetime(frame["close_time"])

    # Indeks = chwila zamknięcia cegły; cegły z jednego ticku rozsuwamy
    # o nanosekundy, żeby indeks był rosnący i unikalny.
    index = frame["close_time"].to_numpy().astype("datetime64[ns]").astype(np.int64)
    for i in range(1, len(index)):
        if index[i] <= index[i - 1]:
            index[i] = index[i - 1] + 1
    frame.index = pd.DatetimeIndex(index.astype("datetime64[ns]"), name="timestamp")
    frame["delta"] = 0.0
    return frame


def calibrate_brick_size(
    timestamps: np.ndarray,
    bid: np.ndarray,
    target_minutes: float,
    days: int = 30,
) -> float:
    """
    Wielkość cegły, przy której w pierwszych `days` dniach danych
    powstaje średnio jedna cegła na target_minutes minut handlu
    (minut z co najmniej jednym tickiem). Bisekcja na skali log.
    """
    times = pd.DatetimeIndex(timestamps)
    end = times[0] + pd.Timedelta(days=days)
    last = int(times.searchsorted(end, side="left"))
    t = timestamps[:last]
    b = bid[:last]

    active_minutes = pd.DatetimeIndex(t).floor("1min").nunique()
    target = max(active_minutes / target_minutes, 1.0)

    price = float(np.median(b))
    lo, hi = np.log(price * 1e-6), np.log(price * 5e-2)

    for _ in range(30):
        mid = (lo + hi) / 2
        bricks = renko_bricks(t, b, float(np.exp(mid)), with_details=False)
        if bricks > target:
            lo = mid        # za dużo cegieł → większa cegła
        else:
            hi = mid

    return float(np.exp((lo + hi) / 2))
