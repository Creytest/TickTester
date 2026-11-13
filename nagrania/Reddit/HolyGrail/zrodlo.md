- **Wątek:** „What is your favorite stupidly simple strategy?” (r/Daytrading)
- **Autor:** wątek usunięty (strategia pochodzi z treści samego wątku)
- **Link:** https://www.reddit.com/r/Daytrading/comments/1ffhuo4/

**Dokładny post:**

> I recently read about Linda Raschke's "Holy Grail". You simply wait for ADX to be above 30 and rising, then buy or sell on a pullback to the 20 EMA. It reminds me a lot of PATs, since they primarily buy on pullbacks too.
>
> What's your favorite simple strategy?

**Pierwotne źródło reguł:** Laurence Connors, Linda Bradford Raschke, „Street Smarts” (1995), rozdział 10 „The Holy Grail” (zrzuty od Kamila):

> FOR BUYS (SELLS ARE REVERSED)
> 1. A 14-period ADX must initially be greater than 30 and rising. This will identify a strongly trending market.
> 2. Look for a retracement in price to the 20-period exponential moving average. Usually the price retracement will be accompanied by a turndown in the ADX.
> 3. When the price touches the 20-period exponential moving average, put a buy stop above the high of the previous bar.
> 4. Once filled, enter a protective sell stop at the newly formed swing low. Trail the stop as profits accrue and look to exit at the most recent swing high. If you think the market may continue its move, you might exit part of the position at the most recent swing high and tighten stops on the balance.
> 5. If stopped out, re-enter this trade by placing a new buy stop at the original entry price.
> 6. After a successful trade, the ADX must once again turn up above 30 before another retracement to the moving average can be traded.

**Nasze założenia (`strategies/reddit/HolyGrail.py`, PR #37):** kierunek z zamknięcia względem EMA 20. Zlecenie stop przesuwane co świecę na high ostatniej świecy; zamknięcie pod dołkiem cofnięcia kasuje setup. SL dołek cofnięcia, TP szczyt przed cofnięciem, bez trailingu i częściowego wyjścia. 1% ryzyka, 15m/1h/4h + 1D (książka: dzienne).
