"""
Event study: czy cena reaguje na strefach Key Level Zones (FCP)?

Wskaźnik nie daje sygnałów, więc nie liczymy wyniku w USD.
Sprawdzamy to, co autor sugeruje: strefa to miejsce, gdzie cena
częściej reaguje, a więcej poziomów w strefie = silniejsza reakcja.

Zdarzenie = PIERWSZE dotknięcie strefy w dniu, w którym obowiązuje
(świece 1 min, ceny Bid). Strefa, w której cena jest już na otwarciu
dnia, jest pomijana.
- Cena przyszła z góry (strefa jako wsparcie): ODBICIE, gdy high dojdzie
  do górnej krawędzi + TARGET_ATR × ATR, zanim low dojdzie do dolnej
  krawędzi − TARGET_ATR × ATR (PRZEBICIE). Z dołu lustrzanie.
- ATR = ten sam ATR(14) z 4h, którego używa wskaźnik danego dnia.
- Wyścig trwa najdłużej HORIZON_DAYS dni; potem "brak rozstrzygnięcia".
  Obie granice w tej samej świecy 1 min → "niejednoznaczne" (pomijane).

Kontrola (ta sama geometria i ta sama reguła):
- Pojedyncze poziomy: HL i pivoty, które wskaźnik odrzucił (nie leżą
  w żadnej strefie), jako pudełka o wysokości mediany stref z tego dnia.
- Losowe poziomy: dla każdej strefy RANDOM_PER_ZONE pudełek tej samej
  wysokości, w tej samej odległości od otwarcia dnia, w losowym
  kierunku, przesuniętych losowo o ±0,25 ATR.

Przy braku przewagi odsetek odbić stref ≈ odsetek odbić losowych poziomów.

Uruchomienie:
    python analizy/event_study_key_levels.py
    python analizy/event_study_key_levels.py XAUUSD 2025-03-12   # strefy z jednego dnia (porównanie z TV)
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Uruchamianie bezpośrednio z tego folderu: dodaj folder repo do ścieżki importów.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from narzedzia.tick_config import ASSETS, REVERSE_BID_ASK
from narzedzia.tick_data import load_ticks_cached
from narzedzia.tick_engine import build_bars
from narzedzia.odcinki import folder_strategii
from strategies.tradingview_porownawcze import KeyLevelZones as klz


ASSETS_TO_TEST = ["XAUUSD", "Bitcoin", "EURUSD", "Brent", "US500"]
START_DATE = "2021-01-01"
END_DATE = "2025-12-31"

TARGET_ATR = 1.0
HORIZON_DAYS = 5
RANDOM_PER_ZONE = 3
SEED = 42

# Zapas danych przed START_DATE na poprzedni miesiąc i ATR.
WARMUP_DAYS = 70

OUTPUT_DIR = folder_strategii("KeyLevelZones") / "wyniki_event_study"

GROUPS = [
    "Strefy: 2 poziomy (turkus)",
    "Strefy: 3 poziomy (złote)",
    "Strefy: 4+ poziomów (czerwone)",
    "Wszystkie strefy",
    "Pojedyncze poziomy",
    "Losowe poziomy",
]


# ============================================================
# Dane
# ============================================================

def load_minute_bars(asset: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Świece 1 min z ticków, rok po roku (mniej pamięci przy BTC)."""
    start = pd.Timestamp(start_date) - pd.Timedelta(days=WARMUP_DAYS)
    end = pd.Timestamp(end_date) + pd.Timedelta(days=HORIZON_DAYS + 3)

    parts = []
    year_start = start
    while year_start < end:
        year_end = min(pd.Timestamp(year=year_start.year + 1, month=1, day=1), end)
        print(f"  ticki {year_start.date()} – {year_end.date()}")
        try:
            ticks = load_ticks_cached(
                ASSETS[asset],
                reverse_bid_ask=REVERSE_BID_ASK[asset],
                start_date=year_start.strftime("%Y-%m-%d"),
                end_date=year_end.strftime("%Y-%m-%d"),
            )
        except (FileNotFoundError, ValueError, RuntimeError) as error:
            print(f"  brak danych: {error}")
            ticks = None
        if ticks is not None and not ticks.empty:
            parts.append(build_bars([ticks], "1min")[["open", "high", "low", "close"]])
        del ticks
        year_start = year_end

    if not parts:
        raise FileNotFoundError(f"Brak danych dla {asset}")
    bars = pd.concat(parts)
    bars = bars[~bars.index.duplicated(keep="last")].sort_index()
    return bars


# ============================================================
# Pomiar jednego zdarzenia
# ============================================================

def measure(top, bot, i0, i_end, i_horizon, o, h, l, target) -> tuple:
    """
    Pierwsze dotknięcie [bot, top] między i0 a i_end i wyścig
    odbicie / przebicie do i_horizon. Zwraca (wynik, strona, czas).
    """
    start_price = o[i0]
    if bot <= start_price <= top:
        return "start w strefie", None, None

    from_above = start_price > top
    window = l[i0:i_end] <= top if from_above else h[i0:i_end] >= bot
    if not window.any():
        return "bez dotknięcia", None, None
    k = i0 + int(np.argmax(window))

    up = top + target
    down = bot - target
    # Świeca dotknięcia: dalszy ruch w kierunku przebicia jest pewny
    # (cena przyszła z drugiej strony), odbicie w tej samej świecy — nie.
    if from_above and l[k] <= down:
        return "przebicie", "z góry", k
    if not from_above and h[k] >= up:
        return "przebicie", "z dołu", k

    hh = h[k + 1:i_horizon]
    ll = l[k + 1:i_horizon]
    hit_up = np.flatnonzero(hh >= up)
    hit_down = np.flatnonzero(ll <= down)
    first_up = hit_up[0] if hit_up.size else None
    first_down = hit_down[0] if hit_down.size else None

    side = "z góry" if from_above else "z dołu"
    if first_up is None and first_down is None:
        return "brak rozstrzygnięcia", side, k
    if first_up is not None and first_down is not None and first_up == first_down:
        return "niejednoznaczne", side, k

    up_first = first_down is None or (first_up is not None and first_up < first_down)
    # Z góry: wyjście w górę = odbicie. Z dołu: wyjście w dół = odbicie.
    bounce = up_first if from_above else not up_first
    return ("odbicie" if bounce else "przebicie"), side, k


def run_asset(asset: str, bars: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    days = klz.daily_zones(bars)
    index = bars.index
    o = bars["open"].to_numpy()
    h = bars["high"].to_numpy()
    l = bars["low"].to_numpy()

    start = pd.Timestamp(START_DATE)
    end = pd.Timestamp(END_DATE) + pd.Timedelta(days=1)

    rows = []
    for day in days:
        if day["day"] < start or day["day"] >= end or np.isnan(day["atr"]):
            continue

        atr = day["atr"]
        target = TARGET_ATR * atr
        i0 = index.searchsorted(day["t0"])
        i_end = index.searchsorted(day["t_end"])
        i_horizon = index.searchsorted(day["t0"] + pd.Timedelta(days=HORIZON_DAYS))
        open_price = o[i0]

        boxes = []
        zones = day["zones"]
        for zone in zones:
            group = (
                GROUPS[0] if zone["members"] <= 2 else GROUPS[1] if zone["members"] == 3 else GROUPS[2]
            )
            boxes.append((group, zone["top"], zone["bot"], zone["members"], zone["names"]))

            height = zone["top"] - zone["bot"]
            distance = abs((zone["top"] + zone["bot"]) / 2 - open_price)
            for _ in range(RANDOM_PER_ZONE):
                centre = open_price + rng.choice([-1, 1]) * distance + rng.uniform(-0.25, 0.25) * atr
                boxes.append((GROUPS[5], centre + height / 2, centre - height / 2, 0, "losowy"))

        heights = [z["top"] - z["bot"] for z in zones]
        lone_height = float(np.median(heights)) if heights else klz.MAX_HEIGHT_ATR * atr
        for price, _, name in day["levels"]:
            if any(z["lo"] <= price <= z["hi"] for z in zones):
                continue
            boxes.append((GROUPS[4], price + lone_height / 2, price - lone_height / 2, 1, name))

        for group, top, bot, members, names in boxes:
            outcome, side, k = measure(top, bot, i0, i_end, i_horizon, o, h, l, target)
            rows.append(
                {
                    "aktywo": asset,
                    "dzien": day["day"].date(),
                    "grupa": group,
                    "poziomy": members,
                    "nazwy": names,
                    "gora": top,
                    "dol": bot,
                    "atr": atr,
                    "strona": side,
                    "dotkniecie": index[k] if k is not None else pd.NaT,
                    "wynik": outcome,
                }
            )
    return pd.DataFrame(rows)


# ============================================================
# Podsumowanie
# ============================================================

def wilson(successes: int, n: int, z: float = 1.96) -> tuple:
    if n == 0:
        return np.nan, np.nan
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return centre - half, centre + half


def summarize(events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for asset in list(events["aktywo"].unique()) + ["RAZEM"]:
        part = events if asset == "RAZEM" else events[events["aktywo"] == asset]
        for group in GROUPS:
            if group == "Wszystkie strefy":
                g = part[part["grupa"].isin(GROUPS[:3])]
            else:
                g = part[part["grupa"] == group]
            touched = g[~g["wynik"].isin(["start w strefie", "bez dotknięcia"])]
            decided = touched[touched["wynik"].isin(["odbicie", "przebicie"])]
            bounces = int((decided["wynik"] == "odbicie").sum())
            n = len(decided)
            lo, hi = wilson(bounces, n)
            rows.append(
                {
                    "aktywo": asset,
                    "grupa": group,
                    "dotknięcia": len(touched),
                    "rozstrzygnięte": n,
                    "odbicia %": round(100 * bounces / n, 1) if n else np.nan,
                    "95% od": round(100 * lo, 1) if n else np.nan,
                    "95% do": round(100 * hi, 1) if n else np.nan,
                    "nierozstrzygnięte": int((touched["wynik"] == "brak rozstrzygnięcia").sum()),
                    "niejednoznaczne": int((touched["wynik"] == "niejednoznaczne").sum()),
                }
            )
    return pd.DataFrame(rows)


def show_day(asset: str, date: str) -> None:
    """Strefy z jednego dnia — do porównania z wykresem TV."""
    bars = load_minute_bars(asset, date, date)
    for day in klz.daily_zones(bars):
        if str(day["day"].date()) != date:
            continue
        print(f"\n{asset} {date}  ATR(14, 4h) = {day['atr']:.5f}")
        for zone in day["zones"]:
            print(
                f"  {zone['bot']:.5f} – {zone['top']:.5f}  "
                f"(zakres poziomów {zone['lo']:.5f} – {zone['hi']:.5f})  "
                f"{zone['members']} poziomy: {zone['names']}"
            )
        return
    print("Brak tego dnia w danych.")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    all_events = []
    for asset in ASSETS_TO_TEST:
        print(f"\n=== {asset} ===")
        try:
            bars = load_minute_bars(asset, START_DATE, END_DATE)
        except FileNotFoundError as error:
            print(f"POMINIĘTO {asset}: {error}")
            continue
        events = run_asset(asset, bars, rng)
        events.to_csv(OUTPUT_DIR / f"zdarzenia_{asset.replace(' ', '_')}.csv", index=False)
        all_events.append(events)
        del bars

    if not all_events:
        print("Brak danych.")
        return

    summary = summarize(pd.concat(all_events, ignore_index=True))
    summary.to_csv(OUTPUT_DIR / f"podsumowanie_{START_DATE}_{END_DATE}.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_rows", 200):
        print(summary.to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) == 3:
        show_day(sys.argv[1], sys.argv[2])
    else:
        main()
