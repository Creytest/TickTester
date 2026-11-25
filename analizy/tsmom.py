"""Replikacja badań akademickich o trendzie: time series momentum (TSMOM) na ~47 rynkach.

Moskowitz, Ooi, Pedersen (2012) „Time series momentum”, JFE 104(2); Hurst, Ooi, Pedersen (2017)
„A Century of Evidence on Trend-Following Investing”. Reguła z artykułu (wariant 12/1):
  - na koniec każdego miesiąca: czy rynek jest wyżej niż 12 miesięcy temu?
    tak → long na następny miesiąc, nie → short,
  - wielkość pozycji = 40% / zmienność roczna rynku (zmienność z dziennych zwrotów, EWMA,
    środek masy 60 dni, liczona tylko z przeszłości),
  - portfel = średnia ze wszystkich rynków dostępnych w danym miesiącu.
Uproszczenia: brak stopy wolnej od ryzyka (indeksy i ETF-y mają ją w cenie, kontrakty nie),
ciągłe kontrakty Yahoo bez korekty rolowania, bez kosztów transakcyjnych (jak w artykule, brutto).

Porównania (ten sam portfel, ta sama wielkość pozycji, inny kierunek):
  - zawsze long:          sam dryf rynków („rynki średnio rosną”),
  - losowy kierunek:      co miesiąc moneta zamiast reguły, na prawdziwych wykresach (N_SIM razy),
  - wykresy z monety:     reguła TSMOM na wykresach, w których każdy dzień ma prawdziwą wielkość
                          ruchu, a kierunek z monety (dryf zostaje) — ta sama kontrola co
                          w event_study_trend.py. Odpowiada na pytanie: czy na wykresie bez pamięci
                          reguła zarobiłaby tyle samo?

Uruchomienie (po event_study_trend.py --szeroki pliki z Yahoo są już na dysku):
    python analizy/tsmom.py
    python analizy/tsmom.py --sztuczne      # test bez danych
Wyniki: nagrania/Trend/wyniki_tsmom/ (tsmom_podsumowanie.csv, tsmom_rynki.csv, tsmom_kapital.png).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analizy import event_study_trend as ets  # noqa: E402

N_SIM = int(os.environ.get("N_SIM_TSMOM", 1000))
LOOKBACK = 12           # miesięcy
VOL_TARGET = 0.40       # jak w artykule
COM = 60                # środek masy EWMA zmienności (dni)
MIN_MIESIECY = 24
OUT = ets.OUTPUT_DIR.parent / "wyniki_tsmom"


# ============================================================
# JEDEN RYNEK
# ============================================================

def miesiace(close: pd.Series):
    """Dzienne log-zwroty, numer miesiąca każdego dnia, koniec każdego miesiąca."""
    close = close[close > 0].dropna()
    r = np.log(close).diff().dropna()
    okres = r.index.to_period("M")
    # zmienność ex ante: EWMA kwadratów zwrotów, roczna, z dniem opóźnienia jak w artykule
    var = (r ** 2).ewm(com=COM, min_periods=COM).mean().shift(1)
    vol_m = np.sqrt(var * 261).groupby(okres).last()
    return r, okres, vol_m


def miesieczne(r_dzienne: np.ndarray, grupy: np.ndarray) -> np.ndarray:
    """Suma log-zwrotów w miesiącu; r_dzienne (..., dni) → (..., miesiące)."""
    starts = np.r_[0, np.flatnonzero(np.diff(grupy)) + 1]
    return np.add.reduceat(r_dzienne, starts, axis=-1)


def pozycje(lr_m: np.ndarray, vol: np.ndarray):
    """Zwrot pozycji w miesiącu t+1 (proste zwroty) dla sygnału 12/1 z miesiąca t.

    lr_m: (..., M) miesięczne log-zwroty, vol: (M,) zmienność na koniec miesiąca.
    Zwraca (zwrot TSMOM, zwrot zawsze long, waga) dla miesięcy 1..M-1 przesuniętych o jeden.
    """
    cs = np.cumsum(lr_m, axis=-1)
    past = cs.copy()
    past[..., LOOKBACK:] = cs[..., LOOKBACK:] - cs[..., :-LOOKBACK]
    past[..., :LOOKBACK - 1] = np.nan                       # za mało historii
    sig = np.sign(past[..., :-1])
    w = VOL_TARGET / vol[:-1]
    nxt = np.expm1(lr_m[..., 1:])
    return sig * w * nxt, w * nxt


# ============================================================
# PORTFEL
# ============================================================

def statystyki(ret: pd.Series) -> dict:
    ret = ret.dropna()
    mu, sd = ret.mean() * 12, ret.std() * np.sqrt(12)
    return {"zwrot_roczny_pct": round(mu * 100, 2), "zmiennosc_pct": round(sd * 100, 2),
            "sharpe": round(mu / sd, 3) if sd > 0 else np.nan,
            "t_stat": round(ret.mean() / ret.std() * np.sqrt(len(ret)), 2) if sd > 0 else np.nan,
            "miesiace": len(ret)}


def main():
    synthetic = "--sztuczne" in sys.argv
    out = OUT / "sztuczne" if synthetic else OUT
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(2012)

    # sumy po rynkach dla każdego miesiąca kalendarzowego: prawdziwe, long, moneta-kierunek, moneta-wykres
    acc = {}
    rynki_rows, grupa_of = [], {}

    def dodaj(klucz, okresy, wartosci):
        """wartosci: (M,) albo (N, M); NaN = rynek nie handluje w tym miesiącu."""
        s = acc.setdefault(klucz, {})
        v = np.atleast_2d(wartosci)
        for j, p in enumerate(okresy):
            col = v[:, j]
            if np.isnan(col).all():
                continue
            a = s.setdefault(p, [np.zeros(v.shape[0]), 0])
            a[0] = a[0] + np.nan_to_num(col)
            a[1] += 1

    for name, close, _ in ets.series_list(synthetic, True):
        grupa = ets.GROUP_OF.get(name, "")
        r, okres, vol_m = miesiace(close)
        if len(vol_m) < MIN_MIESIECY + LOOKBACK:
            print(f"POMINIĘTO {name}: za krótka historia")
            continue
        codes = okres.asi8
        okresy_m = vol_m.index
        vol = vol_m.to_numpy()
        rd = r.to_numpy()

        lr_m = miesieczne(rd, codes)
        ts, lg = pozycje(lr_m, vol)
        valid = ~np.isnan(ts)
        ok = okresy_m[1:]                      # zwrot należy do miesiąca t+1

        # losowy kierunek co miesiąc (na prawdziwym wykresie)
        coin_dir = rng.choice([-1.0, 1.0], size=(N_SIM, len(lg))) * lg
        coin_dir[:, ~valid] = np.nan
        # reguła na wykresach z monety: dzienne ruchy z losowym kierunkiem, dryf zostaje
        mu = rd.mean()
        flips = mu + rng.choice([-1.0, 1.0], size=(N_SIM, len(rd))) * (rd - mu)
        ts_coin, _ = pozycje(miesieczne(flips, codes), vol)
        ts_coin[:, ~valid] = np.nan
        lg_valid = np.where(valid, lg, np.nan)

        dodaj("TSMOM", ok, ts)
        dodaj("Zawsze long", ok, lg_valid)
        dodaj("Losowy kierunek", ok, coin_dir)
        dodaj("Wykresy z monety", ok, ts_coin)
        grupa_of[name] = grupa
        for g in (grupa, "Wszystkie rynki"):
            if g:
                dodaj(f"TSMOM|{g}", ok, ts)
                dodaj(f"Wykresy z monety|{g}", ok, ts_coin)

        t = pd.Series(ts, index=ok).dropna()
        st = statystyki(t)
        sims = ts_coin[:, valid]
        sh_coin = sims.mean(axis=1) / sims.std(axis=1) * np.sqrt(12)
        rynki_rows.append({"rynek": name, "grupa": grupa, "od": str(t.index[0]), "do": str(t.index[-1]),
                           **st, "miesiace_na_plusie_pct": round((t > 0).mean() * 100, 1),
                           "moneta_sharpe_pas_dol": round(np.nanpercentile(sh_coin, 2.5), 3),
                           "moneta_sharpe_pas_gora": round(np.nanpercentile(sh_coin, 97.5), 3)})
        print(f"{name:32s} {st['miesiace']:4d} mies. | Sharpe TSMOM {st['sharpe']:+.2f} | "
              f"wykresy z monety [{np.nanpercentile(sh_coin, 2.5):+.2f} … {np.nanpercentile(sh_coin, 97.5):+.2f}]")

    if not acc:
        sys.exit("Brak rynków.")

    def portfel(klucz) -> pd.DataFrame:
        s = acc[klucz]
        okresy = sorted(s)
        return pd.DataFrame(np.array([s[p][0] / s[p][1] for p in okresy]),
                            index=pd.PeriodIndex(okresy, freq="M"))

    rows = []

    def wiersz(nazwa, kontrola, real: pd.Series, sims: pd.DataFrame | None):
        st = statystyki(real)
        row = {"portfel": nazwa, "porownanie": kontrola, **st,
               "miesiace_na_plusie_pct": round((real.dropna() > 0).mean() * 100, 1)}
        if sims is not None:
            sh = (sims.mean() / sims.std() * np.sqrt(12)).to_numpy()
            row.update({"kontrola_sharpe_srednia": round(np.mean(sh), 3),
                        "kontrola_sharpe_pas_dol": round(np.percentile(sh, 2.5), 3),
                        "kontrola_sharpe_pas_gora": round(np.percentile(sh, 97.5), 3),
                        "p": round((np.sum(sh >= st["sharpe"]) + 1) / (len(sh) + 1), 4)})
        rows.append(row)

    ts_p = portfel("TSMOM")[0]
    wiersz("Wszystkie rynki", "TSMOM (reguła z artykułu)", ts_p, None)
    wiersz("Wszystkie rynki", "Zawsze long (sam dryf)", portfel("Zawsze long")[0], None)
    wiersz("Wszystkie rynki", "TSMOM vs losowy kierunek co miesiąc", ts_p, portfel("Losowy kierunek"))
    wiersz("Wszystkie rynki", "TSMOM vs wykresy z monety", ts_p, portfel("Wykresy z monety"))
    for g in ets.SZEROKI:
        if f"TSMOM|{g}" in acc:
            wiersz(f"{g} (razem)", "TSMOM vs wykresy z monety",
                   portfel(f"TSMOM|{g}")[0], portfel(f"Wykresy z monety|{g}"))
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "tsmom_podsumowanie.csv", index=False)
    pd.DataFrame(rynki_rows).to_csv(out / "tsmom_rynki.csv", index=False)
    wykres(ts_p, portfel("Zawsze long")[0], portfel("Wykresy z monety"), out / "tsmom_kapital.png",
           len(grupa_of))

    print()
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(summary.to_string(index=False))
    print(f"\nWyniki: {out}")


def wykres(ts: pd.Series, lg: pd.Series, coin: pd.DataFrame, path: Path, n_rynkow: int) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from narzedzia.plansze import count_text
    bg, fg, green, grey = "#0B0D10", "#F2F2F2", "#00D084", "#6B7280"
    x = ts.index.to_timestamp()
    eq = lambda s: np.log1p(s.fillna(0)).cumsum()  # noqa: E731  (log kapitału)
    c = np.log1p(coin.fillna(0)).cumsum()
    lo, hi = c.quantile(0.025, axis=1), c.quantile(0.975, axis=1)
    fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
    fig.patch.set_facecolor(bg)
    ax.set_facecolor(bg)
    ax.fill_between(x, np.expm1(lo) * 100, np.expm1(hi) * 100, color=grey, alpha=0.35, lw=0,
                    label="95% wykresów z monety (ta sama reguła)")
    ax.plot(x, np.expm1(eq(lg)) * 100, color=grey, lw=2.5, label="zawsze long")
    ax.plot(x, np.expm1(eq(ts)) * 100, color=green, lw=3.5, label="TSMOM (12 mies.)")
    ax.set_ylabel("zysk portfela, % (bez kosztów)", color=grey, fontsize=16)
    ax.tick_params(colors=grey, labelsize=14)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.grid(color="#1F242B", lw=1)
    ax.set_title(f"MOMENTUM 12 MIESIĘCY · {count_text(n_rynkow, 'rynek', 'rynki', 'rynków').upper()}",
                 color=fg, fontsize=34, fontweight="bold", loc="left", pad=20)
    ax.legend(loc="upper left", frameon=False, labelcolor=fg, fontsize=16)
    fig.savefig(path, facecolor=bg, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
