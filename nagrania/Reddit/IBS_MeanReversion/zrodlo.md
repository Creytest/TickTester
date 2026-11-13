- **Post:** „70% Win Rate Setup that I Found Hiding in Plain Sight” (r/Daytrading, flair: Strategy)
- **Autor:** u/vaanam-dev
- **Link:** https://www.reddit.com/r/Daytrading/comments/1rktyiu/

**Dokładny post (część ze strategią i wynikiem na SPY):**

> I stumbled upon a mean reversion strategy that shows some potential.
> I will get straight into it.
>
> Entry condition
>
> ```
> close < (10 days high - 2.5 * (25 days average high - 25 days average low) and
> ibs < 0.3
> ```
>
> Explanation of entry
> Today's close should be less than the highest high of last 10 bars minus 2.5 times the last 25 days average stock movement.
> Additionally, IBS should be below 0.3.
> What's IBS? not irritable bowel syndrome
> IBS (Internal Bar Strength) = `(close - low) / (high - low)`
> This gives a 0–1 range. 0 means close = low (weakness), 1 means close = high (strength). Below 0.3 = closed in the bottom 30% of the day's range.
>
> Exit
> `close > yesterday's high`
> yep very simple
>
> Backtest
> I'm testing this on multiple instruments, the parameters are
> - Timeframe - Daily
> - Ticker - SPY
> - Slippage - 0.01
> - commission - 0.01
> - Duration - 2006 march till 2026 march
> - Capital - 100,000
>
> Core Returns
> - Total Return: 334.84%
> - CAGR: 7.75%
> - Profit Factor: 2.02
> - Win Rate: 75.00% (180 Wins / 60 Losses)
>
> Risk Metrics
> - Max Drawdown: 15.26%
> - Calmar Ratio: 0.51
> - Sharpe Ratio: 0.46
> - Sortino Ratio: 0.81
> - Avg Profit: $3,677.39
> - Avg Loss: -$5,451.58
>
> Position & Efficiency
> - Time Invested: 21.02%
> - Avg Hold Time: 5.4 days
> - Total Trades: 240
> - Final Capital: $434,835.64
>
> 75% win rate with only 15% max drawdown is really good. The 7.75% CAGR isn't crazy good, but you're only in the market 21% of the time.

Dalej w poście autor testuje QQQ (2011–2026: CAGR 9.18%, WR 70.74%, DD 11.92%), AAPL (CAGR 11.77%, WR 70.27%, DD 29.56%) i ABNB (CAGR 4.74%, WR 56.52%, DD 28.53%). Podsumowanie autora:

> - ~70% win rate held across SPY, QQQ, and AAPL
> - Profit factor consistently around 2.0 on ETFs
> - Time invested stays low (16–25%), capital efficient
> - Individual stocks = higher returns but higher drawdowns
> - Doesn't work on everything (ABNB)

**Odpowiedź autora w komentarzach** (pytanie: „what your stop-loss condition would be in this case?”):

> no stop-loss, because the exit is just close > previous day's close, happens very often.

**Nasze założenia:** świece dzienne, tylko long, 100% kapitału z kapitalizacją, bez SL i TP. Wyjście domyślnie wg posta (`EXIT_MODE = "high"`); wersja z komentarza to `EXIT_MODE = "close"`.
