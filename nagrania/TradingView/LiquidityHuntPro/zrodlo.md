- **Autor:** Viprasol (licencja MPL 2.0)
- **Typ:** `indicator()`, bez raportu wyników; sygnały BUY / SELL z pełnym planem: wejście, SL, TP1/TP2/TP3. Autor: „The indicator does not place or manage trades”, „makes no performance or win-rate claims”
- **Link:** https://www.tradingview.com/script/CDQo43CF-Liquidity-Hunt-Pro-Viprasol/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-03 w wątku „Przetestować Liquidity Hunt Pro” (pierwsza wiadomość)
- **Timeframe autora:** 1m–1D; ustawienia domyślne zalecane dla intraday 15m–1H („Intraday (15m-1H): defaults”). Scalping 1–5m: Swing Length 3–5, Max Bars After Sweep 6–8. Swing 4H–1D: Swing Length 8–10, Max Bars 12–15, filtr EMA włączony
- **Aktywa autora:** „liquid forex pairs, indices, metals, crypto or stocks” (bez konkretnych symboli)

**Dokładny opis (fragmenty):**

> When price wicks through the latest swing high or low and closes back inside it, the indicator waits a few bars for a strong close beyond the opposite swing. If that close comes, it prints BUY or SELL with an entry, a stop at the sweep extreme and three risk-multiple targets.

> entry = signal close / stop = sweep candle low (BUY) or high (SELL) / TP1 / TP2 / TP3 = entry +/- risk x 1 / 2 / 3

> A bar that touches both the stop and a target counts as the stop.

**Reguły z kodu (domyślne):**

1. Swing high / low: pivot 5 świec w lewo i 5 w prawo (znany 5 świec później). Buy-side liquidity = ostatni swing high, sell-side = ostatni swing low.
2. Sweep sell-side: low świecy pod swing low, zamknięcie z powrotem nad nim. Liczy się też poziom już wcześniej przebity zamknięciem („Ignore Sweeps of Broken Levels” = off). Buy-side lustrzanie.
3. Sweep sell-side uzbraja BUY: SL = low świecy sweepu, poziom MSS = swing high z chwili sweepu. Sweep po drugiej stronie kasuje setup, nowy sweep po tej samej stronie go restartuje (nowy SL i poziom).
4. BUY na pierwszej zamkniętej świecy w ciągu 10 świec po sweepie, która: zamyka się nad poziomem MSS, poprzednie zamknięcie było ≤ poziomu (fresh shift), jest wzrostowa z korpusem ≥ 0,15 × ATR(14), zamknięcie > SL o więcej niż 1 tick, minęło > 10 świec od poprzedniego sygnału (w dowolną stronę). Filtr EMA 50/200 domyślnie WYŁĄCZONY. SELL lustrzanie.
5. Wejście = zamknięcie świecy sygnału. Ryzyko = |wejście − SL|, TP1/2/3 = 1×/2×/3× ryzyko. SL stoi w miejscu (bez przesuwania na BE po TP1). Śledzenie kończy SL albo TP3.
6. Nowy sygnał zastępuje plan poprzedniego, także przy otwartym „trade’ie”.
7. BOS/CHoCH, Order Blocki, FVG i dashboard to tylko rysunek: NIE wpływają na sygnały.

**Nasze założenia (2026-11-03, PR #50):** po 1/3 na TP1, TP2, TP3, reszta na SL bez przesuwania; 1% ryzyka. Wejście na pierwszym ticku po zamknięciu świecy sygnału. Świecę z SL i TP rozstrzygają ticki. Nowy sygnał: przeciwny → odwrócenie, w tę samą stronę → zamknięcie starej pozycji i nowe wejście. Interwały 1m/15m/1h/4h/1D (prośba Kamila) z ustawieniami autora: 1m Swing 4 / Max Bars 7; 15m–1h domyślne 5 / 10; 4h–1D Swing 9 / Max Bars 13 + filtr EMA 50/200 (środek zakresów autora). Plansza: plansze_liquidity_hunt/liquidity_hunt_plansza.png.
