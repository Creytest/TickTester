from pathlib import Path

import pandas as pd


COLUMNS = ["timestamp", "bid", "ask", "extra_1", "extra_2"]

DATE_FORMAT = "%d.%m.%Y %H:%M:%S.%f"


def load_ticks(
    file_path: str | Path,
    chunksize: int | None = 1_000_000,
    reverse_bid_ask: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Wczytuje ticki partiami.

    start_date:
        Opcjonalna data początku, np. "2023-12-01".

    end_date:
        Opcjonalna data końca, np. "2025-01-01".
        Jest to granica wyłączna.

    Plik musi być uporządkowany chronologicznie,
    aby można było przerwać odczyt po end_date.
    """

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Nie znaleziono pliku z danymi tickowymi: {path}"
        )

    if chunksize is not None and chunksize <= 0:
        raise ValueError("chunksize musi być większe od zera.")

    start = (
        pd.Timestamp(start_date)
        if start_date is not None
        else None
    )

    end = (
        pd.Timestamp(end_date)
        if end_date is not None
        else None
    )

    if start is not None and end is not None and start >= end:
        raise ValueError("start_date musi być wcześniejsza niż end_date.")

    reader = pd.read_csv(
        path,
        header=None,
        names=COLUMNS,
        usecols=["timestamp", "bid", "ask"],
        dtype={
            "timestamp": "string",
            "bid": "float64",
            "ask": "float64",
        },
        chunksize=chunksize,
        skip_blank_lines=True,
    )

    def prepare(chunk: pd.DataFrame) -> pd.DataFrame:
        if not pd.api.types.is_datetime64_any_dtype(chunk["timestamp"]):
            chunk["timestamp"] = pd.to_datetime(
                chunk["timestamp"],
                format=DATE_FORMAT,
                errors="coerce",
            )

        chunk = chunk.dropna(
            subset=["timestamp", "bid", "ask"]
        )

        if reverse_bid_ask:
            chunk[["bid", "ask"]] = (
                chunk[["ask", "bid"]].to_numpy()
            )

        chunk = chunk[
            (chunk["bid"] > 0)
            & (chunk["ask"] > 0)
            & (chunk["ask"] >= chunk["bid"])
        ]

        if start is not None:
            chunk = chunk[chunk["timestamp"] >= start]

        if end is not None:
            chunk = chunk[chunk["timestamp"] < end]

        return chunk.reset_index(drop=True)

    def prepared_chunks():
        for chunk in reader:
            # Dane są chronologiczne, więc partię w całości
            # sprzed start_date pomijamy bez parsowania wszystkich
            # dat — wystarczy sprawdzić ostatni wiersz.
            if start is not None and not chunk.empty:
                last = pd.to_datetime(
                    chunk["timestamp"].iloc[-1:],
                    format=DATE_FORMAT,
                    errors="coerce",
                ).iloc[0]

                if pd.notna(last) and last < start:
                    continue

            # Daty parsujemy raz i wykorzystujemy je zarówno
            # do sprawdzenia końca okresu, jak i w prepare().
            chunk["timestamp"] = pd.to_datetime(
                chunk["timestamp"],
                format=DATE_FORMAT,
                errors="coerce",
            )

            # Po przekroczeniu końca okresu przerywamy odczyt.
            if end is not None:
                timestamps = chunk["timestamp"]

                if (
                    timestamps.notna().any()
                    and timestamps.min() >= end
                ):
                    break

            result = prepare(chunk)

            if not result.empty:
                yield result

    if chunksize is None:
        return prepare(reader)

    return prepared_chunks()


def load_ticks_cached(
    file_path: str | Path,
    reverse_bid_ask: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    cache_dir: str | Path | None = None,
    chunksize: int = 1_000_000,
) -> pd.DataFrame:
    """
    Jak load_ticks, ale zwraca jeden DataFrame i zapisuje
    przetworzone ticki na dysku w podziale na lata.

    Pierwsze wczytanie danego roku czyta CSV, kolejne ładują
    gotowy plik .pkl w kilka sekund. Pamięć podręczna jest
    unieważniana, gdy zmieni się rozmiar lub data modyfikacji
    pliku CSV. Folder cache można bezpiecznie usunąć.
    """

    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"Nie znaleziono pliku z danymi tickowymi: {path}"
        )

    if start_date is None or end_date is None:
        # Bez zakresu dat cache po latach nic nie daje.
        chunks = load_ticks(
            path,
            chunksize=chunksize,
            reverse_bid_ask=reverse_bid_ask,
            start_date=start_date,
            end_date=end_date,
        )
        return _concat_ticks(list(chunks))

    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)

    if start >= end:
        raise ValueError("start_date musi być wcześniejsza niż end_date.")

    if cache_dir is None:
        cache_dir = Path(__file__).resolve().parent / "cache"

    stat = path.stat()
    signature = (
        f"{path.stem}_{stat.st_size}_{stat.st_mtime_ns}"
        f"_{'rev' if reverse_bid_ask else 'norm'}"
    )
    folder = Path(cache_dir) / signature
    folder.mkdir(parents=True, exist_ok=True)

    # end_date jest wyłączna, więc 2015-01-01 nie wymaga roku 2015.
    years = list(range(start.year, (end - pd.Timedelta(1)).year + 1))
    missing = [
        year for year in years
        if not (folder / f"{year}.pkl").is_file()
    ]

    if missing:
        print(
            "Tworzenie pamięci podręcznej ticków dla lat: "
            + ", ".join(map(str, missing))
            + " (jednorazowo, może potrwać)..."
        )

        chunks = load_ticks(
            path,
            chunksize=chunksize,
            reverse_bid_ask=reverse_bid_ask,
            start_date=f"{min(missing)}-01-01",
            end_date=f"{max(missing) + 1}-01-01",
        )

        # Rok zapisujemy, gdy tylko się skończy, i zwalniamy jego
        # ticki — w pamięci jest najwyżej jeden rok naraz, a nie
        # wszystkie brakujące lata (20 lat złota to ~650 mln ticków).
        buffer = []
        buffer_year = None

        def flush():
            if buffer_year in missing:
                part = _concat_ticks(buffer)
                part.to_pickle(folder / f"{buffer_year}.pkl")

        for chunk in chunks:
            by_year = chunk["timestamp"].dt.year

            for year in by_year.unique():
                if year != buffer_year:
                    flush()
                    buffer = []
                    buffer_year = year
                buffer.append(chunk.loc[by_year == year])

        flush()
        del buffer

        # Lata bez ticków (np. przed początkiem danych) zapisujemy
        # puste, żeby nie czytać CSV przy każdym uruchomieniu.
        for year in missing:
            if not (folder / f"{year}.pkl").is_file():
                _concat_ticks([]).to_pickle(folder / f"{year}.pkl")

    parts = [pd.read_pickle(folder / f"{year}.pkl") for year in years]
    ticks = _concat_ticks(parts)

    mask = (ticks["timestamp"] >= start) & (ticks["timestamp"] < end)
    return ticks.loc[mask].reset_index(drop=True)


def _concat_ticks(chunks: list[pd.DataFrame]) -> pd.DataFrame:
    chunks = [chunk for chunk in chunks if not chunk.empty]

    if not chunks:
        return pd.DataFrame(
            {
                "timestamp": pd.Series(dtype="datetime64[ns]"),
                "bid": pd.Series(dtype="float64"),
                "ask": pd.Series(dtype="float64"),
            }
        )

    return pd.concat(chunks, ignore_index=True)
