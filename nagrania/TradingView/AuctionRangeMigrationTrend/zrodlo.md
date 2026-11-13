- **Autor:** SchizoQuant (licencja MPL 2.0)
- **Typ:** `indicator()`, bez SL, TP, reguł wyjścia i raportu wyników; sygnały LONG / SHORT (trójkąty + alerty) przy zmianie stanu trendu
- **Link:** https://www.tradingview.com/script/QTeLijEz-Auction-Range-Migration-Trend-SchizoQuant/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-03 w wątku „Przetestować Auction Range Migration Trend” (pierwsza wiadomość)
- **Timeframe autora:** nie podaje
- **Aktywa autora:** nie podaje (liczy tylko z OHLC, bez wolumenu: „evaluates candle-range behavior rather than actual order-book activity, traded volume, or exchange auction data”)

**Dokładny opis (fragmenty):**

> Auction Range Migration Trend is an adaptive trend-following indicator designed to identify directional market movement by analyzing how consecutive candle ranges migrate, overlap, and establish new price territory.

> LONG: The trend score exceeds the positive adaptive threshold while the active regime is bearish. SHORT: The trend score falls below the negative adaptive threshold while the active regime is bullish. Signals are generated only after confirmed candle closes.

> It is reactive rather than predictive. Sideways markets can produce repeated regime changes, while stronger smoothing and congestion protection may delay reversal signals.

**Reguły z kodu (domyślne):**

1. Ruch środka świecy (high+low)/2 i ruch zamknięcia względem poprzedniej świecy, oba podzielone przez ATR(14), wagi 0,35 / 0,65.
2. Mnożnik za rozszerzenie zakresu: 1 + 0,5 × (1 − overlap z poprzednią świecą). Premia „nowe terytorium”: zamknięcie nad poprzednim high (+) lub pod poprzednim low (−), w ATR, max 1, waga 0,45. Wynik obcięty do ±2 ATR.
3. Trend score = 0,6 × EMA(20) z tego wyniku + 0,4 × EMA(13) z głosów (+1 gdy wynik > 0,03, −1 gdy < −0,03, inaczej 0).
4. Próg odwrócenia = 0,19 + 0,25 × zatłoczenie, gdzie zatłoczenie = max(0, (EMA(2) overlapu − 0,30) / 0,70).
5. Stan początkowy = znak trend score, bez sygnału. LONG, gdy stan spadkowy i score > próg; SHORT, gdy stan wzrostowy i score < −próg. Tylko na zamkniętych świecach, więc sygnały są naprzemienne.
6. „Auction Migration Path” to tylko rysunek, nie wpływa na sygnały.

**Nasze założenia (propozycja, 2026-11-03):** zawsze w rynku: LONG → long, SHORT → odwrócenie na short (reverse). Wejście na otwarciu kolejnej świecy. Pierwsza pozycja dopiero od pierwszego trójkąta (stan początkowy nie otwiera transakcji). Bez SL → 100% kapitału z kapitalizacją. 15m/1h/4h, koszty jak zawsze. Port: `strategies/tradingview/AuctionRangeMigrationTrend.py` (PR #49).
