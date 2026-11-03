"""
Liquidity Hunt Pro [Viprasol] (TradingView Community Scripts):
https://www.tradingview.com/script/CDQo43CF-Liquidity-Hunt-Pro-Viprasol/
© Viprasol, oryginał na licencji MPL 2.0 (https://mozilla.org/MPL/2.0/);
ten plik jest portem i podlega tej samej licencji.

Port 1:1 sygnałów BUY / SELL wskaźnika (Pine v6, indicator):

1. Swing high / low: ta.pivothigh / ta.pivotlow(Swing Length,
   Swing Length), znane Swing Length świec po szczycie / dołku.
2. Sweep sell-side: low < swing low i close > swing low.
   Sweep buy-side: high > swing high i close < swing high.
   "Ignore Sweeps of Broken Levels" = off: liczy się też poziom
   wcześniej przebity zamknięciem.
3. Sweep sell-side uzbraja BUY (i kasuje czekający SELL):
   SL = low świecy sweepu, poziom MSS = swing high z tej chwili.
   Nowy sweep po tej samej stronie restartuje setup.
   Setup wygasa, gdy minie więcej niż Max Bars After Sweep świec.
4. BUY na zamkniętej świecy, gdy: close > poziom MSS, poprzednie
   close <= poziom MSS (fresh shift), świeca wzrostowa z korpusem
   >= Min Reversal Body × ATR(14), close - SL > 1 tick, minęło
   więcej niż Bars Between Signals świec od poprzedniego sygnału
   (w dowolną stronę), opcjonalnie EMA 50 > EMA 200. SELL lustrzanie.
5. Wejście = zamknięcie świecy sygnału, ryzyko = |wejście - SL|,
   TP1 / TP2 / TP3 = 1× / 2× / 3× ryzyko. SL się nie przesuwa.

BOS / CHoCH, Order Blocki, FVG, linie płynności i dashboard to
wyłącznie rysunek — nie wpływają na sygnały, więc ich tu nie ma.

Nasze założenia (autor ich nie podaje):
- Wyjścia: po 1/3 pozycji na TP1, TP2, TP3, reszta na SL (TP_SPLIT).
- Wejście na pierwszym ticku po zamknięciu świecy sygnału (≈ close).
- Świeca, która dotyka SL i TP: u autora liczy się SL (dane OHLC);
  tu kolejność rozstrzygają ticki.
- Nowy sygnał zastępuje plan poprzedniego (jak na wykresie autora):
  przeciwny odwraca pozycję, w tę samą stronę zamyka starą pozycję
  i otwiera nową z nowym SL / TP i nową wielkością (1% ryzyka).

Interwał autora: 1m–1D; ustawienia zależne od interwału według
"Recommended Starting Points" (PRESETS niżej). Autor podaje zakresy,
bierzemy ich środek.
Aktywa autora: "liquid forex pairs, indices, metals, crypto or stocks".
"""

import numpy as np
import pandas as pd

from strategies.tiktok.CloudMA_EMA30_74 import ema
from strategies.tiktok.LuxAlgo_SR_Breaks_MSTS import pivot_high, pivot_low
from strategies.tiktok.SR_Retest import atr


NAME = "Liquidity Hunt Pro"

TIMEFRAMES = ["1min", "15min", "1h", "4h", "1D"]

# Przeciwny sygnał odwraca pozycję. Sygnał w tę samą stronę zamyka
# starą pozycję przez exit_long / exit_short i otwiera nową.
OPPOSITE_SIGNAL = "reverse"
SAME_SIGNAL = "ignore"

# Części pozycji zamykane na TP1, TP2, TP3 (nasze założenie).
TP_SPLIT = (1 / 3, 1 / 3, 1 / 3)

# Najmniejsza zmiana ceny (syminfo.mintick). Ustawiana przez
# plot_tick_backtest_xauusd.py z TICK_SIZE w tick_config.py.
TICK = 0.01

# "Recommended Starting Points" autora:
#   Scalping (1m-5m): Swing Length 3-5, Max Bars After Sweep 6-8
#   Intraday (15m-1H): defaults
#   Swing (4H-1D): Swing Length 8-10, Max Bars After Sweep 12-15, trend filter on
PRESETS = {
    "scalping": {"swing_len": 4, "confirm_bars": 7, "trend_filter": False},
    "intraday": {"swing_len": 5, "confirm_bars": 10, "trend_filter": False},
    "swing": {"swing_len": 9, "confirm_bars": 13, "trend_filter": True},
}

# None: preset wg interwału świec. Można wymusić, np. "intraday".
PRESET = None

# Pozostałe ustawienia domyślne skryptu (wspólne dla presetów).
ATR_LENGTH = 14
MIN_BODY_ATR = 0.15
FRESH_SHIFT = True
SIGNAL_GAP = 10
STRICT_SWEEPS = False
RR = (1.0, 2.0, 3.0)


# ============================================================
# Ustawienia wg interwału
# ============================================================

def _chart_timeframe(index: pd.DatetimeIndex) -> pd.Timedelta:
    return pd.Series(index).diff().dropna().min()


def settings(bars: pd.DataFrame) -> dict:
    """Preset dla interwału świec: do 5m scalping, do 1h intraday, wyżej swing."""
    if PRESET is not None:
        name = PRESET
    else:
        tf = _chart_timeframe(bars.index)
        if tf <= pd.Timedelta("5min"):
            name = "scalping"
        elif tf <= pd.Timedelta("1h"):
            name = "intraday"
        else:
            name = "swing"
    return {"preset": name, **PRESETS[name]}


# ============================================================
# Obliczenia wskaźnika
# ============================================================

def compute(bars: pd.DataFrame) -> dict:
    """Sygnały BUY / SELL z planem (SL, TP1-3) w kolejności z Pine."""
    cfg = settings(bars)
    swing_len = cfg["swing_len"]
    confirm_bars = cfg["confirm_bars"]
    trend_filter = cfg["trend_filter"]

    open_ = bars["open"].to_numpy(dtype=float)
    high = bars["high"].to_numpy(dtype=float)
    low = bars["low"].to_numpy(dtype=float)
    close = bars["close"].to_numpy(dtype=float)
    n = len(bars)
    tick = TICK

    ph = pivot_high(bars["high"], swing_len, swing_len).to_numpy()
    pl = pivot_low(bars["low"], swing_len, swing_len).to_numpy()

    atr_value = atr(bars, ATR_LENGTH)
    body = np.abs(close - open_)
    with np.errstate(invalid="ignore"):
        # Porównanie z na (początek ATR) daje false, jak w Pine.
        bull_candle = (close > open_) & (body >= atr_value * MIN_BODY_ATR)
        bear_candle = (close < open_) & (body >= atr_value * MIN_BODY_ATR)

    ema50 = ema(bars["close"], 50).to_numpy()
    ema200 = ema(bars["close"], 200).to_numpy()
    with np.errstate(invalid="ignore"):
        bull_trend = ema50 > ema200
        bear_trend = ema50 < ema200

    direction = np.zeros(n, dtype=int)
    stop = np.full(n, np.nan)
    tps = np.full((n, 3), np.nan)
    swing_high_line = np.full(n, np.nan)
    swing_low_line = np.full(n, np.nan)
    sweep_low_mark = np.zeros(n, dtype=bool)
    sweep_high_mark = np.zeros(n, dtype=bool)

    swing_high = np.nan
    swing_low = np.nan
    high_taken = False
    low_taken = False

    wait_bull = False
    wait_bear = False
    bull_sl = bear_sl = np.nan
    bull_mss = bear_mss = np.nan
    bull_bar = bear_bar = -1
    last_signal_bar = None

    for i in range(n):
        if not np.isnan(ph[i]):
            swing_high = ph[i]
            high_taken = False
        if not np.isnan(pl[i]):
            swing_low = pl[i]
            low_taken = False
        swing_high_line[i] = swing_high
        swing_low_line[i] = swing_low

        c = close[i]

        sweep_low = (
            not np.isnan(swing_low)
            and (not STRICT_SWEEPS or not low_taken)
            and low[i] < swing_low
            and c > swing_low
        )
        sweep_high = (
            not np.isnan(swing_high)
            and (not STRICT_SWEEPS or not high_taken)
            and high[i] > swing_high
            and c < swing_high
        )

        # Poziom "wzięty" zamknięciem (ważne tylko przy STRICT_SWEEPS).
        if not np.isnan(swing_high) and not high_taken and c > swing_high:
            high_taken = True
        if not np.isnan(swing_low) and not low_taken and c < swing_low:
            low_taken = True

        if sweep_low and not np.isnan(swing_high):
            wait_bull, wait_bear = True, False
            bull_sl, bull_mss, bull_bar = low[i], swing_high, i
            sweep_low_mark[i] = True

        if sweep_high and not np.isnan(swing_low):
            wait_bear, wait_bull = True, False
            bear_sl, bear_mss, bear_bar = high[i], swing_low, i
            sweep_high_mark[i] = True

        if wait_bull and i - bull_bar > confirm_bars:
            wait_bull = False
        if wait_bear and i - bear_bar > confirm_bars:
            wait_bear = False

        # Fresh shift: close[1] po drugiej stronie poziomu (na → false).
        prev_close = close[i - 1] if i > 0 else np.nan
        fresh_bull = not FRESH_SHIFT or prev_close <= bull_mss
        fresh_bear = not FRESH_SHIFT or prev_close >= bear_mss

        gap_ok = last_signal_bar is None or i - last_signal_bar > SIGNAL_GAP

        valid_buy = (
            wait_bull
            and not np.isnan(bull_mss)
            and c > bull_mss
            and fresh_bull
            and bull_candle[i]
            and c > bull_sl
            and c - bull_sl > tick
            and (not trend_filter or bull_trend[i])
            and gap_ok
        )
        valid_sell = (
            wait_bear
            and not np.isnan(bear_mss)
            and c < bear_mss
            and fresh_bear
            and bear_candle[i]
            and c < bear_sl
            and bear_sl - c > tick
            and (not trend_filter or bear_trend[i])
            and gap_ok
        )

        if valid_buy:
            risk = c - bull_sl
            direction[i] = 1
            stop[i] = bull_sl
            tps[i] = [c + risk * r for r in RR]
            last_signal_bar = i
            wait_bull = False

        if valid_sell:
            risk = bear_sl - c
            direction[i] = -1
            stop[i] = bear_sl
            tps[i] = [c - risk * r for r in RR]
            last_signal_bar = i
            wait_bear = False

    return {
        "settings": cfg,
        "dir": direction,
        "stop": stop,
        "tp": tps,
        "swing_high": swing_high_line,
        "swing_low": swing_low_line,
        "sweep_low": sweep_low_mark,
        "sweep_high": sweep_high_mark,
        "ema50": ema50,
        "ema200": ema200,
        "body_atr": (close - open_) / atr_value,
    }


# ============================================================
# Sygnały
# ============================================================

def generate_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """
    Wyjście: buy, sell, stop_loss, take_profit (TP1), take_profit_2,
    take_profit_3; exit_long / exit_short zamykają starą pozycję
    przy nowym sygnale w tę samą stronę (nowy plan zastępuje stary).
    """
    c = compute(bars)
    d = c["dir"]
    result = pd.DataFrame(index=bars.index)
    result["buy"] = d == 1
    result["sell"] = d == -1
    result["stop_loss"] = c["stop"]
    result["take_profit"] = c["tp"][:, 0]
    result["take_profit_2"] = c["tp"][:, 1]
    result["take_profit_3"] = c["tp"][:, 2]
    result["exit_long"] = d == 1
    result["exit_short"] = d == -1
    return result


def indicators(bars: pd.DataFrame) -> dict:
    """Swing high / low (płynność), sweepy, BUY / SELL i SL; EMA przy filtrze trendu."""
    c = compute(bars)
    idx = bars.index
    d = pd.Series(c["dir"], index=idx)
    stop = pd.Series(c["stop"], index=idx)
    overlays = [
        ("Buy-side liquidity (swing high)", pd.Series(c["swing_high"], index=idx), "#FF9800"),
        ("Sell-side liquidity (swing low)", pd.Series(c["swing_low"], index=idx), "#00BCD4"),
    ]
    if c["settings"]["trend_filter"]:
        overlays += [
            ("EMA 50", pd.Series(c["ema50"], index=idx), "#FFEB3B"),
            ("EMA 200", pd.Series(c["ema200"], index=idx), "#E040FB"),
        ]
    return {
        "trend": None,
        "overlays": overlays,
        "markers": [
            ("Sweep sell-side", bars["low"].where(c["sweep_low"]), "#00BCD4", "below"),
            ("Sweep buy-side", bars["high"].where(c["sweep_high"]), "#FF9800", "above"),
            ("BUY", bars["low"].where(d == 1), "#00D084", "below"),
            ("SELL", bars["high"].where(d == -1), "#FF3B30", "above"),
            ("SL long", stop.where(d == 1), "#FF3B30", "below"),
            ("SL short", stop.where(d == -1), "#FF3B30", "above"),
        ],
        "panel": {
            "title": "Korpus świecy (× ATR 14), próg świecy MSS",
            "lines": [
                ("Korpus / ATR", pd.Series(c["body_atr"], index=idx), "#F2F2F2"),
            ],
            "levels": (MIN_BODY_ATR, -MIN_BODY_ATR),
        },
    }
