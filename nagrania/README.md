# Materiały do odcinków

Wszystko do jednego odcinka w jednym miejscu: `nagrania/<Odcinek>/<Strategia>/`.

| Co | Gdzie | W gicie? |
|---|---|---|
| Plansza „jak działa strategia” (1-2-3) | `<Strategia>/plansza_zasady.png` | tak |
| Inne grafiki objaśniające, plansza rynków | `<Strategia>/*.png`, `<Odcinek>/plansza_rynki.png` | tak |
| Źródło: autor, link, dokładny tekst, nasze założenia | `<Strategia>/zrodlo.md` (TikTok: `TikTok/zrodla_strategii.md`) | tak |
| Rozpiska wszystkich strategii odcinka | `<Odcinek>/rozpiska_strategii.html` | tak |
| Backtest z `run_all_assets.py` (HTML, CSV, plansze wyników) | `<Strategia>/wyniki/` | nie (liczone u Ciebie) |
| Grupa kontrolna / wersja standardowa | `<Strategia>/wyniki_Control/`, `wyniki_Standard/` | nie |
| Badanie zdarzeń, porównanie z kontrolną, koszty spreadu | `<Strategia>/wyniki_event_study/`, `wyniki/porownanie_*`, `wyniki/koszty_spread/` | nie |

Odcinek wynika z folderu strategii: `strategies/tiktok/` → `TikTok`, `reddit` → `Reddit`,
`tradingview` → `TradingView`, `tradingview_porownawcze` → `TradingViewPorownawcze`, `ksiazki` → `Ksiazki`.
Badania bez jednej strategii: `FormacjeSwiecowe/`, `RSI/`. Wyjątki: `ODCINEK_STRATEGII` w `narzedzia/odcinki.py`.

Kod zostaje w `narzedzia/`, `analizy/`, `strategies/` — tutaj nie ma plików `.py`.
Plansze objaśniające robią skrypty z `narzedzia/plansze_objasniajace/` i same zapisują się tutaj.

Stare wyniki z `wyniki/`: `python narzedzia/przenies_wyniki.py` (podgląd), potem `--tak`.
