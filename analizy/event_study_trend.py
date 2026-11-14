"""
Czy trend istnieje? Badanie definicji trendu Murphy'ego (Dow) i trzech
popularnych definicji na świecach dziennych.

Zasady testu (ustalone przed wynikami): nagrania/Trend/zasady_testu.md

Pytanie: czy po potwierdzeniu trendu cena częściej idzie dalej
w jego kierunku, niż gdyby rynek nie miał pamięci kierunku?

Pomiar („wyścig do progu”): od zamknięcia świecy sygnałowej sprawdzamy,
co pierwsze — zamknięcie o a wyżej czy o a niżej. Wygrana = w kierunku
trendu. a = próg fali danego stopnia trendu (ten sam co w zigzagu).

Kontrole:
- MONETA (główna): N_SIM sztucznych wykresów z tymi samymi dziennymi
  ruchami (wielkość i miejsce), ale z kierunkiem losowanym ±1; średni
  dryf zostaje. Na każdym od nowa: zigzag, reguły, wyścig. Pas 95%.
- LOSOWE DNI: prawdziwy wykres, tyle samo startów w tych samych
  kierunkach, ale w losowych dniach (N_SIM_DAYS losowań).
Wniosek „trend istnieje” tylko, gdy obie kontrole wskazują to samo.

Dodatkowo: test wariancji (Lo i MacKinlay, 1988) dla tygodnia,
miesiąca, kwartału i roku z pasem z tych samych „monet”, odsetek czasu
bez trendu (claim „co najmniej 1/3”), część ruchu straconą do sygnału
(claim „20–25%”), wyniki w podziale na dekady.

Wyniki: nagrania/Trend/wyniki_event_study/
    summary.csv     — rynek × stopień × definicja (wyścig, kontrole, p, Holm),
    dekady.csv      — wyścig w każdej dekadzie (Murphy, potwierdzone),
    wariancja.csv   — test wariancji z pasem,
    murphy_opis.csv — czas bez trendu, stracona część ruchu, długość fal,
    trend_<rynek>_<stopień>.png, wariancja_<rynek>.png, murphy_rynki_<stopień>.png.

Uruchomienie:
    python analizy/event_study_trend.py
    python analizy/event_study_trend.py --sztuczne   (test na danych sztucznych)
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from narzedzia.odcinki import folder_badania
from narzedzia.plansze import (
    BLACK, WHITE, GREEN, RED, GRAY, SIZE, DPI,
    _body_font, _heading_font, _heading_weight, count_text,
)
from analizy.trend_definicje import (
    murphy, donchian, sma_cross, momentum, race, variance_ratio, sign_flip,
)


# ============================================================
# KONFIGURACJA (zgodnie z nagrania/Trend/zasady_testu.md)
# ============================================================

# Świece 1D z ticków (cała historia do END).
TICK_ASSETS = ["XAUUSD", "EURUSD", "Brent", "Bitcoin", "US500"]
START = "2003-01-01"
END = "2025-12-31"

# Długa historia z plików CSV (np. Stooq). Brak pliku = pominięte.
DAILY_CSV = {
    "S&P 500 (Stooq)": r"D:\Tickdata\Dzienne\spx_d.csv",
    "Dow Jones (Stooq)": r"D:\Tickdata\Dzienne\dji_d.csv",
    "Złoto (Stooq)": r"D:\Tickdata\Dzienne\xauusd_d.csv",
}

# Stopnie trendu (Murphy s. 65–67). Fale (szczyt→dołek) mają trwać
# średnio tyle dni kalendarzowych; próg a = zmienność dzienna × √(liczba świec fali).
# Trend średni rozpoznajemy po falach krótkich (≤ 2–3 tyg.), trend główny
# po falach średnich (3 tyg.–3 mies., środek geometryczny ≈ 44 dni).
DEGREES = {
    "sredni": 14,
    "glowny": 44,
}
MAIN_DEGREE = "sredni"   # Murphy s. 67: systemy skupiają się na trendzie średnim

# Okna innych definicji w tygodniach (przeliczane na świece danego rynku).
DONCHIAN_WEEKS = 4       # reguła 4 tygodni (Donchian, Murphy)
SMA_WEEKS = 40           # SMA 200 dni sesyjnych
MOMENTUM_WEEKS = 52      # zmiana z 12 miesięcy (Moskowitz, Ooi, Pedersen 2012)

VR_WEEKS = {"tydzień": 1, "miesiąc": 4, "kwartał": 13, "rok": 52}

N_SIM = 1000             # sztuczne wykresy „moneta”
N_SIM_DAYS = 10_000      # losowania „losowe dni”
BAND = 0.95
SEED = 42
MIN_EVENTS = 20          # mniej = brak wniosku

OUTPUT_DIR = folder_badania("Trend", "wyniki_event_study")

DEFINITIONS = {
    "murphy": "Murphy: wyższe szczyty i dołki",
    "murphy_bez": "Murphy: przebicie bez potwierdzenia",
    "donchian": "Reguła 4 tygodni",
    "sma": "Cena vs SMA 200",
    "momentum": "Momentum 12 mies.",
}
# Krótsze podpisy na wykresach.
LABELS = {
    "murphy": "Murphy\nszczyty i dołki",
    "murphy_bez": "Murphy\nbez potwierdzenia",
    "donchian": "Reguła\n4 tygodni",
    "sma": "Cena vs\nSMA 200",
    "momentum": "Momentum\n12 mies.",
}


# ============================================================
# PARAMETRY RYNKU
# ============================================================

def market_params(dates: pd.DatetimeIndex, logc: np.ndarray) -> dict:
    days = (dates[-1] - dates[0]).days
    bars_per_day = (len(dates) - 1) / max(days, 1)
    bars_per_week = bars_per_day * 7
    sigma = float(np.std(np.diff(logc), ddof=1))
    params = {
        "bars_per_week": bars_per_week,
        "sigma": sigma,
        "a": {d: sigma * np.sqrt(days_ * bars_per_day) for d, days_ in DEGREES.items()},
        "donchian": max(2, round(DONCHIAN_WEEKS * bars_per_week)),
        "sma": max(2, round(SMA_WEEKS * bars_per_week)),
        "momentum": max(2, round(MOMENTUM_WEEKS * bars_per_week)),
        "vr_q": {k: max(1, round(w * bars_per_week)) for k, w in VR_WEEKS.items()},
    }
    return params


# ============================================================
# JEDEN WYKRES (prawdziwy albo sztuczny)
# ============================================================

def analyze(logc: np.ndarray, decade: np.ndarray, params: dict, keep_events=False) -> dict:
    """
    Wszystkie miary dla jednego wykresu.
    Zwraca słownik: (stopień, definicja) → {wins, n, wins_up, n_up, wins_dn, n_dn,
    decades: {dekada: (wins, n)}} oraz murphy_opis i vr.
    """
    res = {}
    other_events = {
        "donchian": donchian(logc, params["donchian"]),
        "sma": sma_cross(logc, params["sma"]),
        "momentum": momentum(logc, params["momentum"]),
    }
    for degree, a in params["a"].items():
        ev, state, lag, legs = murphy(logc, a)
        sets = {
            "murphy": ev[ev[:, 2] == 1],
            "murphy_bez": ev[ev[:, 2] == 0],
            **other_events,
        }
        for name, e in sets.items():
            out = race(logc, e[:, 0], a) if len(e) else np.zeros(0, dtype=np.int8)
            done = out != 0
            win = (out == e[:, 1]) & done if len(e) else np.zeros(0, bool)
            up = e[:, 1] == 1 if len(e) else np.zeros(0, bool)
            r = {
                "n": int(done.sum()), "wins": int(win.sum()),
                "n_up": int((done & up).sum()), "wins_up": int((win & up).sum()),
                "n_dn": int((done & ~up).sum()), "wins_dn": int((win & ~up).sum()),
            }
            if name == "murphy":
                dec = decade[e[:, 0]] if len(e) else np.zeros(0, int)
                r["decades"] = {
                    int(d): (int(win[dec == d].sum()), int(done[dec == d].sum()))
                    for d in np.unique(dec)
                }
            if keep_events:
                r["events"] = e
            res[(degree, name)] = r
        lag_f = [f for _, f in lag]
        res[(degree, "opis")] = {
            "bez_trendu": float((state == 0).mean()),
            "strata_srednia": float(np.mean(lag_f)) if lag_f else np.nan,
            "strata_mediana": float(np.median(lag_f)) if lag_f else np.nan,
            "fala_mediana_swiece": float(np.median(legs)) if len(legs) else np.nan,
        }
    lr = np.diff(logc)
    res["vr"] = {k: variance_ratio(lr, q) for k, q in params["vr_q"].items()}
    return res


def rate(w, n):
    return w / n if n else np.nan


# ============================================================
# BADANIE JEDNEGO RYNKU
# ============================================================

def study(name: str, close: pd.Series, rng):
    close = close[close > 0].dropna()
    dates = close.index
    logc = np.log(close.to_numpy(dtype=float))
    decade = (dates.year // 10 * 10).to_numpy()
    params = market_params(dates, logc)
    print(f"  {len(logc)} świec {dates[0].date()} – {dates[-1].date()}, "
          f"zmienność dzienna {params['sigma'] * 100:.2f}%, progi: "
          + ", ".join(f"{d} {a * 100:.1f}%" for d, a in params["a"].items()))

    real = analyze(logc, decade, params, keep_events=True)

    # Kontrola MONETA.
    lr = np.diff(logc)
    sims = []
    for s in range(N_SIM):
        fake = np.concatenate(([logc[0]], logc[0] + np.cumsum(sign_flip(lr, rng))))
        sims.append(analyze(fake, decade, params))
        if (s + 1) % 100 == 0:
            print(f"    moneta {s + 1}/{N_SIM}")

    # Kontrola LOSOWE DNI: wynik wyścigu z każdej świecy w obu kierunkach.
    pool_out = {d: race(logc, np.arange(len(logc)), a) for d, a in params["a"].items()}

    rows, dec_rows, vr_rows, desc_rows = [], [], [], []
    lo_q, hi_q = (1 - BAND) / 2, 1 - (1 - BAND) / 2
    pooled = {}

    for degree, a in params["a"].items():
        out = pool_out[degree]
        done_all = np.flatnonzero(out != 0)
        win_long = out[done_all] == 1
        win_short = out[done_all] == -1
        for d in DEFINITIONS:
            r = real[(degree, d)]
            sim_w = np.array([x[(degree, d)]["wins"] for x in sims], dtype=float)
            sim_n = np.array([x[(degree, d)]["n"] for x in sims], dtype=float)
            # LOSOWE DNI: te same liczby startów w górę i w dół, losowe momenty.
            pick_u = rng.integers(0, len(done_all), size=(N_SIM_DAYS, r["n_up"]))
            pick_d = rng.integers(0, len(done_all), size=(N_SIM_DAYS, r["n_dn"]))
            days_w = win_long[pick_u].sum(axis=1) + win_short[pick_d].sum(axis=1)
            data = {**{k: r[k] for k in ("wins", "n", "wins_up", "n_up", "wins_dn", "n_dn")},
                    "sim_w": sim_w, "sim_n": sim_n, "days_w": days_w}
            pooled[(degree, d)] = data
            rows.append(make_row(
                {"rynek": name, "stopien": degree, "definicja": d, "opis": DEFINITIONS[d],
                 "start": dates[0].date(), "koniec": dates[-1].date(),
                 "prog_pct": round(a * 100, 2)},
                data,
            ))

        # Dekady (Murphy, potwierdzone).
        r = real[(degree, "murphy")]
        for dec, (w, n) in sorted(r.get("decades", {}).items()):
            sd = []
            for x in sims:
                ww, nn = x[(degree, "murphy")]["decades"].get(dec, (0, 0))
                if nn:
                    sd.append(ww / nn)
            sd = np.array(sd)
            dec_rows.append({
                "rynek": name, "stopien": degree, "dekada": f"{dec}s",
                "zdarzenia": n, "wygrane_pct": _pct(rate(w, n)),
                "moneta_srednia_pct": _pct(sd.mean()) if len(sd) else np.nan,
                "moneta_pas_dol_pct": _pct(np.quantile(sd, lo_q)) if len(sd) else np.nan,
                "moneta_pas_gora_pct": _pct(np.quantile(sd, hi_q)) if len(sd) else np.nan,
                "za_malo": n < MIN_EVENTS,
            })

        # Opis Murphy'ego: czas bez trendu, stracona część ruchu, fale.
        o = real[(degree, "opis")]
        so = {k: np.array([x[(degree, "opis")][k] for x in sims]) for k in o}
        desc_rows.append({
            "rynek": name, "stopien": degree, "prog_pct": round(a * 100, 2),
            "bez_trendu_pct": _pct(o["bez_trendu"]),
            "bez_trendu_moneta_pct": _pct(np.nanmean(so["bez_trendu"])),
            "strata_srednia_pct": _pct(o["strata_srednia"]),
            "strata_mediana_pct": _pct(o["strata_mediana"]),
            "strata_srednia_moneta_pct": _pct(np.nanmean(so["strata_srednia"])),
            "fala_mediana_dni": round(o["fala_mediana_swiece"] / params["bars_per_week"] * 7, 1),
            "fala_mediana_moneta_dni": round(
                np.nanmean(so["fala_mediana_swiece"]) / params["bars_per_week"] * 7, 1),
            "fala_cel_dni": DEGREES[degree],
        })

    for k, q in params["vr_q"].items():
        sv = np.array([x["vr"][k] for x in sims])
        sv = sv[~np.isnan(sv)]
        obs = real["vr"][k]
        vr_rows.append({
            "rynek": name, "horyzont": k, "swiece": q,
            "vr": round(obs, 3),
            "moneta_srednia": round(sv.mean(), 3) if len(sv) else np.nan,
            "moneta_pas_dol": round(np.quantile(sv, lo_q), 3) if len(sv) else np.nan,
            "moneta_pas_gora": round(np.quantile(sv, hi_q), 3) if len(sv) else np.nan,
            "moneta_p": _p(obs, sv) if len(sv) else np.nan,
        })

    return rows, dec_rows, vr_rows, desc_rows, pooled


def make_row(meta: dict, data: dict) -> dict:
    """Wiersz summary: wynik prawdziwy, pas „moneta”, pas „losowe dni”, werdykt."""
    lo_q, hi_q = (1 - BAND) / 2, 1 - (1 - BAND) / 2
    obs = rate(data["wins"], data["n"])
    row = {
        **meta,
        "zdarzenia": data["n"],
        "wygrane_pct": _pct(obs),
        "wygrane_w_gore_pct": _pct(rate(data["wins_up"], data["n_up"])),
        "zdarzenia_w_gore": data["n_up"],
        "wygrane_w_dol_pct": _pct(rate(data["wins_dn"], data["n_dn"])),
        "zdarzenia_w_dol": data["n_dn"],
    }
    ok = data["sim_n"] > 0
    sim = data["sim_w"][ok] / data["sim_n"][ok]
    if data["n"] < MIN_EVENTS or len(sim) < len(data["sim_n"]) // 2:
        row["werdykt"] = "za mało zdarzeń"
        return row
    days = data["days_w"] / data["n"]
    row.update({
        "moneta_srednia_pct": _pct(sim.mean()),
        "moneta_pas_dol_pct": _pct(np.quantile(sim, lo_q)),
        "moneta_pas_gora_pct": _pct(np.quantile(sim, hi_q)),
        "moneta_p": _p(obs, sim),
        "losowe_dni_srednia_pct": _pct(days.mean()),
        "losowe_dni_pas_dol_pct": _pct(np.quantile(days, lo_q)),
        "losowe_dni_pas_gora_pct": _pct(np.quantile(days, hi_q)),
        "losowe_dni_p": _p(obs, days),
    })
    row["werdykt"] = _verdict(row)
    return row


def pool_rows(name: str, pooled_list: list) -> list:
    """Wszystkie rynki razem: sumy wygranych i zdarzeń (prawdziwe i w każdym losowaniu)."""
    rows = []
    for key in pooled_list[0]:
        parts = [p[key] for p in pooled_list if key in p]
        data = {k: sum(p[k] for p in parts)
                for k in ("wins", "n", "wins_up", "n_up", "wins_dn", "n_dn", "sim_w", "sim_n", "days_w")}
        degree, d = key
        rows.append(make_row(
            {"rynek": name, "stopien": degree, "definicja": d, "opis": DEFINITIONS[d],
             "start": "", "koniec": "", "prog_pct": np.nan},
            data,
        ))
    return rows


def _pct(x):
    return round(float(x) * 100, 1) if x is not None and not np.isnan(x) else np.nan


def _p(obs, sims) -> float:
    """p dwustronne: jak często przypadek odjeżdża od swojej średniej co najmniej tak daleko."""
    mu = sims.mean()
    return round(float((np.sum(np.abs(sims - mu) >= abs(obs - mu)) + 1) / (len(sims) + 1)), 4)


def _verdict(row) -> str:
    def side(prefix):
        if row["wygrane_pct"] > row[f"{prefix}_pas_gora_pct"]:
            return 1
        if row["wygrane_pct"] < row[f"{prefix}_pas_dol_pct"]:
            return -1
        return 0
    a, b = side("moneta"), side("losowe_dni")
    if a == b == 1:
        return "trend: lepiej niż przypadek (obie kontrole)"
    if a == b == -1:
        return "odwrotnie: częściej zawraca (obie kontrole)"
    if a == b == 0:
        return "jak przypadek"
    return "niejednoznaczne (kontrole się różnią)"


def holm(p: pd.Series) -> pd.Series:
    s = p.dropna().sort_values()
    m = len(s)
    adj = (s * (m - np.arange(m))).cummax().clip(upper=1.0)
    return adj.reindex(p.index).round(4)


# ============================================================
# WYKRESY
# ============================================================

def _style(ax):
    ax.set_facecolor(BLACK)
    ax.tick_params(colors=GRAY, labelsize=15)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(axis="y", color=GRAY, alpha=0.15)


def _header(fig, title, subtitle):
    fig.text(0.04, 0.92, title, color=WHITE, fontsize=42, fontfamily=_heading_font(),
             fontweight=_heading_weight(), va="center")
    fig.text(0.04, 0.855, subtitle, color=GRAY, fontsize=19, fontfamily=_body_font(),
             va="center")


def chart_market(rows: pd.DataFrame, file: Path, title: str, subtitle: str, labels):
    """Kropka = prawdziwy wynik, szary pas = 95% wyników „monety”."""
    data = rows[rows["moneta_pas_dol_pct"].notna()] if "moneta_pas_dol_pct" in rows else rows.iloc[0:0]
    if data.empty:
        return
    font = _body_font()
    fig, ax = plt.subplots(figsize=SIZE, dpi=DPI, facecolor=BLACK)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.76, bottom=0.2)
    _header(fig, title, subtitle)
    _style(ax)
    x = np.arange(len(data))
    for i, (_, r) in enumerate(data.iterrows()):
        ax.bar(i, r["moneta_pas_gora_pct"] - r["moneta_pas_dol_pct"],
               bottom=r["moneta_pas_dol_pct"], width=0.5, color=GRAY, alpha=0.3)
        ax.plot([i - 0.25, i + 0.25], [r["moneta_srednia_pct"]] * 2, color=GRAY, linewidth=2)
        above = r["wygrane_pct"] > r["moneta_pas_gora_pct"]
        below = r["wygrane_pct"] < r["moneta_pas_dol_pct"]
        color = GREEN if above else RED if below else WHITE
        ax.scatter(i, r["wygrane_pct"], s=420, color=color, zorder=3)
        ax.text(i, r["wygrane_pct"] + 0.8, f"{r['wygrane_pct']:.0f}%", color=color,
                fontsize=22, fontfamily=font, ha="center", va="bottom")
    ax.set_xticks(x)
    ax.set_xticklabels([labels(r) for _, r in data.iterrows()], color=WHITE,
                       fontsize=16, fontfamily=font)
    ax.axhline(50, color=GRAY, linewidth=0.8, alpha=0.6)
    ax.set_ylabel("cena poszła dalej w kierunku trendu, %", color=GRAY, fontsize=16,
                  fontfamily=font)
    lo = min(data["moneta_pas_dol_pct"].min(), data["wygrane_pct"].min()) - 5
    hi = max(data["moneta_pas_gora_pct"].max(), data["wygrane_pct"].max()) + 6
    ax.set_ylim(lo, hi)
    fig.savefig(file, dpi=DPI, facecolor=BLACK)
    plt.close(fig)


def chart_vr(rows: pd.DataFrame, file: Path, name: str):
    data = rows[rows["moneta_pas_dol"].notna()]
    if data.empty:
        return
    font = _body_font()
    fig, ax = plt.subplots(figsize=SIZE, dpi=DPI, facecolor=BLACK)
    fig.subplots_adjust(left=0.07, right=0.97, top=0.76, bottom=0.12)
    _header(fig, f"CZY CENA MA PAMIĘĆ? {name}",
            "1 = brak pamięci · powyżej = ruchy się kontynuują · poniżej = zawracają · "
            f"szary pas = 95% wykresów z losowym kierunkiem ({N_SIM} wykresów)")
    _style(ax)
    for i, (_, r) in enumerate(data.iterrows()):
        ax.bar(i, r["moneta_pas_gora"] - r["moneta_pas_dol"], bottom=r["moneta_pas_dol"],
               width=0.5, color=GRAY, alpha=0.3)
        color = GREEN if r["vr"] > r["moneta_pas_gora"] else RED if r["vr"] < r["moneta_pas_dol"] else WHITE
        ax.scatter(i, r["vr"], s=420, color=color, zorder=3)
        ax.text(i + 0.12, r["vr"], f"{r['vr']:.2f}".replace(".", ","), color=color,
                fontsize=22, fontfamily=font, va="center")
    ax.axhline(1, color=GRAY, linewidth=0.8, alpha=0.6)
    ax.set_xticks(range(len(data)))
    ax.set_xticklabels(data["horyzont"], color=WHITE, fontsize=18, fontfamily=font)
    fig.savefig(file, dpi=DPI, facecolor=BLACK)
    plt.close(fig)


def save_charts(summary, vr, name):
    safe = _safe(name)
    for degree in DEGREES:
        rows = summary[(summary["rynek"] == name) & (summary["stopien"] == degree)]
        if rows.empty:
            continue
        r0 = rows.iloc[0]
        chart_market(
            rows, OUTPUT_DIR / f"trend_{safe}_{degree}.png",
            f"CZY TREND ISTNIEJE? {name}",
            f"trend {'średni' if degree == 'sredni' else 'główny'} · próg {r0['prog_pct']:.1f}% · ".replace(".", ",")
            + 
            f"{r0['start']} – {r0['koniec']} · szary pas = 95% wykresów z losowym kierunkiem",
            lambda r: f"{LABELS[r['definicja']]}\n"
                      f"{count_text(r['zdarzenia'], 'sygnał', 'sygnały', 'sygnałów')}",
        )
    chart_vr(vr[vr["rynek"] == name], OUTPUT_DIR / f"wariancja_{safe}.png", name)


def save_summary_chart(summary):
    for degree in DEGREES:
        rows = summary[(summary["definicja"] == "murphy") & (summary["stopien"] == degree)]
        chart_market(
            rows, OUTPUT_DIR / f"murphy_rynki_{degree}.png",
            "TREND WG MURPHY'EGO: CZY IDZIE DALEJ?",
            f"trend {'średni' if degree == 'sredni' else 'główny'} · wyższe szczyty i dołki · "
            "szary pas = 95% wykresów z losowym kierunkiem",
            lambda r: f"{r['rynek']}\n{count_text(r['zdarzenia'], 'sygnał', 'sygnały', 'sygnałów')}",
        )


def _safe(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_")


# ============================================================
# START
# ============================================================

def series_list(synthetic: bool):
    if synthetic:
        rng = np.random.default_rng(7)
        dates = pd.bdate_range("2003-01-01", "2025-12-31")
        n = len(dates)
        # 1) bez pamięci, 2) z trwałym dryfem (trend), oba ze skupianiem zmienności
        vol = 0.01 * np.exp(np.cumsum(rng.normal(0, 0.05, n)) * 0.2)
        vol = 0.01 * vol / vol.mean()
        rw = np.cumsum(rng.standard_normal(n) * vol)
        rho = 0.5 ** (1 / 60)
        mu = np.zeros(n)
        z = rng.standard_normal(n)
        for t in range(1, n):
            mu[t] = rho * mu[t - 1] + np.sqrt(1 - rho ** 2) * 0.2 * 0.01 * z[t]
        tr = np.cumsum(mu + rng.standard_normal(n) * vol)
        yield "Sztuczny bez trendu", pd.Series(100 * np.exp(rw), index=dates), True
        yield "Sztuczny z trendem", pd.Series(100 * np.exp(tr), index=dates), True
        return

    from narzedzia.dane_dzienne import daily_bars_from_ticks, load_daily_csv
    for asset in TICK_ASSETS:
        try:
            yield asset, daily_bars_from_ticks(asset, START, END)["close"], True
        except (FileNotFoundError, KeyError, OSError) as error:
            print(f"POMINIĘTO {asset}: {error}")
    for name, path in DAILY_CSV.items():
        try:
            df = load_daily_csv(path)
            yield name, df.loc[:END, "close"], False
        except (FileNotFoundError, ValueError) as error:
            print(f"POMINIĘTO {name}: {error}")


POOLED_NAME = "Wszystkie rynki"


def main():
    synthetic = "--sztuczne" in sys.argv
    out_dir = OUTPUT_DIR / "sztuczne" if synthetic else OUTPUT_DIR
    globals()["OUTPUT_DIR"] = out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)

    all_rows, all_dec, all_vr, all_desc, to_pool = [], [], [], [], []
    for name, close, in_pool in series_list(synthetic):
        print("\n" + "=" * 60 + f"\n{name}\n" + "=" * 60)
        rows, dec, vr, desc, pooled = study(name, close, rng)
        all_rows += rows
        all_dec += dec
        all_vr += vr
        all_desc += desc
        if in_pool:
            to_pool.append(pooled)
        summary = save_tables(all_rows, all_dec, all_vr, all_desc, to_pool, out_dir)
        save_charts(summary, pd.DataFrame(all_vr), name)
        for r in rows:
            if r["stopien"] == MAIN_DEGREE:
                print_row(r)

    if all_rows:
        summary = save_tables(all_rows, all_dec, all_vr, all_desc, to_pool, out_dir)
        save_summary_chart(summary)
        print("\n" + POOLED_NAME + " (" + ", ".join(
            n for n in summary.loc[summary["rynek"] != POOLED_NAME, "rynek"].unique()) + ")")
        for _, r in summary[(summary["rynek"] == POOLED_NAME)
                            & (summary["stopien"] == MAIN_DEGREE)].iterrows():
            print_row(r)
    print(f"\nWyniki: {out_dir}")


def save_tables(all_rows, all_dec, all_vr, all_desc, to_pool, out_dir) -> pd.DataFrame:
    rows = list(all_rows)
    if len(to_pool) > 1:
        rows += pool_rows(POOLED_NAME, to_pool)
    summary = pd.DataFrame(rows)
    for col in ("moneta_p", "losowe_dni_p"):
        if col in summary:
            mask = ((summary["definicja"] == "murphy") & (summary["stopien"] == MAIN_DEGREE)
                    & (summary["rynek"] != POOLED_NAME))
            summary.loc[mask, f"{col}_holm"] = holm(summary.loc[mask, col])
    summary.to_csv(out_dir / "summary.csv", index=False)
    pd.DataFrame(all_dec).to_csv(out_dir / "dekady.csv", index=False)
    pd.DataFrame(all_vr).to_csv(out_dir / "wariancja.csv", index=False)
    pd.DataFrame(all_desc).to_csv(out_dir / "murphy_opis.csv", index=False)
    return summary


def print_row(r) -> None:
    print(f"  {DEFINITIONS[r['definicja']]:38s} n={int(r['zdarzenia']):5d} | "
          f"w kierunku trendu {r['wygrane_pct']}% | moneta {r.get('moneta_srednia_pct')}% "
          f"[{r.get('moneta_pas_dol_pct')}–{r.get('moneta_pas_gora_pct')}] | "
          f"losowe dni {r.get('losowe_dni_srednia_pct')}% | {r['werdykt']}")


if __name__ == "__main__":
    main()
