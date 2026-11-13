- **Post:** „Renko setup 70%-80% win rate.” (r/Daytrading)
- **Autor:** u/PauloMinozo
- **Link:** https://www.reddit.com/r/Daytrading/comments/1g3b92s/

**Dokładny post:**

> Been testing and trading with this setup and I've managed to make 50% profit over my capital over the past 3 months […]
> Setup:
> Long when box is crossing 9(yellow)-20(blue) EMA. Target is the same size of the box + wick (70% win rate). If I set my target at 50%, win rate goes up to 80%.
> Stop below wick.
> Same logic for shorting. Tried it on multiple different kind of products (shares, futures, crypto, forex). Works great with only minor percentages changes on the win rate.

**Dopowiedzenia autora w komentarzach:**

> I wait for the pullback as you said [pullback to 20 ema, then price crosses 9 again] and then I wait for the brick to close. I position my order 1 tick above where the brick will close.
> 1:1 = 70% win rate 1:0.5 = 80% win rate
> EURUSD = 4R. I can go to 6R if it's too volatile (printing too many boxes in a few seconds or in less than a minute).
> For the Ibovespa (Brazilian Index) I use 11R. […] Trial and error. […] I never tried ATR.
> avoid a Renko that prints more than one box within less than a minute […] You also need to exclude news events from your backtest.
> I do all my backtests manually with an excel spreadsheet. I usually backtest 2 years of data
> I can have between 2 and 8 entry signals per day.
> Renko z knotami (cTrader + dodatek; platforma ProfitChart dla Brazylii).

**Claim:** 70% WR (TP 1:1), 80% WR (TP 1:0,5), +50% kapitału w 3 miesiące, „works great” na akcjach, futures, krypto i FX. Backtest ręczny w Excelu, 2 lata.

**Ocena (2026-11-07):** ~60% reguł od autora: wykres Renko z knotami, EMA 9 i 20 (z zamknięć cegieł), cofnięcie do EMA 20 → cegła zamyka się z powrotem przez EMA 9 → zlecenie tick za zamknięciem cegły, SL za knotem, TP = cegła + knot (1:1) albo połowa (1:0,5), long i short, EURUSD 4R. Od nas: dokładna definicja „crossing” (cegła w kierunku trendu zamyka się po drugiej stronie obu EMA po cofnięciu), wielkość cegły dla innych aktywów (autor: „trial and error”, nie więcej niż 1 cegła na minutę — da się to zamienić na regułę), znaczenie „4R” (4 ticki/pipsy — niejednoznaczne), pominięcie newsów (nie mamy kalendarza). Renko z ticków da się zbudować uczciwie: cegła zamyka się na konkretnym ticku, knot = skrajna cena w trakcie cegły, wejście dopiero po zamknięciu — bez „magicznych” cen z backtestów Renko w TradingView. Wymaga zmiany w silniku (świece o nieregularnym czasie zamknięcia) i wykresach.

**Nasze założenia (kod, 2026-11-07):** Renko klasyczne (odwrócenie o 2 cegły) z cen Bid, knot = skrajny Bid w trakcie cegły. EMA 9 i 20 z zamknięć cegieł. Long: EMA 9 > EMA 20, od ostatniego zamknięcia nad EMA 9 knot dotknął EMA 20 (cofnięcie), cegła wzrostowa otwiera się na/pod EMA 9 i zamyka nad nią → wejście rynkowe na ticku zamknięcia cegły. SL tick za knotem, TP = zamknięcie + (cegła + knot) × TP_FRACTION (1,0 albo 0,5). Short lustrzanie. Cegły z jednego ticku (luka) pomijamy. Cegła: EURUSD 0,0004 (4R w cTrader = 4 pipsy), pozostałe aktywa — średnio 1 cegła na 5 minut handlu w pierwszych 30 dniach danych. Newsów nie wykluczamy (brak kalendarza).
