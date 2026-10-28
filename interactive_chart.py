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


# Najwięcej świec w jednym pliku HTML. 5 lat na 30 min to ok. 62 tys.
# świec i działa; 1 min to ok. 1,8 mln i przeglądarka pokazuje
# białą stronę.
HTML_MAX_BARS = 100_000


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
    overlays: list | None = None,
    candle_fill: dict | None = None,
    markers: list | None = None,
    max_bars: int | None = HTML_MAX_BARS,
) -> None:
    # Import tutaj, aby brak plotly nie blokował reszty programu.
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    # Za dużo świec (np. 1 min × 5 lat) daje plik, którego przeglądarka
    # nie otworzy — wtedy HTML pokazuje tylko fragment wokół
    # najdłuższej serii strat. Statystyki zostają z całego okresu.
    if max_bars and len(bars) > max_bars:
        i0 = len(bars) - max_bars

        if stats.get("loss_streak_start") is not None:
            s0, s1 = bars.index.searchsorted(
                [stats["loss_streak_start"], stats["loss_streak_end"]]
            )
            i0 = (s0 + s1) // 2 - max_bars // 2

        i0 = int(min(max(i0, 0), len(bars) - max_bars))
        i1 = i0 + max_bars
        t0 = bars.index[i0]
        t1 = bars.index[i1] if i1 < len(bars) else pd.Timestamp.max

        bars = bars.iloc[i0:i1]
        signals = signals.reindex(bars.index)
        trend = trend.reindex(bars.index) if trend is not None else None
        panel = dict(panel)
        panel["lines"] = [
            (name, series.reindex(bars.index), color)
            for name, series, color in panel["lines"]
        ]

        if not trades.empty:
            trades = trades[
                (pd.to_datetime(trades["entry_time"]) < t1)
                & (pd.to_datetime(trades["exit_time"]) >= t0)
            ]
        if not equity.empty:
            stamps = pd.to_datetime(equity["timestamp"])
            equity = equity[(stamps >= t0) & (stamps < t1)]

        title += (
            f" | fragment {bars.index[0]:%Y-%m-%d} – {bars.index[-1]:%Y-%m-%d}"
        )

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

    def add_segments(mask, y0, y1, color, width):
        # Odcinki rozdzielone przerwami (NaN) — jeden ślad na kolor.
        if not mask.any():
            return
        fig.add_trace(
            go.Scattergl(
                x=_segments(x[mask], x[mask]),
                y=_segments(y0[mask], y1[mask]),
                mode="lines",
                line=dict(color=color, width=width),
                hoverinfo="skip",
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    price_colors = ((rising, "#26a69a"), (~rising, "#ef5350"))

    for mask, color in price_colors:
        add_segments(mask, lo, h, color, 1)

    if candle_fill is None:
        for mask, color in price_colors:
            add_segments(mask, o, c, color, 4)
    else:
        # Jak Volume Delta Candles [LuxAlgo]: pusty korpus z ramką
        # w kolorze ceny, w środku wypełnienie wskaźnika od base
        # do value w jego własnym kolorze.
        for mask, color in price_colors:
            add_segments(mask, o, c, color, 7)
        add_segments(np.ones(n, dtype=bool), o, c, "white", 4)

        base = candle_fill["base"].reindex(bars.index).to_numpy(dtype=float)
        value = candle_fill["value"].reindex(bars.index).to_numpy(dtype=float)
        colors = candle_fill["color"].reindex(bars.index).to_numpy(dtype=object)
        has_fill = np.isfinite(base) & np.isfinite(value)

        for color in pd.unique(colors[has_fill]):
            add_segments(has_fill & (colors == color), base, value, color, 4)

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

    # Odstęp znaczników od świecy: ułamek typowej wysokości świecy,
    # a nie procent ceny — inaczej na EURUSD 30 min znaczniki
    # wiszą kilka świec nad wykresem.
    gap = _marker_gap(h, lo)

    fig.add_trace(
        go.Scattergl(
            x=x[buy],
            y=lo[buy] - 0.7 * gap,
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
            y=h[sell] + 0.7 * gap,
            mode="markers",
            marker=dict(symbol="triangle-down", size=7, color="orange"),
            name="Sygnał short",
            hoverinfo="skip",
        ),
        row=1,
        col=1,
    )

    # Dodatkowe linie na cenie, np. średnie kroczące.
    for name, series, color in overlays or []:
        fig.add_trace(
            go.Scattergl(
                x=x,
                y=series.reindex(bars.index).to_numpy(dtype=float),
                mode="lines",
                line=dict(color=color, width=1.5),
                name=name,
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )

    # Kropki wskaźnika w podanej cenie, np. pivoty na knotach.
    for name, series, color, _ in markers or []:
        values = series.reindex(bars.index).to_numpy(dtype=float)
        has_value = ~np.isnan(values)
        fig.add_trace(
            go.Scattergl(
                x=x[has_value],
                y=values[has_value],
                mode="markers",
                marker=dict(size=7, color=color, line=dict(width=0)),
                name=name,
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
                y=h[mask] + 1.5 * gap if above else lo[mask] - 1.5 * gap,
                mode="markers+text",
                marker=dict(
                    symbol="square", size=22, color=color,
                    line=dict(width=0),
                ),
                text=[text] * int(mask.sum()),
                textposition="middle center",
                textfont=dict(color="white", size=14),
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
                f"wejście {t.entry_time:%Y-%m-%d %H:%M:%S} @ {_price(t.entry_price)}<br>"
                f"wyjście {t.exit_time:%Y-%m-%d %H:%M:%S} @ {_price(t.exit_price)}<br>"
                f"SL {_price(t.stop_loss)} | TP {_price(t.take_profit)}<br>"
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
                        size=20,
                        color=color,
                        line=dict(color="black", width=1.5),
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
                marker=dict(
                    symbol="x", size=16, color="black",
                    line=dict(color="white", width=1),
                ),
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

    # Najdłuższa seria strat — czerwone tło i pionowe linie na cenie
    # i kapitale, czerwony odcinek krzywej kapitału. Na kilku latach
    # danych tło ma ułamek piksela, więc linie mają stałą grubość,
    # a kliknięcie napisu przybliża wykres do serii.
    streak = None
    if stats.get("loss_streak") and stats.get("loss_streak_start") is not None:
        x0, x1 = bar_position(
            [stats["loss_streak_start"], stats["loss_streak_end"]]
        )
        streak = [float(x0), float(x1)]
        for row in (1, 3):
            fig.add_vrect(
                x0=x0 - 0.5, x1=x1 + 0.5, row=row, col=1,
                fillcolor="#FF3B30", opacity=0.15, line_width=0,
                layer="below",
            )
            for x in (x0 - 0.5, x1 + 0.5):
                fig.add_vline(
                    x=x, row=row, col=1,
                    line=dict(color="#FF3B30", width=1.5, dash="dot"),
                )
        inside = (equity_x >= x0 - 1) & (equity_x <= x1)
        if inside.any():
            fig.add_trace(
                go.Scattergl(
                    x=equity_x[inside],
                    y=equity_y[inside],
                    mode="lines",
                    line=dict(color="#FF3B30", width=3),
                    name="Seria strat",
                    hovertemplate="%{y:,.2f} $<extra></extra>",
                ),
                row=3,
                col=1,
            )
        fig.add_annotation(
            x=0, y=1, xref="paper", yref="y domain",
            xanchor="left", yanchor="bottom", showarrow=False,
            text=(
                f"<b>Najdłuższa seria strat: {stats['loss_streak']} z rzędu "
                f"({stats['loss_streak_return'] * 100:+.1f}%)</b>"
                " — kliknij, żeby przybliżyć"
            ),
            font=dict(size=13, color="#FF3B30"),
            bgcolor="rgba(255,59,48,0.08)", bordercolor="#FF3B30",
            borderpad=3, captureevents=True, name="loss_streak",
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
        title_text=panel["title"],
        range=list(panel.get("range", (0, 100))),
        row=2,
        col=1,
    )
    fig.update_yaxes(title_text="Kapitał ($)", row=3, col=1)

    data = {
        "labels": list(labels),
        "low": _json_floats(lo),
        "high": _json_floats(h),
        "equityX": _json_floats(equity_x),
        "equityY": _json_floats(equity_y),
        "initialCapital": float(initial_capital),
        "streak": streak,
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

// Kliknięcie napisu o serii strat: przybliż do niej z marginesem.
gd.on('plotly_clickannotation', function (ev) {
    if (!D.streak || ev.annotation.name !== 'loss_streak') return;
    var span = D.streak[1] - D.streak[0];
    var pad = Math.max(span * 0.5, 20);
    Plotly.relayout(gd, {
        'xaxis.range': [D.streak[0] - pad, D.streak[1] + pad]
    });
});

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


def _price(value) -> str:
    """Cena w podpowiedzi bez szumu typu 29159.890000000003."""
    if value is None or pd.isna(value):
        return "–"
    value = float(value)
    decimals = 2 if abs(value) >= 1000 else 3 if abs(value) >= 10 else 5
    return f"{value:.{decimals}f}"


def _marker_gap(high: np.ndarray, low: np.ndarray) -> float:
    """Mediana wysokości świecy (zapas: 0,1% ceny przy zerowej)."""
    gap = float(np.nanmedian(high - low)) if len(high) else 0.0
    if not np.isfinite(gap) or gap <= 0:
        gap = float(np.nanmedian(high)) * 0.001 if len(high) else 0.0
    return gap
