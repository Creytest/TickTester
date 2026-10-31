from pathlib import Path

import pandas as pd


COLUMNS = ["timestamp", "bid", "ask", "extra_1", "extra_2"]

DATE_FORMAT = "%d.%m.%Y %H:%M:%S.%f"

# Pliki pobrane prosto z Dukascopy (z nagłówkiem).
COMPACT_DATE_FORMAT = "%Y%m%d %H:%M:%S:%f"


def tick_files(file_path: str | Path) -> list[Path]:
    """
    Pliki CSV aktywa: jeden plik albo folder z plikami (np. jeden
    na rok), posortowane po nazwie — muszą iść chronologicznie.
    """
    path = Path(file_path)

    if path.is_dir():
        files = sorted(path.glob("*.csv"))
    elif path.is_file():
        files = [path]
    else:
        files = []

    if not files:
        raise FileNotFoundError(
            f"Nie znaleziono pliku z danymi tickowymi: {path}"
        )

    return files


def _signature(file_path: str | Path, reverse_bid_ask: bool) -> str:
    """Nazwa folderu cache — zmienia się razem z plikami danych."""
    files = tick_files(file_path)
    size = sum(file.stat().st_size for file in files)
    mtime = max(file.stat().st_mtime_ns for file in files)
    return (
        f"{Path(file_path).stem}_{size}_{mtime}"
        f"_{'rev' if reverse_bid_ask else 'norm'}"
    )


def _date_format(timestamp: str) -> str:
    """Tickstory: 01.11.2021 01:00:15.669, Dukascopy: 20211101 01:00:15:669."""
    return DATE_FORMAT if timestamp[2:3] == "." else COMPACT_DATE_FORMAT


def file_range(path: Path) -> tuple[pd.Timestamp, pd.Timestamp, int]:
    """
    Pierwszy i ostatni czas w pliku bez czytania całości
    oraz liczba wierszy nagłówka do pominięcia.
    """
    with open(path, "rb") as file:
        first = file.readline().decode(errors="replace").strip()
        header = 0

        # Nagłówek (np. "Timestamp,Bid price,...") nie zaczyna się cyfrą.
        if first and not first[0].isdigit():
            header = 1
            first = file.readline().decode(errors="replace").strip()

        file.seek(0, 2)
        size = file.tell()
        file.seek(max(0, size - 4096))
        tail = file.read().decode(errors="replace").strip().splitlines()

    last = tail[-1] if tail else first
    first_time, last_time = (
        pd.to_datetime(
            line.split(",")[0],
            format=_date_format(line.split(",")[0]),
            errors="coerce",
        )
        for line in (first, last)
    )
    return first_time, last_time, header


def load_ticks(
    file_path: str | Path,
    chunksize: int | None = 1_000_000,
    reverse_bid_ask: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
):
    """
    Wczytuje ticki partiami.

    file_path:
        Plik CSV albo folder z plikami CSV (np. jeden na rok).
        Obsługuje format Tickstory (01.11.2021 01:00:15.669)
        i Dukascopy z nagłówkiem (20211101 01:00:15:669).

    start_date:
        Opcjonalna data początku, np. "2023-12-01".

    end_date:
        Opcjonalna data końca, np. "2025-01-01".
        Jest to granica wyłączna.

    Pliki muszą być uporządkowane chronologicznie,
    aby można było przerwać odczyt po end_date.
    """

    files = tick_files(file_path)

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

    def prepare(chunk: pd.DataFrame, date_format: str) -> pd.DataFrame:
        if not pd.api.types.is_datetime64_any_dtype(chunk["timestamp"]):
            chunk["timestamp"] = pd.to_datetime(
                chunk["timestamp"],
                format=date_format,
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
        for path in files:
            first, last, header = file_range(path)

            # Cały plik przed okresem albo po nim — bez czytania.
            if start is not None and pd.notna(last) and last < start:
                continue
            if end is not None and pd.notna(first) and first >= end:
                break

            # Format daty rozpoznajemy po pierwszym wierszu pliku.
            date_format = None

            reader = pd.read_csv(
                path,
                header=None,
                skiprows=header,
                names=COLUMNS,
                usecols=["timestamp", "bid", "ask"],
                dtype={
                    "timestamp": "string",
                    "bid": "float64",
                    "ask": "float64",
                },
                chunksize=chunksize or 1_000_000,
                skip_blank_lines=True,
            )

            for chunk in reader:
                if chunk.empty:
                    continue

                if date_format is None:
                    date_format = _date_format(str(chunk["timestamp"].iloc[0]))

                # Dane są chronologiczne, więc partię w całości
                # sprzed start_date pomijamy bez parsowania wszystkich
                # dat — wystarczy sprawdzić ostatni wiersz.
                if start is not None:
                    last_row = pd.to_datetime(
                        chunk["timestamp"].iloc[-1:],
                        format=date_format,
                        errors="coerce",
                    ).iloc[0]

                    if pd.notna(last_row) and last_row < start:
                        continue

                # Daty parsujemy raz i wykorzystujemy je zarówno
                # do sprawdzenia końca okresu, jak i w prepare().
                chunk["timestamp"] = pd.to_datetime(
                    chunk["timestamp"],
                    format=date_format,
                    errors="coerce",
                )

                # Po przekroczeniu końca okresu przerywamy odczyt.
                if end is not None:
                    timestamps = chunk["timestamp"]

                    if (
                        timestamps.notna().any()
                        and timestamps.min() >= end
                    ):
                        return

                result = prepare(chunk, date_format)

                if not result.empty:
                    yield result

    if chunksize is None:
        return _concat_ticks(list(prepared_chunks()))

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
    tick_files(path)  # błąd, gdy brak danych

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

    signature = _signature(path, reverse_bid_ask)
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


def daily_max_bid(
    file_path: str | Path,
    reverse_bid_ask: bool = False,
    cache_dir: str | Path | None = None,
    chunksize: int = 1_000_000,
) -> pd.Series:
    """
    Najwyższy Bid każdego dnia w całym pliku CSV (indeks: data).

    Plik czytany jest partiami, bez trzymania ticków w pamięci,
    a wynik zapisywany w cache — liczy się raz na wersję pliku.
    Służy do szczytu wszech czasów sprzed okresu backtestu.
    """
    path = Path(file_path)
    tick_files(path)  # błąd, gdy brak danych

    if cache_dir is None:
        cache_dir = Path(__file__).resolve().parent / "cache"

    signature = _signature(path, reverse_bid_ask)
    cache_file = Path(cache_dir) / signature / "daily_max_bid.pkl"

    if cache_file.is_file():
        return pd.read_pickle(cache_file)

    print(
        "Liczenie dziennych maksimów z całego pliku "
        "(jednorazowo, może potrwać)..."
    )

    parts = []
    for chunk in load_ticks(
        path, chunksize=chunksize, reverse_bid_ask=reverse_bid_ask
    ):
        parts.append(chunk.groupby(chunk["timestamp"].dt.normalize())["bid"].max())

    if parts:
        daily = pd.concat(parts)
        # Dzień może być podzielony między dwie partie.
        daily = daily.groupby(level=0).max()
    else:
        daily = pd.Series(dtype="float64")

    cache_file.parent.mkdir(parents=True, exist_ok=True)
    daily.to_pickle(cache_file)
    return daily


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
