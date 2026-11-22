- **Wątek:** „Crazy simple strategies” (r/Daytrading)
- **Autor strategii (komentarz):** u/The-Goat-Trader
- **Link:** https://www.reddit.com/r/Daytrading/comments/1npv2p3/crazy_simple_strategies/ (komentarz ng30so8)

**Dokładny komentarz:**

> One of my trades is pullback between two moving averages. The actual averages vary between asset and timeframe, but the basic setup is the same: fast EMA and slow SMA of about double the EMA period. So like EMA(10) and SMA(20).
>
> 1. Price > ema > sma
> 2. ema & sma are both trending up (or flat)
> 3. Price closes between them — buy
> 4. Sell when price is above ema and closes higher than previous high
>
> Yeah, there's some rules around stops and a couple of other little price action things that enhance it, but that's the basic edge: a simple, mechanical implementation of "buy the dip, sell the rip". I'm trading about half a dozen different variations of this in algos, and will discretionary trade it on just about anything if I see that trend setup and looks like I can catch the 2nd or 3rd pullback in a strong trend. Not the usual way to trade moving averages, but it works pretty well and is super simple.

**Claim:** „it works pretty well and is super simple”, handluje kilkoma wariantami w algorytmach. Bez liczb.

**Nasze założenia:** EMA 10 i SMA 20 (przykład autora). Punkty 1–2 to stan na świecy przed cofnięciem, punkt 3 to sygnał: wszystkie trzy naraz na jednej świecy się wykluczają (EMA rośnie tylko, gdy zamknięcie jest nad poprzednią EMA, więc świeca z rosnącą EMA nie zamknie się pod nią). Kupno na zamknięciu świecy, która zamyka się między średnimi (SMA < zamknięcie < EMA), gdy poprzednia świeca zamknęła się nad EMA, EMA > SMA, a obie średnie były nie niższe niż świecę wcześniej („trending up (or flat)”). Wyjście na zamknięciu świecy nad EMA i nad high poprzedniej świecy. Tylko long (autor opisuje tylko kupno). Stopów autora nie znamy, więc bez SL i TP, 100% kapitału. Autor nie podaje rynku ani interwału — standard 15m/1h/4h.
