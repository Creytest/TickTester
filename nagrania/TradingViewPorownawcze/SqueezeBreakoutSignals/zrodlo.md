- **Autor:** bitpunk (MPL-2.0)
- **Typ:** `indicator()`, kompresja BB/KC (2×odch. std. zamknięć < 1,5×średni TR z 20 świec) → pudełko → wybicie zamknięciem i retest krawędzi. Daje wejścia ▲/▼ (BREAKOUT / RETEST), bez SL, TP i wyjścia („does not manage exits”)
- **Link:** https://www.tradingview.com/script/Ah51TSsn/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-04 w wątku „Przetestować Squeeze Breakout Signals” (pierwsza wiadomość)
- **Timeframe autora:** nie podaje (tylko „Use standard time-based candles”)
- **Aktywa autora:** nie podaje

**Dokładny opis (fragmenty):**

> Squeeze Breakout draws a range around compressed price action, then marks its first close breakout and a later retest. You can follow the breakout or wait for price to return to the broken edge.

> Each range allows one breakout and one later retest entry, both in the first breakout's direction. An opposite break does not start a new entry on that box. The default watch is 20 bars, including the locking bar; a return does not restart it. A close at or through the opposite edge cancels a pending retest.

> Breakouts and retests can fail. The script marks entries for chart analysis and does not manage exits.

**Reguły z kodu (domyślne):**

1. Kompresja: 2 × stdev(close, 20, biased) < 1,5 × SMA(TR, 20). Wszystko na zamkniętych świecach.
2. Pudełko = high/low serii skompresowanych świec (max 20 ostatnich). Gotowe po 3 skompresowanych zamknięciach. Nowy epizod wymaga 3 nieskompresowanych zamknięć.
3. Zablokowanie: pierwsze zamknięcie poza pudełkiem w trakcie kompresji albo koniec kompresji. Krawędzie i średni TR (z poprzedniej świecy) zamrożone. Okno obserwacji: 20 świec łącznie ze świecą blokady.
4. BREAKOUT: pierwsze zamknięcie nad górną (long) / pod dolną (short) krawędzią. Kierunek pierwszego wybicia = jedyny kierunek wejść z tego pudełka.
5. RETEST: najpierw cała świeca poza strefą krawędź ± 0,25 średniego TR, potem świeca dotyka strefy i zamknięcie za krawędzią (na tej lub późniejszej świecy). Filtr „Retest Close Progress”: zamknięcie retestu musi być wyżej (long) / niżej (short) niż poprzednie. Zamknięcie na/za przeciwną krawędzią kasuje oczekujący retest.
6. Max Entry Extension = 0 (bez limitu odległości od krawędzi).

**Status (2026-11-04):** Kamil wybrał wariant A. PR #60: `SqueezeBreakoutSignals.py` (port 1:1 + wejście na ▲/▼ autora, SL = przeciwna krawędź pudełka, TP = krawędź + 1× wysokość pudełka, 1% ryzyka, jedna pozycja naraz; SL/TP to nasze założenie), `SqueezeBreakoutSignals_Control.py` (losowe momenty, te same odległości SL/TP w średnim TR), preset w compare_control.py. 15m/1h/4h.
