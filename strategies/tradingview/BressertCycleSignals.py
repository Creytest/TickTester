"""
Bressert Cycle Signals (BY_Tse, TradingView Community Scripts):
https://pl.tradingview.com/script/ARm00iF4-Bressert-Cycle-Signals/

Port 1:1 wskaźnika (Pine v6, indicator) z ustawieniami domyślnymi:
Double Stochastic 10, linie 40/70, filtr trendu "HTF oscillator
direction" z automatycznym wyższym interwałem, próg skrętu 0,
okno wejścia 4 świece, zlecenie 1 tick za świecą setupu, trailing
stop 2 świece "At oscillator extreme". Pasma czasowe przy domyślnym
"Signal band filter = Off" nie wpływają na sygnały, więc ich nie
liczymy.

Autor projektował skrypt na D1 z trendem z W1. Nasze 15m/1h/4h
to test poza tym zastosowaniem; 1D to wariant autorski.
"""

import numpy as np
import pandas as pd


NAME = "Bressert Cycle Signals"

TIMEFRAMES = ["15min", "1h", "4h", "1D"]

# Przeciwny trigger odwraca pozycję. Trigger w tę samą stronę
# zostawia pozycję i jej stop bez zmian (opis autora).
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"

# Ustawienia domyślne skryptu.
DS_LENGTH = 10
BUY_LINE = 40.0
SELL_LINE = 70.0
TURN_THRESHOLD = 0.0
TRIGGER_WINDOW = 4
TRIGGER_OFFSET_TICKS = 1
TRAIL_BARS = 2
TREND_FILTER = True     # False = "None"

# Najmniejsza zmiana ceny (syminfo.mintick). Ustawiana przez
# plot_tick_backtest_xauusd.py z TICK_SIZE w tick_config.py.
TICK = 0.01


# ============================================================
# Oscylator
# ============================================================

def _ratio(src, hi, lo, n, start_bar):
    """f_ratio(): stochastic, przy zerowym zakresie poprzednia wartość."""
    hh = pd.Series(hi).rolling(n).max().to_numpy()
    ll = pd.Series(lo).rolling(n).min().to_numpy()
    out = np.full(len(src), np.nan)
    r = np.nan
    for i in range(len(src)):
        rng = hh[i] - ll[i]
        if i >= start_bar and i >= n - 1 and rng > 0:
            r = 100.0 * (src[i] - ll[i]) / rng
        out[i] = r
    return out


def _smooth(x):
    """f_smooth(): każda wartość przesuwa się w połowie drogi do nowej."""
    out = np.full(len(x), np.nan)
    s = np.nan
    for i, v in enumerate(x):
        if not np.isnan(v):
            s = v if np.isnan(s) else s + 0.5 * (v - s)
        out[i] = s
    return out


def double_stochastic(bars: pd.DataFrame, n: int = DS_LENGTH) -> np.ndarray:
    """f_dbs(): stochastic ze stochastica, oba wygładzone (rekonstrukcja autora)."""
    close = bars["close"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    k1 = _smooth(_ratio(close, high, low, n, n - 1))
    return _smooth(_ratio(k1, k1, k1, n, 2 * (n - 1)))


# ============================================================
# Filtr trendu z wyższego interwału
# ============================================================

def _chart_timeframe(index: pd.DatetimeIndex) -> pd.Timedelta:
    return pd.Series(index).diff().dropna().min()


def _htf_keys(index: pd.DatetimeIndex, chart_tf: pd.Timedelta) -> pd.DatetimeIndex:
    """
    f_autoHTF(): intraday × 4 (15m → 1h, 1h → 4h, 4h → 16h),
    dzienny → tygodniowy. Świece HTF liczone od początku dnia
    danych (00:00 = 17:00 NY, start sesji FX), tydzień od poniedziałku.
    """
    day = index.normalize()
    if chart_tf >= pd.Timedelta("1D"):
        return day - pd.to_timedelta(index.dayofweek, unit="D")
    htf = chart_tf * 4
    return day + ((index - day) // htf) * htf


def htf_trend(bars: pd.DataFrame) -> np.ndarray:
    """
    f_htfState() z lookahead_on i [1]: kierunek oscylatora HTF
    z ostatniej ZAMKNIĘTEJ świecy HTF (+1 rósł, −1 spadał, 0 brak).
    """
    keys = _htf_keys(bars.index, _chart_timeframe(bars.index))
    htf = bars.groupby(keys).agg(
        high=("high", "max"), low=("low", "min"), close=("close", "last")
    )
    osc = pd.Series(double_stochastic(htf), index=htf.index)
    prev = osc.shift(1)
    state = np.where(osc > prev, 1, np.where(osc < prev, -1, 0))
    # st[1]: stan poprzedniej świecy HTF.
    state = pd.Series(state, index=htf.index).shift(1).fillna(0)
    return state.reindex(keys).to_numpy(dtype=int)


# ============================================================
# Sygnały
# ============================================================

def _simulate(bars: pd.DataFrame) -> dict:
    """
    Kod wskaźnika świeca po świecy (te same kroki i kolejność co w Pine).

    Silnik wykonuje zlecenia na tickach, a strategia przekazuje:
    - buy / sell + entry_stop: zlecenie stop ważne w następnej świecy,
      ponawiane do końca okna 4 świec;
    - stop_loss: przybliżony stop początkowy do wielkości pozycji
      (Pine liczy go dopiero na świecy wejścia);
    - trail_long / trail_short: stop pozycji z zamknięcia świecy
      (początkowy i podciągany) — dokładnie jak linia stopu w Pine.
    """
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    osc = double_stochastic(bars)
    trend = htf_trend(bars) if TREND_FILTER else np.zeros(len(bars), dtype=int)
    tick = TICK
    off = TRIGGER_OFFSET_TICKS * tick
    n = len(bars)

    low_n = pd.Series(low).rolling(TRAIL_BARS).min().to_numpy()
    high_n = pd.Series(high).rolling(TRAIL_BARS).max().to_numpy()

    out = {
        "osc": osc,
        "trend": trend,
        "allow_b": np.zeros(n, dtype=bool),
        "allow_s": np.zeros(n, dtype=bool),
        "trig_b": np.zeros(n, dtype=bool),
        "trig_s": np.zeros(n, dtype=bool),
        "pos": np.zeros(n, dtype=int),
        "stop": np.full(n, np.nan),
        "b_stop": np.full(n, np.nan),   # zlecenie czekające po zamknięciu świecy
        "b_exp": np.full(n, -1),
        "b_start": np.full(n, -1),
        "s_stop": np.full(n, np.nan),
        "s_exp": np.full(n, -1),
        "s_start": np.full(n, -1),
    }

    pos, stop_p, entry_bar, trail_on = 0, np.nan, -1, False
    b_stop, b_exp, b_start = np.nan, -1, -1
    s_stop, s_exp, s_start = np.nan, -1, -1
    ext_b, done_b, start_b = np.nan, True, -1
    ext_s, done_s, start_s = np.nan, True, -1

    for i in range(n):
        # Wyjścia otwartej pozycji (nie na świecy wejścia).
        if pos == 1 and i > entry_bar and low[i] <= stop_p:
            pos = 0
        elif pos == -1 and i > entry_bar and high[i] >= stop_p:
            pos = 0

        # Triggery czekających zleceń.
        trig_b = trig_s = False
        b_start_trig = s_start_trig = -1
        if not np.isnan(b_stop):
            trig_b = i <= b_exp and high[i] >= b_stop
            b_start_trig = b_start
            if trig_b or i >= b_exp:
                b_stop, b_exp = np.nan, -1
        if not np.isnan(s_stop):
            trig_s = i <= s_exp and low[i] <= s_stop
            s_start_trig = s_start
            if trig_s or i >= s_exp:
                s_stop, s_exp = np.nan, -1

        # Wejścia; oba triggery na jednej świecy — brak wejścia.
        if trig_b and not trig_s and pos != 1:
            pos, entry_bar = 1, i
            trail_on = False
            stop_p = low[max(b_start_trig, 0):i + 1].min() - tick
        elif trig_s and not trig_b and pos != -1:
            pos, entry_bar = -1, i
            trail_on = False
            stop_p = high[max(s_start_trig, 0):i + 1].max() + tick

        # Świece setupu na zamknięciu.
        setup_b = setup_s = False
        if i >= 1 and not np.isnan(osc[i]) and not np.isnan(osc[i - 1]):
            o, o1 = osc[i], osc[i - 1]
            if o < o1:
                if done_b or o1 - ext_b > TURN_THRESHOLD:
                    ext_b, done_b, start_b = o, False, i - 1
                else:
                    ext_b = min(ext_b, o)
            elif o > o1 and not done_b:
                if ext_b < BUY_LINE and o - ext_b > TURN_THRESHOLD:
                    setup_b, done_b = True, True
            if o > o1:
                if done_s or ext_s - o1 > TURN_THRESHOLD:
                    ext_s, done_s, start_s = o, False, i - 1
                else:
                    ext_s = max(ext_s, o)
            elif o < o1 and not done_s:
                if ext_s > SELL_LINE and ext_s - o > TURN_THRESHOLD:
                    setup_s, done_s = True, True

        allow_b = setup_b and trend[i] >= 0
        allow_s = setup_s and trend[i] <= 0
        if allow_b:
            b_stop, b_exp, b_start = high[i] + off, i + TRIGGER_WINDOW, start_b
        if allow_s:
            s_stop, s_exp, s_start = low[i] - off, i + TRIGGER_WINDOW, start_s

        # Trailing stop na zamknięciu.
        if pos != 0:
            if not np.isnan(osc[i]):
                if (pos == 1 and osc[i] >= SELL_LINE) or (pos == -1 and osc[i] <= BUY_LINE):
                    trail_on = True
            if trail_on and i >= TRAIL_BARS - 1:
                if pos == 1:
                    stop_p = max(stop_p, low_n[i] - tick)
                else:
                    stop_p = min(stop_p, high_n[i] + tick)

        out["allow_b"][i], out["allow_s"][i] = allow_b, allow_s
        out["trig_b"][i], out["trig_s"][i] = trig_b, trig_s
        out["pos"][i] = pos
        out["stop"][i] = stop_p if pos != 0 else np.nan
        out["b_stop"][i], out["b_exp"][i], out["b_start"][i] = b_stop, b_exp, b_start
        out["s_stop"][i], out["s_exp"][i], out["s_start"][i] = s_stop, s_exp, s_start

    return out


def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Wyjście: buy, sell, entry_stop, stop_loss, trail_long, trail_short.

    Silnik przyjmuje jedno zlecenie stop na świecę, a wskaźnik może
    mieć jednocześnie czekający buy stop i sell stop. Wtedy
    wystawiamy to, które zostanie trafione w następnej świecy
    (oba trafione = brak wejścia, jak w Pine), a jeśli żadne —
    nowsze. Sama cena wejścia i tak pochodzi z ticków.

    Ask może dojść do buy stopu, gdy Bid (świece) nie doszedł.
    Silnik ma wtedy pozycję, której symulacja na świecach nie ma —
    dla niej utrzymujemy "zapasowy" stop (początkowy + te same
    reguły trailingu), żeby pozycja nie została bez stopu.
    """
    sim = _simulate(bars)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    osc = sim["osc"]
    tick = TICK
    n = len(bars)

    low_n = pd.Series(low).rolling(TRAIL_BARS).min().to_numpy()
    high_n = pd.Series(high).rolling(TRAIL_BARS).max().to_numpy()

    buy = np.zeros(n, dtype=bool)
    sell = np.zeros(n, dtype=bool)
    entry = np.full(n, np.nan)
    stop_loss = np.full(n, np.nan)
    trail_long = np.full(n, np.nan)
    trail_short = np.full(n, np.nan)

    # Zlecenia na następną świecę.
    for i in range(n - 1):
        has_b = not np.isnan(sim["b_stop"][i])
        has_s = not np.isnan(sim["s_stop"][i])
        side = 0
        if has_b and has_s:
            hit_b = high[i + 1] >= sim["b_stop"][i]
            hit_s = low[i + 1] <= sim["s_stop"][i]
            if hit_b and hit_s:
                side = 0
            elif hit_b or hit_s:
                side = 1 if hit_b else -1
            else:
                side = 1 if sim["b_exp"][i] >= sim["s_exp"][i] else -1
        elif has_b:
            side = 1
        elif has_s:
            side = -1

        if side == 1:
            buy[i] = True
            entry[i] = sim["b_stop"][i]
            stop_loss[i] = low[max(sim["b_start"][i], 0):i + 1].min() - tick
        elif side == -1:
            sell[i] = True
            entry[i] = sim["s_stop"][i]
            stop_loss[i] = high[max(sim["s_start"][i], 0):i + 1].max() + tick

    # Stopy pozycji z zamknięcia świecy (obowiązują od następnej).
    spare_l = spare_s = np.nan
    spare_l_trail = spare_s_trail = False
    for i in range(n):
        pos = sim["pos"][i]

        # Zapasowy stop long: zlecenie z poprzedniej świecy mogło się
        # wypełnić na Asku, a symulacja nie weszła.
        if i >= 1 and buy[i - 1] and pos != 1 and np.isnan(spare_l):
            spare_l, spare_l_trail = stop_loss[i - 1], False
        if i >= 1 and sell[i - 1] and pos != -1 and np.isnan(spare_s):
            spare_s, spare_s_trail = stop_loss[i - 1], False

        if pos == 1:
            spare_l = np.nan
        elif not np.isnan(spare_l):
            if low[i] <= spare_l:
                spare_l = np.nan
            else:
                if not np.isnan(osc[i]) and osc[i] >= SELL_LINE:
                    spare_l_trail = True
                if spare_l_trail and not np.isnan(low_n[i]):
                    spare_l = max(spare_l, low_n[i] - tick)

        if pos == -1:
            spare_s = np.nan
        elif not np.isnan(spare_s):
            if high[i] >= spare_s:
                spare_s = np.nan
            else:
                if not np.isnan(osc[i]) and osc[i] <= BUY_LINE:
                    spare_s_trail = True
                if spare_s_trail and not np.isnan(high_n[i]):
                    spare_s = min(spare_s, high_n[i] + tick)

        trail_long[i] = sim["stop"][i] if pos == 1 else spare_l
        trail_short[i] = sim["stop"][i] if pos == -1 else spare_s

    result = pd.DataFrame(index=bars.index)
    result["buy"] = buy
    result["sell"] = sell
    result["entry_stop"] = entry
    result["stop_loss"] = stop_loss
    result["trail_long"] = trail_long
    result["trail_short"] = trail_short
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """Linia stopu na cenie, triggery B/S, Double Stochastic w panelu."""
    sim = _simulate(bars)
    close = bars["close"]
    stop = pd.Series(sim["stop"], index=bars.index)
    osc = pd.Series(sim["osc"], index=bars.index)
    return {
        "trend": None,
        "overlays": [
            ("Stop", stop, "#FF9800"),
        ],
        "markers": [
            ("Buy trigger", close.where(sim["trig_b"]), "#00D084", "below"),
            ("Sell trigger", close.where(sim["trig_s"]), "#FF3B30", "above"),
        ],
        "panel": {
            "title": f"Double Stochastic({DS_LENGTH})",
            "lines": [(f"DS {DS_LENGTH}", osc, "#2962FF")],
            "levels": (BUY_LINE, SELL_LINE),
            "range": (0, 100),
        },
    }
