# Czy formacje świecowe przewidują kierunek? Zasady testu

Zapisane 2026-11-08, **przed uruchomieniem testu na prawdziwych danych**.
Wyniki nie zmieniają tych zasad. Każda późniejsza zmiana jest dopisywana
na dole z datą i powodem.

## Claim

Plansza „Candlestick Patterns — Complete Guide for Traders” (TredWithRahul,
Instagram/TikTok). Dwie kolumny: **Bullish** (byk, wykres w górę)
i **Bearish** (niedźwiedź, wykres w dół), po 6 formacji w każdej:

| Bullish (obiecuje wzrost) | Bearish (obiecuje spadek) |
|---|---|
| Dragonfly Doji | Gravestone Doji |
| Hammer | Inverted Hammer |
| Tweezer Bottom | Tweezer Top |
| Morning Star | Evening Star |
| Bullish Engulfing | Bearish Engulfing |
| Three White Soldiers | Three Black Crows |

Plansza nie podaje wejść, wyjść, SL, TP, interwału ani rynku. Testujemy
więc tylko to, co obiecuje: po formacji „bullish” cena rośnie, po „bearish”
spada.

Uwaga: plansza umieszcza Inverted Hammer w kolumnie bearish (w większości
źródeł ten kształt po spadku jest bullish, a po wzroście nazywa się
shooting star). Testujemy tak, jak jest na planszy.

## Hipotezy

- H0: po formacji cena zachowuje się tak samo jak po losowej świecy.
- H1: po formacji bullish cena rośnie mocniej niż po losowej świecy,
  po bearish spada mocniej.
- Test dwustronny: „po formacji bullish cena spada” też jest wynikiem.
- Werdykt patrzy na kierunek obiecany na planszy.

## Dane

Jak w badaniu RSI (`event_study_rsi_zasady.md`):

- Aktywa: XAUUSD, Bitcoin, EURUSD, Brent, US500 (ceny Bid z ticków).
- Interwały 15m, 1h, 4h: 2021-01-01 – 2025-12-31.
- Interwał 1D: cała dostępna historia do 2025-12-31.

## Definicje formacji (ustalone z góry)

Oznaczenia dla świecy: korpus = |close − open|, zakres = high − low,
górny knot = high − max(open, close), dolny knot = min(open, close) − low.
Zielona: close > open, czerwona: close < open.

Średnie (liczone z 10 świec **przed** daną świecą, bez niej):
`śr_korpus` = średni korpus, `śr_zakres` = średni zakres.
„Długa” świeca: korpus > śr_korpus. „Mała”: korpus < śr_korpus.
Progi wzorowane na domyślnych ustawieniach biblioteki TA-Lib
(BodyDoji, BodyLong, BodyShort, ShadowVeryShort); sama biblioteka
nie jest używana, wzory są w `analizy/formacje_swiecowe.py`.

Sygnał = zamknięcie ostatniej świecy formacji.

1. **Dragonfly Doji**: korpus ≤ 10% śr_zakres, górny knot ≤ 10% śr_zakres,
   dolny knot > 10% śr_zakres.
2. **Gravestone Doji**: lustrzanie (długi górny knot, brak dolnego).
3. **Hammer**: korpus > 10% śr_zakres (nie doji), mała świeca,
   dolny knot ≥ 2 × korpus, górny knot ≤ 10% śr_zakres. Kolor dowolny.
4. **Inverted Hammer**: lustrzanie (górny knot ≥ 2 × korpus,
   dolny ≤ 10% śr_zakres).
5. **Tweezer Bottom**: świeca 1 czerwona, świeca 2 zielona, obie nie doji,
   dołki różnią się o ≤ 5% ATR 14.
6. **Tweezer Top**: świeca 1 zielona, świeca 2 czerwona, szczyty
   różnią się o ≤ 5% ATR 14. **Definicji tweezer nie ma w TA-Lib — to
   nasze założenie.**
7. **Morning Star**: świeca 1 długa czerwona, świeca 2 mała,
   dolna krawędź jej korpusu poniżej zamknięcia świecy 1, świeca 3 długa
   zielona zamyka się powyżej połowy korpusu świecy 1.
   **Bez wymogu luki** (TA-Lib wymaga luki, a rynki 24h prawie ich
   nie mają — to nasze założenie).
8. **Evening Star**: lustrzanie (1 długa zielona, 2 mała z górną krawędzią
   korpusu powyżej zamknięcia 1, 3 długa czerwona zamyka się poniżej
   połowy korpusu 1).
9. **Bullish Engulfing**: świeca 1 czerwona, świeca 2 zielona,
   open 2 ≤ close 1 i close 2 ≥ open 1, korpus 2 > korpus 1.
10. **Bearish Engulfing**: lustrzanie.
11. **Three White Soldiers**: 3 zielone świece, każda długa, każda zamyka
    się wyżej od poprzedniej, open świec 2 i 3 w obrębie korpusu
    poprzedniej, górny knot każdej ≤ 25% jej korpusu.
12. **Three Black Crows**: lustrzanie (dolny knot ≤ 25% korpusu).

Formacje mogą się nakładać (np. ta sama para świec bywa jednocześnie
Tweezer Bottom i Bullish Engulfing). Każda formacja liczona jest osobno.

## Dwa warianty (oba raportowane)

- **Bez kontekstu**: każda formacja na wykresie.
- **Z kontekstem**: bullish tylko po spadku, bearish tylko po wzroście.
  Spadek = zamknięcie świecy tuż przed pierwszą świecą formacji poniżej
  SMA 20 z zamknięć; wzrost = powyżej SMA 20.

## Zdarzenia

- Nowe zdarzenie tej samej formacji (w tym samym wariancie) liczy się
  tylko, jeśli od poprzedniego minęło co najmniej 20 świec.
- Min. 20 zdarzeń w kombinacji, inaczej „brak wniosku”.

## Pomiar

- Zmiana ceny od zamknięcia świecy sygnałowej do zamknięcia świecy
  +1 … +20, w % (wykres) i w ATR 14 (tabela). Średnia = ścieżka formacji.

## Grupy kontrolne

- A, losowe świece: 10 000 losowań, w każdym tyle świec co zdarzeń,
  z tego samego aktywa, interwału i okresu.
- B (tylko wariant z kontekstem), ten sam ruch bez formacji: świece bez
  zdarzenia z tym samym ruchem ceny w ostatnich 14 świecach (w ATR, ten sam
  przedział 5-procentowy). Odpowiada na pytanie, czy formacja daje coś
  ponad „cena wcześniej spadła/wzrosła”.

## Pas i werdykt (ustalone z góry)

- Pas 95% dla całej ścieżki 1–20 naraz (statystyka maksimum), jak przy RSI.
- **Werdykt główny: grupa A. Formacja „działa” w danej kombinacji, jeśli
  ścieżka wychodzi z pasu w kierunku obiecanym na planszy.**
- Dla każdej formacji i wariantu: w ilu z 20 kombinacji (5 aktywów ×
  4 interwały) ścieżka wychodzi z pasu w obiecanym kierunku, a w ilu
  w przeciwnym.
- 12 formacji × 2 warianty × 20 kombinacji = 480 testów. Raportujemy p
  po korekcie Holma w obrębie formacji i wariantu (20 kombinacji)
  oraz po korekcie Holma dla wszystkich 480 testów.
- Stabilność: średnia po 10 świecach osobno dla pierwszej i drugiej
  połowy okresu.
- Istotne ≠ opłacalne: ruch porównany z kosztem transakcji w obie
  strony (mediana spreadu + 2 × prowizja z `tick_config`).

## Poza zakresem tego testu

- Strategia z kapitałem (plansza nie podaje wejść ani wyjść).
- Inne progi definicji i inne filtry trendu.
- Wolumen.

## Zmiany

### 2026-11-10: druga wersja „kolory jak na planszy”

Powód: plansza rysuje każdą świecę w konkretnym kolorze, a definicje
podręcznikowe (wyżej) dla doji i młotów kolor pomijają. Kamil poprosił
o drugą, osobną wersję całego testu wierną rysunkowi. Wersja podręcznikowa
zostaje bez zmian, obie są raportowane.

Wersja „kolory jak na planszy” = definicje jak wyżej + kolor każdej świecy
z rysunku (od najstarszej):

| Formacja | Kolory na planszy |
|---|---|
| Dragonfly Doji | zielona |
| Gravestone Doji | czerwona |
| Hammer | zielona |
| Inverted Hammer | czerwona |
| Tweezer Bottom | czerwona, zielona (bez zmian) |
| Tweezer Top | **czerwona, zielona** (podręcznik: zielona, czerwona) |
| Morning Star | czerwona, **czerwona**, zielona |
| Evening Star | zielona, **zielona**, czerwona |
| Bullish / Bearish Engulfing | bez zmian |
| Three White Soldiers / Black Crows | bez zmian |

Wszystkie pozostałe zasady (dane, warianty, kontrole, pas, werdykt) bez
zmian. Wyniki: `wyniki/event_study_candles_plansza/`, uruchomienie
`python analizy/event_study_candles.py --plansza`.
