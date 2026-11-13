- **Autor:** nie podany we wklejce (do uzupełnienia z TV)
- **Typ:** `indicator()`, bez raportu wyników i bez wejść/SL/TP; tylko zdarzenia wybicia + 6 alertów. Autor: „This is an analysis aid, not a trading recommendation”
- **Link:** https://www.tradingview.com/script/7C36YesS-auto-levels-trendlines-breakout-check/
- **Pełny kod Pine v6 i opis:** wklejone przez Kamila 2026-11-03 w wątku „Przetestować Auto Levels & Trendlines” (pierwsza wiadomość)
- **Timeframe autora:** nie podaje
- **Aktywa autora:** nie podaje (wolumen używany tylko opcjonalnie, domyślnie wyłączony)

**Dokładny opis (fragmenty):**

> Breakouts: a close beyond the boundary by an ATR buffer starts the check. Holding for several closes, optionally with elevated volume, makes it true. A close back across the boundary makes it false. A later retest then confirms or fails it.

> All tolerances scale with ATR, and every threshold is adjustable. This is an analysis aid, not a trading recommendation.

**Reguły z kodu (domyślne):**

1. Pivoty high/low 5/5 (znane 5 świec później), ATR(14).
2. Poziomy: pivot dołączany do istniejącej strefy, jeśli leży w ±0,35 ATR od niej i strefa nie przekroczy 1,5 ATR grubości; inaczej nowa strefa ±0,10 ATR. Strona (opór/wsparcie) ustalana raz, przy powstaniu: close nad pivotem = wsparcie. Max 20 stref (najstarsze wypadają, także kwalifikowane).
3. Dotyk poziomu: knot w strefie ±0,35 ATR, zamknięcie po „swojej” stronie, ≥ 5 świec od poprzedniego dotyku. Poziom aktywny przy ≥ 3 dotykach (pivot = 1. dotyk).
4. Linie trendu: z ostatniego pivota i jednego z 10 poprzednich (≤ 300 świec, różnica ≥ 0,5 ATR), żaden knot między nimi nie przebija linii o > 0,25 ATR, ≥ 3 dotyki. Opór tylko spadający, wsparcie tylko rosnące. Max 6 linii.
5. Wybicie: zamknięcie za granicą strefy/linii o > 0,15 ATR. Wybicie poziomu z < 3 dotykami po cichu go kasuje (bez zdarzenia).
6. TRUE: 3 kolejne zamknięcia za granicą (licząc świecę wybicia). FALSE: wcześniej zamknięcie z powrotem za granicą (bez bufora). Dla linii granica idzie dalej linią.
7. Po TRUE retest w 10 świec: knot dotyka granicy → zamknięcie za nią = „confirmed by retest”, z powrotem = „failed” (alert liczy go jako false).

**Decyzja Kamila (2026-11-03): tylko badanie zdarzeń, bez strategii i bez naszych SL/TP.** PR #51: `strategies/tradingview/AutoLevelsTrendlines.py` (port 1:1 zdarzeń) + `event_study.py` (% TRUE/FALSE/retest, ruch po 5/10/20 świecach od sygnału breakout/true/false w ATR i % vs losowe świece w tym samym kierunku; bez kosztów, spread w ATR wypisany obok). XAUUSD/Bitcoin/EURUSD/Brent × 15m/1h/4h, 2021–2025.
