- **Post:** „Does anyone believe "Holy Grail" strategies actually exist, but are just incredibly hard to find?” (r/Daytrading)
- **Autor:** u/SubDayTrader (flair: futures trader)
- **Link:** https://www.reddit.com/r/Daytrading/comments/q8bgk3/

**Dokładny post:**

> These are purely mechanical trading strategies where you just execute the same exact rules every day and generate profit over a long period (maybe not since market inception but they work for many years at a time). Almost every trader/invester I have heard speak about them say that they don't exist and to not spend time looking for them except maybe Jim Simons.
>
> Anyways I feel like I accidently stumbled upon one so it feels too good to be true. I back tested it for as far as tradingview would go which was 19 months and it returned 110R, approximately 5-6R per month, with the greatest drawdown in the PnL graph being 10R from highest to lowest, it is overall a pretty smooth graph. I did no curve fitting to the data and used a very simple entry and exit theory that I created the system from. The product of choice is in Gold Futures, so I don't think it is affected much by the strong equities trend in the past years (gold went up from March->August of last year, and then down from August until today), and it is multi-directional, selling short some days, going long others.
>
> I have done this in the past and every single one of the holy grails I thought I discovered eventually fell flat on it's face as I always heavily scrutinize them and discriminate against them in the backtest (i.e. if price didn't fully run through my Profit Target but simply touched it I call it a loser). But this one just... works, which worries me.

**Komentarz autora z regułami** (ok. rok później, na pytanie „Has this worked out for you so far?”):

> I continued to backtest it and it does appear profitable, but I remember running into some issue which prevented me from pursuing it. I believe it was capital required. I don't remember the specifics as it was 9 months ago, but I remember coming to the conclusion that I would need about $100,000 in order to properly forward test the system, and much more to extract better levels of R. That is basically all my savings and not something I was willing to put on the line. I also figure there are things like slippage or errors in the data that I wasn't accounting for that would also chip away at the alpha that might end up not making it worthwhile.
>
> If you are interested in checking it out, I believe it was marking out the high and low for the first hour of the trading day for Gold futures, this is the Initial Balance (IB). If the high of the IB was broken by a tick at any point of the day, you would go long with a stop a tick below the low of the IB. And vice versa for if the low of the IB was broken first. I believe the take profit was the length of the IB in the direction you are playing, or just exiting at the very end of the day if your TP or SL were not hit.
>
> I just looked back at my notes and another reason I did not pursue this was there was at least a 200 day period where no gains were made. Since I am looking for more of a short term return, it wasn't going to work for me to go 200 days without my capital working for me at all. But there was also a period of 40x ROI over 400 days.
>
> Edit: And by 200 days of no gains it was about 100 days of gains followed by 100 days of losses. I believe this was another reason for me not putting live money in it. The equity curve over a long enough timeframe showed decent drawdowns in it, but followed by pretty substantial winning streaks. But you don't know when you invest if you are getting in at the start of a drawdown or winning streak. I know I am not willing to stomach a 50% drawdown of all my life savings to just experiment with a strategy.

**Nasze założenia:** XAUUSD spot zamiast kontraktu GC, świece 1 min. IB = 8:20–9:20 NY (sesja COMEX). Jedna transakcja dziennie. SL tick za drugą stroną IB, TP = długość IB, wyjście o 13:30 NY. Ryzyko 1%.
