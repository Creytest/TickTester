"""
Świece dzienne z długą historią i adapter do silnika TickTestera.

Dane tickowe z Dukascopy pobierają się dniami. Strategie na świecach
dziennych (np. IBS Mean Reversion) potrzebują tylko OHLC z każdego
dnia, a te pobierają się w sekundy:

    Stooq (CSV)       — QQQ, SPY od 1999/1993, XAUUSD od dawna,
    Binance (klines)  — BTCUSDT Spot od 2017-08-17,
    Dukascopy (d1)    — przez `npx dukascopy-node` (wymaga Node.js),
    własny plik CSV   — dowolne aktywo (np. pobrane ręcznie ze Stooq).

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
- Strategie intraday (godziny sesji, interwały < 1D) tu nie pasują.
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
#   zrodlo: "stooq" | "binance" | "dukascopy" | "csv"
#   symbol: symbol w źródle (dla "csv": nazwa pliku w FOLDER)
#   commission: prowizja jako ułamek wartości, za stronę
#   spread_pct: przybliżony spread jako ułamek ceny (Ask = Bid × (1 + spread_pct))
#   tick: najmniejsza zmiana ceny — poślizg = 1 tick
#   opis: do tabel i plansz
# Koszty są PRZYBLIŻONE — na świecach dziennych nie ma spreadu z danych.
AKTYWA_DZIENNE = {
    # ETF na Nasdaq 100. Stooq: ceny skorygowane o splity; czy także
    # o dywidendy — sprawdzić przed filmem (wpływa na wynik buy & hold,
    # nie na sygnały IBS).
    "QQQ": {
        "zrodlo": "stooq", "symbol": "qqq.us",
        "commission": 0.0005,      # standard kanału 0,05%/stronę
        "spread_pct": 0.0001,      # ~1 cent przy cenie ~100 USD
        "tick": 0.01,
        "opis": "Nasdaq 100 ETF",
    },
    # ETF na S&P 500 — na nim autor IBS Mean Reversion pokazywał wyniki.
    "SPY": {
        "zrodlo": "stooq", "symbol": "spy.us",
        "commission": 0.0005,
        "spread_pct": 0.0001,
        "tick": 0.01,
        "opis": "S&P 500 ETF",
    },
    # Złoto spot. Prowizja jak w TickTesterze (CFD), spread ~0,3 USD przy 3000 USD.
    # Alternatywa: {"zrodlo": "dukascopy", "symbol": "xauusd", ...} (świece d1 z Dukascopy).
    "XAUUSD": {
        "zrodlo": "stooq", "symbol": "xauusd",
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
    # Bitcoin ze Stooq — może sięgać przed 2017 (dane z giełd sprzed Binance,
    # zakres sprawdzić po pobraniu; inne źródło niż Binance).
    "BTCUSD": {
        "zrodlo": "stooq", "symbol": "btcusd",
        "commission": 0.0005,
        "spread_pct": 0.0,
        "tick": 0.01,
        "opis": "Bitcoin (Stooq)",
    },
}

_USER_AGENT = "Mozilla/5.0 (ticktester)"


# ============================================================
# POBIERANIE
# ============================================================

def plik(asset: str) -> Path:
    return FOLDER / f"{asset.replace(' ', '_')}.csv"


def pobierz(asset: str) -> Path:
    """Pobiera pełną historię świec dziennych aktywa do FOLDER."""
    spec = _spec(asset)
    zrodlo = spec["zrodlo"]
    print(f"Pobieranie {asset} ({zrodlo}: {spec['symbol']})...")

    if zrodlo == "stooq":
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
