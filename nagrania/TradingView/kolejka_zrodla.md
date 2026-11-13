# TradingView — w kolejce (jeszcze bez kodu)

- **Autor:** Uncle_the_shooter (licencja MPL 2.0)
- **Typ:** `indicator()`, bez sygnałów, SL, TP i raportu wyników
- **Link:** https://pl.tradingview.com/script/ERScIMjp/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-03 w wątku „Przetestować Confluence Profile” (pierwsza wiadomość)
- **Timeframe autora:** nie podaje (ATR ma działać „on any market and timeframe”)
- **Aktywa autora:** nie podaje (bez wolumenu kolumny V1–V3/Vext są puste)

**Dokładny opis (fragmenty):**

> Confluence Profile is a tool for finding places where several independent technical factors point to a similar price level. It does not give buy or sell signals.

> When several of these zones fall in the same place, it is likely that more orders sit there, so the price reaction may be more pronounced. This is not a rule, however.

> High confluence does not mean that price will react at that level [...] The profile reflects the current state and is recalculated on the last candle. The indicator does not draw a history of the profile.

**Co liczy (domyślne):** 3 trailing swingi (pivot 10/30/80) → Fibo 0; 0,382; 0,5; 0,618; 0,786; 1; 1,272. Order Blocki (pivot 12), FVG (min. 0,25 ATR, tryb Shrink), profile wolumenu V1–V3 w trybie Nodes + Vext (aktywny, bo poziom 1,272 jest domyślnie włączony). Tolerancja 0,15 × ATR(100). Confluence = suma wag (domyślnie 1) trafień w danym przedziale ceny. Wszystko na zamkniętych świecach, ale profil rysowany tylko na ostatniej świecy.

**Status (2026-11-03):** brak reguł wejścia/wyjścia → nie da się zrobić backtestu 1:1. Jedyna uczciwa opcja: test twierdzenia „przy wysokim confluence reakcja ceny jest mocniejsza” (event study, bez transakcji). Czeka na decyzję Kamila.


- **Autor:** RedKTrader (licencja MPL 2.0)
- **Typ:** `indicator()`, bez SL, TP, reguł wyjścia i raportu wyników; 6 alertów (przecięcie zera, Control Levels ±70)
- **Link:** https://pl.tradingview.com/script/lygT3bP0-RedK-DualTF-Volume-Accelerated-CCI-RedK-VA-CCI/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-03 w wątku „Przetestować RedK VA-CCI” (pierwsza wiadomość)
- **Timeframe autora:** nie podaje (Context TF = interwał wykresu × mnożnik, przykład „5 on a 1H chart = 5H” to tylko przykład działania)
- **Aktywa autora:** nie podaje („today it is used on all kinds of instruments” dotyczy klasycznego CCI); bez wolumenu wskaźnik przechodzi na samą cenę

**Dokładny opis (fragmenty):**

> RedK VA-CCI with volume weighting and dual TF capabilities can deliver improved insight on TA elements like divergence with price, timeframe alignment, and other valuable signals [...]

> Volume weighting: each bar is weighted by its volume - both in the average and in the deviation around it - so moves that happen on higher participation carry more weight. This setting is on by default.

> This is an insight tool, not a signal service. The markers and alerts describe price and volume readings. They are not advice to enter or exit any position, and the indicator does not claim predictive accuracy.

**Co liczy (domyślne):** CCI(10) z HLC3, stała 0,015. Średnia = VWAP z 10 świec (wolumen jako waga), odchylenie średnie też ważone wolumenem. Potem wygładzenie WMA(3). Linia sygnałowa EMA(5) (bez alertu). Stochastic Mode, Context TF i soft cap domyślnie WYŁĄCZONE. Alerty liczone z wygładzonej linii głównej: przecięcie 0 oraz +70 / −70.

**Ocena (2026-11-03, propozycja):** autor nie składa obietnicy zysku, jedyne twierdzenie to „ważenie wolumenem daje lepszy wgląd”. Uczciwy test = A/B: ta sama reguła na VA-CCI (wolumen ON) i na klasycznym CCI (wolumen OFF, bez wygładzenia, 20/HLC3). Nasze założenia: przecięcie 0 w górę → long, w dół → odwrócenie na short, zawsze w rynku, bez SL → 100% kapitału z kapitalizacją, wejście na otwarciu kolejnej świecy, 15m/1h/4h. Control Levels ±70 pominięte: autor nie mówi, czy to kontynuacja, czy odwrócenie, ani gdzie wyjść. Wolumen w TickTesterze = liczba ticków Dukascopy (na TV zależy od brokera), więc sygnały mogą się różnić od TV.

**Status (2026-11-03):** pominięty, decyzja Kamila. Bez backtestu.


- **Autor:** GBB
- **Typ:** `indicator()`, zigzag na ATR (swing kończy się po cofnięciu k × ATR(14) od ekstremum) + prawdopodobieństwa liczone z historii swingów na tym samym wykresie. Bez wejść, SL i TP
- **Link:** https://www.tradingview.com/script/XsxfReug-Swing-Clock-GBB/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-04 w wątku „Przetestować Swing Clock” (pierwsza wiadomość)
- **Timeframe autora:** nie podaje. Działa na każdym; tylko horyzont N zależy od TF (5 na 1m, 3 na 2m–15m, 2 na 30m+). Komentarz w kodzie wspomina weryfikację na ES 1m
- **Aktywa autora:** nie podaje (przykładowy poziom 7 582,00 wygląda na S&P 500 / ES)

**Dokładny opis (fragmenty):**

> Swing Clock gives you that missing information as odds. It shows how likely it is that the current swing's high or low is already in, how likely price is to reach the levels beyond it, and roughly when swings like this one tend to end.

> Use the level odds to judge whether a target is realistic. A 30% level is missed about twice as often as it is hit.

> Combine it with your own setup and risk management. Swing Clock tells you where the odds stand, not what to trade.

**Reguły z kodu (domyślne, Standard, Wicks):**

1. ATR(14) = RMA z TR (start SMA), minimum 2 mintick. Swing kończy się, gdy cena cofnie się ≥ 2,5 × ATR (ATR z chwili ekstremum) od ekstremum. Pierwsze 2 swingi odrzucone. Prognozy „gotowe” po 30 swingach w każdym kierunku.
2. Stan na każdej świecy: kierunek, głębokość cofnięcia rho = (ekstremum − close)/(k × ATR) w 5 przedziałach, wiek od ekstremum (0 / 1–2 / 3–5 / 6+ świec), wielkość swingu w k×ATR (<1,5 / <2,5 / <4 / 4+). 160 komórek.
3. Top/Bottom in = rho + średni błąd (wynik − rho) w komórce, ściągany (M = 80) do marginesu kierunek×rho, a ten do 0. Turn ≤N i Conf ≤N: częstości w komórce ściągane do marginesu i kierunku.
4. Poziomy 50/75/90%: kwantyle końcowej wielkości swingów, które doszły tak daleko (empiryczny rozkład mieszany z wykładniczym, waga n/(n+25), łączenie kierunków przy < 10 swingach). Szansa dotarcia = (1 − Top in) × P(wielkość ≥ poziom).
5. Okno czasowe: kwantyle 25–75% długości porównywalnych swingów, ustalane na starcie swingu. OVERDUE po jego końcu. „Likely in” gdy Top in ≥ 50%.
6. Liczone tylko na zamkniętych świecach, wyłącznie z już zamkniętych swingów → bez repaintu i bez zaglądania w przyszłość.

**Status (2026-11-04):** propozycja: test kalibracji (czy „X%” zdarza się w X% przypadków) + porównanie z prostą bazą (samo rho), na 15m/1h/4h. Opcjonalnie strategia na sygnale „TOP/BOTTOM LIKELY IN” + `_Control`. Kamil (2026-11-04): na razie nie robimy, odłożone.


- **Autor:** nie podany we wklejonym tekście; w kodzie nazwa „Value Trend Strategy” (VTS). Licencja nie podana we wklejonym kodzie
- **Typ:** `strategy()` z pełnymi regułami: wejście (retest krawędzi value area z poprzedniego tygodnia), SL = 1,5 × ATR, TP = 2 × odległość SL, wyjście przy odwróceniu trendu. Da się testować 1:1, bez grupy kontrolnej
- **Link:** https://www.tradingview.com/script/PGMAHksx-Aurora-Value-Trend-Value-Area-Retest-Strategy/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-05 w wątku „Przetestować Aurora Value Trend” (pierwsza wiadomość)
- **Timeframe autora:** 15m–4h („Use an intraday chart (15m to 4h)”)
- **Aktywa autora:** bez symboli, „liquid, volume-reporting markets”; ostrzega: „Instruments with no or unreliable volume data will produce meaningless value areas”
- **Ustawienia autora w backteście:** 100 000 kapitału, 10% kapitału na transakcję, prowizja 0,05%, 2 ticki poślizgu (my: 10 000 USD, 1% ryzyka przy SL, 1 tick, koszty TickTestera)

**Dokładny opis (fragmenty):**

> Aurora Value Trend trades retests of last week's value area, but only in the direction of the prevailing trend and only when momentum agrees.

> Long: the trend is up, flow is bullish, and price dips back to VAH and closes above it on a green candle. Short: the trend is down, flow is bearish, and price pokes up to VAL and closes below it on a red candle.

> Exit: an ATR-based stop and an R-multiple target, or an early exit if the trend flips against the position.

> Test different stop and target pairs on your own market. The defaults are starting points, not optimised values.

**Reguły z kodu (domyślne):**

1. Profil wolumenu poprzedniego tygodnia: 48 wierszy, wolumen świecy rozkładany proporcjonalnie do zakresu. POC = najcięższy wiersz, value area = 70% wolumenu (rozszerzana od POC w stronę większego sąsiada). VAH/VAL obowiązują przez cały następny tydzień.
2. Filtr bilateralny z 40 zamknięć: waga exp(−i²/200) × exp(−((close[i] − mediana 3 zamknięć) / (1,5 × ATR14))² / 2).
3. Trend odwraca się, gdy filtr cofnie się o 1,0 × 1,5 × ATR od szczytu (w dół) albo dołka (w górę).
4. Flow (hue) = 0,65 × EMA3((close − EMA9)/ATR) / 1,5 + 0,35 × EMA5((close − EMA34)/ATR) / 2,5, obcięte do ±1. Long wymaga hue > 0, short hue < 0.
5. LONG: trend w górę, low ≤ VAH + 0,25 × ATR, close > VAH, świeca wzrostowa. SHORT lustrzanie przy VAL. Przeciwny sygnał odwraca pozycję.
6. SL/TP od zamknięcia świecy sygnału, wejście na otwarciu następnej. Wyjście wcześniej, gdy trend zmieni się przeciw pozycji.
7. Aurora, gradient, kolory świec i panel to tylko rysunek.

**Uwagi:** wolumen w TickTesterze = liczba ticków (na FX/złocie/ropie/indeksach CFD TV też ma tylko wolumen tickowy; na BTC z giełdy prawdziwy). Granica tygodnia = poniedziałek 00:00 czasu danych Tickstory (GMT+2 z US DST = niedziela 17:00 NY, jak tydzień FX/CFD w TV); na BTC w TV tydzień od poniedziałku 00:00 UTC (opcja WEEK_START_OFFSET_HOURS). Autor sam ostrzega przed małą liczbą transakcji.

**Status (2026-11-05):** port `strategies/tradingview/AuroraValueTrend.py` gotowy lokalnie, 15m/1h/4h, koszyk standardowy. Czeka na zgodę Kamila na push/PR.
