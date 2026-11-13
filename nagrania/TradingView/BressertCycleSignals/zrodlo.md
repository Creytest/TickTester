- **Autor:** BY_Tse (licencja MPL 2.0)
- **Typ:** `indicator()`, nie `strategy()`: skrypt nie raportuje wyników, sam autor pisze, że pozycja jest hipotetyczna
- **Link:** https://pl.tradingview.com/script/ARm00iF4-Bressert-Cycle-Signals/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-03 w wątku „Testować strategie z TradingView” (pierwsza wiadomość)
- **Interwał autora:** D1 z trendem z W1 („The script is designed for daily charts”); intraday dopuszcza, ale ustawienia cyklu trzeba dopasować
- **Aktywa autora:** nie podaje konkretnych; „runs on any symbol class” (OHLC + mintick, bez wolumenu)

**Dokładny opis (fragmenty):**

> The method's thesis is that a trading-cycle turn should be traded when three things line up: the time since the last turn says a new one is due, an oscillator turns from an extreme, and the next longer cycle points the same way, with entry deferred until price trades through the turning bar.

> For a buy, the oscillator drops below its buy line and turns up. The bar that turns it up is the setup bar. A buy stop one tick above that bar's high is the entry, and the protective stop goes one tick below the cycle low. Sells mirror this. His software defaults were a Double Stochastic length of 10, about half the trading cycle, a buy line of 40, a sell line of 70 and a 4-bar window for the entry. He took signals in the direction of the next longer cycle or at trend reversals, and read the weekly Double Stochastic's direction as the trend for daily charts. Near an oscillator extreme he trailed a 2-bar reversal stop.

> Bressert never published the Double Stochastic's arithmetic. [...] so the version in this script is a reconstruction.

**Reguły z kodu (ustawienia domyślne):**

1. Oscylator: Double Stochastic(10) (rekonstrukcja autora skryptu), linie 40 / 70.
2. Setup long: oscylator spadał, jego dołek był poniżej 40, świeca zamyka się z oscylatorem wyżej niż poprzednio (próg skrętu 0). Short lustrzanie: szczyt powyżej 70 i skręt w dół.
3. Filtr trendu: kierunek Double Stochastic(10) na wyższym interwale z ostatniej zamkniętej świecy HTF (auto: D→W, intraday ×4). Long dozwolony przy trendzie 0/+1, short przy 0/−1.
4. Wejście: buy stop = high świecy setupu + 1 tick, ważny przez 4 kolejne świece; nowszy setup zastępuje stary. Short: sell stop = low − 1 tick.
5. SL początkowy: 1 tick pod najniższym low od świecy przed początkiem spadku oscylatora do świecy wejścia (short lustrzanie). Nie testowany na świecy wejścia.
6. Trailing: gdy w longu oscylator dojdzie do 70 (w shorcie do 40), SL na każdym zamknięciu podciągany na 1 tick pod najniższe low z 2 ostatnich świec (tylko w stronę zysku).
7. Przeciwny trigger odwraca pozycję. Trigger w tę samą stronę nic nie zmienia. Oba triggery na jednej świecy → brak wejścia.
8. Brak TP. Pasma czasowe (timing bands) przy domyślnym „Signal band filter = Off” NIE wpływają na sygnały, są tylko rysunkiem.

**Nasze założenia (propozycja, 2026-11-03):** port do TickTestera (`strategies/tradingview/`), 1% ryzyka od SL, reverse, koszty jak zawsze. Interwały: 15m/1h/4h (nasz standard, autor ich nie projektował) + 1D z trendem W jako wariant autorski. Przy 4h auto-HTF daje 16h — do decyzji.
