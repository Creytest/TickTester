- **Autor:** Forex City Pro (FCP)
- **Typ:** `indicator()`, rysuje tylko strefy (boxy), bez sygnałów, SL/TP i raportu wyników
- **Link:** https://www.tradingview.com/script/MVfnGVle-FCP-Key-Level-Zones-Pivots-Daily-Weekly-Monthly-High-Low/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-03 w wątku „Przetestować Key Level Zones” (pierwsza wiadomość)
- **Timeframe autora:** nie podaje konkretnego; „Intraday and swing traders who plan around daily and weekly key levels”. Strefy identyczne na każdym interwale ≤ D (tolerancja z ATR 4h)
- **Aktywa autora:** nie podaje (wspomina tylko, że na futures pivoty TV mogą różnić się przez settlement)

**Dokładny opis (fragmenty):**

> At the start of every period it compares each previous high/low level with each pivot level and draws a zone only where the two sit close together. Lone levels are never drawn.

> A zone marks a price area where two different methods agree. It is a place to pay attention to, not a signal to buy or sell

> Zones show where levels cluster. They do not predict whether price will react there.

**Reguły z kodu (domyślne):** poziomy HL = high/low/mid poprzedniego dnia, tygodnia, miesiąca. Pivoty Traditional D/W/M: P, R1–R3, S1–S3 (z poprzedniego okresu). Para HL–pivot w odległości ≤ 0,5 × ATR(14) z 4h (ostatnia zamknięta świeca 4h) → kandydat na strefę [min, max]. Nakładające się kandydaty łączone. Kolor = liczba poziomów w strefie (2 / 3 / 4+). Rysunek przycinany do 0,1 × ATR wokół środka (liczba poziomów bez zmian). Strefy przeliczane na każdej zmianie dnia/tygodnia/miesiąca, ważne do końca najkrótszego okresu. Bez repaintu.

**Status (2026-11-03):** brak reguł wejścia/wyjścia → Kamil wybrał event study zamiast backtestu. Kod: `strategies/tradingview/KeyLevelZones.py` + `event_study_key_levels.py`. Zdarzenie = pierwsze dotknięcie strefy w dniu (1 min, Bid); odbicie = 1 × ATR(4h) od krawędzi w stronę, z której cena przyszła, zanim 1 × ATR przebicia; horyzont 5 dni. Kontrola: pojedyncze poziomy odrzucone przez wskaźnik i losowe poziomy (ta sama wysokość i odległość od otwarcia dnia). Interwał wykresu nie ma znaczenia (strefy identyczne na 15m/1h/4h).

**2026-11-04 (Kamil: „tak jak Auto Levels”), PR #55:** strategia `KeyLevelZones` (NASZE założenia: 1. dotknięcie strefy w dniu → wejście w stronę odbicia na zamknięciu świecy dotknięcia, wyjście po 10 świecach, bez SL/TP, 100% kapitału, MIN_LEVELS = 2) + `KeyLevelZones_Control` (losowe momenty, te same liczby/kierunki/czas) + `compare_control.py` z ACTIVE = "KeyLevelZones". 15m/1h/4h.
