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
            # Dane są chronologiczne, więc po przekroczeniu
            # końca okresu możemy przerwać dalszy odczyt.
            if end is not None:
                timestamps = pd.to_datetime(
                    chunk["timestamp"],
                    format=DATE_FORMAT,
                    errors="coerce",
                )

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