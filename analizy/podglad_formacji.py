"""
Podgląd formacji świecowych na prawdziwych świecach: jeden HTML na każdą
z 12 formacji (analizy/formacje_swiecowe.py), jedno aktywo, jeden interwał.

Na wykresie:
- świece formacji podświetlone (zielone tło = bullish, czerwone = bearish),
- ramka ciągła = formacja w kontekście (po spadku / wzroście względem SMA 20),
  ramka przerywana = bez kontekstu (liczy się tylko w wariancie „bez kontekstu”),
- szara linia = SMA 20 (filtr kontekstu),
- przyciski „◀ poprzednia / następna ▶” przeskakują między wykrytymi
  formacjami, pole „tylko z kontekstem” zawęża listę.

Pokazuje WSZYSTKIE wykrycia (bez odstępu 20 świec z badania zdarzeń),
żeby można było ocenić same definicje.

Wyniki: wyniki/podglad_formacji/<aktywo>_<interwał>/<formacja>.html

Uruchomienie:
    python analizy/podglad_formacji.py
Wersja „kolory jak na planszy” (wyniki/podglad_formacji_plansza/):
    python analizy/podglad_formacji.py --plansza
"""

from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

# Uruchamianie bezpośrednio z tego folderu: dodaj folder repo do ścieżki importów.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from narzedzia.tick_config import ASSETS, REVERSE_BID_ASK
from narzedzia.tick_data import load_ticks_cached
from narzedzia.tick_engine import build_bars
from strategies.tiktok.SR_Retest import atr as atr_rma
from analizy.formacje_swiecowe import PATTERNS, detect_patterns, context_mask


# ============================================================
# KONFIGURACJA
# ============================================================

ASSET = "XAUUSD"
TIMEFRAME = "1h"
START_DATE = "2025-01-01"
END_DATE = "2025-12-31"
SMA_CONTEXT = 20
WINDOW_BEFORE = 40     # świece widoczne przed formacją po przeskoku
WINDOW_AFTER = 25      # i po niej (żeby było widać, co stało się dalej)
WARMUP_DAYS = 30

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "wyniki" / "podglad_formacji"

# Wersja „kolory jak na planszy” (każda świeca w kolorze z rysunku,
# formacje_swiecowe.PLANSZA_COLORS). Wyniki idą wtedy do folderu z dopiskiem
# _plansza. To samo daje uruchomienie z parametrem --plansza.
KOLORY_JAK_NA_PLANSZY = False

BLACK, WHITE, GREEN, RED, GRAY = "#0B0D10", "#F2F2F2", "#00D084", "#FF3B30", "#8A8F98"


# ============================================================
# DANE
# ============================================================

def load_bars() -> pd.DataFrame:
    start = pd.Timestamp(START_DATE) - pd.Timedelta(days=WARMUP_DAYS)
    end = pd.Timestamp(END_DATE) + pd.Timedelta(days=1)
    ticks = load_ticks_cached(
        ASSETS[ASSET],
        reverse_bid_ask=REVERSE_BID_ASK[ASSET],
        start_date=start.strftime("%Y-%m-%d"),
        end_date=end.strftime("%Y-%m-%d"),
    )
    if ticks.empty:
        raise SystemExit(f"Brak ticków {ASSET} w okresie {START_DATE} – {END_DATE}")
    ticks = ticks.sort_values("timestamp").reset_index(drop=True)
    return build_bars([ticks], TIMEFRAME)


# ============================================================
# HTML
# ============================================================

def save_pattern_html(bars: pd.DataFrame, name: str, signal: np.ndarray,
                      in_context: np.ndarray, sma: np.ndarray, file: Path) -> int:
    import plotly.graph_objects as go

    direction, n_candles = PATTERNS[name]
    color = GREEN if direction > 0 else RED
    fill = "rgba(0,208,132,0.16)" if direction > 0 else "rgba(255,59,48,0.16)"

    first = int(bars.index.searchsorted(pd.Timestamp(START_DATE)))
    hits = np.flatnonzero(signal)
    hits = hits[hits >= first]

    o = bars["open"].to_numpy(dtype=float)
    h = bars["high"].to_numpy(dtype=float)
    lo = bars["low"].to_numpy(dtype=float)
    c = bars["close"].to_numpy(dtype=float)
    x = np.arange(len(bars))
    dates = bars.index.strftime("%Y-%m-%d %H:%M")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=x, open=o, high=h, low=lo, close=c, name=ASSET,
        increasing=dict(line=dict(color=GREEN, width=1), fillcolor=GREEN),
        decreasing=dict(line=dict(color=RED, width=1), fillcolor=RED),
        text=dates, hoverinfo="text+x",
    ))
    fig.add_trace(go.Scatter(
        x=x, y=sma, mode="lines", name=f"SMA {SMA_CONTEXT}",
        line=dict(color=GRAY, width=1), hoverinfo="skip",
    ))

    # Podświetlenie świec formacji: ramka ciągła = w kontekście.
    shapes = []
    gap = float(np.nanmedian(h - lo)) if len(h) else 0.0
    for i in hits:
        a = i - n_candles + 1
        top = float(h[a:i + 1].max()) + 0.3 * gap
        bot = float(lo[a:i + 1].min()) - 0.3 * gap
        shapes.append(dict(
            type="rect", xref="x", yref="y", x0=a - 0.45, x1=i + 0.45, y0=bot, y1=top,
            fillcolor=fill, line=dict(color=color, width=1.5,
                                      dash="solid" if in_context[i] else "dot"),
            layer="below",
        ))
    label_y = [float(lo[i]) - 1.2 * gap if direction > 0 else float(h[i]) + 1.2 * gap
               for i in hits]
    fig.add_trace(go.Scatter(
        x=hits, y=label_y, mode="text",
        text=["▲" if direction > 0 else "▼"] * len(hits),
        textfont=dict(color=color, size=16), hoverinfo="skip", name=name,
    ))

    n_ctx = int(in_context[hits].sum()) if len(hits) else 0
    fig.update_layout(
        title=dict(
            text=(f"<b>{name}</b>{' (kolory jak na planszy)' if KOLORY_JAK_NA_PLANSZY else ''}  ·  {ASSET} {TIMEFRAME}  ·  {START_DATE} – {END_DATE}  ·  "
                  f"{len(hits)} wykryć, w tym {n_ctx} w kontekście (ramka ciągła)"),
            font=dict(color=WHITE, size=18), x=0.01,
        ),
        shapes=shapes,
        paper_bgcolor=BLACK, plot_bgcolor=BLACK,
        font=dict(color=WHITE, family="Inter, Arial, sans-serif"),
        xaxis=dict(rangeslider=dict(visible=False), gridcolor="#1c2027",
                   tickmode="array", showspikes=True),
        yaxis=dict(gridcolor="#1c2027", side="right", fixedrange=False),
        showlegend=False, margin=dict(l=20, r=70, t=60, b=40), dragmode="pan",
        height=820,
    )
    step = max(1, len(x) // 12)
    fig.update_xaxes(tickvals=x[::step].tolist(),
                     ticktext=bars.index[::step].strftime("%Y-%m-%d").tolist())

    data = {
        "hits": hits.tolist(),
        "ctx": [bool(in_context[i]) for i in hits],
        "dates": [dates[i] for i in hits],
        "high": h.tolist(), "low": lo.tolist(),
        "before": WINDOW_BEFORE, "after": WINDOW_AFTER, "n": n_candles,
    }
    nav = _NAV_JS.replace("__DATA__", json.dumps(data))
    html = fig.to_html(include_plotlyjs="cdn", full_html=True, div_id="chart",
                       post_script=nav, config={"scrollZoom": True})
    html = html.replace("<body>", f"<body style='background:{BLACK};margin:0'>" + _NAV_HTML, 1)
    file.write_text(html, encoding="utf-8")
    return len(hits)


_NAV_HTML = """
<div style="font-family:Inter,Arial,sans-serif;color:#F2F2F2;padding:10px 16px;display:flex;
gap:12px;align-items:center;background:#0B0D10">
  <button id="prev" style="padding:6px 14px">◀ poprzednia</button>
  <button id="next" style="padding:6px 14px">następna ▶</button>
  <span id="info" style="min-width:320px"></span>
  <label><input type="checkbox" id="ctxOnly"> tylko z kontekstem</label>
  <span style="color:#8A8F98">strzałki ← → też działają</span>
</div>
"""

_NAV_JS = """
var D = __DATA__;
var gd = document.getElementById('chart');
var pos = -1;
function list() {
  var only = document.getElementById('ctxOnly').checked;
  var out = [];
  for (var k = 0; k < D.hits.length; k++) if (!only || D.ctx[k]) out.push(k);
  return out;
}
function show(step) {
  var L = list();
  var info = document.getElementById('info');
  if (!L.length) { info.textContent = 'brak formacji'; return; }
  pos = Math.min(Math.max(pos + step, 0), L.length - 1);
  var k = L[pos], i = D.hits[k];
  var a = i - D.before, b = i + D.after;
  var lo = Infinity, hi = -Infinity;
  for (var t = Math.max(a, 0); t <= Math.min(b, D.high.length - 1); t++) {
    lo = Math.min(lo, D.low[t]); hi = Math.max(hi, D.high[t]);
  }
  var pad = (hi - lo) * 0.08;
  Plotly.relayout(gd, {'xaxis.range': [a, b], 'yaxis.range': [lo - pad, hi + pad]});
  info.textContent = (pos + 1) + ' / ' + L.length + '  ·  ' + D.dates[k] +
                     (D.ctx[k] ? '  ·  w kontekście' : '  ·  bez kontekstu');
}
document.getElementById('prev').onclick = function () { show(-1); };
document.getElementById('next').onclick = function () { show(1); };
document.getElementById('ctxOnly').onchange = function () { pos = 0; show(0); };
document.addEventListener('keydown', function (e) {
  if (e.key === 'ArrowRight') show(1);
  if (e.key === 'ArrowLeft') show(-1);
});
show(1);
"""


# ============================================================
# START
# ============================================================

def main(bars: pd.DataFrame | None = None):
    global KOLORY_JAK_NA_PLANSZY, OUTPUT_DIR
    if "--plansza" in sys.argv:
        KOLORY_JAK_NA_PLANSZY = True
    if KOLORY_JAK_NA_PLANSZY and not OUTPUT_DIR.name.endswith("_plansza"):
        OUTPUT_DIR = OUTPUT_DIR.with_name(OUTPUT_DIR.name + "_plansza")
    print("Wersja:", "kolory jak na planszy" if KOLORY_JAK_NA_PLANSZY else "podręcznikowa")
    if bars is None:
        print(f"Wczytywanie {ASSET} {TIMEFRAME} {START_DATE} – {END_DATE} ...")
        bars = load_bars()
    atr = atr_rma(bars, 14)
    signals = detect_patterns(bars, atr, plansza=KOLORY_JAK_NA_PLANSZY)
    context = context_mask(bars, SMA_CONTEXT)
    sma = bars["close"].rolling(SMA_CONTEXT).mean().to_numpy()

    out = OUTPUT_DIR / f"{ASSET.replace(' ', '_')}_{TIMEFRAME}"
    out.mkdir(parents=True, exist_ok=True)
    for k, name in enumerate(PATTERNS, start=1):
        file = out / f"{k:02d}_{name.replace(' ', '_')}.html"
        n = save_pattern_html(bars, name, signals[name], context[name], sma, file)
        print(f"  {name:22s} {n:5d} wykryć -> {file.name}")
    print(f"Zapisano w {out}")


if __name__ == "__main__":
    main()
