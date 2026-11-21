"""
Zbiorczy wykres HTML wszystkich kombinacji aktywo × interwał.

Słupki to wynik netto każdej kombinacji (zielony zysk, czerwony
strata), przerywana linia to mediana. Nad wykresem: ile kombinacji
jest na plusie po kosztach, mediana, najlepsza i najgorsza.
Pod wykresem tabela z pozostałymi statystykami.

min_trades (opcja): kombinacje z mniejszą liczbą transakcji są szare,
na końcu, i nie wchodzą do „na plusie”, mediany ani najlepszej/najgorszej
(jak w narzedzia/plansze.py).
"""

import pandas as pd


GREEN = "#00D084"
RED = "#FF3B30"
YELLOW = "#F5C542"
GRAY = "#B0B4BA"


def save_summary_chart(
    path,
    summary: pd.DataFrame,
    title: str,
    costs: str,
    min_trades=None,
    zero_text: str = "brak transakcji",
):
    # Import tutaj, aby brak plotly nie blokował reszty programu.
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from narzedzia.plansze import low_trades_text, skipped_note, split_by_trades

    counted, skipped = split_by_trades(summary, min_trades)
    # Pominięte na końcu — liczone są pierwsze len(counted) wierszy.
    data = pd.concat([counted, skipped], ignore_index=True)
    n = len(counted)
    labels = data["asset"] + " " + data["timeframe"].str.replace("min", "m")
    returns = data["return_%"].astype(float)
    colors = [
        (GREEN if value > 0 else RED) if i < n else GRAY
        for i, value in enumerate(returns)
    ]

    stats = returns.iloc[:n]
    profitable = int((stats > 0).sum())
    median = float(stats.median()) if n else 0.0
    best = int(stats.idxmax()) if n else None
    worst = int(stats.idxmin()) if n else None
    notes = [
        "" if i < n else low_trades_text(
            pd.to_numeric(row["trades"], errors="coerce"), min_trades, zero_text
        )
        for i, (_, row) in enumerate(data.iterrows())
    ]

    fig = make_subplots(
        rows=2,
        cols=1,
        vertical_spacing=0.08,
        row_heights=[0.55, 0.45],
        specs=[[{"type": "xy"}], [{"type": "table"}]],
    )

    # ========================================================
    # 1. WYNIK NETTO KAŻDEJ KOMBINACJI
    # ========================================================

    hover = [
        f"<b>{label}</b><br>"
        f"Wynik netto: {row['return_%']:.2f}%<br>"
        f"Profit Factor: {_fmt(row['profit_factor'])}<br>"
        f"Win Rate: {_fmt(row['win_rate_%'], '%')}<br>"
        f"Max Drawdown: {_fmt(row['max_drawdown_%'], '%')}<br>"
        f"Transakcje: {row['trades']}"
        + (f"<br><i>poza statystyką: {note}</i>" if note else "")
        for label, note, (_, row) in zip(labels, notes, data.iterrows())
    ]

    fig.add_trace(
        go.Bar(
            x=labels,
            y=returns,
            marker_color=colors,
            text=[f"{value:+.1f}%" for value in returns],
            textposition="outside",
            hovertext=hover,
            hoverinfo="text",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    fig.add_hline(
        y=median,
        line=dict(color="gray", width=2, dash="dash"),
        annotation_text=f"mediana {median:+.2f}%",
        annotation_position="bottom right",
        row=1,
        col=1,
    )
    fig.add_hline(y=0, line=dict(color="black", width=1), row=1, col=1)

    # ========================================================
    # 2. TABELA
    # ========================================================

    columns = [
        ("Aktywo", labels),
        ("Wynik netto", [f"{v:+.2f}%" for v in returns]),
        ("Profit Factor", [_fmt(v) for v in data["profit_factor"]]),
        ("Win Rate", [_fmt(v, "%") for v in data["win_rate_%"]]),
        ("Max Drawdown", [_fmt(v, "%") for v in data["max_drawdown_%"]]),
        ("Transakcje", [str(v) for v in data["trades"]]),
        ("Kapitał końcowy", [f"${v:,.0f}" for v in data["final_capital"]]),
    ]
    if notes[n:]:
        columns.append(("Uwagi", notes))
    result_colors = [
        ("#e8faf3" if v > 0 else "#ffecea") if i < n else "#eeeeee"
        for i, v in enumerate(returns)
    ]

    fig.add_trace(
        go.Table(
            header=dict(
                values=[f"<b>{name}</b>" for name, _ in columns],
                fill_color="#f2f2f2",
                font=dict(size=13),
                align="center",
            ),
            cells=dict(
                values=[values for _, values in columns],
                fill_color=[result_colors] * len(columns),
                font=dict(size=13),
                align="center",
                height=26,
            ),
        ),
        row=2,
        col=1,
    )

    # ========================================================
    # 3. NAGŁÓWEK
    # ========================================================

    items = [
        (
            "NA PLUSIE PO KOSZTACH",
            f"{profitable} z {n}",
            profitable_color(profitable, n),
        ),
        ("MEDIANA WYNIKU", f"{median:+.2f}%" if n else "–", _sign_color(median)),
    ]
    if n:
        items += [
            (
                "NAJLEPSZA",
                f"{labels[best]} {returns[best]:+.1f}%",
                _sign_color(returns[best]),
            ),
            (
                "NAJGORSZA",
                f"{labels[worst]} {returns[worst]:+.1f}%",
                _sign_color(returns[worst]),
            ),
        ]

    width = 1 / len(items)

    for i, (label, value, color) in enumerate(items):
        center = width * (i + 0.5)
        fig.add_annotation(
            text=label,
            x=center, y=1.10, xref="paper", yref="paper",
            showarrow=False, font=dict(size=12, color="gray"),
        )
        fig.add_annotation(
            text=f"<b>{value}</b>",
            x=center, y=1.065, xref="paper", yref="paper",
            showarrow=False, font=dict(size=20, color=color),
        )

    note = skipped_note(skipped, min_trades)
    if note:
        fig.add_annotation(
            text=note + ".",
            x=0, y=1.03, xref="paper", yref="paper", xanchor="left",
            showarrow=False, font=dict(size=10, color="gray"),
        )

    fig.add_annotation(
        text=f"Koszty: {costs}.",
        x=1, y=1.03, xref="paper", yref="paper", xanchor="right",
        showarrow=False, font=dict(size=10, color="gray"),
    )

    fig.update_layout(
        title=dict(text=f"<b>{title}</b>", font=dict(size=22), y=0.985),
        template="plotly_white",
        height=max(1000, 700 + 28 * len(data)),
        margin=dict(t=170, l=60, r=40, b=30),
    )
    fig.update_yaxes(title_text="Wynik netto (%)", ticksuffix="%", row=1, col=1)

    fig.write_html(
        str(path),
        include_plotlyjs=True,  # plik działa bez internetu
        config={"displaylogo": False},
    )


def _fmt(value, suffix="") -> str:
    if value is None or pd.isna(value):
        return "–"
    if value == float("inf"):
        return "∞"
    return f"{value:.2f}{suffix}"


def _sign_color(value) -> str:
    if value == 0:
        return "black"
    return GREEN if value > 0 else RED


def profitable_color(profitable: int, total: int) -> str:
    """Jak w narzedzia/plansze.py: poniżej połowy czerwony, od połowy żółty, od 80% zielony."""
    if total == 0:
        return "#F2F2F2"
    share = profitable / total
    if share < 0.5:
        return RED
    return YELLOW if share < 0.8 else GREEN
