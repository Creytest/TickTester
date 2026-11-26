# Materiały do odcinków

Wszystko do jednego odcinka w jednym miejscu: `nagrania/<Odcinek>/<Strategia>/`.

| Co | Gdzie | W gicie? |
|---|---|---|
| Plansza „jak działa strategia” (1-2-3) | `<Strategia>/plansza_zasady.png`, animacja obok: `plansza_zasady.mp4` (`zasady_animacja.py`) | tak / nie |
| Testowane aktywa i interwały („na czym testuję”) | `<Strategia>/plansza_rynki.png`, animacja obok: `plansza_rynki.mp4` (`rynki_animacja.py`), po teście też `wyniki/plansze_*/0_rynki.png` | tak / nie |
| Plansze wyników i ich animacje | `wyniki/plansze_*/`: `0_rynki`, `1_mediany`, `2_wykres_kapitalu` jako `.png` + `.mp4` (`wyniki_animacja.py`), `3_tabela.png` | nie |
| Inne grafiki objaśniające | `<Strategia>/*.png`, `<Odcinek>/plansza_rynki.png` | tak |
| Źródło: autor, link, dokładny tekst, nasze założenia | `<Strategia>/zrodlo.md` (TikTok: `TikTok/zrodla_strategii.md`) | tak |
| Rozpiska „działanie strategii” (schemat + reguły) | `<Strategia>/rozpiska.html`, całość: `<Odcinek>/rozpiska_strategii.html` | tak |
| Backtest z `run_all_assets.py` (HTML, CSV, plansze wyników) | `<Strategia>/wyniki/` | nie (liczone u Ciebie) |
| Grupa kontrolna / wersja standardowa | `<Strategia>/wyniki_Control/`, `wyniki_Standard/` | nie |
| Badanie zdarzeń, porównanie z kontrolną, koszty spreadu | `<Strategia>/wyniki_event_study/`, `wyniki/porownanie_*`, `wyniki/koszty_spread/` | nie |

Odcinek wynika z folderu strategii: `strategies/tiktok/` → `TikTok`, `reddit` → `Reddit`,
`tradingview` → `TradingView`, `tradingview_porownawcze` → `TradingViewPorownawcze`, `ksiazki` → `Ksiazki`.
Badania bez jednej strategii: `FormacjeSwiecowe/`, `RSI/`, `Trend/` (czy trend istnieje, Murphy). Wyjątki: `ODCINEK_STRATEGII` w `narzedzia/odcinki.py`.

Znaczniki do montażu (okręgi, ramki, strzałki w kolorach kanału, PNG z przezroczystym tłem): `_montaz/znaczniki/` (`python narzedzia/plansze_objasniajace/znaczniki_montaz.py`).
Kod zostaje w `narzedzia/`, `analizy/`, `strategies/` — tutaj nie ma plików `.py`.
Plansze objaśniające robią skrypty z `narzedzia/plansze_objasniajace/` i same zapisują się tutaj.
Animacja zawsze leży w tym samym folderze co jej plansza, pod tą samą nazwą (`.png` ↔ `.mp4`). MP4 nie idą do gita.
Wszystkie animacje naraz:

```
python narzedzia/plansze_objasniajace/rynki_animacja.py            # plansza_rynki.mp4 każdej strategii
python narzedzia/plansze_objasniajace/zasady_animacja.py           # plansza_zasady.mp4
python narzedzia/plansze_objasniajace/wyniki_animacja.py --wszystkie   # 0_rynki/1_mediany/2_wykres_kapitalu.mp4 w wyniki/plansze_*/
```

Ponowny test tych samych aktywów, interwałów i dat nadpisuje pliki w `wyniki/` (nie tworzy nowego folderu).
Test tylko części aktywów aktualizuje ich wiersze w podsumowaniu i planszach, reszta zostaje z poprzedniego testu.

Stare wyniki z `wyniki/`: `python narzedzia/przenies_wyniki.py` (podgląd), potem `--tak`.
