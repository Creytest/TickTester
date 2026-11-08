# Uruchamianie bezpośrednio z tego folderu: dodaj folder repo do ścieżki importów.
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from narzedzia.tick_config import ASSETS
from narzedzia.tick_data import file_range, tick_files


def main():
    print(f"{'aktywo':<10} {'rozmiar':>10}  {'od':<20} {'do':<20}")
    print("-" * 64)

    for asset, path in ASSETS.items():
        try:
            files = tick_files(path)
        except FileNotFoundError:
            print(f"{asset:<10} {'':>10}  brak pliku: {path}")
            continue

        # Plik albo folder z plikami (np. jeden na rok).
        start = file_range(files[0])[0]
        end = file_range(files[-1])[1]
        size = sum(file.stat().st_size for file in files) / 1024**3

        print(
            f"{asset:<10} {size:>7.2f} GB  "
            f"{start:%Y-%m-%d %H:%M}     {end:%Y-%m-%d %H:%M}"
        )


if __name__ == "__main__":
    main()
