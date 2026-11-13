- **Autor:** ProjectSyndicate
- **Typ:** `indicator()` z własnym dashboardem statystyk (bez spreadu, prowizji i poślizgu — autor sam to zaznacza)
- **Link:** https://pl.tradingview.com/script/E0ietNMM-Strong-Pressure-Signals-ProjectSyndicate/
- **Kod:** pełny Pine w /mnt/project-files/ticktester/strong_pressure_signals.pine
- **Timeframe autora:** intraday, bez konkretnego interwału („built and tuned on XAUUSD (gold) on intraday timeframes”); domyślny pasek MTF: 15 i 60 min
- **Aktywa autora:** XAUUSD jako bazowe; „FX majors and crosses, metals, indices, and crypto on intraday timeframes”

**Dokładny opis (fragment):**

> A burst happens when a bar's wick pokes beyond that band [...] the signal fires on the first confirmed bar where the previous reading was the peak and the current reading comes in smaller. Up-bursts flip to a SHORT, down-bursts to a LONG.

> Default settings were chosen on historical gold data [...] the dashboard's statistics are historical and descriptive, not a forecast, and are simulated without spread, commission or slippage.

**Reguły z dostępnej części kodu (domyślne):** EMA 20 ± 2 × ATR 14. Burst = high nad górną bandą (low pod dolną). Sygnał na zamknięciu świecy, gdy poprzednia świeca miała największe wybicie, a obecna mniejsze. Min. wybicie piku ≥ 1 ATR poza bandą (stack 3 przy kroku 0,5 ATR). Bramki (klastry, sesje, RSI, gwiazdki) domyślnie WYŁĄCZONE, czyli klastry i sesje nie filtrują wejść. SL: za knotem piku + 0,3 ATR, w granicach 0,5–3 ATR. TP1/2/3: „Pressure Ladder” (najbliższe klastry, inaczej 1R/2R/3R). Odstęp 20 świec, jedna transakcja naraz, time stop 200 świec. Dashboard autora: transakcję, która dotknęła TP1/TP2 i wróciła na SL, liczy jako +R1/+R2 całej pozycji (bez kosztów).

**Nasze założenia (2026-11-03, PR #46):** po 1/3 pozycji na TP1, TP2, TP3 (wybór Kamila), reszta na SL bez przesuwania; 1% ryzyka; 15m/1h/4h; klastry z całej historii (TV: ostatnie 3000 świec).
