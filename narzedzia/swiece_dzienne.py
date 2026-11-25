"""
Świece dzienne z długą historią i adapter do silnika TickTestera.

Dane tickowe z Dukascopy pobierają się dniami. Strategie na świecach
dziennych (np. IBS Mean Reversion) potrzebują tylko OHLC z każdego
dnia, a te pobierają się w sekundy:

    Yahoo Finance     — QQQ od 1999, SPY od 1993, BTC-USD od 2014-09,
                        indeks S&P 500 (^GSPC) od 1928
                        (biblioteka yfinance: pip install yfinance),
    ticki z D:\\Tickdata — np. XAUUSD od 2003 (świece 1D z ticków, które już masz),
    Binance (klines)  — BTCUSDT Spot od 2017-08-17,
    Dukascopy (d1)    — przez `npx dukascopy-node` (wymaga Node.js),
    Stooq (CSV)       — od 2026-11 blokuje pobieranie spoza przeglądarki,
    własny plik CSV   — dowolne aktywo.

Pliki trafiają do FOLDER (jeden CSV na aktywo: date, open, high, low,
close, volume). Ponowne uruchomienie korzysta z pliku, chyba że
zażądasz pobrania od nowa (test_dzienny.py --pobierz).

ADAPTER: silnik (tick_backtest.run_backtest) liczy na tickach Bid/Ask.
na_ticki() zamienia każdą świecę dzienną na 4 sztuczne ticki:
    otwarcie → low → high → zamknięcie   (świeca wzrostowa),
    otwarcie → high → low → zamknięcie   (świeca spadkowa),
tak jak TradingView bez Bar Magnifier zakłada drogę ceny w świecy.
Silnik buduje z nich z powrotem identyczne świece 1D, a sygnał
z zamknięcia świecy wykonuje się na otwarciu następnego dnia
(jak w TradingView). Ask = Bid + spread przybliżony jako ułamek ceny.

OGRANICZENIA (mówić w filmie, gdy wyniki z tego źródła):
- Brak spreadu z ticków — spread i prowizja są przybliżone (SPREAD_PCT,
  COMMISSION w AKTYWA_DZIENNE).
- Strategie z SL/TP: gdy w jednym dniu cena dotknie i SL, i TP,
  kolejność wynika z założonej drogi ceny (wyżej), a nie z ticków.
- Strategie intraday (godziny sesji, interwały < 1D) tu nie pasują,
  z wyjątkiem handlujących tylko na otwarciu i zamknięciu sesji USA
  (MOC to MOO) — dla nich na_ticki_sesja() i atrybut strategii
  SWIECE_DZIENNE = "sesja".
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from narzedzia.dane_dzienne import load_daily_csv

# Folder na pliki CSV ze świecami dziennymi.
FOLDER = Path(r"D:\Tickdata\Dzienne")

# Aktywa do testów na świecach dziennych.
#   zrodlo: "yahoo" | "ticki" | "binance" | "dukascopy" | "stooq" | "csv"
#   symbol: symbol w źródle (dla "ticki": nazwa aktywa z tick_config,
#           dla "csv": nazwa pliku w FOLDER)
#   commission: prowizja jako ułamek wartości, za stronę
#   spread_pct: przybliżony spread jako ułamek ceny (Ask = Bid × (1 + spread_pct))
#   tick: najmniejsza zmiana ceny — poślizg = 1 tick
#   opis: do tabel i plansz
# Koszty są PRZYBLIŻONE — na świecach dziennych nie ma spreadu z danych.
AKTYWA_DZIENNE = {
    # ETF na Nasdaq 100. Yahoo: ceny skorygowane o splity, bez dywidend
    # (buy & hold nie liczy dywidend — mówić w filmie, jeśli ważne).
    "QQQ": {
        "zrodlo": "yahoo", "symbol": "QQQ",
        "commission": 0.0005,      # standard kanału 0,05%/stronę
        "spread_pct": 0.0001,      # ~1 cent przy cenie ~100 USD
        "tick": 0.01,
        "opis": "Nasdaq 100 ETF",
    },
    # ETF na S&P 500 — na nim autor IBS Mean Reversion pokazywał wyniki.
    "SPY": {
        "zrodlo": "yahoo", "symbol": "SPY",
        "commission": 0.0005,
        "spread_pct": 0.0001,
        "tick": 0.01,
        "opis": "S&P 500 ETF",
    },
    # Indeks S&P 500 (Yahoo ^GSPC) od 1928 — sam indeks, bez dywidend.
    # Do badań na długiej historii (np. analizy/event_study_trend.py);
    # indeksem nie da się handlować wprost, koszty jak dla SPY.
    "SPX": {
        "zrodlo": "yahoo", "symbol": "^GSPC", "od": "1927-01-01",
        "commission": 0.0005,
        "spread_pct": 0.0001,
        "tick": 0.01,
        "opis": "S&P 500 (indeks)",
    },
    # Złoto spot: świece 1D z Twoich ticków XAUUSD (Tickstory, od 2003-08,
    # GMT+2 US-DST = dzień kończy się o 17:00 NY). Pierwsze wczytanie trwa
    # kilka minut (ticki rok po roku), potem plik CSV w FOLDER.
    # Prowizja jak w TickTesterze (CFD), spread ~0,3 USD przy 3000 USD.
    "XAUUSD": {
        "zrodlo": "ticki", "symbol": "XAUUSD",
        "commission": 0.000035,
        "spread_pct": 0.0001,
        "tick": 0.01,
        "opis": "Złoto",
    },
    # Binance Spot od 2017-08-17 (Futures dopiero od 2019-09).
    # Taker 0,1% na Spot, 0,05% na Futures — przyjmujemy standard kanału 0,05%.
    "BTCUSDT Spot": {
        "zrodlo": "binance", "symbol": "BTCUSDT",
        "commission": 0.0005,
        "spread_pct": 0.0,         # spread na Binance to ~1 tick, poślizg go pokrywa
        "tick": 0.01,
        "opis": "Bitcoin (Binance Spot)",
    },
    # Bitcoin z Yahoo (indeks CoinMarketCap) od 2014-09 — dłużej niż Binance,
    # ale to nie są ceny jednej giełdy.
    "BTCUSD": {
        "zrodlo": "yahoo", "symbol": "BTC-USD",
        "commission": 0.0005,
        "spread_pct": 0.0,
        "tick": 0.01,
        "opis": "Bitcoin (Yahoo)",
    },
    # Berkshire Hathaway A — na niej autor MOC to MOO (Reddit) grał.
    # Jedna akcja kosztuje setki tysięcy USD: przy 10 000 USD silnik
    # liczy ułamek akcji (w realu na BRK.A niemożliwe; BRK.B ma ten sam
    # ruch ceny). Spread BRK.A jest szeroki — przyjmujemy ~0,03% ceny
    # (przybliżenie, nie z danych).
    "BRK.A": {
        "zrodlo": "yahoo", "symbol": "BRK-A",
        "commission": 0.0005,
        "spread_pct": 0.0003,
        "tick": 0.01,
        "opis": "Berkshire Hathaway A",
    },
}

_USER_AGENT = "Mozilla/5.0 (ticktester)"


# ============================================================
# POBIERANIE
# ============================================================

def plik(asset: str) -> Path:
    safe = asset.replace(" ", "_").replace(":", "_").replace("^", "_").replace("=", "_")
    return FOLDER / f"{safe}.csv"


def pobierz(asset: str) -> Path:
    """Pobiera pełną historię świec dziennych aktywa do FOLDER."""
    spec = _spec(asset)
    zrodlo = spec["zrodlo"]
    print(f"Pobieranie {asset} ({zrodlo}: {spec['symbol']})...")

    if zrodlo == "yahoo":
        bars = _yahoo(spec["symbol"], spec.get("od", "1990-01-01"))
    elif zrodlo == "ticki":
        bars = _ticki(spec["symbol"])
    elif zrodlo == "stooq":
        bars = _stooq(spec["symbol"], asset)
    elif zrodlo == "binance":
        bars = _binance(spec["symbol"])
    elif zrodlo == "dukascopy":
        bars = _dukascopy(spec["symbol"])
    elif zrodlo == "csv":
        raise FileNotFoundError(
            f"{asset}: źródło 'csv' — wrzuć plik {FOLDER / spec['symbol']}"
        )
    else:
        raise ValueError(f"{asset}: nieznane źródło {zrodlo!r}")

    path = plik(asset)
    path.parent.mkdir(parents=True, exist_ok=True)
    bars.rename_axis("date").reset_index().to_csv(path, index=False)
    print(
        f"  zapisano {len(bars)} świec "
        f"({bars.index[0]:%Y-%m-%d} – {bars.index[-1]:%Y-%m-%d}) → {path}"
    )
    return path


def wczytaj(asset: str, od=None, do=None, pobierz_od_nowa: bool = False) -> pd.DataFrame:
    """
    Świece dzienne aktywa (indeks: data, kolumny open/high/low/close
    i volume, jeśli źródło go podaje). Pobiera, gdy brak pliku.
    """
    spec = _spec(asset)
    path = FOLDER / spec["symbol"] if spec["zrodlo"] == "csv" else plik(asset)
    if pobierz_od_nowa or not path.exists():
        path = pobierz(asset)

    bars = load_daily_csv(path)

    # Źródła z samym zamknięciem: OHLC = zamknięcie.
    for col in ("open", "high", "low"):
        if col not in bars:
            bars[col] = bars["close"]
    bars["high"] = bars[["open", "high", "low", "close"]].max(axis=1)
    bars["low"] = bars[["open", "high", "low", "close"]].min(axis=1)
    bars.index = pd.DatetimeIndex(bars.index).normalize()
    bars = bars[~bars.index.duplicated(keep="last")]

    if od is not None:
        bars = bars[bars.index >= pd.Timestamp(od)]
    if do is not None:
        bars = bars[bars.index <= pd.Timestamp(do)]
    cols = ["open", "high", "low", "close"] + (["volume"] if "volume" in bars else [])
    return bars[cols].astype(float)


def _spec(asset: str) -> dict:
    # Dowolny symbol z Yahoo bez wpisu w AKTYWA_DZIENNE: "yahoo:SYMBOL" (np. "yahoo:^N225").
    # Tylko do badań bez transakcji (np. event_study_trend.py --szeroki) — koszty standardowe.
    if asset.startswith("yahoo:"):
        return {"zrodlo": "yahoo", "symbol": asset[len("yahoo:"):], "commission": 0.0005,
                "spread_pct": 0.0, "tick": 0.01, "opis": asset[len("yahoo:"):]}
    if asset not in AKTYWA_DZIENNE:
        raise KeyError(
            f"nieznane aktywo {asset!r} — dopisz je do AKTYWA_DZIENNE "
            f"w narzedzia/swiece_dzienne.py (są: {', '.join(AKTYWA_DZIENNE)})"
        )
    return AKTYWA_DZIENNE[asset]


def _get(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except OSError as error:
            if attempt == 3:
                raise
            print(f"  błąd sieci ({error}), ponawiam...")
            time.sleep(2 ** attempt)


def _stooq(symbol: str, asset: str) -> pd.DataFrame:
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    text = _get(url).decode("utf-8", errors="replace")
    first = text.splitlines()[0].lower() if text.strip() else ""
    if not ("date" in first or "data" in first):
        # Stooq zamiast CSV zwraca np. „Brak danych” albo informację o limicie.
        raise RuntimeError(
            f"Stooq nie zwrócił CSV dla {symbol!r}: {text.strip()[:200]!r}\n"
            f"Pobierz ręcznie: stooq.pl → {symbol} → Dane historyczne → interwał "
            f"dzienny → „Pobierz dane w pliku CSV” i zapisz jako {plik(asset)}"
        )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(text)
        tmp = Path(f.name)
    try:
        return load_daily_csv(tmp)
    finally:
        tmp.unlink(missing_ok=True)


def _yahoo(symbol: str, start: str = "1990-01-01") -> pd.DataFrame:
    """
    Świece dzienne z Yahoo Finance (yfinance). Ceny skorygowane o splity,
    bez korekty o dywidendy (auto_adjust=False, kolumny Open/High/Low/Close).
    """
    try:
        import yfinance as yf
    except ImportError:
        raise RuntimeError("Brak biblioteki yfinance — zainstaluj: pip install yfinance") from None
    df = yf.download(
        symbol, start=start, interval="1d", auto_adjust=False,
        progress=False, multi_level_index=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"Yahoo nie zwrócił danych dla {symbol!r}")
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df.index = pd.DatetimeIndex(df.index).tz_localize(None).normalize()
    df = df.astype(float)
    # Ostatnia świeca może być niedokończona (dzisiejsza sesja).
    today = pd.Timestamp.now().normalize()
    return df[(df.index < today) & (df["close"] > 0)].dropna(subset=["close"])


def _ticki(asset: str) -> pd.DataFrame:
    """
    Świece 1D (Bid) z ticków aktywa z tick_config. Jeden przebieg przez
    cały plik CSV partiami — w pamięci jest tylko bieżąca partia.
    Jednorazowo trwa długo (cały plik ticków), potem jest plik CSV w FOLDER.
    """
    from narzedzia.tick_config import ASSETS, REVERSE_BID_ASK
    from narzedzia.tick_data import load_ticks
    from narzedzia.tick_engine import build_bars

    if asset not in ASSETS:
        raise KeyError(f"brak aktywa {asset!r} w narzedzia/tick_config.py")

    def chunks():
        last_year = None
        for chunk in load_ticks(
            ASSETS[asset], chunksize=2_000_000,
            reverse_bid_ask=REVERSE_BID_ASK[asset],
        ):
            if chunk.empty:
                continue
            year = chunk["timestamp"].iloc[-1].year
            if year != last_year:
                print(f"  ticki {asset} {year}...")
                last_year = year
            yield chunk[["timestamp", "bid", "ask"]]

    bars = build_bars(chunks(), "1D")
    if bars.empty:
        raise RuntimeError(f"brak ticków {asset}")
    return bars[["open", "high", "low", "close"]].dropna(subset=["close"])


def _binance(symbol: str) -> pd.DataFrame:
    """Świece 1d z Binance Spot (publiczne API danych rynkowych, czas UTC)."""
    url = "https://data-api.binance.vision/api/v3/klines"
    start = 0
    rows = []
    while True:
        data = json.loads(_get(
            f"{url}?symbol={symbol}&interval=1d&startTime={start}&limit=1000"
        ))
        if not data:
            break
        rows.extend(data)
        start = int(data[-1][0]) + 1
        if len(data) < 1000:
            break
    if not rows:
        raise RuntimeError(f"Binance nie zwrócił świec dla {symbol}")
    df = pd.DataFrame(
        [r[:6] for r in rows],
        columns=["date", "open", "high", "low", "close", "volume"],
    )
    df["date"] = pd.to_datetime(df["date"], unit="ms")
    df = df.set_index("date").astype(float)
    # Ostatnia świeca może być niedokończona (dzisiejszy dzień).
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    return df[df.index < today]


def _dukascopy(symbol: str) -> pd.DataFrame:
    """Świece d1 (Bid, UTC) z Dukascopy przez dukascopy-node (Node.js 20+)."""
    npx = shutil.which("npx")
    if npx is None:
        raise RuntimeError("Brak npx — zainstaluj Node.js 20+ albo użyj źródła 'stooq'.")
    out_dir = Path(tempfile.mkdtemp(prefix="dukascopy_d1_"))
    to = pd.Timestamp.now().strftime("%Y-%m-%d")
    cmd = [
        npx, "--yes", "dukascopy-node",
        "-i", symbol, "-from", "1990-01-01", "-to", to,
        "-t", "d1", "-f", "csv", "-dir", str(out_dir),
    ]
    print("  " + " ".join(cmd[1:]))
    subprocess.run(cmd, check=True)
    files = sorted(out_dir.glob("*.csv"), key=lambda p: p.stat().st_mtime)
    if not files:
        raise RuntimeError(f"dukascopy-node nie zapisał pliku CSV w {out_dir}")
    try:
        return load_daily_csv(files[-1])
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


# ============================================================
# ADAPTER: ŚWIECE DZIENNE → TICKI DLA SILNIKA
# ============================================================

# Godziny sztucznych ticków w dniu świecy: otwarcie, pierwszy
# ekstremum, drugi ekstremum, zamknięcie. Wszystkie przed północą,
# więc silnik złoży z nich dokładnie tę samą świecę 1D.
_GODZINY = (pd.Timedelta(0), pd.Timedelta(hours=6), pd.Timedelta(hours=12),
            pd.Timedelta(hours=23, minutes=59))


def na_ticki(bars: pd.DataFrame, spread_pct: float = 0.0) -> pd.DataFrame:
    """
    Świece dzienne → ticki (timestamp, bid, ask[, volume]) dla
    tick_backtest.run_backtest / plot_tick_backtest_xauusd.main.

    Bid = droga ceny w świecy (O→L→H→C dla wzrostowej, O→H→L→C dla
    spadkowej), Ask = Bid × (1 + spread_pct). Wolumen dnia jest na
    ticku zamknięcia, więc suma wolumenu świecy się zgadza.
    """
    if bars.empty:
        return pd.DataFrame(columns=["timestamp", "bid", "ask"])

    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)
    up = c >= o
    first = np.where(up, l, h)
    second = np.where(up, h, l)

    prices = np.column_stack([o, first, second, c]).ravel()
    day = pd.DatetimeIndex(bars.index).normalize().to_numpy()
    offsets = np.array([g.to_timedelta64() for g in _GODZINY])
    times = (day[:, None] + offsets[None, :]).ravel()

    ticks = pd.DataFrame({
        "timestamp": pd.DatetimeIndex(times).astype("datetime64[ns]"),
        "bid": prices,
        "ask": prices * (1.0 + spread_pct),
    })
    if "volume" in bars:
        vol = np.zeros((len(bars), 4))
        vol[:, 3] = bars["volume"].fillna(0).to_numpy(float)
        ticks["volume"] = vol.ravel()
    return ticks


# Sesja akcji USA w czasie danych TickTestera (Nowy Jork + 7 h, cały rok).
# Daty świec dziennych z Yahoo to daty sesji w Nowym Jorku.
SESJA_OTWARCIE = pd.Timedelta(hours=16, minutes=30)   # 9:30 NY
SESJA_ZAMKNIECIE = pd.Timedelta(hours=23)             # 16:00 NY


def na_ticki_sesja(bars: pd.DataFrame, spread_pct: float = 0.0) -> pd.DataFrame:
    """
    Świece dzienne → ticki o godzinach sesji USA, dla strategii, które
    handlują tylko na otwarciu i zamknięciu sesji (MOC to MOO). Pozwala
    liczyć je na interwale minutowym (np. 15min) bez danych intraday.

    Ticki dnia (czas danych = NY + 7 h):
        16:29:59  otwarcie  — żeby istniała świeca kończąca się o 9:30 NY
                              (sygnał wyjścia na otwarciu),
        16:30:00  otwarcie  — 9:30 NY, tu wykonuje się zlecenie MOO,
        18:00     pierwsze ekstremum (O→L→H→C / O→H→L→C jak na_ticki),
        21:00     drugie ekstremum,
        22:59:59  zamknięcie,
        23:00:00  zamknięcie — 16:00 NY, tu wykonuje się zlecenie MOC.

    Zlecenie wykonuje się na pierwszym ticku po zamknięciu świecy
    sygnałowej, więc kupno = cena zamknięcia sesji, sprzedaż = cena
    otwarcia następnej. Ceny w środku dnia są umowne (jak w na_ticki).
    """
    if bars.empty:
        return pd.DataFrame(columns=["timestamp", "bid", "ask"])

    o = bars["open"].to_numpy(float)
    h = bars["high"].to_numpy(float)
    l = bars["low"].to_numpy(float)
    c = bars["close"].to_numpy(float)
    up = c >= o
    first = np.where(up, l, h)
    second = np.where(up, h, l)

    prices = np.column_stack([o, o, first, second, c, c]).ravel()
    godziny = (
        SESJA_OTWARCIE - pd.Timedelta(seconds=1), SESJA_OTWARCIE,
        pd.Timedelta(hours=18), pd.Timedelta(hours=21),
        SESJA_ZAMKNIECIE - pd.Timedelta(seconds=1), SESJA_ZAMKNIECIE,
    )
    day = pd.DatetimeIndex(bars.index).normalize().to_numpy()
    offsets = np.array([g.to_timedelta64() for g in godziny])
    times = (day[:, None] + offsets[None, :]).ravel()

    ticks = pd.DataFrame({
        "timestamp": pd.DatetimeIndex(times).astype("datetime64[ns]"),
        "bid": prices,
        "ask": prices * (1.0 + spread_pct),
    })
    if "volume" in bars:
        vol = np.zeros((len(bars), 6))
        vol[:, 4] = bars["volume"].fillna(0).to_numpy(float)
        ticks["volume"] = vol.ravel()
    return ticks
