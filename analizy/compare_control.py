"""
Strategia vs grupa kontrolna — plansze do filmu (PNG 1920×1080).

Najpierw policz obie wersje w run_all_assets.py, np.:
    STRATEGY = ["AutoLevelsTrendlines", "AutoLevelsTrendlines_Control"]
(te same aktywa, interwały i daty), ustaw ACTIVE niżej i uruchom ten plik.

Zapisuje do wyniki/<STRATEGY>/porownanie_z_kontrolna/ (albo folderu z presetu):
    1_strategia_vs_kontrolna.png — duże liczby obok siebie: ile
        kombinacji na plusie, mediana wyniku netto, mediana Win Rate,
        łączna liczba transakcji,
    2_kombinacje.png — wynik netto każdej kombinacji: strategia,
        grupa kontrolna i różnica.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

# Uruchamianie bezpośrednio z tego folderu: dodaj folder repo do ścieżki importów.
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from narzedzia.plansze import (
    BLACK, DPI, GRAY, GREEN, RED, SIZE, WHITE,
    _body_font, _fit_width, _header, _heading_font, _heading_weight,
    _pct, _save, _sign_color, _timeframe,
)


# ============================================================
# KONFIGURACJA
# ============================================================

# Która para strategia / grupa kontrolna: klucz z PRESETS.
ACTIVE = "AutoLevelsTrendlines"

PRESETS = {
    "AutoLevelsTrendlines": {
        "control": "AutoLevelsTrendlines_Control",
        "title": "Auto Levels & Trendlines + Breakout Check",
        "strategy_label": "Sygnał TRUE",
    },
    "KeyLevelZones": {
        "control": "KeyLevelZones_Control",
        "title": "FCP Key Level Zones | Pivots & Daily Weekly Monthly High Low",
        "strategy_label": "Dotknięcie strefy",
    },
    "Wyckoff": {
        "control": "Wyckoff_Control",
        "title": "Wyckoff Accumulation & Distribution, Spring, UTAD, SOS [LunqFX]",
        "strategy_label": "Wejście na SOS / SOW",
    },
    # Efficiency Weighted Hull: dwa porównania z tą samą strategią.
    "EfficiencyWeightedHull": {
        "control": "EfficiencyWeightedHull_Control",
        "title": "Efficiency Weighted Hull",
        "strategy_label": "Flipy Hulla",
        "subtitle_note": "tyle samo odwróceń long/short, losowe momenty",
    },
    "EfficiencyWeightedHull_vs_Standard": {
        "strategy": "EfficiencyWeightedHull",
        "control": "EfficiencyWeightedHull_Standard",
        "title": "Efficiency Weighted Hull",
        "strategy_label": "Efficiency Hull",
        "control_label": "Zwykły Hull",
        "versus": "porównanie ze zwykłym Hullem",
        "better_text": "Efficiency Hull lepszy od zwykłego Hulla",
        "subtitle_note": "te same reguły, standardowa kompensacja Hulla",
        "folder": "porownanie_ze_standardowym_hullem",
    },
}

# Klucze opcjonalne w PRESETS (domyślnie: grupa kontrolna z losowymi wejściami):
#   strategy      — nazwa strategii, jeśli inna niż klucz presetu,
#   control_label, versus, better_text, subtitle_note, folder.

_P = PRESETS[ACTIVE]
STRATEGY = _P.get("strategy", ACTIVE)
CONTROL = _P["control"]

# Te same daty co w run_all_assets.py.
START_DATE = "2021-01-01"
END_DATE = "2025-12-31"

TITLE = _P["title"]
STRATEGY_LABEL = _P["strategy_label"]
CONTROL_LABEL = _P.get("control_label", "Losowe wejścia")
VERSUS = _P.get("versus", "strategia vs grupa kontrolna")
BETTER_TEXT = _P.get("better_text", "Strategia lepsza od grupy kontrolnej")
SUBTITLE_NOTE = _P.get("subtitle_note", "te same kierunki i czas trzymania, losowe momenty wejścia")
FOLDER = _P.get("folder", "porownanie_z_kontrolna")

RESULTS = Path(__file__).resolve().parents[1] / "wyniki"


def load_summary(name: str) -> pd.DataFrame:
    path = RESULTS / name / f"podsumowanie_{name}_{START_DATE}_{END_DATE}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Brak {path} — najpierw policz {name} w run_all_assets.py "
            f"z datami {START_DATE} – {END_DATE}."
        )
    data = pd.read_csv(path, sep=";", decimal=",")
    return data[data["status"] == "OK"].reset_index(drop=True)


def _column(fig, x, label, data, color):
    returns = data["return_%"].astype(float)
    profitable = int((returns > 0).sum())
    items = [
        (f"{profitable}/{len(data)}", "kombinacji na plusie",
         GREEN if profitable > len(data) / 2 else RED),
        (_pct(returns.median()), "mediana wyniku netto",
         _sign_color(returns.median())),
        (_pct(data["win_rate_%"].astype(float).median(), 1, sign=False),
         "mediana Win Rate", WHITE),
    ]

    fig.text(x, 0.76, label.upper(), ha="center", va="center", color=color,
             fontsize=34, fontfamily=_heading_font(),
             fontweight=_heading_weight())

    values = []
    for k, (value, caption, value_color) in enumerate(items):
        y = 0.60 - k * 0.19
        values.append(fig.text(
            x, y, value, ha="center", va="baseline", color=value_color,
            fontsize=86, fontfamily=_heading_font(),
            fontweight=_heading_weight(),
        ))
        fig.text(x, y - 0.035, caption, ha="center", va="top", color=GRAY,
                 fontsize=22, fontfamily=_body_font())
    fig.text(x, 0.07, f"transakcje: {int(data['trades'].sum())}",
             ha="center", va="center", color=GRAY, fontsize=20,
             fontfamily=_body_font())
    return values


def big_numbers(path, strategy, control, subtitle):
    fig = plt.figure(figsize=SIZE, dpi=DPI, facecolor=BLACK)
    _header(fig, f"{TITLE}: {VERSUS}", subtitle)
    fig.add_artist(plt.Line2D([0.5, 0.5], [0.08, 0.80], color="#2A2E35",
                              transform=fig.transFigure))
    values = _column(fig, 0.27, STRATEGY_LABEL, strategy, WHITE)
    values += _column(fig, 0.73, CONTROL_LABEL, control, GRAY)
    _fit_width(fig, values, 0.40, min_size=40)
    _save(fig, path)


def per_combination(path, strategy, control, subtitle):
    merged = strategy.merge(
        control, on=["asset", "timeframe"], suffixes=("_s", "_c")
    )
    fig = plt.figure(figsize=SIZE, dpi=DPI, facecolor=BLACK)
    _header(fig, f"{TITLE}: wynik netto kombinacji", subtitle)

    columns = [
        ("Aktywo", 0.06, "left"),
        ("Interwał", 0.24, "left"),
        (STRATEGY_LABEL, 0.52, "right"),
        (CONTROL_LABEL, 0.74, "right"),
        ("Różnica (pkt %)", 0.95, "right"),
    ]
    top, bottom = 0.76, 0.10
    row_height = min(0.055, (top - bottom) / (len(merged) + 1))
    font_size = 24 if row_height >= 0.05 else 18

    for name, x, align in columns:
        fig.text(x, top, name, ha=align, va="center", color=GRAY,
                 fontsize=font_size - 4, fontfamily=_body_font())

    for i, row in merged.iterrows():
        y = top - row_height * (i + 1)
        if i % 2 == 0:
            fig.patches.append(plt.Rectangle(
                (0.04, y - row_height / 2), 0.94, row_height,
                transform=fig.transFigure, color="#14171C", zorder=0,
            ))
        s, c = float(row["return_%_s"]), float(row["return_%_c"])
        cells = [
            (row["asset"], WHITE),
            (_timeframe(row["timeframe"]), WHITE),
            (_pct(s), _sign_color(s)),
            (_pct(c), _sign_color(c)),
            (_pct(s - c).replace("%", ""), _sign_color(s - c)),
        ]
        for (_, x, align), (text, color) in zip(columns, cells):
            fig.text(x, y, text, ha=align, va="center", color=color,
                     fontsize=font_size, fontfamily=_body_font())

    better = int((merged["return_%_s"] > merged["return_%_c"]).sum())
    fig.text(0.04, 0.04,
             f"{BETTER_TEXT} w {better} z {len(merged)} kombinacji.",
             ha="left", va="center", color=GRAY, fontsize=16,
             fontfamily=_body_font())
    _save(fig, path)
    return better, len(merged)


def main():
    strategy = load_summary(STRATEGY)
    control = load_summary(CONTROL)

    folder = RESULTS / STRATEGY / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    subtitle = (
        f"{strategy['asset'].nunique()} aktywa × "
        f"{strategy['timeframe'].nunique()} interwały  |  "
        f"{START_DATE[:4]}–{END_DATE[:4]}  |  po kosztach  |  "
        f"{SUBTITLE_NOTE}"
    )

    with plt.style.context("default"):
        big_numbers(folder / "1_strategia_vs_kontrolna.png", strategy, control, subtitle)
        better, total = per_combination(
            folder / "2_kombinacje.png", strategy, control, subtitle
        )

    for label, data in ((STRATEGY_LABEL, strategy), (CONTROL_LABEL, control)):
        r = data["return_%"].astype(float)
        print(
            f"{label:16s}: na plusie {(r > 0).sum()}/{len(r)}, "
            f"mediana {r.median():+.2f}%, transakcje {int(data['trades'].sum())}"
        )
    print(f"{BETTER_TEXT} w {better} z {total} kombinacji.")
    print(f"Plansze: {folder}")


if __name__ == "__main__":
    main()
