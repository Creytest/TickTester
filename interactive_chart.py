"""
Interaktywny wykres backtestu zapisywany jako plik HTML.

Otwierasz go w przeglądarce:
- kółko myszy przybliża i oddala (oś czasu),
- przeciąganie myszą przesuwa wykres,
- lupa w prawym górnym rogu: zaznacz obszar do powiększenia,
- dwuklik wraca do całości,
- po najechaniu na świecę lub transakcję widać szczegóły.

Jak w TradingView oś X to kolejne świece (bez pustych weekendów),
a skala ceny i kapitału dopasowuje się do widocznego fragmentu.
Świece rysowane są przez WebGL, więc nawet rok na 5 minutach
przesuwa się płynnie.
"""

import json

import numpy as np
import pandas as pd


def save_interactive_chart(
    path,
    title: str,
    bars: pd.DataFrame,
    signals: pd.DataFrame,
    trades: pd.DataFrame,
    trend: pd.Series | None,
    panel: dict,
    equity: pd.DataFrame,
    stats: dict,
    initial_capital: float,
    labels: list | None = None,
) -> None:
    # Import tutaj, aby brak plotly nie blokował reszty programu.
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    n = len(bars)
    x = np.arange(n, dtype=float)
    bar_labels = labels
    labels = bars.index.strftime("%Y-%m-%d %H:%M")

    def bar_position(times) -> np.ndarray:
        """Numer świecy, w której wypada dany czas."""
        times = pd.DatetimeIndex(pd.to_datetime(times))
        positions = bars.index.searchsorted(times, side="right") - 1
        return np.clip(positions, 0, n - 1).astype(float)

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.62, 0.18, 0.20],
    )

    # ========================================================
    # 1. ŚWIECE (WebGL)
    # ========================================================

    o = bars["open"].to_numpy(dtype=float)
    h = bars["high"].to_numpy(dtype=float)
    lo = bars["low"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)
    rising = c >= o

    for mask, color in ((rising, "#26a69a"), (~rising, "#ef5350")):
        # Knoty i korpusy jako odcinki rozdzielone przerwami (NaN).
        fig.add_trace(
            go.Scattergl(
                x=_segments(x[mask], x[mask]),
                y=_segments(lo[mask], h[mask]),
                mode="lines",
                line=dict(color=color, width=1),
                hoverinfo="skip",
                showlegend=False,
            ),
            row=1,
            col=1,
        )
        fig.add_trace(
            go.Scattergl(
                x=_segments(x[mask], x[mask]),
                y=_segments(o[mask], c[mask]),
                mode="lines",
                line=dict(color=color, width=4),
                hoverinfo="skip",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    # Niewidoczne punkty na zamknięciu — tylko do podpowiedzi.
    fig.add_trace(
        go.Scattergl(
            x=x,
            y=c,
            mode="markers",
            marker=dict(size=6, opacity=0),
            customdata=np.column_stack((o, h, lo, c)),
            text=labels,
            hovertemplate=(
                "%{text}<br>O %{customdata[0]}  H %{customdata[1]}"
                "<br>L %{customdata[2]}  C %{customdata[3]}<extra></extra>"
            ),
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # ========================================================
    # 2. TWO-POLE FILTER W KOLORACH
    # ========================================================

    # Kolor jak na wykresie PNG: wzrost względem 2 świec wstecz
    # zielony, spadek czerwony, brak zmiany żółty. Każdy kolor
    # to osobna linia; na granicy zostawiamy wspólny punkt,
    # aby linia była ciągła.
    trend_values = (
        trend.to_numpy(dtype=float) if trend is not None else None
    )
    direction = (
        np.sign(trend.diff(2).to_numpy(dtype=float))
        if trend is not None
        else None
    )

    for value, color, name in (
        ()
        if trend is None
        else (
            (1, "lime", "Trend ↑"),
            (-1, "red", "Trend ↓"),
            (0, "gold", "Trend ="),
        )
    ):
        mask = direction == value
        visible = mask | np.append(mask[1:], False)
        fig.add_trace(
            go.Scattergl(
                x=x,
                y=np.where(visible, trend_values, np.nan),
                mode="lines",
                line=dict(color=color, width=2),
                name=name,
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )

    # ========================================================
    # 3. SYGNAŁY, WEJŚCIA I WYJŚCIA
    # ========================================================

    buy = signals["buy"].fillna(False).astype(bool).to_numpy()
    sell = signals["sell"].fillna(False).astype(bool).to_numpy()

    fig.add_trace(
        go.Scattergl(
            x=x[buy],
            y=lo[buy] * 0.999,
            mode="markers",
            marker=dict(symbol="triangle-up", size=7, color="deepskyblue"),
            name="Sygnał long",
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scattergl(
            x=x[sell],
            y=h[sell] * 1.001,
            mode="markers",
            marker=dict(symbol="triangle-down", size=7, color="orange"),
            name="Sygnał short",
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )

    # Etykiety wskaźnika jak w TradingView, np. „B” LuxAlgo.
    # Rysowane jako SVG — WebGL nie obsługuje tekstu na znacznikach.
    for name, mask, text, color, location in bar_labels or []:
        mask = mask.reindex(bars.index).fillna(False).to_numpy(dtype=bool)
        above = location == "above"
        fig.add_trace(
            go.Scatter(
                x=x[mask],
                y=h[mask] * 1.0015 if above else lo[mask] * 0.9985,
                mode="markers+text",
                marker=dict(
                    symbol="square", size=15, color=color,
                    line=dict(width=0),
                ),
                text=[text] * int(mask.sum()),
                textposition="middle center",
                textfont=dict(color="white", size=10),
                name=name,
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )

    if not trades.empty:
        entry_x = bar_position(trades["entry_time"])
        exit_x = bar_position(trades["exit_time"])

        hover = [
            (
                f"{t.side} | {t.reason}<br>"
                f"wejście {t.entry_time:%Y-%m-%d %H:%M:%S} @ {t.entry_price}<br>"
                f"wyjście {t.exit_time:%Y-%m-%d %H:%M:%S} @ {t.exit_price}<br>"
                f"SL {t.stop_loss} | TP {t.take_profit}<br>"
                f"wynik netto: {t.net_pnl:.2f} $"
            )
            for t in trades.itertuples()
        ]

        for side, symbol, color, name in (
            ("long", "triangle-up", "lime", "Wejście long"),
            ("short", "triangle-down", "red", "Wejście short"),
        ):
            mask = (trades["side"] == side).to_numpy()
            fig.add_trace(
                go.Scattergl(
                    x=entry_x[mask],
                    y=trades.loc[mask, "entry_price"],
                    mode="markers",
                    marker=dict(
                        symbol=symbol,
                        size=13,
                        color=color,
                        line=dict(color="black", width=1),
                    ),
                    name=name,
                    text=[text for text, m in zip(hover, mask) if m],
                    hovertemplate="%{text}<extra></extra>",
                ),
                row=1,
                col=1,
            )

        fig.add_trace(
            go.Scattergl(
                x=exit_x,
                y=trades["exit_price"],
                mode="markers",
                marker=dict(symbol="x", size=10, color="black"),
                name="Wyjście",
                text=hover,
                hovertemplate="%{text}<extra></extra>",
            ),
            row=1,
            col=1,
        )

        # Poziomy SL i TP od wejścia do wyjścia.
        for column, color, name in (
            ("stop_loss", "red", "SL"),
            ("take_profit", "green", "TP"),
        ):
            levels = trades[column].to_numpy(dtype=float)
            has_level = ~np.isnan(levels)
            fig.add_trace(
                go.Scattergl(
                    x=_segments(entry_x[has_level], exit_x[has_level]),
                    y=_segments(levels[has_level], levels[has_level]),
                    mode="lines",
                    line=dict(color=color, width=1, dash="dash"),
                    name=name,
                    hoverinfo="skip",
                ),
                row=1,
                col=1,
            )

    # ========================================================
    # 4. OSCYLATOR STRATEGII (np. Stochastic, RSI)
    # ========================================================

    for name, series, color in panel["lines"]:
        fig.add_trace(
            go.Scattergl(
                x=x,
                y=series.to_numpy(dtype=float),
                mode="lines",
                line=dict(color=color, width=1),
                name=name,
                hoverinfo="skip",
            ),
            row=2,
            col=1,
        )

    for level in panel["levels"]:
        fig.add_hline(
            y=level, row=2, col=1,
            line=dict(color="gray", width=1, dash="dot"),
        )

    # ========================================================
    # 5. KRZYWA KAPITAŁU
    # ========================================================

    equity_x = np.array([], dtype=float)
    equity_y = np.array([], dtype=float)

    if not equity.empty:
        curve = equity.sort_values("timestamp")
        equity_x = bar_position(curve["timestamp"])
        equity_y = curve["equity"].to_numpy(dtype=float)

        fig.add_trace(
            go.Scattergl(
                x=equity_x,
                y=equity_y,
                mode="lines",
                line=dict(color="black", width=1.5),
                name="Kapitał",
                hovertemplate="%{y:,.2f} $<extra></extra>",
            ),
            row=3,
            col=1,
        )

    fig.add_hline(
        y=initial_capital, row=3, col=1,
        line=dict(color="gray", width=1, dash="dash"),
    )

    # ========================================================
    # 6. UKŁAD I STATYSTYKI
    # ========================================================

    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            x=0.5,
            y=0.985,
            font=dict(size=20),
        ),
        height=1000,
        hovermode="closest",
        dragmode="pan",
        legend=dict(orientation="h", y=-0.06, font=dict(size=13)),
        margin=dict(l=70, r=30, t=150, b=70),
        plot_bgcolor="white",
        font=dict(size=13),
    )

    # Rząd statystyk nad wykresem, jak na wykresie PNG:
    # szara etykieta, pod nią duża kolorowa wartość.
    items = _stats_items(stats)
    width = 1 / len(items)

    for i, (label, value, color) in enumerate(items):
        center = width * (i + 0.5)
        fig.add_annotation(
            text=label,
            x=center, y=1.115, xref="paper", yref="paper",
            showarrow=False, font=dict(size=12, color="gray"),
        )
        fig.add_annotation(
            text=f"<b>{value}</b>",
            x=center, y=1.08, xref="paper", yref="paper",
            showarrow=False, font=dict(size=19, color=color),
        )

    fig.add_annotation(
        text="W nawiasach: bez prowizji (gross). Avg trade: % kapitału.",
        x=1, y=1.045, xref="paper", yref="paper", xanchor="right",
        showarrow=False, font=dict(size=10, color="gray"),
    )
    fig.update_xaxes(showgrid=True, gridcolor="#eee", range=[-1, n])
    # Skalę Y ustawia skrypt poniżej, więc zoom działa tylko w poziomie.
    fig.update_yaxes(showgrid=True, gridcolor="#eee", fixedrange=True)
    fig.update_yaxes(title_text="Cena Bid", row=1, col=1)
    fig.update_yaxes(
        title_text=panel["title"], range=[0, 100], row=2, col=1
    )
    fig.update_yaxes(title_text="Kapitał ($)", row=3, col=1)

    data = {
        "labels": list(labels),
        "low": _json_floats(lo),
        "high": _json_floats(h),
        "equityX": _json_floats(equity_x),
        "equityY": _json_floats(equity_y),
        "initialCapital": float(initial_capital),
    }

    fig.write_html(
        str(path),
        include_plotlyjs=True,  # plik działa bez internetu
        config={"scrollZoom": True, "displaylogo": False},
        post_script=_AXIS_SCRIPT.replace("__DATA__", json.dumps(data)),
    )


def _segments(start: np.ndarray, end: np.ndarray) -> np.ndarray:
    """[s0, e0, NaN, s1, e1, NaN, ...] — osobne odcinki w jednej linii."""
    out = np.full(len(start) * 3, np.nan)
    out[0::3] = start
    out[1::3] = end
    return out


def _json_floats(values: np.ndarray) -> list:
    return [None if np.isnan(v) else round(float(v), 6) for v in values]


def _stats_items(stats: dict) -> list[tuple[str, str, str]]:
    """(etykieta, wartość, kolor) — zielony zysk, czerwony strata."""

    def pct(value):
        return "–" if value is None else f"{value * 100:.2f}%"

    def pf(value):
        if value is None:
            return "–"
        return "∞" if value == float("inf") else f"{value:.2f}"

    def sign_color(value):
        if value is None or value == 0:
            return "black"
        return "green" if value > 0 else "red"

    start = stats["start_capital"]
    final = stats["final_capital"]
    profit_factor = stats["profit_factor"]

    return [
        ("START CAPITAL", f"${start:,.0f}", "black"),
        ("FINAL CAPITAL", f"${final:,.0f}", sign_color(final - start)),
        ("RETURN", pct(stats["return"]), sign_color(stats["return"])),
        ("CAGR", pct(stats["cagr"]), sign_color(stats["cagr"])),
        (
            "MAX DRAWDOWN",
            pct(stats["max_drawdown"]),
            "red" if stats["max_drawdown"] < 0 else "black",
        ),
        ("TRADES", str(stats["trades"]), "black"),
        ("WIN RATE", pct(stats["win_rate"]), "black"),
        (
            "PROFIT FACTOR",
            f"{pf(profit_factor)} ({pf(stats['profit_factor_gross'])})",
            "black"
            if profit_factor is None
            else ("green" if profit_factor >= 1 else "red"),
        ),
        (
            "AVG TRADE",
            f"{pct(stats['avg_trade'])} ({pct(stats['avg_trade_gross'])})",
            sign_color(stats["avg_trade"]),
        ),
    ]


# Po każdym przybliżeniu lub przesunięciu: daty na osi X
# i skala Y ceny oraz kapitału dla widocznych świec.
_AXIS_SCRIPT = """
var gd = document.getElementById('{plot_id}');
var D = __DATA__;
var n = D.labels.length;

function niceStep(raw) {
    var steps = [1, 2, 3, 6, 12, 24, 48, 72, 144, 288, 576, 1152, 2016,
                 4032, 8064, 16128, 32256, 64512];
    for (var i = 0; i < steps.length; i++) {
        if (steps[i] >= raw) return steps[i];
    }
    return Math.ceil(raw);
}

function rangeOf(xs, ys, i0, i1) {
    var lo = Infinity, hi = -Infinity;
    for (var i = 0; i < xs.length; i++) {
        if (xs[i] < i0 || xs[i] > i1 || ys[i] === null) continue;
        if (ys[i] < lo) lo = ys[i];
        if (ys[i] > hi) hi = ys[i];
    }
    return [lo, hi];
}

function update() {
    var r = gd.layout.xaxis.range;
    var i0 = Math.max(0, Math.ceil(r[0]));
    var i1 = Math.min(n - 1, Math.floor(r[1]));
    if (i1 < i0) return;

    var lo = Infinity, hi = -Infinity;
    for (var i = i0; i <= i1; i++) {
        if (D.low[i] !== null && D.low[i] < lo) lo = D.low[i];
        if (D.high[i] !== null && D.high[i] > hi) hi = D.high[i];
    }
    var pad = (hi - lo) * 0.05 || Math.abs(hi) * 0.001 || 1;

    var eq = rangeOf(D.equityX, D.equityY, i0 - 1, i1 + 1);
    eq[0] = Math.min(eq[0], D.initialCapital);
    eq[1] = Math.max(eq[1], D.initialCapital);
    var eqPad = (eq[1] - eq[0]) * 0.05 || 1;

    var step = niceStep((i1 - i0 + 1) / 8);
    var vals = [], text = [];
    for (var t = Math.ceil(i0 / step) * step; t <= i1; t += step) {
        vals.push(t);
        text.push(D.labels[t]);
    }

    Plotly.relayout(gd, {
        'yaxis.range': [lo - pad, hi + pad],
        'yaxis3.range': [eq[0] - eqPad, eq[1] + eqPad],
        'xaxis3.tickmode': 'array',
        'xaxis3.tickvals': vals,
        'xaxis3.ticktext': text
    });
}

gd.on('plotly_relayout', function (ev) {
    for (var key in ev) {
        if (key.indexOf('xaxis') === 0 &&
            (key.indexOf('range') > 0 || key.indexOf('autorange') > 0)) {
            update();
            return;
        }
    }
});

update();
"""
