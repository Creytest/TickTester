- **Post:** „From 45% to 75% Win Rate. My Journey to a More Reliable Strategy” (r/Daytrading)
- **Autor:** u/thefakeab
- **Link:** https://www.reddit.com/r/Daytrading/comments/1mvv085/

**Dokładny post (reguły):**

> The Second Entry Strategy • Built on patience: wait for the market’s second attempt instead of the first fake-out. • Works across trends and ranges (EMA 21, trendlines, support/resistance as guides). • Entry: pullback + second entry setup (higher low in uptrend / lower high in downtrend). • Stop: just beyond the signal bar. • Target: usually 1:1 RR, sometimes leave a runner for extended moves.
>
> After 1.5 years of using it (~300 trades) this has been holding at about a 75% win rate.

**Dopowiedzenia autora w komentarzach:**

> I only use 1 timeframe, the 2000 ticks chart. […] check Thomas Wade on YouTube […] I started by reading the second entry books […] he takes profit at 8 ticks for around a 90% win rate while I do 1:1 RR for a 75% win rate
> In a range I try to ignore the ema and buy low/sell high and fade breakouts
> You can look up "second entry" strategy, my system is a little modified but that's the idea mostly
> (signal bar) Check the section about signal bars, this is exactly what I follow. https://youtu.be/TegF3yYjnng

**Claim:** 75% Win Rate przy 1:1, ~300 transakcji w 1,5 roku. Autor gra na kontach fundowanych.

**Ocena (2026-11-07):** ~50% reguł od autora (EMA 21, kierunek, „drugie wejście” po cofnięciu, SL za świecą sygnałową, TP 1:1). Pojęcie „second entry” to znany setup Ala Brooksa (H2/L2), więc resztę da się wziąć z pierwowzoru, a nie wymyślać: w trendzie (cena nad EMA 21) cofnięcie, w którym high świecy drugi raz przebija high poprzedniej → buy stop tick nad świecą sygnałową, SL tick pod nią, TP 1:1. Część „w konsolidacji” (fade wybić, S/R, linie trendu) jest uznaniowa — do pominięcia. Definicji świecy sygnałowej z filmu YouTube nie znamy (sieć blokuje YT). Wykres 2000 ticków (giełdowych, futures) — w danych Dukascopy ticki to zmiany kwotowań, więc zostają świece czasowe (1m/5m). Win Rate da się uczciwie sprawdzić, bo TP 1:1 to wyjście autora.

**Nasze założenia (kod):** trend = EMA 21 rośnie (short: spada). Cofnięcie zaczyna świeca z niższym high; H1 = pierwsza świeca z wyższym high (nie gramy); potem świeca z niższym high = druga noga, jej dołek wyżej niż dołek pierwszej nogi. Świeca sygnałowa wzrostowa z zamknięciem w górnej połowie → buy stop na jej high (ważny 1 świecę, ponawiany póki setup trwa), SL na jej low, TP 1:1, 1% ryzyka. Setup kasuje nowy szczyt nad początkiem cofnięcia, niższy dołek drugiej nogi albo koniec trendu. Pominięte: konsolidacje, S/R, linie trendu, runner. Interwały 1m i 5m.
