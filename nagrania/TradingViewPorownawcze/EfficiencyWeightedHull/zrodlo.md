- **Autor:** BackQuant
- **Typ:** `indicator()`, Hull MA z kompensacją ważoną Kaufman Efficiency Ratio + stan trendu z nachylenia (martwa strefa). Bez wejść, SL i TP; tylko alerty zmiany stanu (bull/bear flip)
- **Link:** https://www.tradingview.com/script/2A4GKtHB-Efficiency-Weighted-Hull-BackQuant/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-04 w wątku „Przetestować Efficiency Weighted Hull” (pierwsza wiadomość)
- **Timeframe autora:** nie podaje
- **Aktywa autora:** nie podaje

**Dokładny opis (fragmenty):**

> Efficiency Weighted Hull is a variation of the Hull Moving Average that adjusts the usual Hull lag-compensation term using Kaufman's Efficiency Ratio.

> When price movement is relatively efficient, the filter behaves more like a standard Hull. When movement is less efficient, the fast-minus-slow compensation is reduced.

> The indicator uses current and historical price data and does not predict future direction.

**Reguły z kodu (domyślne):**

1. Source = close, Hull Length 34 → fast = WMA(17), slow = WMA(34), rootLen = round(√34) = 6.
2. ER(20) = |src − src[20]| / suma |zmian 1-świecowych| z 20 świec (sma × 20), obcięte do [0, 1]; path = 0 → 0.
3. Kompensacja = minComp (0) + (1 − minComp) × ER^1,0. hullRaw = fast + komp × (fast − slow); EWH = WMA(hullRaw, 6).
4. Standard Hull = WMA(2·fast − slow, 6) (tylko Data Window). Base = WMA(slow, 6) (tylko wstążka).
5. slope = EWH − EWH[2]; noise = EMA(|EWH − EWH[1]|, 20); próg = noise × 0,20.
6. Stan: pierwszy = znak slope (≥0 → bull). Potem slope > próg → bull, slope < −próg → bear, w środku stan bez zmian.
7. bullFlip = stan −1 → 1, bearFlip = 1 → −1 (alerty). Trend Strength, wstążka, gradient, glow, świece = tylko wygląd.

**Status (2026-11-04):** Kamil wybrał long i short (zawsze w rynku). PR #59: `EfficiencyWeightedHull.py`, `EfficiencyWeightedHull_Standard.py`, `EfficiencyWeightedHull_Control.py`, presety w compare_control.py. Pierwotna propozycja: port 1:1 (`strategies/tradingview/EfficiencyWeightedHull.py`), strategia na flipach (sygnał na zamknięciu, wejście na otwarciu następnej świecy, 100% kapitału, bez SL/TP), ta sama strategia na standardowym Hullu (z tą samą martwą strefą) jako punkt odniesienia + `_Control` z losowymi momentami i compare_control.py. 15m/1h/4h, koszyk standardowy.
