"""
Plansze wyników do filmu (PNG 1920×1080, kolory kanału).

1_wykres_kapitalu.png — krzywe kapitału wszystkich kombinacji
    aktywo × interwał na szaro, mediana grubą linią (zielona
    na plusie, czerwona na minusie).
2_mediany.png — trzy duże liczby: ile kombinacji na plusie,
    mediana wyniku netto i mediana Win Rate (gdy autor obiecuje
    Win Rate) albo mediana Profit Factor.
3_tabela.png — pełna tabela wyników do pobrania z opisu.

Fonty: Anton (nagłówki, liczby) i Inter (reszta). Jeśli nie są
zainstalowane w systemie, używany jest font zastępczy. Tytuł
i duże liczby same zmniejszają się, gdy nie mieszczą się
w szerokości planszy.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import font_manager


BLACK = "#0B0D10"
WHITE = "#F2F2F2"
GREEN = "#00D084"
RED = "#FF3B30"
GRAY = "#8A8F98"

# 1920×1080 przy dpi=100.
SIZE = (19.2, 10.8)
DPI = 100


def save_plansze(
    folder,
    summary: pd.DataFrame,
    equities: dict,
    title: str,
    period: str,
    costs: str,
    claim_win_rate=None,
) -> list[Path]:
    """
    Zapisuje trzy plansze do folderu i zwraca ich ścieżki.

    summary — wiersze ze statusem OK z run_all_assets.py.
    equities — {(aktywo, interwał): DataFrame z kolumnami
    timestamp i equity}.
    claim_win_rate — Win Rate obiecany przez autora w procentach
    (np. 90) albo None.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)

    data = summary.reset_index(drop=True)
    subtitle = (
        f"{data['asset'].nunique()} aktywa × "
        f"{data['timeframe'].nunique()} interwały  |  {period}  |  po kosztach"
    )

    paths = [
        folder / "1_wykres_kapitalu.png",
        folder / "2_mediany.png",
        folder / "3_tabela.png",
    ]

    # mplfinance (wykresy pojedynczych testów) zmienia globalne
    # ustawienia Matplotlib, np. włącza pionową siatkę. Plansze
    # rysujemy więc na ustawieniach domyślnych.
    with plt.style.context("default"):
        _equity_chart(paths[0], data, equities, title, subtitle)
        _medians(paths[1], data, title, subtitle, claim_win_rate)
        _table(paths[2], data, title, subtitle, costs)

    return paths


# ============================================================
# 1. WYKRES KAPITAŁU
# ============================================================

def _equity_chart(path, data, equities, title, subtitle):
    curves = {}

    for _, row in data.iterrows():
        equity = equities.get((row["asset"], row["timeframe"]))

        if equity is None or equity.empty:
            continue

        values = (
            equity.assign(timestamp=pd.to_datetime(equity["timestamp"]))
            .set_index("timestamp")["equity"]
            .astype(float)
            .sort_index()
        )
        start = values.iloc[0]
        # Dzienny krok wystarcza do wykresu i wyrównuje osie czasu.
        values = values.resample("1D").last().dropna()
        curves[_label(row)] = (values / start - 1) * 100

    fig, ax = _figure()

    if curves:
        frame = pd.DataFrame(curves).sort_index().ffill().fillna(0.0)
        median = frame.median(axis=1)

        for column in frame.columns:
            ax.plot(frame.index, frame[column], color=WHITE,
                    alpha=0.22, linewidth=1.6)

        color = _sign_color(median.iloc[-1])

        ax.axhline(0, color=GRAY, linewidth=1.2, linestyle="--")

        # Podpisy na prawym końcu: mediana oraz najlepsza
        # i najgorsza kombinacja, jeśli nie nachodzą na medianę.
        end = frame.index[-1]
        last = frame.iloc[-1]
        gap = (frame.max().max() - frame.min().min()) * 0.06
        labels = [
            (median.iloc[-1], f"mediana {_pct(median.iloc[-1])}", color,
             26, "bold"),
        ]
        for y, name in ((last.max(), last.idxmax()), (last.min(), last.idxmin())):
            if all(abs(y - other) > gap for other, *_ in labels):
                labels.append((y, f"{name} {_pct(y)}", _sign_color(y),
                               22, "normal"))
                # Podpisana krzywa jaśniejsza, żeby było widać,
                # do której linii odnosi się podpis.
                ax.plot(frame.index, frame[name], color=WHITE,
                        alpha=0.55, linewidth=2)

        ax.plot(median.index, median, color=color, linewidth=5)

        for y, text, text_color, size, weight in labels:
            ax.annotate(
                text, (end, y), xytext=(14, 0), textcoords="offset points",
                va="center", color=text_color, fontsize=size,
                fontfamily=_body_font(), fontweight=weight,
                annotation_clip=False,
            )

    ax.set_ylabel("Zmiana kapitału", color=GRAY, fontsize=18,
                  fontfamily=_body_font())
    ax.yaxis.set_major_formatter(lambda value, _: _pct(value, 0))
    ax.tick_params(colors=GRAY, labelsize=18)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily(_body_font())
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#2A2E35")
    ax.grid(axis="y", color="#1C2026", linewidth=1)

    _header(fig, title, subtitle)
    fig.subplots_adjust(left=0.08, right=0.80, top=0.80, bottom=0.08)
    _save(fig, path)


# ============================================================
# 2. MEDIANY
# ============================================================

def _medians(path, data, title, subtitle, claim_win_rate):
    returns = data["return_%"].astype(float)
    profitable = int((returns > 0).sum())
    median_return = float(returns.median())

    items = [
        (
            f"{profitable}/{len(data)}",
            "kombinacji na plusie\npo kosztach",
            GREEN if profitable > len(data) / 2 else RED,
        ),
        (
            _pct(median_return),
            "mediana\nwyniku netto",
            _sign_color(median_return),
        ),
    ]

    if claim_win_rate is not None:
        win_rate = float(data["win_rate_%"].astype(float).median())
        items.append((
            _pct(win_rate, 0, sign=False),
            f"mediana Win Rate\nobiecane: {_num(claim_win_rate, 0)}%",
            GREEN if win_rate >= claim_win_rate else RED,
        ))
    else:
        profit_factor = float(data["profit_factor"].astype(float).median())
        items.append((
            _num(profit_factor, 2),
            "mediana\nProfit Factor",
            GREEN if profit_factor >= 1 else RED,
        ))

    fig = plt.figure(figsize=SIZE, dpi=DPI, facecolor=BLACK)
    _header(fig, title, subtitle)

    # Blok liczb i podpisów wyśrodkowany w pionie pod nagłówkiem.
    width = 1 / len(items)
    values = []
    for i, (value, label, color) in enumerate(items):
        x = width * (i + 0.5)
        # Liczba stoi na stałej linii nad podpisem — przy
        # zmniejszonej czcionce odstęp między nimi się nie zmienia.
        values.append(fig.text(
            x, 0.45, value, ha="center", va="baseline", color=color,
            fontsize=150, fontfamily=_heading_font(),
            fontweight=_heading_weight(),
        ))
        fig.text(x, 0.38, label, ha="center", va="top", color=WHITE,
                 fontsize=32, fontfamily=_body_font(), linespacing=1.3)

    # Wszystkie liczby tej samej wielkości, każda z odstępem od
    # sąsiednich (najwyżej 80% szerokości swojej kolumny).
    _fit_width(fig, values, width * 0.8, min_size=60)

    _save(fig, path)


# ============================================================
# 3. TABELA
# ============================================================

def _table(path, data, title, subtitle, costs):
    columns = [
        ("Aktywo", 0.06, "left"),
        ("Interwał", 0.21, "left"),
        ("Wynik netto", 0.40, "right"),
        ("CAGR", 0.51, "right"),
        ("Profit Factor", 0.62, "right"),
        ("Win Rate", 0.72, "right"),
        ("Max Drawdown", 0.87, "right"),
        ("Transakcje", 0.96, "right"),
    ]

    fig = plt.figure(figsize=SIZE, dpi=DPI, facecolor=BLACK)
    _header(fig, title, subtitle)

    top, bottom = 0.76, 0.10
    row_height = min(0.055, (top - bottom) / (len(data) + 1))
    font_size = 24 if row_height >= 0.05 else 18

    for name, x, align in columns:
        fig.text(x, top, name, ha=align, va="center", color=GRAY,
                 fontsize=font_size - 4, fontfamily=_body_font())

    for i, (_, row) in enumerate(data.iterrows()):
        y = top - row_height * (i + 1)

        if i % 2 == 0:
            fig.patches.append(plt.Rectangle(
                (0.04, y - row_height / 2), 0.94, row_height,
                transform=fig.transFigure, color="#14171C", zorder=0,
            ))

        result = float(row["return_%"])
        cells = [
            (row["asset"], WHITE),
            (_timeframe(row["timeframe"]), WHITE),
            (_pct(result), _sign_color(result)),
            (_pct(row["cagr_%"]), _sign_color(row["cagr_%"])),
            (_num(row["profit_factor"], 2), WHITE),
            (_pct(row["win_rate_%"], 1, sign=False), WHITE),
            (_pct(row["max_drawdown_%"], 1, sign=False), WHITE),
            (str(row["trades"]), WHITE),
        ]
        for (_, x, align), (text, color) in zip(columns, cells):
            fig.text(x, y, text, ha=align, va="center", color=color,
                     fontsize=font_size, fontfamily=_body_font())

    fig.text(0.04, 0.04, f"Koszty: {costs}.", ha="left", va="center",
             color=GRAY, fontsize=14, fontfamily=_body_font())

    _save(fig, path)


# ============================================================
# POMOCNICZE
# ============================================================

def _figure():
    fig, ax = plt.subplots(figsize=SIZE, dpi=DPI, facecolor=BLACK)
    ax.set_facecolor(BLACK)
    return fig, ax


def _header(fig, title, subtitle):
    heading = fig.text(0.04, 0.92, title.upper(), ha="left", va="center",
                       color=WHITE, fontsize=48, fontfamily=_heading_font(),
                       fontweight=_heading_weight())
    # Długi tytuł zmniejszamy, aby zmieścił się do prawego marginesu.
    _fit_width(fig, [heading], 0.92, min_size=26)
    fig.text(0.04, 0.855, subtitle, ha="left", va="center",
             color=GRAY, fontsize=22, fontfamily=_body_font())


def _fit_width(fig, texts, max_width, min_size):
    """
    Zmniejsza czcionkę tekstów (wspólną dla wszystkich), aż każdy
    zmieści się w max_width (ułamek szerokości planszy).
    """
    renderer = fig.canvas.get_renderer()
    limit = max_width * fig.bbox.width
    size = texts[0].get_fontsize()

    while size > min_size and any(
        text.get_window_extent(renderer).width > limit for text in texts
    ):
        size -= 2
        for text in texts:
            text.set_fontsize(size)


def _save(fig, path):
    fig.savefig(path, dpi=DPI, facecolor=BLACK)
    plt.close(fig)


def _installed(family: str) -> bool:
    return any(f.name == family for f in font_manager.fontManager.ttflist)


def _heading_font() -> str:
    if _installed("Anton"):
        return "Anton"
    return _body_font()


def _heading_weight() -> str:
    # Anton ma jedną grubość; zastępczy font pogrubiamy.
    return "normal" if _installed("Anton") else "bold"


def _body_font() -> str:
    return "Inter" if _installed("Inter") else "DejaVu Sans"


def _label(row) -> str:
    return f"{row['asset']} {_timeframe(row['timeframe'])}"


def _timeframe(value: str) -> str:
    return value.replace("min", "m")


def _num(value, decimals: int) -> str:
    if value is None or pd.isna(value):
        return "–"
    if value == float("inf"):
        return "∞"
    # Polski zapis: przecinek dziesiętny.
    return f"{value:.{decimals}f}".replace(".", ",")


def _pct(value, decimals: int = 1, sign: bool = True) -> str:
    if value is None or pd.isna(value):
        return "–"
    text = f"{value:+.{decimals}f}" if sign else f"{value:.{decimals}f}"
    return text.replace(".", ",").replace("-", "−") + "%"


def _sign_color(value) -> str:
    if value is None or pd.isna(value) or value == 0:
        return WHITE
    return GREEN if value > 0 else RED
