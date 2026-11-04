"""
Squeeze Breakout Signals [bitpunk] (TradingView Community Scripts):
https://www.tradingview.com/script/Ah51TSsn/

Autor nie podaje interwału ani rynku ("Use standard time-based
candles"). Wskaźnik daje WEJŚCIA (białe ▲ / ▼, alerty "LONG @close"
/ "SHORT @close", typ BREAKOUT albo RETEST), ale nie wyjście:
"The script marks entries for chart analysis and does not manage
exits." Plik zawiera port 1:1 maszyny stanów (Pine v6, MPL-2.0).

Reguły z kodu (ustawienia domyślne, DEFAULTS niżej). Wszystko na
zamkniętych świecach:

1. Kompresja: 2 × odch. std. zamknięć (20, populacyjne) <
   1,5 × SMA(TR, 20). TR pierwszej świecy = high − low.
2. Seria skompresowanych świec buduje pudełko (high / low serii,
   najwyżej 20 ostatnich świec). Gotowe po 3 skompresowanych
   zamknięciach; świeca zdarzenia nie poszerza własnej krawędzi.
   Nowy epizod wymaga 3 nieskompresowanych zamknięć.
3. Blokada pudełka: pierwsze zamknięcie poza gotowym pudełkiem w
   trakcie kompresji albo pierwsza nieskompresowana świeca. Krawędzie
   i średni TR (z poprzedniej świecy) zamrożone. Okno obserwacji:
   20 świec łącznie ze świecą blokady.
4. BREAKOUT: pierwsze zamknięcie nad górną / pod dolną krawędzią.
   Kierunek pierwszego wybicia to jedyny kierunek wejść z pudełka.
5. RETEST: po wybiciu cała świeca musi wyjść poza strefę
   krawędź ± 0,25 średniego TR, potem świeca dotyka strefy i
   zamknięcie jest za krawędzią (na tej lub późniejszej świecy).
   Zamknięcie na / za przeciwną krawędzią kasuje oczekujący retest.
   Filtr "Retest Close Progress": zamknięcie retestu wyżej (long) /
   niżej (short) niż poprzednie zamknięcie.
6. Max Entry Extension = 0: bez limitu odległości od krawędzi.
7. Nowe dojrzałe pudełko w trakcie obserwacji: jeśli zachodzi na stare
   cenowo, dzieli z nim okno i limit wejść, jeśli nie — zastępuje je.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


NAME = "Squeeze Breakout Signals [bitpunk]"

# Autor nie podaje interwału. Standard kanału: 15m / 1h / 4h.
TIMEFRAMES = ["15min", "1h", "4h"]

# ------------------------------------------------------------
# Wersja do backtestu. Wejścia = białe ▲ / ▼ autora (BREAKOUT i
# RETEST), pierwszy tick po zamknięciu świecy sygnału.
# NASZE założenie (autor nie zarządza wyjściem):
# - SL = przeciwna krawędź pudełka (u autora zamknięcie za nią
#   kasuje setup), wykonywany na ticku,
# - TP = krawędź wybicia + 1 × wysokość pudełka (measured move),
# - 1% ryzyka do SL, bez wyjścia czasowego,
# - jedna pozycja naraz: sygnał przy otwartej pozycji (np. retest
#   po wybiciu) jest pomijany, tak jak w silniku (SAME_SIGNAL="ignore").
#   Sygnał, którego zamknięcie jest już za TP, jest pomijany (silnik
#   i tak nie otworzy pozycji z TP po złej stronie ceny).
# Grupa kontrolna: SqueezeBreakoutSignals_Control.py.
# ------------------------------------------------------------
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

TP_BOX_MULT = 1.0   # TP = krawędź ± TP_BOX_MULT × wysokość pudełka

# Ustawienia wskaźnika inne niż domyślne autora, np. {"entry_filter": False}.
PARAMS = {}

DEFAULTS = {
    "length": 20,             # Compression Length
    "minimum_bars": 3,        # Minimum Compression
    "validity_bars": 20,      # Range Watch (bars)
    "max_extension": 0.0,     # Max Entry Extension (TR)
    "retest_tolerance": 0.25, # Retest Tolerance (TR)
    "entry_filter": True,     # Retest Close Progress
}


def _indicator_series(bars: pd.DataFrame, length: int):
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    prev = np.concatenate(([np.nan], close[:-1]))
    # ta.tr(true): na pierwszej świecy high − low.
    tr = np.fmax(high - low, np.fmax(np.abs(high - prev), np.abs(low - prev)))
    tr[0] = high[0] - low[0]
    c = pd.Series(close)
    deviation = c.rolling(length).std(ddof=0).to_numpy()   # ta.stdev(..., true)
    scale = pd.Series(tr).rolling(length).mean().to_numpy()
    recent_high = pd.Series(high).rolling(length).max().to_numpy()
    recent_low = pd.Series(low).rolling(length).min().to_numpy()
    return high, low, close, deviation, scale, recent_high, recent_low


@dataclass
class Watch:
    """Zablokowane pudełko (okno obserwacji) — do wykresu i statystyk."""
    start: int          # pierwsza świeca serii kompresji
    lock: int           # świeca blokady
    top: float
    bot: float
    scale: float        # zamrożony średni TR
    end: int | None = None
    owner: int = 0


@dataclass
class _S:
    count: int = 0
    episode: int = 0
    outside_count: int = 0
    can_start: bool = True
    run_high: float = np.nan
    run_low: float = np.nan
    run_start: int | None = None
    used: bool = False
    run_upper_probe: bool = False
    run_lower_probe: bool = False
    watching: bool = False
    watch_episode: int | None = None
    range_high: float = np.nan
    range_low: float = np.nan
    frozen_scale: float = np.nan
    started: int | None = None
    upper_broken: bool = False
    lower_broken: bool = False
    owner_side: int = 0
    departed: bool = False
    failed: bool = False
    upper_probed: bool = False
    lower_probed: bool = False
    retest_side: int = 0
    break_at: int | None = None
    touched: bool = False
    # zdarzenia bieżącej świecy
    breakout: int = 0
    retest: int = 0
    signal: int = 0
    kind: int = 0


def _run(bars: pd.DataFrame, params: dict):
    """
    Maszyna stanów 1:1 z Pine. Zwraca (events, watches, ratio):
    events — lista słowników na każdą świecę z wybiciem / retestem,
    watches — zablokowane pudełka, ratio — Compression Width Ratio.
    """
    p = {**DEFAULTS, **params}
    length = p["length"]
    min_bars = p["minimum_bars"]
    validity = p["validity_bars"]
    max_ext = p["max_extension"]
    tol = p["retest_tolerance"]

    high, low, close, dev, scale, rhigh, rlow = _indicator_series(bars, length)
    n = len(bars)
    data_ready = ~np.isnan(dev) & ~np.isnan(scale) & (scale > 0)
    with np.errstate(invalid="ignore"):
        compressed = data_ready & (2.0 * dev < 1.5 * scale)
        ratio = np.where(data_ready, 2.0 * dev / (1.5 * scale), np.nan)

    s = _S()
    events, watches = [], []
    cur: list[Watch | None] = [None]

    def clear_watch(i):
        s.watching = False
        s.watch_episode = None
        s.retest_side = 0
        s.break_at = None
        s.touched = False
        s.departed = False
        s.failed = False
        if cur[0] is not None:
            cur[0].end = i
            cur[0] = None

    def lock(i, prior_scale):
        s.used = True
        if not np.isnan(prior_scale) and prior_scale > 0:
            s.watching = True
            s.watch_episode = s.episode
            s.range_high = s.run_high
            s.range_low = s.run_low
            s.frozen_scale = prior_scale
            s.started = i
            s.upper_broken = False
            s.lower_broken = False
            s.owner_side = 0
            s.departed = False
            s.failed = False
            s.upper_probed = s.run_upper_probe
            s.lower_probed = s.run_lower_probe
            s.retest_side = 0
            s.break_at = None
            s.touched = False
            if cur[0] is not None:   # nie powinno się zdarzyć
                cur[0].end = i
            cur[0] = Watch(s.run_start, i, s.run_high, s.run_low, prior_scale)
            watches.append(cur[0])

    def observe(i):
        h, lo, c = high[i], low[i], close[i]
        if h > s.range_high and not s.upper_probed:
            s.upper_probed = True
        if lo < s.range_low and not s.lower_probed:
            s.lower_probed = True
        side = 1 if c > s.range_high else -1 if c < s.range_low else 0
        first_break = (
            not s.upper_broken if side > 0
            else not s.lower_broken if side < 0 else False
        )
        if first_break:
            s.breakout = side
            s.upper_broken = s.upper_broken or side > 0
            s.lower_broken = s.lower_broken or side < 0
            if s.owner_side == 0:
                s.owner_side = side
                s.retest_side = side
                s.break_at = i
                s.touched = False
                pocket = tol * s.frozen_scale
                s.departed = (
                    lo > s.range_high + pocket if side > 0
                    else h < s.range_low - pocket
                )
                cur[0].owner = side
        if s.retest_side != 0 and i > s.break_at:
            d = s.retest_side
            edge = s.range_high if d > 0 else s.range_low
            opposite = s.range_low if d > 0 else s.range_high
            if d * (c - opposite) / s.frozen_scale <= 0:
                s.retest_side = 0
                s.touched = False
                s.failed = True
            else:
                pocket = tol * s.frozen_scale
                if s.departed:
                    s.touched = s.touched or (lo <= edge + pocket and h >= edge - pocket)
                    if s.touched and d * (c - edge) / s.frozen_scale > 0:
                        s.retest = d
                        s.retest_side = 0
                        s.touched = False
                elif (lo > edge + pocket if d > 0 else h < edge - pocket):
                    s.departed = True
        ev = s.retest if s.retest != 0 else s.breakout
        if ev != 0:
            edge = s.range_high if ev > 0 else s.range_low
            distance = ev * (c - edge) / s.frozen_scale
            within = max_ext == 0 or distance <= max_ext
            if ev == s.owner_side and within:
                s.signal = ev
                s.kind = 2 if s.retest != 0 else 1

    for i in range(n):
        s.breakout = s.retest = s.signal = s.kind = 0
        prior_scale = scale[i - 1] if i > 0 else np.nan
        if not data_ready[i]:
            clear_watch(i)
            s.count = 0
            s.outside_count = 0
            s.can_start = True
            s.used = False
            s.run_high = s.run_low = np.nan
            s.run_start = None
            continue

        had_watch = s.watching
        if s.watching and i - s.started >= validity:
            clear_watch(i - 1)
        if s.watching:
            observe(i)
        if compressed[i]:
            if s.count == 0:
                if s.can_start:
                    s.episode += 1
                    s.used = False
                    s.run_upper_probe = False
                    s.run_lower_probe = False
                s.run_high = high[i]
                s.run_low = low[i]
                s.run_start = i
            s.can_start = False
            s.outside_count = 0
            prior_prepared = (
                s.count >= min_bars and not s.used and s.run_high > s.run_low
            )
            if prior_prepared and not had_watch:
                early = (
                    1 if close[i] > s.run_high
                    else -1 if close[i] < s.run_low else 0
                )
                if early != 0:
                    lock(i, prior_scale)
                    if s.watching:
                        observe(i)
                else:
                    if high[i] > s.run_high and not s.run_upper_probe:
                        s.run_upper_probe = True
                    if low[i] < s.run_low and not s.run_lower_probe:
                        s.run_lower_probe = True
            s.count += 1
            if not s.used:
                if s.count >= length:
                    s.run_high = rhigh[i]
                    s.run_low = rlow[i]
                    s.run_start = i - (length - 1)
                else:
                    s.run_high = max(s.run_high, high[i])
                    s.run_low = min(s.run_low, low[i])
                if (
                    s.watching and s.watch_episode != s.episode
                    and s.count >= min_bars and s.run_high > s.run_low
                ):
                    overlaps = (
                        s.run_low <= s.range_high and s.run_high >= s.range_low
                    )
                    if overlaps:
                        s.used = True   # to samo pole cenowe: wspólne okno i limit
                    else:
                        clear_watch(i)  # replaced
                if not s.watching:
                    s.range_high = s.run_high
                    s.range_low = s.run_low
        else:
            if (
                s.count >= min_bars and not s.used and not s.watching
                and s.run_high > s.run_low
            ):
                lock(i, prior_scale)
                if s.watching:
                    observe(i)
            s.count = 0
            s.outside_count += 1
            if s.outside_count >= min_bars:
                s.can_start = True

        if s.breakout != 0 or s.retest != 0:
            events.append({
                "bar": i,
                "breakout": s.breakout,
                "retest": s.retest,
                "signal": s.signal,
                "kind": s.kind,
                "top": s.range_high,
                "bot": s.range_low,
                "scale": s.frozen_scale,
                "close": close[i],
                "watch": len(watches) - 1,
            })
    if cur[0] is not None:
        cur[0].end = n - 1
    return events, watches, ratio


def entry_signals(bars: pd.DataFrame, params: dict | None = None) -> list[dict]:
    """Białe ▲ / ▼ autora (po filtrze Retest Close Progress)."""
    p = {**DEFAULTS, **(PARAMS if params is None else params)}
    events, _, _ = _cached_run(bars)
    close = bars["close"].to_numpy(dtype=float)
    out = []
    for e in events:
        if e["signal"] == 0:
            continue
        i = e["bar"]
        if p["entry_filter"] and e["kind"] == 2:
            if i == 0 or not e["signal"] * (close[i] - close[i - 1]) > 0:
                continue   # "filtered"
        out.append(e)
    return out


# ============================================================
# STRATEGIA (nasze SL / TP, patrz u góry)
# ============================================================

_CACHE = {}


def _cached_run(bars: pd.DataFrame):
    """generate_signals i indicators liczą to samo — liczymy raz."""
    key = (
        len(bars),
        bars.index[0] if len(bars) else None,
        bars.index[-1] if len(bars) else None,
        float(bars["close"].sum()) if len(bars) else 0.0,
        tuple(sorted(PARAMS.items())),
    )
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = _run(bars, PARAMS)
    return _CACHE[key]


def bar_exit(high, low, j, d, sl, tp):
    """Pierwsza świeca po j, na której knot dotyka SL lub TP (None = do końca)."""
    h, lo = high[j + 1:], low[j + 1:]
    hit = (lo <= sl) | (h >= tp) if d == 1 else (h >= sl) | (lo <= tp)
    k = np.flatnonzero(hit)
    return j + 1 + int(k[0]) if len(k) else None


def trades(bars: pd.DataFrame) -> list[dict]:
    """
    Wejścia, które strategia faktycznie weźmie: sygnał autora, SL na
    przeciwnej krawędzi, TP = krawędź + wysokość pudełka, jedna
    pozycja naraz (wyjście szacowane na świecach: knot dotyka SL / TP).
    """
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    out, busy_until = [], -1
    for e in entry_signals(bars):
        j, d = e["bar"], e["signal"]
        if j <= busy_until:
            continue   # pozycja otwarta — sygnał pominięty
        height = e["top"] - e["bot"]
        if d == 1:
            sl, tp = e["bot"], e["top"] + TP_BOX_MULT * height
        else:
            sl, tp = e["top"], e["bot"] - TP_BOX_MULT * height
        if d * (tp - e["close"]) <= 0:
            continue   # zamknięcie już za TP
        x = bar_exit(high, low, j, d, sl, tp)
        busy_until = x if x is not None else len(bars)
        out.append({
            "bar": j, "dir": d, "kind": e["kind"], "sl": sl, "tp": tp,
            "close": e["close"], "scale": e["scale"], "exit_bar": None,
        })
    return out


def signals_frame(bars: pd.DataFrame, entries: list[dict]) -> pd.DataFrame:
    n = len(bars)
    buy = np.zeros(n, dtype=bool)
    sell = np.zeros(n, dtype=bool)
    exit_long = np.zeros(n, dtype=bool)
    exit_short = np.zeros(n, dtype=bool)
    sl = np.full(n, np.nan)
    tp = np.full(n, np.nan)
    for e in entries:
        b = e["bar"]
        (buy if e["dir"] == 1 else sell)[b] = True
        sl[b], tp[b] = e["sl"], e["tp"]
        x = e.get("exit_bar")
        if x is not None and x < n:
            (exit_long if e["dir"] == 1 else exit_short)[x] = True
    return pd.DataFrame(
        {
            "buy": buy, "sell": sell,
            "stop_loss": sl, "take_profit": tp,
            "exit_long": exit_long, "exit_short": exit_short,
        },
        index=bars.index,
    )


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    return signals_frame(bars, trades(bars))


def indicators(bars: pd.DataFrame) -> dict:
    """
    Zablokowane pudełka (od początku kompresji do końca okna
    obserwacji), krawędzie w kolorach autora, etykiety BREAKOUT /
    RETEST (wejścia) i kropki wybić bez wejścia. Panel: Compression
    Width Ratio (< 1 = kompresja).
    """
    idx = bars.index
    events, watches, ratio = _cached_run(bars)
    bull, bear = "#00C2FF", "#FF3864"
    zones, lines = [], []
    for w in watches:
        end = w.end if w.end is not None else len(bars) - 1
        color = (
            "rgba(0,194,255,0.12)" if w.owner > 0
            else "rgba(255,56,100,0.12)" if w.owner < 0
            else "rgba(242,242,242,0.08)"
        )
        zones.append((idx[w.start], idx[end], w.top, w.bot, color))
        lines.append((idx[w.lock], w.top, idx[end], w.top, bull))
        lines.append((idx[w.lock], w.bot, idx[end], w.bot, bear))

    entered = {e["bar"]: e for e in entry_signals(bars)}
    ev = {}
    for e in events:
        b = e["bar"]
        if b in entered:
            k = entered[b]
            key = ("BO" if k["kind"] == 1 else "RT") + ("+" if k["signal"] > 0 else "-")
        elif e["breakout"] != 0:
            key = "obs+" if e["breakout"] > 0 else "obs-"
        else:
            key = "held+" if e["retest"] > 0 else "held-"
        ev.setdefault(key, []).append(b)

    def mask(bars_list):
        m = np.zeros(len(bars), dtype=bool)
        m[list(bars_list)] = True
        return pd.Series(m, index=idx)

    spec = [
        ("BO+", "Long BREAKOUT ▲", "▲ BO", bull, "below"),
        ("RT+", "Long RETEST ▲", "▲ RT", bull, "below"),
        ("BO-", "Short BREAKOUT ▼", "▼ BO", bear, "above"),
        ("RT-", "Short RETEST ▼", "▼ RT", bear, "above"),
        ("obs+", "Wybicie w górę bez wejścia", "•", "#8A8F9C", "above"),
        ("obs-", "Wybicie w dół bez wejścia", "•", "#8A8F9C", "below"),
        ("held+", "Retest long odfiltrowany", "◆", "#8A8F9C", "below"),
        ("held-", "Retest short odfiltrowany", "◆", "#8A8F9C", "above"),
    ]
    labels = [
        (name, mask(ev[key]), text, color, where)
        for key, name, text, color, where in spec
        if key in ev
    ]

    r = pd.Series(ratio, index=idx)
    top = float(np.nanpercentile(r, 99)) if r.notna().any() else 2.0
    return {
        "trend": None,
        "zones": zones,
        "lines": lines,
        "labels": labels,
        "panel": {
            "title": "Compression Width Ratio (< 1 = kompresja)",
            "lines": [("Width Ratio", r, "#B0BEC5")],
            "levels": (1.0,),
            "range": (0, max(top * 1.1, 1.5)),
        },
    }
