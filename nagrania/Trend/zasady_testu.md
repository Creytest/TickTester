# Czy trend istnieje? Zasady testu

Zapisane 2026-11-14, **przed uruchomieniem testu na prawdziwych danych**.
Wyniki nie zmieniają tych zasad. Każda późniejsza zmiana jest dopisywana
na dole z datą i powodem.

Kod: `analizy/event_study_trend.py` (badanie), `analizy/trend_definicje.py`
(definicje trendu), `narzedzia/dane_dzienne.py` (świece dzienne).

## Claim

John J. Murphy, „Analiza techniczna rynków finansowych” (wyd. polskie):

- s. 25: „trend wykazuje silniejszą tendencję do kontynuacji swego biegu
  w dotychczasowym kierunku aniżeli do jego zmiany”; „istniejący trend
  będzie kontynuował swój bieg, dopóki nie nastąpi jego odwrócenie”.
- s. 42 (teoria Dowa) i s. 63: trend wzrostowy = seria coraz wyżej
  położonych szczytów i dołków, spadkowy = coraz niżej położonych.
- s. 47: Dow przywiązywał wagę wyłącznie do cen zamknięcia.
- s. 46–47, diagramy 2.3a–b i 2.4a–b: sygnał kupna B1 = przebicie
  poziomu szczytu B po wyższym dołku C; sprzedaży S lustrzanie.
  Część analityków nie uznaje sygnału S1 (przełamanie dołka bez niższego
  szczytu) i czeka na S2.
- s. 65: „przynajmniej jedną trzecią czasu, licząc ostrożnie, ceny
  poruszają się wewnątrz formacji horyzontalnej”.
- s. 47: sygnał Dowa traci „przeciętnie rzecz biorąc 20–25 procent
  całego ruchu”.
- s. 65–67: trzy stopnie trendu: główny (dla rynków terminowych > 6 mies.),
  średni (3 tygodnie – 3 miesiące), krótki (do 2–3 tygodni). Większość
  systemów koncentruje się na trendzie średnim.

Porównawczo (ta sama metoda pomiaru):
- reguła 4 tygodni (Donchian; opisana też przez Murphy'ego),
- cena powyżej/poniżej SMA 200,
- momentum 12 miesięcy (Moskowitz, Ooi, Pedersen, „Time Series Momentum”, 2012).

## Hipotezy

- H0: rynek nie ma pamięci kierunku. Po potwierdzeniu trendu cena idzie
  dalej w jego kierunku tak samo często jak na wykresie z losowym kierunkiem.
- H1: po potwierdzeniu trendu cena częściej idzie dalej w jego kierunku.
- Test dwustronny: „częściej zawraca” też jest wynikiem.

## Dane

- Świece dzienne (1D) z ticków, ceny Bid, zamknięcie dnia o północy
  GMT+2 (17:00 Nowy Jork): XAUUSD, EURUSD (od 2003), Brent (od 2010),
  Bitcoin CFD (od 2017; dłuższa historia niż Binance BTCUSDT od 2020-09),
  US500 (od 2020-11). Do 2025-12-31.
- Długa historia z plików CSV (Stooq), jeśli są: S&P 500, Dow Jones,
  złoto. Liczone osobno, nie wchodzą do wyniku „Wszystkie rynki”
  (złoto i S&P powtarzałyby rynki z ticków).
- Tylko ceny zamknięcia (Dow, s. 47). Bez kosztów: to badanie pamięci
  rynku, nie transakcje.

## Szczyty i dołki (nasze założenie, książka go nie podaje)

- Zigzag na zamknięciach: szczyt = najwyższe zamknięcie od ostatniego
  dołka, **potwierdzony dopiero**, gdy zamknięcie spadnie o próg a poniżej
  niego (dołki odwrotnie). Wcześniej szczytu „nie ma” — bez zaglądania
  w przyszłość.
- Próg a dla każdego rynku osobno: a = zmienność dzienna (odchylenie
  standardowe dziennych zmian logarytmu ceny z całego okresu) × √(liczba
  świec fali). Jeden próg % dla wszystkich rynków byłby błędem
  (3% na BTC to szum z jednego dnia, na EUR/USD fala na kilka tygodni).
- Długość fali z Murphy'ego:
  - **trend średni** (główny wynik) rozpoznajemy po falach krótkich:
    14 dni kalendarzowych (s. 67: „do dwóch, trzech tygodni”),
  - **trend główny** po falach średnich: 44 dni (środek geometryczny
    3 tygodni i 3 miesięcy).
- Kontrola założenia: w `murphy_opis.csv` mediana długości fal
  (prawdziwa i na „monecie”) obok długości docelowej.

## Zdarzenia

Murphy (diagramy 2.3–2.4):
- **potwierdzone**: pierwsze zamknięcie powyżej ostatniego szczytu, gdy
  ostatni dołek jest wyższy od poprzedniego (B1/B2), lub poniżej ostatniego
  dołka, gdy ostatni szczyt jest niższy od poprzedniego (S/S2).
  Każdy szczyt/dołek daje najwyżej jedno zdarzenie.
- **bez potwierdzenia** (S1): przebicie bez wyższego dołka / niższego szczytu.

Inne definicje (zdarzenie = zmiana kierunku; okna w tygodniach
przeliczane na świece danego rynku, BTC ma 7 świec w tygodniu):
- reguła 4 tygodni: zamknięcie ponad najwyższe / pod najniższe zamknięcie
  z poprzednich 4 tygodni (na zamknięciach, nie high/low),
- SMA 200 (40 tygodni): cena przecina średnią,
- momentum: zmienia się znak zmiany ceny z ostatnich 52 tygodni.

## Pomiar: wyścig do progu

- Od zamknięcia świecy zdarzenia: co pierwsze — zamknięcie o a wyżej
  czy o a niżej (w logarytmach, więc symetrycznie). a = próg fali
  danego stopnia, ten sam co w zigzagu. Bez limitu czasu; wyścig
  nierozstrzygnięty do końca danych jest pomijany.
- Wynik = % zdarzeń, w których cena doszła najpierw do progu
  **w kierunku trendu**.

## Kontrole

- **MONETA (główna)**: 1000 sztucznych wykresów na rynek. Każdy dzień
  zostaje na swoim miejscu i z tą samą wielkością ruchu (od średniej),
  a jego kierunek jest losowany ±1; średni dryf rynku zostaje
  (wild bootstrap: r* = μ + ε·(r − μ)). Na każdym wykresie od nowa:
  zigzag, reguły, wyścig. Pas 95% = 2,5–97,5 percentyl wyników.
  Dlaczego nie tasowanie dni: tasowanie niszczy też okresy spokojne
  i nerwowe (skupianie zmienności), co samo może zawęzić pas.
- **LOSOWE DNI**: prawdziwy wykres, tyle samo startów w górę i w dół
  co zdarzeń, ale w losowych dniach (10 000 losowań).
- Ograniczenie monety: zakłada, że duży ruch w górę i w dół jest równie
  prawdopodobny (na akcjach krachy są większe niż wzrosty). Dlatego
  wniosek tylko, gdy obie kontrole wskazują to samo.

## Werdykt (ustalony z góry)

- **Główny: definicja Murphy'ego (potwierdzone), trend średni,
  „Wszystkie rynki” z ticków razem** (sumy zdarzeń i wygranych, w każdym
  losowaniu „monety” tak samo).
  - „Trend istnieje”, jeśli wynik jest powyżej pasu obu kontroli.
  - „Częściej zawraca”, jeśli poniżej pasu obu kontroli.
  - „Jak przypadek”, jeśli w pasie obu kontroli.
  - Inaczej „niejednoznaczne”.
- Wyniki pojedynczych rynków: z korektą Holma (`*_p_holm`).
- Mniej niż 20 zdarzeń = „za mało zdarzeń”, bez wniosku.
- Pokazujemy wszystkie rynki, stopnie i definicje, nie tylko ciekawe.

## Dodatkowe pomiary

- Test wariancji (Lo i MacKinlay, 1988): VR(q) = wariancja zmian
  q-świecowych / (q × wariancja zmian dziennych), q = tydzień, miesiąc,
  kwartał, rok. 1 = brak pamięci, > 1 = ruchy się kontynuują,
  < 1 = zawracają. Pas z tych samych wykresów „moneta”.
- Czas bez trendu (claim „co najmniej 1/3”): stan +1 od potwierdzonego
  zdarzenia w górę do zamknięcia poniżej ostatniego dołka (przełamanie
  wsparcia, s. 69) albo potwierdzenia w dół; −1 symetrycznie; 0 = bez
  trendu. Porównane z „monetą”.
- Część ruchu straconą do sygnału (claim „20–25%”): dla każdego trendu
  (od stanu 0/−1 do +1) = (cena sygnału − dołek startowy A) /
  (ekstremum trendu − A). Liczone dla wszystkich trendów, także nieudanych.
- Dekady: wynik Murphy'ego w każdej dekadzie z pasem „monety”
  (sens głównie dla długiej historii z CSV).

## Moc testu (sprawdzone na danych sztucznych przed testem)

Na 23 latach dziennych świec jednego rynku jest ok. 100 zdarzeń Murphy'ego
(trend średni), a pas „monety” ma szerokość ok. ±10 pkt proc. Słaby
trend (np. 53%) na jednym rynku będzie więc wyglądał jak przypadek.
Dlatego główny wynik łączy rynki, a test wariancji i długa historia
z CSV są ważnym uzupełnieniem. Uruchomienie testowe:
`python analizy/event_study_trend.py --sztuczne`.
