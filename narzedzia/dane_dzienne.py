"""
Świece dzienne do badań na długiej historii.

Dwa źródła:
1. Ticki z D:\\Tickdata (te same co w backtestach) → świece 1D,
   ticki czytane rok po roku, żeby nie zabrakło pamięci.
2. Pliki CSV z cenami dziennymi, np. ze Stooq (stooq.pl → wykres
   instrumentu → „Pobierz dane w pliku CSV”, interwał dzienny).
   Obsługiwane nagłówki: angielskie (Date, Open, High, Low, Close)
   i polskie ze Stooq (Data, Otwarcie, Najwyzszy, Najnizszy, Zamkniecie).
   Wystarczą kolumny daty i zamknięcia.
"""

from pathlib import Path

import pandas as pd

from narzedzia.tick_config import ASSETS, REVERSE_BID_ASK
from narzedzia.tick_data import load_ticks_cached
from narzedzia.tick_engine import build_bars

_COLUMNS = {
    "date": "date", "data": "date", "datetime": "date",
    "open": "open", "otwarcie": "open",
    "high": "high", "najwyzszy": "high", "najwyższy": "high",
    "low": "low", "najnizszy": "low", "najniższy": "low",
    "close": "close", "zamkniecie": "close", "zamknięcie": "close",
    "adj close": "adj_close",
}


def load_daily_csv(path) -> pd.DataFrame:
    """CSV z cenami dziennymi → DataFrame (indeks: data; kolumny open/high/low/close)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"brak pliku {path}")
    df = pd.read_csv(path, sep=None, engine="python")
    df.columns = [_COLUMNS.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns]
    if "date" not in df or "close" not in df:
        raise ValueError(f"{path.name}: potrzebne kolumny daty i zamknięcia, są {list(df.columns)}")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    cols = [c for c in ("open", "high", "low", "close") if c in df]
    df = df[cols].apply(pd.to_numeric, errors="coerce")
    return df[df["close"] > 0].dropna(subset=["close"])


def daily_bars_from_ticks(asset: str, start: str, end: str) -> pd.DataFrame:
    """Świece 1D z ticków (ceny Bid), ładowanie rok po roku."""
    if asset not in ASSETS:
        raise KeyError(f"nieznane aktywo {asset}")
    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end) + pd.Timedelta(days=1)
    parts = []
    for year in range(start_ts.year, end_ts.year + 1):
        a = max(start_ts, pd.Timestamp(f"{year}-01-01"))
        b = min(end_ts, pd.Timestamp(f"{year + 1}-01-01"))
        if a >= b:
            continue
        ticks = load_ticks_cached(
            ASSETS[asset],
            reverse_bid_ask=REVERSE_BID_ASK[asset],
            start_date=a.strftime("%Y-%m-%d"),
            end_date=b.strftime("%Y-%m-%d"),
        )
        if ticks.empty:
            continue
        print(f"  ticki {asset} {year}")
        parts.append(build_bars([ticks.sort_values("timestamp")], "1D"))
        del ticks
    if not parts:
        raise FileNotFoundError(f"brak ticków {asset} w {start} – {end}")
    bars = pd.concat(parts).sort_index()
    bars = bars[~bars.index.duplicated(keep="last")]
    return bars[["open", "high", "low", "close"]].dropna(subset=["close"])
