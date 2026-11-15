"""
Test strategii na długiej historii świec dziennych (bez ticków).

Dane: narzedzia/swiece_dzienne.py (Stooq, Binance, Dukascopy d1, własny CSV)
— pobierają się w sekundy, a nie dniami jak ticki. Silnik i statystyki
te same co w run_all_assets.py (10 000 USD, 1% ryzyka przy SL, bez SL
EQUITY_FRACTION strategii, kapitalizacja, 1 tick poślizgu, prowizja),
tylko spread jest przybliżony (świece dzienne nie mają Bid/Ask).

Uruchomienie z głównego folderu repo — ustawienia niżej albo z wiersza poleceń:

    python narzedzia/test_dzienny.py
    python narzedzia/test_dzienny.py --strategia IBS_MeanReversion --aktywa QQQ XAUUSD "BTCUSDT Spot" --od 2000-01-01 --do 2025-12-31
    python narzedzia/test_dzienny.py --pobierz      # pobierz dane od nowa (np. o nowe dni)
    python narzedzia/test_dzienny.py --lista        # aktywa i zakresy pobranych danych

Wyniki: nagrania/<Odcinek>/<Strategia>/wyniki_dzienne/ (poza gitem):
podsumowanie CSV + HTML, wykres HTML i transakcje każdego aktywa,
plansze PNG jak z run_all_assets.py. Ponowny test części aktywów
podmienia ich wiersze, resztę bierze z poprzedniego podsumowania.

Pasuje do strategii na świecach dziennych (TIMEFRAMES z "1D"). Strategie
intraday (godziny sesji, interwały minutowe) i własne świece (Renko)
na świecach dziennych nie mają sensu — program ostrzega albo je pomija.
"""

import argparse
import sys
from contextlib import contextmanager
from pathlib import Path

# Uruchamianie bezpośrednio z tego folderu: dodaj folder repo do ścieżki importów.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import matplotlib

matplotlib.use("Agg")

import pandas as pd

from narzedzia import plot_tick_backtest_xauusd as single
from narzedzia import swiece_dzienne as sd
from narzedzia.tick_config import COMMISSION, TICK_SIZE
from narzedzia.odcinki import folder_strategii
from narzedzia.plansze import save_plansze
from narzedzia.summary_chart import save_summary_chart
from narzedzia.plansze_objasniajace.rynki_plansza import period_text, plansza as rynki_plansza


# ============================================================
# KONFIGURACJA (wiersz poleceń ją nadpisuje)
# ============================================================

STRATEGY = "IBS_MeanReversion"

# Nazwy z AKTYWA_DZIENNE w narzedzia/swiece_dzienne.py:
# "QQQ", "SPY", "XAUUSD", "BTCUSDT Spot", "BTCUSD" (+ własne).
ASSETS_TO_TEST = ["QQQ", "XAUUSD", "BTCUSDT Spot"]

# Okres handlu. Gdy dane aktywa zaczynają się później (BTC), handel
# rusza po rozgrzewce wskaźników od pierwszej dostępnej świecy.
START_DATE = "2000-01-01"
END_DATE = "2025-12-31"

TIMEFRAME = "1D"

SAVE_HTML = True
SAVE_PLANSZE = True

# Win Rate obiecany przez autora w procentach albo None.
CLAIM_WIN_RATE = None


# ============================================================
# PROGRAM
# ============================================================

def main(strategy=STRATEGY, assets=ASSETS_TO_TEST, start_date=START_DATE,
         end_date=END_DATE, pobierz=False, claim_win_rate=CLAIM_WIN_RATE):
    module = single.load_strategy(strategy)
    name = module.NAME
    _check_strategy(strategy, module)

    out_dir = folder_strategii(strategy) / "wyniki_dzienne"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Strategia: {name} | świece dzienne | {start_date} – {end_date}")

    warmup = single.warmup_span(TIMEFRAME, module)
    rows, equities = [], {}

    for asset in assets:
        print("\n" + "=" * 60 + f"\n{asset}\n" + "=" * 60)
        try:
            spec = sd._spec(asset)
            history = sd.wczytaj(asset, pobierz_od_nowa=pobierz)
        except Exception as error:  # brak pliku, sieć, nieznane aktywo
            print(f"POMINIĘTO {asset}: {error}")
            rows.append(_skipped(asset, error))
            continue

        # Handel od START_DATE albo od pierwszej świecy po rozgrzewce.
        start = max(pd.Timestamp(start_date), history.index[0] + warmup)
        end = min(pd.Timestamp(end_date), history.index[-1])
        if start > end:
            error = f"za mało danych ({history.index[0]:%Y-%m-%d} – {history.index[-1]:%Y-%m-%d})"
            print(f"POMINIĘTO {asset}: {error}")
            rows.append(_skipped(asset, error))
            continue
        s, e = f"{start:%Y-%m-%d}", f"{end:%Y-%m-%d}"
        if s != start_date:
            print(f"Dane od {history.index[0]:%Y-%m-%d} → handel od {s} (po rozgrzewce {warmup.days} dni)")

        bars = history[(history.index >= start - warmup) & (history.index <= end)]
        ticks = sd.na_ticki(bars, spec["spread_pct"])
        file_name = f"{strategy}_{asset.replace(' ', '_')}_{TIMEFRAME}_{start_date}_{end_date}"

        try:
            with _koszty_aktywa(asset, spec, history):
                stats = single.main(
                    asset=asset, timeframe=TIMEFRAME, start_date=s, end_date=e,
                    show=False,
                    html_path=out_dir / f"{file_name}.html" if SAVE_HTML else None,
                    print_trades=False, ticks=ticks, strategy=strategy,
                )
        except (RuntimeError, ValueError) as error:
            print(f"POMINIĘTO {asset}: {error}")
            rows.append(_skipped(asset, error))
            continue

        equity = stats.pop("equity")
        trades = stats.pop("trades_table")
        stats.pop("daily_bars", None)
        if not trades.empty:
            trades.to_csv(out_dir / f"{file_name}_transakcje.csv", index=False, sep=";", decimal=",")
        _save_daily_equity(equity, out_dir / f"{file_name}_kapital.csv")
        equities[(asset, TIMEFRAME)] = equity

        # Kupno na otwarciu pierwszego dnia i trzymanie do końca — punkt odniesienia.
        period = history[(history.index >= start) & (history.index <= end)]
        years = (period.index[-1] - period.index[0]).days / 365.25
        bh = period["close"].iloc[-1] / period["open"].iloc[0]

        rows.append({
            "asset": asset,
            "timeframe": TIMEFRAME,
            "status": "OK",
            "od": s,
            "do": e,
            "trades": stats["trades"],
            "win_rate_%": _pct(stats["win_rate"]),
            "profit_factor": _round(stats["profit_factor"]),
            "return_%": _pct(stats["return"]),
            "cagr_%": _pct(stats["cagr"]),
            "max_drawdown_%": _pct(stats["max_drawdown"]),
            "avg_trade_%": _pct(stats["avg_trade"]),
            "final_capital": round(stats["final_capital"], 2),
            "buy_hold_%": round((bh - 1) * 100, 2),
            "buy_hold_cagr_%": round((bh ** (1 / years) - 1) * 100, 2) if years > 0 else None,
            "seria_strat": stats["loss_streak"],
            "seria_strat_%": _pct(stats["loss_streak_return"]),
            "seria_od": _date(stats["loss_streak_start"]),
            "seria_do": _date(stats["loss_streak_end"]),
            "koszty": _costs_text(asset),
            "zrodlo": f"{spec['zrodlo']}: {spec['symbol']}",
            "uwagi": f"pliki: {file_name}.*",
        })

    # ========================================================
    # PODSUMOWANIE
    # ========================================================

    summary = pd.DataFrame(rows)
    table = out_dir / f"podsumowanie_{strategy}_{start_date}_{end_date}.csv"
    summary = _merge_previous(summary, table, out_dir, equities, strategy, start_date, end_date, assets)
    if "trades" in summary:
        summary["trades"] = pd.to_numeric(summary["trades"], errors="coerce").astype("Int64")
    summary.to_csv(table, index=False, sep=";", decimal=",")

    ok = summary[summary["status"] == "OK"] if "status" in summary else summary.iloc[0:0]
    costs = (
        "świece dzienne, koszty przybliżone: "
        + "; ".join(_costs_text(a) for a in dict.fromkeys(ok["asset"]) if a in sd.AKTYWA_DZIENNE)
        + "; poślizg 1 tick"
    )
    later = [f"{a} od {str(o)[:4]}" for a, o in zip(ok.get("asset", []), ok.get("od", []))
             if str(o)[:4] != start_date[:4]]
    period = f"{start_date[:4]}–{end_date[:4]}" + (f" ({', '.join(later)})" if later else "")

    if not ok.empty:
        save_summary_chart(out_dir / f"{table.stem}.html", ok,
                           title=f"{name} | świece dzienne | {period}", costs=costs)
        if SAVE_PLANSZE:
            plansze_dir = out_dir / f"plansze_{strategy}_{start_date}_{end_date}"
            rynki_plansza(list(dict.fromkeys(ok["asset"])), [TIMEFRAME],
                          plansze_dir / "0_rynki.png", period_text(start_date, end_date))
            save_plansze(plansze_dir, ok, equities, title=name, period=period,
                         costs=costs, claim_win_rate=claim_win_rate)

    print("\n" + "=" * 60)
    print(f"PODSUMOWANIE | {name} | świece dzienne | {period}")
    print(costs)
    print("=" * 60)
    show = [c for c in ("asset", "status", "od", "trades", "win_rate_%", "profit_factor", "return_%",
                        "cagr_%", "max_drawdown_%", "buy_hold_%", "buy_hold_cagr_%") if c in summary]
    print(summary[show].astype(object).fillna("–").to_string(index=False))
    if not ok.empty:
        print(f"\nNa plusie po kosztach: {int((ok['return_%'] > 0).sum())} z {len(ok)}. "
              f"Mediana wyniku netto: {ok['return_%'].median():.2f}%.")
    print(f"\nWyniki zapisane w: {out_dir}")
    return summary


def lista():
    """Aktywa z AKTYWA_DZIENNE i zakres pobranych danych."""
    print(f"Folder danych: {sd.FOLDER}\n")
    for asset, spec in sd.AKTYWA_DZIENNE.items():
        path = sd.FOLDER / spec["symbol"] if spec["zrodlo"] == "csv" else sd.plik(asset)
        if path.exists():
            bars = sd.wczytaj(asset)
            info = f"{bars.index[0]:%Y-%m-%d} – {bars.index[-1]:%Y-%m-%d} ({len(bars)} świec)"
        else:
            info = "nie pobrane"
        print(f"  {asset:<14} {spec['zrodlo']}: {spec['symbol']:<10} {info}")


# ============================================================
# POMOCNICZE
# ============================================================

def _check_strategy(strategy, module):
    if getattr(module, "BUILD_BARS", None) is not None:
        raise SystemExit(f"{strategy}: strategia buduje własne świece (BUILD_BARS) — nie da się jej liczyć na świecach dziennych.")
    timeframes = getattr(module, "TIMEFRAMES", None)
    if timeframes is not None and TIMEFRAME not in timeframes:
        print(f"UWAGA: autor/strategia zakłada interwały {timeframes}, a tu liczymy {TIMEFRAME}. "
              "Wynik nie jest testem strategii autora.")


@contextmanager
def _koszty_aktywa(asset, spec, history):
    """
    plot_tick_backtest_xauusd.main bierze prowizję i tick z tick_config,
    a szczyt historii (HISTORY_HIGH, np. ATH_ATR) z pliku ticków.
    Na czas testu podstawiamy wartości aktywa dziennego.
    """
    saved = {d_name: (d, d.get(asset, _MISSING)) for d_name, d in (("c", COMMISSION), ("t", TICK_SIZE))}
    saved_history_high = single.history_high
    COMMISSION[asset] = spec["commission"]
    TICK_SIZE[asset] = spec["tick"]

    def history_high(_asset, _ticks, before):
        older = history["high"][history.index < pd.Timestamp(before).normalize()]
        return float(older.max()) if not older.empty else None

    single.history_high = history_high
    try:
        yield
    finally:
        single.history_high = saved_history_high
        for d, value in saved.values():
            if value is _MISSING:
                d.pop(asset, None)
            else:
                d[asset] = value


_MISSING = object()


def _costs_text(asset):
    spec = sd.AKTYWA_DZIENNE[asset]
    text = (f"{asset}: prowizja {spec['commission'] * 100:.4g}%/stronę"
            + (f", spread ~{spec['spread_pct'] * 100:.3g}% ceny" if spec["spread_pct"] else ""))
    return text.replace(".", ",")


def _merge_previous(summary, table, out_dir, equities, strategy, start_date, end_date, assets):
    """Wiersze aktywów spoza tego testu zostają z poprzedniego podsumowania."""
    if not table.exists():
        return summary
    old = pd.read_csv(table, sep=";", decimal=",")
    keep = old[~old["asset"].isin(list(assets)) & (old["status"] == "OK")]
    if keep.empty:
        return summary
    print("\nZ poprzedniego podsumowania zostają: " + ", ".join(keep["asset"]))
    for asset in keep["asset"]:
        path = out_dir / f"{strategy}_{asset.replace(' ', '_')}_{TIMEFRAME}_{start_date}_{end_date}_kapital.csv"
        if path.exists():
            equities[(asset, TIMEFRAME)] = pd.read_csv(path, sep=";", decimal=",")
    return pd.concat([keep, summary], ignore_index=True)


def _save_daily_equity(equity, path):
    if equity.empty:
        return
    values = (equity.assign(timestamp=pd.to_datetime(equity["timestamp"]))
              .set_index("timestamp")["equity"].astype(float).sort_index())
    values.rename("equity").rename_axis("timestamp").reset_index().to_csv(
        path, index=False, sep=";", decimal=",")


def _skipped(asset, error):
    return {"asset": asset, "timeframe": TIMEFRAME, "status": "pominięto", "uwagi": str(error)}


def _date(value):
    return None if value is None else value.strftime("%Y-%m-%d")


def _pct(value):
    return None if value is None else round(value * 100, 2)


def _round(value):
    return None if value is None else round(value, 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test strategii na świecach dziennych z długą historią.")
    parser.add_argument("--strategia", default=STRATEGY)
    parser.add_argument("--aktywa", nargs="+", default=ASSETS_TO_TEST)
    parser.add_argument("--od", default=START_DATE)
    parser.add_argument("--do", default=END_DATE)
    parser.add_argument("--pobierz", action="store_true", help="pobierz dane od nowa")
    parser.add_argument("--claim-win-rate", type=float, default=CLAIM_WIN_RATE)
    parser.add_argument("--lista", action="store_true", help="pokaż aktywa i zakresy danych")
    args = parser.parse_args()
    if args.lista:
        lista()
    else:
        main(args.strategia, args.aktywa, args.od, args.do, args.pobierz, args.claim_win_rate)
