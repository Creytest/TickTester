from pathlib import Path

import pandas as pd

from tick_config import ASSETS
from tick_data import DATE_FORMAT


def first_and_last_line(path: Path) -> tuple[str, str]:
    """Pierwsza i ostatnia linia pliku bez czytania całości."""
    with open(path, "rb") as file:
        first = file.readline().decode(errors="replace").strip()

        file.seek(0, 2)
        size = file.tell()
        file.seek(max(0, size - 4096))
        tail = file.read().decode(errors="replace").strip().splitlines()

    return first, tail[-1] if tail else first


def main():
    print(f"{'aktywo':<10} {'rozmiar':>10}  {'od':<20} {'do':<20}")
    print("-" * 64)

    for asset, path in ASSETS.items():
        path = Path(path)

        if not path.is_file():
            print(f"{asset:<10} {'':>10}  brak pliku: {path}")
            continue

        first, last = first_and_last_line(path)
        start = pd.to_datetime(first.split(",")[0], format=DATE_FORMAT)
        end = pd.to_datetime(last.split(",")[0], format=DATE_FORMAT)
        size = path.stat().st_size / 1024**3

        print(
            f"{asset:<10} {size:>7.2f} GB  "
            f"{start:%Y-%m-%d %H:%M}     {end:%Y-%m-%d %H:%M}"
        )


if __name__ == "__main__":
    main()
