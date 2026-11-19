# IBS Mean Reversion — TradingView (Pine Script v6)

Reguła: u/vaanam-dev (r/Daytrading), na podstawie badań Quantified Strategies.
Wersja w Pythonie: `strategies/reddit/IBS_MeanReversion.py` (te same reguły).

## Pliki

| Plik | Co to jest |
|---|---|
| `ibs_mean_reversion_indicator.pine` | Wskaźnik na cenie: próg wejścia, sygnały BUY/EXIT, oznaczenia IBS, alerty |
| `ibs_panel.pine` | IBS w osobnym panelu (słupki 0–1, linia 0,3) |
| `ibs_mean_reversion_strategy.pine` | Wersja strategy do backtestu w TradingView (10 000 USD, 100% kapitału, prowizja 0,05%, poślizg 1 tick) |

## Jak dodać na wykres (działa na darmowym koncie)

1. Otwórz wykres na interwale 1D.
2. Na dole kliknij **Pine Editor** → **New indicator** (albo New strategy).
3. Zaznacz cały domyślny kod, wklej zawartość pliku `.pine`.
4. **Save** → **Add to chart**.

## Zasady

- **IBS** = (close − low) / (high − low).
- **Wejście (long):** close < najwyższy high z 10 świec − 2,5 × (SMA25 high − SMA25 low) **i** IBS < 0,3.
- **Wyjście:** close > wczorajszy high (opcja: > wczorajsze zamknięcie).
- Tylko long, jedna pozycja naraz, bez SL i TP. Sygnały na zamknięciu świecy (bez repaintu).

## Ograniczenia

- Testowane tylko na świecach dziennych.
- Bez stop lossa: w długim trendzie spadkowym kupuje kolejne spadki, obsunięcia mogą być głębokie.
- Wynik historyczny nie gwarantuje przyszłych zysków. To nie jest porada inwestycyjna.

---

**EN:** Daily IBS mean-reversion setup by u/vaanam-dev (r/Daytrading), based on Quantified Strategies.
Open TradingView → Pine Editor → New indicator → paste the `.pine` file → Save → Add to chart.
Long only, no stop loss, daily timeframe only. Past performance does not guarantee future results.
