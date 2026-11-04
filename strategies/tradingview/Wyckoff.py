"""
Wyckoff Accumulation & Distribution, Spring, UTAD, SOS [LunqFX]
(TradingView Community Scripts):
https://www.tradingview.com/script/y9jjEUGv-Wyckoff-Accumulation-Distribution-Spring-UTAD-SOS-LunqFX/

Autor: forex, złoto, indeksy, krypto, 15m–1D. Wskaźnik NIE daje
wejścia ("The schematic gives structure and targets, not an entry.
It has no stop loss or position sizing"). Plik zawiera port 1:1
maszyny stanów wskaźnika (Pine v6), z którego korzystają:
- analizy/event_study_wyckoff.py: track record autora (panel "THIS SYMBOL"),
- run_all_assets.py: strategia z NASZYM wejściem na poziomach autora
  + grupa kontrolna Wyckoff_Control, porównanie: analizy/compare_control.py.

Reguły z kodu (ustawienia domyślne, DEFAULTS niżej). Wszystko na
zamkniętych świecach i dopiero, gdy ATR(50) ma wartość:

1. Klimaks (szukany tylko, gdy żaden schemat nie trwa):
   SC: low <= najniższe low z 50 świec, high − low >= 1,2 ATR,
   wolumen >= 1,5 × SMA(20) wolumenu (wolumen = liczba ticków).
   BC lustrzanie. SC i BC na tej samej świecy: SC, gdy świeca
   spadkowa, inaczej BC.
2. Faza A: ekstremum klimaksu przesuwa się z nowymi knotami. AR =
   pivot high (akumulacja) / low (dystrybucja) 3/3 po ekstremum,
   >= 2 ATR od niego. AR dalej niż 10 ATR → model kasowany. Brak AR
   przez 50 świec od ekstremum → kasowany.
3. Zakres = [klimaks, AR]. Strona klimaksu cs, strona wybicia bs
   (creek / ice = AR). ST = pierwszy pivot po AR po stronie klimaksu,
   nie dalej niż 35% zakresu od klimaksu i bez przebicia.
4. Spring / UTAD: knot za cs i zamknięcie z powrotem w zakresie
   (na tej samej świecy albo w <= 3 świecach). Zamknięcie dalej niż
   30% zakresu za cs albo > 3 świece poza → FAILED. Spring przed
   15. świecą od klimaksu nie jest liczony, fail przed 15. świecą
   kasuje model (V-turn). Po springu zamknięcie za jego knotem →
   FAILED.
5. SOS / SOW: zamknięcie za bs. Przed 15. świecą od klimaksu → V-turn,
   model kasowany (nie trafia do track recordu).
6. Po SOS: T1 = bs + 1 × zakres, T2 = bs + 2 × zakres (od krawędzi
   zakresu, nie od ceny). INVALID = knot springu, bez springu =
   klimaks. T1 / T2 trafiane knotem, T2 = COMPLETE. FAILED =
   zamknięcie za INVALID (T2 sprawdzane pierwsze na tej samej
   świecy). Wygasa, gdy minie > 300 świec od SOS. Zakres bez wybicia
   wygasa po > 300 świecach od klimaksu (po springu: od springu).
7. LPS / LPSY: pierwszy pivot po SOS po stronie wybicia od środka
   zakresu (tylko etykieta, faza E).
8. Track record (panel): wszystkie zakończone zakresy (FAILED,
   COMPLETE, wygasłe) — liczba, % spring/UTAD, % SOS/SOW, % T2,
   % FAILED; mianownik obejmuje też zakresy bez wybicia.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from strategies.tiktok.LuxAlgo_SR_Breaks_MSTS import pivot_high, pivot_low
from strategies.tiktok.SR_Retest import atr as atr_rma


NAME = "Wyckoff (LunqFX)"

# Autor: "15m to 1D". Standard kanału: 15m / 1h / 4h.
TIMEFRAMES = ["15min", "1h", "4h"]

# ------------------------------------------------------------
# Wersja do backtestu (NASZE założenie wejścia — autor podaje tylko
# poziomy, nie wejście):
# - wejście na SOS (long) / SOW (short): pierwszy tick po zamknięciu
#   świecy SOS / SOW,
# - SL = INVALID autora (knot springu / UTAD, bez niego klimaks),
#   wykonywany na ticku (autor uznaje FAILED dopiero zamknięciem),
# - TP = T2 autora (COMPLETE),
# - wyjście, gdy schemat się kończy inaczej (wygaśnięcie po 300
#   świecach od SOS albo FAILED z luką za SL): po zamknięciu tej
#   świecy,
# - 1% ryzyka do SL. Jeden schemat naraz = jedna pozycja naraz.
# Grupa kontrolna: Wyckoff_Control.py.
# ------------------------------------------------------------
OPPOSITE_SIGNAL = "ignore"
SAME_SIGNAL = "ignore"

# Ustawienia wskaźnika inne niż domyślne autora, np. {"side": "Accumulation"}.
PARAMS = {}

DEFAULTS = {
    "side": "Both",        # "Both" / "Accumulation" / "Distribution"
    "trend_len": 50,       # Climax lookback
    "clim_rng": 1.2,       # Climax bar range (× ATR)
    "clim_vol": 1.5,       # Climax volume (× 20-bar average)
    "piv_len": 3,          # Swing strength
    "ar_min": 2.0,         # Min. automatic rally / reaction (× ATR)
    "max_h": 10.0,         # Max. range height (× ATR)
    "min_range": 15,       # Min. range length (bars)
    "st_tol": 0.35,        # Secondary test zone (part of range)
    "spr_bars": 3,         # Spring / UTAD max. bars outside
    "fail_dep": 0.30,      # Break depth (part of range)
    "max_rng": 300,        # Range expiry (bars)
    "max_leg": 300,        # Markup / markdown expiry (bars)
}

ATR_LEN = 50
VOL_LEN = 20


@dataclass
class Schematic:
    dir: int                  # 1 akumulacja, -1 dystrybucja
    start: int                # świeca klimaksu (startBar)
    ext: float                # ekstremum klimaksu
    ext_bar: int
    ar: float = np.nan
    ar_bar: int | None = None
    range_bar: int | None = None   # świeca, na której AR został potwierdzony
    top: float = np.nan
    bot: float = np.nan
    st_bar: int | None = None
    st: float = np.nan
    spring: float = np.nan
    spring_bar: int | None = None       # świeca knota springu
    spring_conf_bar: int | None = None  # świeca potwierdzenia springu
    sos_bar: int | None = None
    sos_close: float = np.nan
    sos_atr: float = np.nan
    t1: float = np.nan
    t2: float = np.nan
    inv: float = np.nan
    lps_bar: int | None = None
    lps: float = np.nan
    t1_bar: int | None = None
    t2_bar: int | None = None
    end_bar: int | None = None
    result: str | None = None      # "complete" / "failed" / "expired" / "dropped"

    @property
    def height(self) -> float:
        return self.top - self.bot

    @property
    def cs(self) -> float:
        return self.ext

    @property
    def bs(self) -> float:
        return self.ar


def _run(bars: pd.DataFrame, params: dict) -> list[Schematic]:
    """Maszyna stanów 1:1 z Pine. Zwraca wszystkie modele (też skasowane)."""
    p = {**DEFAULTS, **params}
    n = len(bars)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    open_ = bars["open"].to_numpy(dtype=float)
    volume = (
        np.nan_to_num(bars["volume"].to_numpy(dtype=float))
        if "volume" in bars.columns
        else np.zeros(n)
    )

    atr = atr_rma(bars, ATR_LEN)
    avg_v = pd.Series(volume).rolling(VOL_LEN).mean().to_numpy()
    has_vol = np.nan_to_num(avg_v) > 0
    rng_ok = ~np.isnan(atr) & (high - low >= p["clim_rng"] * np.nan_to_num(atr, nan=np.inf))
    vol_ok = ~has_vol | (volume >= p["clim_vol"] * np.nan_to_num(avg_v))
    tl = p["trend_len"]
    lowest = pd.Series(low).rolling(tl).min().to_numpy()
    highest = pd.Series(high).rolling(tl).max().to_numpy()
    new_lo = low <= np.nan_to_num(lowest, nan=-np.inf)
    new_hi = high >= np.nan_to_num(highest, nan=np.inf)
    new_lo &= ~np.isnan(lowest)
    new_hi &= ~np.isnan(highest)

    pv_len = p["piv_len"]
    ph = pivot_high(bars["high"], pv_len, pv_len).to_numpy(dtype=float)
    pl = pivot_low(bars["low"], pv_len, pv_len).to_numpy(dtype=float)

    side = p["side"]
    min_range = p["min_range"]

    out: list[Schematic] = []
    s: Schematic | None = None
    stage = 0
    # stan springu w toku (pend)
    pend = False
    pend_n = 0
    pend_ext = np.nan
    pend_ext_bar = None
    hit_max = 0

    for i in range(n):
        if np.isnan(atr[i]):
            continue

        ev_drop = ev_fail = ev_done = ev_exp = False
        d = s.dir if s is not None else 0
        age = i - s.start if s is not None else None
        early = age is not None and age < min_range
        wick_c = low[i] if d == 1 else high[i]
        fav = high[i] if d == 1 else low[i]
        p_bar = i - pv_len

        if stage >= 4:
            prev_hit = hit_max
            if (fav - s.t2) * d >= 0:
                hit_max = 2
            elif hit_max < 1 and (fav - s.t1) * d >= 0:
                hit_max = 1
            if hit_max > prev_hit:
                if hit_max >= 1 and s.t1_bar is None:
                    s.t1_bar = i
                if hit_max == 2:
                    s.t2_bar = i
            if hit_max == 2:
                ev_done = True
            elif (s.inv - close[i]) * d > 0:
                ev_fail = True
            elif i - s.sos_bar > p["max_leg"]:
                ev_exp = True
            if stage == 4 and not ev_done and not ev_fail:
                pv = pl[i] if d == 1 else ph[i]
                mid = (s.top + s.bot) / 2
                if not np.isnan(pv) and p_bar > s.sos_bar and (pv - mid) * d > 0:
                    stage = 5
                    s.lps_bar, s.lps = p_bar, pv

        elif stage in (2, 3):
            cs, bs, h = s.cs, s.bs, s.height
            if stage == 2 and not pend and s.st_bar is None:
                pv = pl[i] if d == 1 else ph[i]
                if (
                    not np.isnan(pv) and p_bar > s.ar_bar
                    and (pv - cs) * d >= 0 and (pv - cs) * d <= p["st_tol"] * h
                ):
                    s.st_bar, s.st = p_bar, pv
            spr_on = False
            if (close[i] - bs) * d > 0:
                if early:
                    ev_drop = True
                else:
                    stage = 4
                    s.sos_bar = i
                    s.sos_close = close[i]
                    s.sos_atr = atr[i]
                    s.t1 = bs + d * h
                    s.t2 = bs + d * 2 * h
                    s.inv = s.spring if s.spring_bar is not None else cs
            elif stage == 2:
                if pend:
                    pend_n += 1
                    if (pend_ext - wick_c) * d > 0:
                        pend_ext, pend_ext_bar = wick_c, i
                    if (close[i] - cs) * d >= 0:
                        pend = False
                        if not early:
                            spr_on = True
                            s.spring, s.spring_bar = pend_ext, pend_ext_bar
                    elif (cs - close[i]) * d > p["fail_dep"] * h or pend_n > p["spr_bars"]:
                        if early:
                            ev_drop = True
                        else:
                            ev_fail = True
                elif (cs - wick_c) * d > 0:
                    if (close[i] - cs) * d >= 0:
                        if not early:
                            spr_on = True
                            s.spring, s.spring_bar = wick_c, i
                    elif (cs - close[i]) * d > p["fail_dep"] * h:
                        if early:
                            ev_drop = True
                        else:
                            ev_fail = True
                    else:
                        pend, pend_n = True, 1
                        pend_ext, pend_ext_bar = wick_c, i
                if spr_on:
                    stage = 3
                    s.spring_conf_bar = i
                elif age > p["max_rng"] and not ev_fail and not ev_drop:
                    ev_exp = True
            else:
                if (s.spring - close[i]) * d > 0:
                    ev_fail = True
                elif i - s.spring_bar > p["max_rng"]:
                    ev_exp = True

        elif stage == 1:
            if (s.ext - wick_c) * d > 0:
                s.ext, s.ext_bar = wick_c, i
            pv = ph[i] if d == 1 else pl[i]
            if not np.isnan(pv) and p_bar > s.ext_bar and (pv - s.ext) * d >= p["ar_min"] * atr[i]:
                if abs(pv - s.ext) > p["max_h"] * atr[i]:
                    ev_drop = True
                else:
                    stage = 2
                    s.ar, s.ar_bar, s.range_bar = pv, p_bar, i
                    s.top, s.bot = max(s.ext, pv), min(s.ext, pv)
            elif i - s.ext_bar > tl:
                ev_drop = True

        if stage == 0:
            sc = side != "Distribution" and new_lo[i] and rng_ok[i] and vol_ok[i]
            bc = side != "Accumulation" and new_hi[i] and rng_ok[i] and vol_ok[i]
            if sc or bc:
                d_new = 1 if sc and (not bc or close[i] < open_[i]) else -1
                s = Schematic(
                    dir=d_new, start=i,
                    ext=low[i] if d_new == 1 else high[i], ext_bar=i,
                )
                out.append(s)
                stage = 1
                pend, pend_n = False, 0
                hit_max = 0

        if ev_drop:
            s.result, s.end_bar = "dropped", i
            stage = 0
        if (ev_fail or ev_done or ev_exp) and stage >= 2:
            s.result = "failed" if ev_fail else "complete" if ev_done else "expired"
            s.end_bar = i
            stage = 0

    return out


def schematics(bars: pd.DataFrame, **params) -> pd.DataFrame:
    """
    Tabela modeli, które stały się zakresem (bez skasowanych V-turnów
    i bez modeli bez AR). result = None: schemat trwał do końca danych.
    """
    rows = []
    idx = bars.index
    for s in _run(bars, params):
        if s.result == "dropped" or s.range_bar is None:
            continue
        t = lambda b: idx[b] if b is not None else pd.NaT  # noqa: E731
        rows.append({
            "type": "accumulation" if s.dir == 1 else "distribution",
            "dir": s.dir,
            "climax_bar": s.start, "climax_time": t(s.start),
            "range_bar": s.range_bar, "range_time": t(s.range_bar),
            "range_bot": s.bot, "range_top": s.top, "height": s.height,
            "spring": s.spring_bar is not None,
            "spring_price": s.spring,
            "sos": s.sos_bar is not None,
            "sos_bar": s.sos_bar, "sos_time": t(s.sos_bar),
            "sos_close": s.sos_close, "sos_atr": s.sos_atr,
            "t1": s.t1, "t2": s.t2, "invalid": s.inv,
            "t1_hit": s.t1_bar is not None, "t2_hit": s.t2_bar is not None,
            "lps": s.lps_bar is not None,
            "result": s.result,
            "end_bar": s.end_bar, "end_time": t(s.end_bar),
            "bars_before_break": (s.sos_bar - s.start) if s.sos_bar is not None else np.nan,
        })
    return pd.DataFrame(rows, columns=_COLUMNS)


_COLUMNS = [
    "type", "dir", "climax_bar", "climax_time", "range_bar", "range_time",
    "range_bot", "range_top", "height", "spring", "spring_price", "sos",
    "sos_bar", "sos_time", "sos_close", "sos_atr", "t1", "t2", "invalid",
    "t1_hit", "t2_hit", "lps", "result", "end_bar", "end_time",
    "bars_before_break",
]


def track_record(table: pd.DataFrame) -> dict:
    """Panel autora: tylko zakończone zakresy, osobno akumulacja i dystrybucja."""
    done = table[table["result"].notna()] if len(table) else table
    rec = {}
    for name in ("accumulation", "distribution"):
        part = done[done["type"] == name] if len(done) else done
        n = len(part)
        pct = lambda m: round(100 * m.sum() / n, 1) if n else np.nan  # noqa: E731
        rec[name] = {
            "ranges": n,
            "spring_pct": pct(part["spring"]) if n else np.nan,
            "sos_pct": pct(part["sos"]) if n else np.nan,
            "t1_pct": pct(part["t1_hit"]) if n else np.nan,
            "t2_pct": pct(part["t2_hit"]) if n else np.nan,
            "failed_pct": pct(part["result"] == "failed") if n else np.nan,
        }
    sos = done[done["sos"]] if len(done) else done
    rec["avg_bars_before_break"] = (
        float(sos["bars_before_break"].mean()) if len(sos) else np.nan
    )
    return rec


# ============================================================
# STRATEGIA (nasze założenie wejścia, patrz u góry)
# ============================================================

_CACHE = {}


def _cached_run(bars: pd.DataFrame) -> list[Schematic]:
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


def trades(bars: pd.DataFrame) -> list[dict]:
    """Jedno wejście na każdy SOS / SOW: świeca, kierunek, SL, TP, wyjście."""
    out = []
    for s in _cached_run(bars):
        if s.sos_bar is None:
            continue
        out.append({
            "bar": s.sos_bar,
            "dir": s.dir,
            "sl": s.inv,
            "tp": s.t2,
            "exit_bar": s.end_bar,  # None = do końca danych
            "close": s.sos_close,
            "atr": s.sos_atr,
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
        x = e["exit_bar"]
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
    Zakres (prostokąt) od klimaksu do SOS / końca, creek / ice,
    po SOS: T1, T2 i INVALID do końca schematu. Etykiety zdarzeń
    jak u autora. Tylko zakresy, które nie zostały skasowane.
    Panel: ATR(50).
    """
    idx = bars.index
    last = len(bars) - 1
    zones, lines = [], []
    ev = {}

    def add(name, bar):
        ev.setdefault(name, []).append(bar)

    for s in _cached_run(bars):
        if s.result == "dropped" or s.range_bar is None:
            continue
        acc = s.dir == 1
        end = s.end_bar if s.end_bar is not None else last
        box_end = s.sos_bar if s.sos_bar is not None else end
        zones.append((idx[s.ext_bar], idx[box_end], s.top, s.bot, "rgba(124,140,255,0.15)"))
        edge = "#B4FF39" if acc else "#FF6B2C"
        lines.append((idx[s.ar_bar], s.bs, idx[box_end], s.bs, edge))
        if s.sos_bar is not None:
            for y, c in ((s.t1, edge), (s.t2, edge), (s.inv, "#8A8F9C")):
                lines.append((idx[s.sos_bar], y, idx[end], y, c))

        add("SC" if acc else "BC", s.ext_bar)
        add("AR+" if acc else "AR-", s.ar_bar)
        if s.st_bar is not None:
            add("ST+" if acc else "ST-", s.st_bar)
        if s.spring_bar is not None:
            add("SPRING" if acc else "UTAD", s.spring_bar)
        if s.sos_bar is not None:
            add("SOS" if acc else "SOW", s.sos_bar)
        if s.lps_bar is not None:
            add("LPS" if acc else "LPSY", s.lps_bar)
        if s.t2_bar is not None:
            add("T2+" if acc else "T2-", s.t2_bar)
        if s.result == "failed":
            add("FAILED+" if acc else "FAILED-", s.end_bar)

    def mask(bars_list):
        m = np.zeros(len(bars), dtype=bool)
        m[list(bars_list)] = True
        return pd.Series(m, index=idx)

    # (klucz, nazwa, tekst, kolor, położenie)
    spec = [
        ("SC", "SC", "SC", "#969CAB", "below"),
        ("BC", "BC", "BC", "#969CAB", "above"),
        ("AR+", "AR (akumulacja)", "AR", "#969CAB", "above"),
        ("AR-", "AR (dystrybucja)", "AR", "#969CAB", "below"),
        ("ST+", "ST (akumulacja)", "ST", "#969CAB", "below"),
        ("ST-", "ST (dystrybucja)", "ST", "#969CAB", "above"),
        ("SPRING", "Spring", "SPRING", "#7C8CFF", "below"),
        ("UTAD", "UTAD", "UTAD", "#7C8CFF", "above"),
        ("SOS", "SOS", "SOS", "#B4FF39", "above"),
        ("SOW", "SOW", "SOW", "#FF6B2C", "below"),
        ("LPS", "LPS", "LPS", "#B4FF39", "below"),
        ("LPSY", "LPSY", "LPSY", "#FF6B2C", "above"),
        ("T2+", "T2 ✓ (akumulacja)", "T2 ✓", "#00D084", "above"),
        ("T2-", "T2 ✓ (dystrybucja)", "T2 ✓", "#00D084", "below"),
        ("FAILED+", "FAILED (akumulacja)", "FAILED", "#FF3B30", "below"),
        ("FAILED-", "FAILED (dystrybucja)", "FAILED", "#FF3B30", "above"),
    ]
    labels = [
        (name, mask(ev[key]), text, color, where)
        for key, name, text, color, where in spec
        if key in ev
    ]

    atr_series = pd.Series(atr_rma(bars, ATR_LEN), index=idx)
    top = float(np.nanpercentile(atr_series, 99.5)) if atr_series.notna().any() else 1.0
    return {
        "trend": None,
        "zones": zones,
        "lines": lines,
        "labels": labels,
        "panel": {
            "title": "ATR(50)",
            "lines": [("ATR(50)", atr_series, "#B0BEC5")],
            "levels": (),
            "range": (0, top * 1.3 or 1.0),
        },
    }
