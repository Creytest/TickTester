- **Autor:** BigBeluga (licencja CC BY-NC-SA 4.0: uznanie autorstwa, bez użytku komercyjnego, przeróbki na tej samej licencji)
- **Typ:** `indicator()`, bez SL/TP i bez raportu wyników
- **Link:** https://pl.tradingview.com/script/mFMTYEYR-Market-Structure-Oscillator-BigBeluga/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-03 w wątku „Przetestować Market Structure Oscillator” (pierwsza wiadomość)
- **Timeframe autora:** nie podaje
- **Aktywa autora:** nie podaje

**Dokładny opis (fragmenty):**

> Market Structure Oscillator [BigBeluga] is a dual-purpose tool that tracks market structure breaks (CHoCH & BoS) on the price chart while calculating a trend-filtered momentum oscillator in a separate pane. [...] keeping momentum values strictly above 50 during an uptrend and below 50 during a downtrend.

> 1. Trade Structural Breaks: Use the CHoCH and BoS lines as entry triggers, entering in the direction of the break.
> 2. Anticipate Reversals: Look for "Div" markers on the price chart when the trend is extended.

**Reguły z kodu (domyślne):**

1. Swing high / swing low: pivot 5 świec w lewo i 5 w prawo (potwierdzony 5 świec po szczycie/dołku).
2. Zamknięcie przebija ostatni swing high → trend wzrostowy (pierwsze wybicie = CHoCH, kolejne = BoS). Zamknięcie pod ostatnim swing low → trend spadkowy. Przebity poziom znika do następnego pivota.
3. Oscylator: zmiana ceny z 14 świec / odchylenie standardowe zmian z 14 świec → sigmoid 0–100 → EMA 10. Histogram dostaje tylko znak od struktury (nad 50 w trendzie wzrostowym, pod 50 w spadkowym). Linia wygładzona i dywergencje NIE są filtrowane i NIE wpływają na trend.
4. Brak SL, TP i reguł wyjścia.

**Nasze założenia (2026-11-03, PR #48):** zawsze w rynku: wybicie w górę → long, wybicie w dół → odwrócenie na short; kolejne BoS w tę samą stronę nic nie zmieniają. Bez SL → 100% kapitału z kapitalizacją. Dywergencje pominięte (autor nie podaje, jak z nich wchodzić). 15m/1h/4h, koszty jak zawsze.
