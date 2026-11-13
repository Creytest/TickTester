# Czy rynek wie, że jest wyprzedany? Zasady testu RSI

Zapisane 2026-11-07, **przed uruchomieniem testu na prawdziwych danych**.
Wyniki nie zmieniają tych zasad. Każda późniejsza zmiana jest dopisywana
na dole z datą i powodem.

## Claim

Podręcznikowa interpretacja RSI (Wilder, 1978, i większość kursów):
RSI poniżej 30 = rynek wyprzedany (należy oczekiwać odbicia w górę),
RSI powyżej 70 = rynek wykupiony (należy oczekiwać spadku).

## Hipotezy

- H0: po sygnale RSI cena zachowuje się tak samo jak po losowej świecy.
- H1: po RSI < 30 cena rośnie mocniej niż po losowej świecy,
  po RSI > 70 spada mocniej.
- Test dwustronny: wynik „po RSI < 30 dalej spada” też jest wynikiem.

## Dane

- Aktywa: XAUUSD, Bitcoin, EURUSD, Brent, US500 (ceny Bid z ticków).
  USA 100 pominięte (dane tylko 2011–2014, bez spreadu).
- Interwały 15m, 1h, 4h: 2021-01-01 – 2025-12-31.
- Interwał 1D (oryginalny interwał Wildera): cała dostępna historia
  do 2025-12-31 (5 lat dziennych świec daje za mało sygnałów).

## Wskaźnik i zdarzenie

- RSI 14 Wildera (jak `ta.rsi` w TradingView), parametry domyślne,
  bez optymalizacji.
- Wyprzedanie: świeca, na której RSI przecina 30 w dół
  (poprzednia ≥ 30, obecna < 30).
- Wykupienie: świeca, na której RSI przecina 70 w górę.
- Nowe zdarzenie liczy się tylko, jeśli od poprzedniego zdarzenia tego
  samego typu minęło co najmniej 20 świec (ścieżki się nie nakładają).

## Pomiar

- Zmiana ceny od zamknięcia świecy sygnałowej do zamknięcia świecy
  +1, +2, …, +20, skumulowana, w % (wykres) i w ATR 14 (tabela).
- Średnia po wszystkich zdarzeniach = „ścieżka RSI”.

## Grupy kontrolne

- A, losowe świece: 10 000 losowań, w każdym tyle samo świec
  co zdarzeń, z tego samego aktywa, interwału i okresu.
- B, ten sam spadek bez sygnału: świece (nie-zdarzenia) z tym samym
  ruchem ceny w ostatnich 14 świecach (w ATR, ten sam przedział
  5-procentowy) co zdarzenie. Odpowiada na pytanie, czy RSI daje coś
  ponad informację „cena spadła”.

## Pas i werdykt (ustalone z góry)

- Pas 95% liczony dla całej ścieżki 1–20 naraz (statystyka maksimum),
  więc 20 punktów nie daje 20 szans na przypadek.
- **Werdykt główny: dla wyprzedania, grupa A. Rynek „wie”, że jest
  wyprzedany, jeśli ścieżka RSI wychodzi z pasu w górę.**
- p-value = odsetek losowań, w których przypadek odjechał co najmniej
  tak daleko jak RSI (na którejkolwiek świecy 1–20).
- 20 kombinacji (5 aktywów × 4 interwały): przy p < 0,05 około jednej
  wyjdzie „istotnie” przypadkiem. Raportujemy p po korekcie Holma.
- Stabilność: średnia po 10 świecach osobno dla pierwszej i drugiej
  połowy okresu.
- Istotne ≠ opłacalne: ruch porównany z kosztem transakcji w obie
  strony (mediana spreadu + 2 × prowizja z `tick_config`).

## Poza zakresem tego testu

- Strategia z kapitałem (osobny krok, po tym badaniu).
- Inne długości i progi RSI.

## Zmiany

(brak)
