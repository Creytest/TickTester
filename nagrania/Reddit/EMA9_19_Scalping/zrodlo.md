- **Post:** „I’m Getting a Lot of Questions About My Strategy – Here’s the Breakdown (Not Selling Anything)” (r/Daytrading)
- **Autor:** konto usunięte
- **Link:** https://www.reddit.com/r/Daytrading/comments/1ln0lpm/

**Dokładny post (reguły):**

> Timeframe: 1-minute chart Indicators: Two Exponential Moving Averages: 9 EMA, 19 EMA
>
> 1. Identify the Trend
> * If price is consistently above both EMAs, I’m only looking for longs.
> * If price is below both EMAs, I’m only looking for shorts.
>
> 2. Entry Setup - The Retest
> * Wait for a clean retest of the 9 EMA in the direction of the trend. Only take an entry if the candle touches or dips slightly below the 9 EMA.
>
> 3. Stop-Loss
> * Place it just below the 19 EMA (for longs) or just above it (for shorts).
> * The stop needs to be tight. If it’s too wide, skip the trade, that means the entry wasn’t perfect.
>
> 4. Take-Profit
> * Target the most recent high or low, or use a 1:2 to 1:3 RRR (Risk-Reward Ratio).
>
> Does It Work on Every Market? Yes. I’ve tested this strategy across multiple forex pairs, indices, and even crypto, and it seems to work across the board. […] However, I personally only trade NQ on the 1-minute chart.
>
> No perfect entry = no trade. […] If you don’t get the perfect pullback to the 9 EMA (or slightly below it for longs / above it for shorts), skip the trade.

**Dopowiedzenia autora w komentarzach:**

> I don’t wait for candle closure, if it touches with the right momentum, i enter right away.
> My SL is usually 5 to 15 points depending on the market volatility.
> Once the price gives me 1 RRR i move SL to BE.
> I only trade the first 30 minutes of the NY open. Usually i finish within the first 15 minutes. But it does work in all sessions at all times
> No all my trades are market order.
> Last week i took 13 trades, 10 wins, 1 BE, 2 losses.

**Claim:** „works across the board” (FX, indeksy, krypto), „high-probability”, w komentarzu 10/13 wygranych w tygodniu. Autor przyznaje: „I’m not saying I’m consistently profitable yet”. Komentujący (ApprehensiveDot1121) zarzuca, że transakcje na zrzutach nie trzymają się podanych reguł (hindsight bias), a inny pisze, że jego backtest w Pythonie na BTC „bust within 6m”.

**Ocena:** ~70% reguł od autora (interwał, EMA 9/19, kierunek trendu, wejście na dotyku EMA 9 bez czekania na zamknięcie, SL za EMA 19, TP 1:2–1:3, BE przy 1:1, pierwsze 30 min NY, NQ). Do ustalenia przez nas: „consistently above” (ile świec), „just below” EMA 19 (bufor), próg „too wide” (autor: 5–15 pkt NQ), filtr „momentum” (uznaniowy — pomijamy). Wejście w trakcie świecy wymaga zlecenia na dotyku EMA 9 (silnik ma tylko wejście po zamknięciu albo stop). Rynek: NQ — mamy US500 (od 2020) i USA 100 tylko 2011–2014.

**Nasze założenia (2026-11-07):** trend = 3 ostatnie zamknięcia nad obiema EMA (short: pod), EMA 9 > EMA 19. Zlecenie na dotyk EMA 9 w następnej świecy (poziom = EMA 9 z zamknięcia — dokładnie tam żywa EMA równa się cenie), wejście rynkowe na pierwszym ticku dotyku. SL = EMA 19 w chwili dotyku ∓ 0,1 × ATR(14); SL > 1,5 × ATR(14) → brak transakcji. TP 2:1, SL na cenę wejścia po 1:1. Tylko 9:30–10:00 NY (16:30–17:00 w danych); wariant SESSION_ONLY = False — cała doba (autor: „works in all sessions”). Filtr momentum pominięty. Silnik: nowe kolumny entry_touch i break_even (PR).
