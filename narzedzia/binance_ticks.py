"""
Pobieranie transakcji BTCUSDT z Binance Futures i zapis w formacie
ticków TickTestera.

Źródło: oficjalne archiwum Binance, https://data.binance.vision
(USDⓈ-M Futures, kontrakt perpetual BTCUSDT, miesięczne pliki
aggTrades). Każdy plik ma sumę kontrolną SHA-256, którą skrypt
sprawdza po pobraniu.

Co trafia do CSV (format jak z dukascopy_ticks.py, więc
narzedzia/tick_data.py czyta go bez zmian):

    Timestamp,Bid price,Ask price,Sell volume,Buy volume
    20210104 02:00:00:123,32150.1,32150.2,0.512,1.034

- Bid = cena transakcji, Ask = Bid + spread 0,10 USD (1 tick
  BTCUSDT Perpetual, typowy spread na Binance Futures). Poślizg
  i prowizję dolicza TickTester (tick_config.py).
- Transakcje są ścięte do 1 sekundy: z każdej sekundy zostają dołek
  i szczyt w kolejności, w jakiej wystąpiły, a z każdej minuty także
  jej pierwsza i ostatnia transakcja. Świece od 1 min w górę mają
  więc dokładnie takie OHLC jak na Binance, a SL/TP sprawdzane są
  z dokładnością do sekundy. Ticków jest mniej więcej tyle, co
  w danych CFD, więc pamięci wystarczy.
- Sell/Buy volume: wolumen BTC z inicjatywy sprzedających
  i kupujących w danej sekundzie, zapisany przy jej ostatnim ticku.
  TickTester na razie go nie czyta (wolumen świecy = liczba ticków,
  co po ścięciu do 1 s jest prawie stałe) — strategie z wolumenem
  liczyć na BTCUSDT dopiero po dodaniu jego obsługi w silniku.
- Czas: GMT+2 z czasem letnim USA (= Nowy Jork + 7 h), tak jak
  pozostałe dane. Strategie z godzinami sesji (np. EMA 9/19 od 16:30)
  zakładają ten czas. W noc końca czasu letniego (listopad) dwie
  godziny UTC mieszczą się w jednej godzinie 8:00–9:00, żeby czas się
  nie cofał (patrz to_local_ms). --strefa utc daje czas wykresu
  Binance w TradingView (inne granice świec 4h i doby), ale wtedy
  godziny sesji w strategiach przestają pasować.

Okres: miesiące OD–DO włącznie, domyślnie tak jak START_DATE–END_DATE
w run_all_assets.py (2021–2025) plus wrzesień–grudzień 2020 na
rozgrzewkę wskaźników (Key Level Zones potrzebuje 70 dni wstecz).

Pliki: <FOLDER>/<SYMBOL>/<SYMBOL>_GMT+2_US-DST_RRRR-MM.csv (jeden na
miesiąc, najwyżej ~2 ticki na sekundę, czyli do ~270 MB na miesiąc
i do ~17 GB za cały domyślny okres). Surowe zipy trafiają do
<FOLDER>/<SYMBOL>/_zip i są usuwane po konwersji (--zostaw-zip je
zostawia). Przerwane pobieranie wznawia się po ponownym
uruchomieniu: gotowe miesiące są pomijane, a niedokończony zip jest
dociągany od miejsca przerwania.

Uruchomienie z głównego folderu repo:
    python narzedzia/binance_ticks.py
    python narzedzia/binance_ticks.py --od 2020-09 --do 2025-12
    python narzedzia/binance_ticks.py --folder "E:\\Dane\\Binance_Futures"

Potem python narzedzia/data_info.py pokaże aktywo "BTCUSDT".
"""

import argparse
import hashlib
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd


# ============================================================
# KONFIGURACJA
# ============================================================

SYMBOL = "BTCUSDT"

# Miesiące włącznie (RRRR-MM).
OD = "2020-09"
DO = "2025-12"

# Folder główny; pliki symbolu trafiają do <FOLDER>/<SYMBOL>.
# Ten sam folder jest wpisany w narzedzia/tick_config.py.
FOLDER = Path(r"D:\Tickdata\Binance_Futures")

# "gmt2us" = GMT+2 z czasem letnim USA (jak reszta danych), "utc".
STREFA = "gmt2us"

# Spread = 1 tick kontraktu perpetual (Ask = Bid + spread).
SPREAD = {"BTCUSDT": 0.10}

BASE_URL = "https://data.binance.vision/data/futures/um/monthly/aggTrades"
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Tyle transakcji czytamy naraz z pliku (~70 MB pamięci).
CHUNK_ROWS = 2_000_000

HOUR_MS = 3_600_000
MINUTE_MS = 60_000


# ============================================================
# CZAS
# ============================================================

def _nth_sunday(year: int, month: int, n: int) -> datetime:
    day = datetime(year, month, 1, tzinfo=timezone.utc)
    day += timedelta(days=(6 - day.weekday()) % 7)
    return day + timedelta(weeks=n - 1)


def us_dst_bounds_ms(year: int) -> tuple[int, int]:
    """
    Czas letni w USA w ms od 1970 (UTC): od 2. niedzieli marca
    2:00 EST do 1. niedzieli listopada 2:00 EDT — jak w
    dukascopy_ticks.py.
    """
    start = _nth_sunday(year, 3, 2) + timedelta(hours=7)
    end = _nth_sunday(year, 11, 1) + timedelta(hours=6)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def to_local_ms(t_ms: np.ndarray, strefa: str) -> np.ndarray:
    """
    Czas UTC (ms) -> czas w strefie CSV (ms).

    gmt2us: +3 h w czasie letnim USA, +2 h poza nim. Przy końcu
    czasu letniego zegar cofa się o godzinę, a BTC handluje też
    w niedzielę w nocy, więc godzina 8:00–9:00 wypadłaby dwa razy
    i po sortowaniu ticki dwóch różnych godzin by się przemieszały.
    Dlatego te dwie godziny UTC (05:00–07:00) mieszczą się w jednej
    godzinie 8:00–9:00 (czas biegnie dwa razy wolniej, kolejność
    i ceny zostają) — podobnie jak na wykresie MT4.
    """
    if strefa == "utc":
        return t_ms.copy()

    years = (
        t_ms.astype("datetime64[ms]").astype("datetime64[Y]").astype(np.int64)
        + 1970
    )
    local = t_ms + 2 * HOUR_MS
    for year in np.unique(years):
        start, end = us_dst_bounds_ms(int(year))
        in_year = years == year
        summer = in_year & (t_ms >= start) & (t_ms < end - HOUR_MS)
        local[summer] = t_ms[summer] + 3 * HOUR_MS

        merged = in_year & (t_ms >= end - HOUR_MS) & (t_ms < end + HOUR_MS)
        local[merged] = (
            end + 2 * HOUR_MS + (t_ms[merged] - (end - HOUR_MS)) // 2
        )
    return local


def format_timestamps(t_ms: np.ndarray) -> np.ndarray:
    """
    Czas w ms (już w strefie CSV) -> "RRRRMMDD GG:MM:SS:mmm", jak
    w plikach z dukascopy_ticks.py. Liczone wektorowo (szybko).
    """
    days = t_ms // 86_400_000
    rest = t_ms - days * 86_400_000

    date = days.astype("datetime64[D]")
    month_start = date.astype("datetime64[M]")
    year = date.astype("datetime64[Y]").astype(np.int64) + 1970
    month = month_start.astype(np.int64) % 12 + 1
    day = (date - month_start).astype(np.int64) + 1

    text = np.empty((len(t_ms), 21), dtype=np.uint8)

    def put(column: int, value: np.ndarray, width: int) -> None:
        for i in range(width):
            text[:, column + width - 1 - i] = 48 + value // 10**i % 10

    put(0, year, 4)
    put(4, month, 2)
    put(6, day, 2)
    text[:, 8] = ord(" ")
    put(9, rest // HOUR_MS, 2)
    text[:, 11] = ord(":")
    put(12, rest // MINUTE_MS % 60, 2)
    text[:, 14] = ord(":")
    put(15, rest // 1000 % 60, 2)
    text[:, 17] = ord(":")
    put(18, rest % 1000, 3)

    return text.view("S21").ravel().astype(str)


# ============================================================
# POBIERANIE
# ============================================================

def month_list(od: str, do: str) -> list[str]:
    first = datetime.strptime(od, "%Y-%m")
    last = datetime.strptime(do, "%Y-%m")
    if first > last:
        raise ValueError("OD musi być wcześniej niż DO.")

    months = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def zip_url(symbol: str, month: str) -> str:
    return f"{BASE_URL}/{symbol}/{symbol}-aggTrades-{month}.zip"


def fetch_text(url: str, retries: int = 6, timeout: float = 30) -> str | None:
    """Mały plik tekstowy albo None, gdy go nie ma na serwerze."""
    delay, error = 2, None
    for _ in range(retries):
        try:
            request = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode()
        except urllib.error.HTTPError as err:
            # Archiwum Binance (S3) odpowiada 404 albo 403 na brak pliku.
            if err.code in (403, 404):
                return None
            error = err
        except OSError as err:  # timeout, zerwane połączenie
            error = err
        time.sleep(delay)
        delay = min(delay * 2, 60)
    raise RuntimeError(f"{url} -> {error}")


def download(url: str, dest: Path, retries: int = 10, timeout: float = 60) -> None:
    """
    Pobiera duży plik do dest. Niedokończony plik (.part) jest
    dociągany od miejsca przerwania (nagłówek Range).
    """
    part = dest.with_name(dest.name + ".part")
    delay, error = 2, None

    for _ in range(retries):
        have = part.stat().st_size if part.exists() else 0
        headers = dict(HEADERS)
        if have:
            headers["Range"] = f"bytes={have}-"

        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if have and response.status != 206:
                    have = 0  # serwer nie wznawia, pobieramy od nowa
                length = response.headers.get("Content-Length")
                total = have + int(length) if length else None
                done = have
                shown = time.time()
                started, start_bytes = shown, done

                with open(part, "ab" if have else "wb") as file:
                    while True:
                        block = response.read(1 << 20)
                        if not block:
                            break
                        file.write(block)
                        done += len(block)

                        if time.time() - shown >= 10:
                            shown = time.time()
                            speed = (done - start_bytes) / max(shown - started, 1e-9)
                            share = f" / {total / 1e6:,.0f} MB" if total else " MB"
                            print(
                                f"    {done / 1e6:,.0f}{share}  "
                                f"({speed / 1e6:,.1f} MB/s)",
                                flush=True,
                            )

            if total is not None and done < total:
                raise OSError(f"przerwane po {done:,} z {total:,} bajtów")

            part.replace(dest)
            return

        except urllib.error.HTTPError as err:
            if err.code == 416 and have:
                # Range poza końcem: plik .part jest już cały.
                part.replace(dest)
                return
            error = err
        except OSError as err:
            error = err

        print(f"    błąd pobierania ({error}), ponawiam za {delay} s...", flush=True)
        time.sleep(delay)
        delay = min(delay * 2, 120)

    raise RuntimeError(f"Nie udało się pobrać {url}: {error}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def get_zip(symbol: str, month: str, zip_dir: Path) -> Path | None:
    """Zip miesiąca ze sprawdzoną sumą kontrolną albo None, gdy brak."""
    url = zip_url(symbol, month)
    checksum = fetch_text(url + ".CHECKSUM")
    if checksum is None:
        return None
    expected = checksum.split()[0].lower()

    dest = zip_dir / url.rsplit("/", 1)[1]
    for attempt in range(2):
        if not dest.exists():
            print(f"  pobieranie {dest.name}...", flush=True)
            download(url, dest)

        if sha256(dest) == expected:
            return dest

        print(f"  UWAGA: zła suma kontrolna {dest.name}, pobieram ponownie.")
        dest.unlink()

    raise RuntimeError(f"{dest.name}: suma kontrolna dalej się nie zgadza.")


# ============================================================
# KONWERSJA
# ============================================================

def read_trades(zip_path: Path, chunk_rows: int = CHUNK_ROWS):
    """
    Transakcje z pliku aggTrades partiami: czas (ms, UTC), cena,
    ilość i czy inicjatorem był sprzedający (is_buyer_maker).

    Kolumny Binance: agg_trade_id, price, quantity, first_trade_id,
    last_trade_id, transact_time, is_buyer_maker. Nowsze pliki mają
    nagłówek, starsze nie.
    """
    with zipfile.ZipFile(zip_path) as archive:
        names = [name for name in archive.namelist() if name.endswith(".csv")]
        if len(names) != 1:
            raise ValueError(f"{zip_path.name}: oczekiwano jednego pliku CSV.")

        with archive.open(names[0]) as file:
            first = file.readline().decode(errors="replace").strip()

        header = 0 if first[:1].isdigit() else 1
        if header:
            columns = [name.strip() for name in first.split(",")]
            if (
                len(columns) < 7
                or columns[1] != "price"
                or columns[2] != "quantity"
                or columns[5] != "transact_time"
                or columns[6] != "is_buyer_maker"
            ):
                raise ValueError(
                    f"{zip_path.name}: nieznany układ kolumn: {first}"
                )

        with archive.open(names[0]) as file:
            reader = pd.read_csv(
                file,
                header=None,
                skiprows=header,
                usecols=[1, 2, 5, 6],
                dtype={1: "float64", 2: "float64", 5: "int64", 6: "bool"},
                chunksize=chunk_rows,
            )
            for chunk in reader:
                t_ms = chunk[5].to_numpy(dtype=np.int64)
                # Binance zapisuje czas w ms; gdyby plik miał
                # mikrosekundy (tak jest w nowszych danych spot),
                # przeliczamy na ms.
                if len(t_ms) and t_ms.max() > 10**14:
                    t_ms = t_ms // 1000
                yield (
                    t_ms,
                    chunk[1].to_numpy(dtype=np.float64),
                    chunk[2].to_numpy(dtype=np.float64),
                    chunk[6].to_numpy(dtype=bool),
                )


def _first_in_group(mask: np.ndarray, group: np.ndarray) -> np.ndarray:
    """Pierwszy indeks z mask=True w każdej grupie (grupy rosnąco)."""
    rows = np.flatnonzero(mask)
    groups = group[rows]
    first = np.ones(len(rows), dtype=bool)
    first[1:] = groups[1:] != groups[:-1]
    return rows[first]


def thin_trades(
    t_ms: np.ndarray,
    price: np.ndarray,
    qty: np.ndarray,
    sell: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Wybiera transakcje, które zostają tickami (dane posortowane
    po czasie, pełne minuty):
      - dołek i szczyt każdej sekundy (pierwsze wystąpienie),
      - pierwsza i ostatnia transakcja każdej minuty.
    Zwraca indeksy tych transakcji oraz wolumen sprzedających
    i kupujących sekundy, wpisany przy jej ostatnim ticku.
    """
    n = len(t_ms)
    second = t_ms // 1000

    new = np.empty(n, dtype=bool)
    new[0] = True
    np.not_equal(second[1:], second[:-1], out=new[1:])
    starts = np.flatnonzero(new)
    ends = np.append(starts[1:], n) - 1
    group = np.cumsum(new) - 1

    low = np.minimum.reduceat(price, starts)
    high = np.maximum.reduceat(price, starts)
    at_low = _first_in_group(price == low[group], group)
    at_high = _first_in_group(price == high[group], group)

    minute = second[starts] // 60
    minute_open = np.ones(len(starts), dtype=bool)
    minute_open[1:] = minute[1:] != minute[:-1]
    minute_close = np.ones(len(starts), dtype=bool)
    minute_close[:-1] = minute[1:] != minute[:-1]

    keep = np.unique(
        np.concatenate(
            [starts[minute_open], at_low, at_high, ends[minute_close]]
        )
    )

    sell_volume = np.add.reduceat(np.where(sell, qty, 0.0), starts)
    buy_volume = np.add.reduceat(np.where(sell, 0.0, qty), starts)

    # Każda sekunda ma co najmniej jeden tick (dołek), więc ostatnich
    # ticków sekund jest dokładnie tyle, co sekund, i w tej samej kolejności.
    kept_group = group[keep]
    last = np.ones(len(keep), dtype=bool)
    last[:-1] = kept_group[1:] != kept_group[:-1]

    sell_out = np.zeros(len(keep))
    buy_out = np.zeros(len(keep))
    sell_out[last] = sell_volume
    buy_out[last] = buy_volume
    return keep, sell_out, buy_out


def convert_month(
    zip_path: Path,
    out_path: Path,
    spread: float,
    strefa: str,
) -> dict:
    """Zip aggTrades -> CSV ticków. Zwraca liczby do podsumowania."""
    part = out_path.with_name(out_path.name + ".part")
    stats = {"trades": 0, "ticks": 0, "unsorted": 0, "gap_ms": 0, "gap_at": None}
    first_price = last_price = None
    last_time = None

    carry = None

    def write(file, t_ms, price, qty, sell):
        nonlocal first_price, last_price, last_time
        keep, sell_volume, buy_volume = thin_trades(t_ms, price, qty, sell)
        t_kept = t_ms[keep]
        p_kept = price[keep]

        # Najdłuższa przerwa w danych (np. prace techniczne giełdy).
        times = t_kept if last_time is None else np.append(last_time, t_kept)
        if len(times) > 1:
            gaps = np.diff(times)
            i = int(np.argmax(gaps))
            if gaps[i] > stats["gap_ms"]:
                stats["gap_ms"] = int(gaps[i])
                stats["gap_at"] = int(times[i])
        last_time = int(t_kept[-1])

        if first_price is None:
            first_price = float(p_kept[0])
        last_price = float(p_kept[-1])

        local = to_local_ms(t_kept, strefa)
        frame = pd.DataFrame(
            {
                "timestamp": format_timestamps(local),
                "bid": p_kept,
                "ask": np.round(p_kept + spread, 8),
                "sell": np.round(sell_volume, 6),
                "buy": np.round(buy_volume, 6),
            }
        )
        frame.to_csv(file, header=False, index=False, lineterminator="\n")
        stats["ticks"] += len(keep)

    with open(part, "w", newline="") as file:
        file.write("Timestamp,Bid price,Ask price,Sell volume,Buy volume\n")

        for t_ms, price, qty, sell in read_trades(zip_path):
            stats["trades"] += len(t_ms)
            if carry is not None:
                t_ms, price, qty, sell = (
                    np.concatenate([old, new])
                    for old, new in zip(carry, (t_ms, price, qty, sell))
                )

            # Czas powinien rosnąć; gdyby nie, sortujemy stabilnie.
            unsorted = int(np.count_nonzero(np.diff(t_ms) < 0))
            if unsorted:
                stats["unsorted"] += unsorted
                order = np.argsort(t_ms, kind="stable")
                t_ms, price, qty, sell = t_ms[order], price[order], qty[order], sell[order]

            # Ostatnia minuta partii może ciągnąć się w następnej,
            # więc czeka na nią (dołek, szczyt i zamknięcie minuty).
            minute = t_ms // MINUTE_MS
            cut = int(np.searchsorted(minute, minute[-1], side="left"))
            carry = (t_ms[cut:], price[cut:], qty[cut:], sell[cut:])
            if cut:
                write(file, t_ms[:cut], price[:cut], qty[:cut], sell[:cut])

        if carry is not None and len(carry[0]):
            write(file, *carry)

    if stats["ticks"] == 0:
        part.unlink()
        raise ValueError(f"{zip_path.name}: brak transakcji w pliku.")

    part.replace(out_path)
    stats["first_price"] = first_price
    stats["last_price"] = last_price
    return stats


# ============================================================
# PROGRAM
# ============================================================

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Pobieranie ticków BTCUSDT z Binance Futures (aggTrades)"
    )
    parser.add_argument("--symbol", default=SYMBOL)
    parser.add_argument("--od", default=OD, help="pierwszy miesiąc, RRRR-MM")
    parser.add_argument("--do", dest="do", default=DO, help="ostatni miesiąc, RRRR-MM")
    parser.add_argument("--folder", default=str(FOLDER), help="folder główny danych")
    parser.add_argument("--strefa", choices=["gmt2us", "utc"], default=STREFA)
    parser.add_argument("--spread", type=float, help="Ask - Bid w USD (domyślnie 1 tick)")
    parser.add_argument(
        "--zostaw-zip", action="store_true", help="nie usuwaj zipów po konwersji"
    )
    args = parser.parse_args(argv)

    symbol = args.symbol.upper()
    spread = args.spread if args.spread is not None else SPREAD.get(symbol)
    if spread is None:
        parser.error(f"Podaj --spread dla {symbol} (1 tick kontraktu).")

    months = month_list(args.od, args.do)
    out_dir = Path(args.folder) / symbol
    zip_dir = out_dir / "_zip"
    zip_dir.mkdir(parents=True, exist_ok=True)
    suffix = "GMT+2_US-DST" if args.strefa == "gmt2us" else "UTC"

    print(f"Binance Futures {symbol}, miesiące {months[0]} – {months[-1]}")
    print(f"Pliki CSV: {out_dir}")
    print(f"Strefa: {suffix}, spread: {spread} USD\n")

    done, missing = [], []
    t0 = time.time()

    for number, month in enumerate(months, start=1):
        out_path = out_dir / f"{symbol}_{suffix}_{month}.csv"
        prefix = f"[{number}/{len(months)}] {month}"

        if out_path.exists():
            print(f"{prefix}: już jest, pomijam.")
            done.append(month)
            continue

        zip_path = get_zip(symbol, month, zip_dir)
        if zip_path is None:
            print(f"{prefix}: brak pliku na serwerze Binance, pomijam.")
            missing.append(month)
            continue

        print(f"{prefix}: konwersja...", flush=True)
        started = time.time()
        stats = convert_month(zip_path, out_path, spread, args.strefa)

        gap = ""
        if stats["gap_ms"] >= 10 * MINUTE_MS:
            at = pd.Timestamp(stats["gap_at"], unit="ms")
            gap = (
                f", najdłuższa przerwa {stats['gap_ms'] / MINUTE_MS:,.0f} min "
                f"od {at:%Y-%m-%d %H:%M} UTC"
            )
        unsorted = (
            f", posortowano {stats['unsorted']:,} transakcji"
            if stats["unsorted"]
            else ""
        )
        print(
            f"{prefix}: {stats['trades']:,} transakcji -> {stats['ticks']:,} ticków, "
            f"cena {stats['first_price']:,.1f} -> {stats['last_price']:,.1f}"
            f"{gap}{unsorted} ({time.time() - started:,.0f} s)",
            flush=True,
        )

        if not args.zostaw_zip:
            zip_path.unlink()
        done.append(month)

    print(f"\nGotowe: {len(done)} z {len(months)} miesięcy "
          f"w {(time.time() - t0) / 60:,.0f} min.")
    if missing:
        print("Brak na serwerze: " + ", ".join(missing))
        if len(missing) == len(months):
            print(
                "Żadnego pliku nie udało się pobrać. Sprawdź, czy strona "
                "https://data.binance.vision otwiera się w przeglądarce."
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
