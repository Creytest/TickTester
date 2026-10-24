"""
Zbiorczy wykres HTML wszystkich kombinacji aktywo × interwał.

Słupki to wynik netto każdej kombinacji (zielony zysk, czerwony
strata), przerywana linia to mediana. Nad wykresem: ile kombinacji
jest na plusie po kosztach, mediana, najlepsza i najgorsza.
Pod wykresem tabela z pozostałymi statystykami.
"""

import pandas as pd


GREEN = "#00D084"
RED = "#FF3B30"


def save_summary_chart(path, summary: pd.DataFrame, title: str, costs: str):
    # Import tutaj, aby brak plotly nie blokował reszty programu.
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    data = summary.reset_index(drop=True)
    labels = data["asset"] + " " + data["timeframe"].str.replace("min", "m")
    returns = data["return_%"].astype(float)
    colors = [GREEN if value > 0 else RED for value in returns]

    profitable = int((returns > 0).sum())
    median = float(returns.median())
    best = int(returns.idxmax())
    worst = int(returns.idxmin())

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
        for label, (_, row) in zip(labels, data.iterrows())
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
    result_colors = ["#e8faf3" if v > 0 else "#ffecea" for v in returns]

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
            f"{profitable} z {len(data)}",
            GREEN if profitable > len(data) / 2 else RED,
        ),
        ("MEDIANA WYNIKU", f"{median:+.2f}%", _sign_color(median)),
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
