- **Autor:** LunqFX
- **Typ:** `indicator()`, maszyna stanów Wyckoffa (SC/BC → AR → ST → Spring/UTAD → SOS/SOW → LPS/LPSY), cele T1/T2 i poziom unieważnienia, panel z track recordem. Bez wejść, SL i wielkości pozycji
- **Link:** https://www.tradingview.com/script/y9jjEUGv-Wyckoff-Accumulation-Distribution-Spring-UTAD-SOS-LunqFX/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-04 w wątku „Przetestować Wyckoff Accumulation & Distribution” (pierwsza wiadomość)
- **Timeframe autora:** 15m–1D („Works on forex, gold (XAUUSD), indices and crypto, 15m to 1D”)
- **Aktywa autora:** forex, złoto (XAUUSD), indeksy, krypto; bez wolumenu klimaks tylko z zakresu świecy

**Dokładny opis (fragmenty):**

> Check the track record before relying on a schematic: it shows how often ranges on this symbol and timeframe actually reached T2.

> The schematic gives structure and targets, not an entry. It has no stop loss or position sizing; combine it with your own entry rules and risk management.

**Reguły z kodu (domyślne):**

1. ATR(50), średni wolumen SMA(20). Klimaks SC: low = najniższe z 50 świec, zakres świecy ≥ 1,2 ATR, wolumen ≥ 1,5 × średnia (pomijane bez wolumenu). BC lustrzanie. Gdy oba na jednej świecy: SC jeśli świeca spadkowa.
2. Faza A: ekstremum klimaksu przesuwa się, dopóki nie pojawi się AR = pivot (3/3) w przeciwną stronę ≥ 2 ATR od ekstremum. AR > 10 ATR → model kasowany. Brak AR w 50 świec → kasowany.
3. Zakres = [klimaks, AR]; AR = creek (akumulacja) / ice (dystrybucja). ST = pierwszy pivot po AR w strefie 35% zakresu od klimaksu, bez przebicia.
4. Spring/UTAD: knot za stroną klimaksu i zamknięcie z powrotem w zakresie w ≤ 3 świecach. Zamknięcie > 30% zakresu za klimaksem albo > 3 świece poza zakresem → FAILED.
5. SOS/SOW: zamknięcie za creek/ice. Jeśli < 15 świec od klimaksu (także spring/fail) → V-turn, model kasowany i nie liczony.
6. Po SOS: T1 = creek + 1 × zakres, T2 = creek + 2 × zakres (od krawędzi, nie od ceny wejścia). INVALID = low springa, bez springa = SC. T1/T2 trafiane knotem, FAILED = zamknięcie za INVALID. T2 sprawdzane przed FAILED na tej samej świecy. Wygasa po 300 świecach (zakres bez wybicia też po 300).
7. LPS/LPSY: pierwszy pivot po SOS powyżej środka zakresu (faza E).
8. Naraz śledzony tylko jeden schemat; nowy klimaks szukany dopiero po zakończeniu poprzedniego. Track record: liczba zakresów, % spring/UTAD, % SOS/SOW, % T2, % failed (mianownik obejmuje też zakresy bez wybicia).

**Status (2026-11-04):** Kamil: „rób”. PR #56: `strategies/tradingview/Wyckoff.py` (port 1:1 + strategia SOS/SOW → T2, SL = INVALID na ticku, 1% ryzyka), `Wyckoff_Control.py` (losowe momenty, te same odległości SL/TP w ATR), `event_study_wyckoff.py` (track record + % T2 vs losowy ruch przy tej samej geometrii). Pierwotna propozycja: Propozycja: port 1:1 do `strategies/tradingview/Wyckoff.py` + odtworzenie track recordu autora + strategia na naszym założeniu (wejście na SOS/SOW, TP = T2, wyjście na FAILED/wygaśnięciu, 1% ryzyka do INVALID) + grupa `_Control` z losowymi wejściami.
