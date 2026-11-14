"""
Definicje trendu do badania „Czy trend istnieje?” (Murphy, rozdz. 2 i 4).

Wszystko liczone tylko z cen zamknięcia (Dow: „wyłącznie ceny zamknięcia”,
s. 47) i tylko z danych do bieżącej świecy (bez zaglądania w przyszłość).
Ceny w logarytmach, więc próg „a” to ruch o a·100% w skali logarytmicznej
(dla małych progów prawie to samo co %).

Zasady: nagrania/Trend/zasady_testu.md
"""

import numpy as np


# ============================================================
# SZCZYTY I DOŁKI (zigzag na zamknięciach)
# ============================================================

def zigzag(logc: np.ndarray, a: float):
    """
    Szczyty i dołki potwierdzone dopiero po ruchu powrotnym o a.

    Szczyt = najwyższe zamknięcie od ostatniego dołka; jest potwierdzony
    na świecy, na której zamknięcie spadło o a poniżej niego (dołki
    odwrotnie). Wcześniej szczytu „nie ma” — tak jak trader nie wie,
    że to szczyt, dopóki cena nie zawróci.

    Zwraca listę (świeca_potwierdzenia, świeca_szczytu, wartość, rodzaj),
    rodzaj +1 = szczyt, -1 = dołek, w kolejności potwierdzenia.
    """
    pivots = []
    n = len(logc)
    if n == 0:
        return pivots
    direction = 0
    hi_v = lo_v = ext_v = logc[0]
    hi_i = lo_i = ext_i = 0
    for t in range(1, n):
        x = logc[t]
        if direction == 0:
            if x > hi_v:
                hi_v, hi_i = x, t
            if x < lo_v:
                lo_v, lo_i = x, t
            if x - lo_v >= a:
                pivots.append((t, lo_i, lo_v, -1))
                direction, ext_v, ext_i = 1, x, t
            elif hi_v - x >= a:
                pivots.append((t, hi_i, hi_v, 1))
                direction, ext_v, ext_i = -1, x, t
        elif direction == 1:
            if x > ext_v:
                ext_v, ext_i = x, t
            elif ext_v - x >= a:
                pivots.append((t, ext_i, ext_v, 1))
                direction, ext_v, ext_i = -1, x, t
        else:
            if x < ext_v:
                ext_v, ext_i = x, t
            elif x - ext_v >= a:
                pivots.append((t, ext_i, ext_v, -1))
                direction, ext_v, ext_i = 1, x, t
    return pivots


# ============================================================
# MURPHY / DOW: wyższe szczyty i dołki
# ============================================================

def murphy(logc: np.ndarray, a: float):
    """
    Zdarzenia i stan trendu wg Dowa/Murphy'ego.

    Zdarzenie = pierwsze zamknięcie powyżej ostatniego szczytu
    (lub poniżej ostatniego dołka). Każdy szczyt/dołek daje najwyżej
    jedno zdarzenie.
    - potwierdzone (diagram 2.4a, B1/B2; 2.3a S, 2.3b S2): przed
      przebiciem szczytu był wyższy dołek (dla spadku: niższy szczyt
      przed przebiciem dołka) → wyższe szczyty I wyższe dołki,
    - bez potwierdzenia (diagram 2.3b, S1): przebicie bez wyższego
      dołka (bez niższego szczytu).

    Stan (do pomiaru czasu „w bok”): +1 od potwierdzonego zdarzenia
    w górę, aż zamknięcie spadnie poniżej ostatniego dołka (przełamanie
    wsparcia, s. 69) albo pojawi się potwierdzenie w dół; -1 symetrycznie;
    0 = brak potwierdzonego trendu.

    Zwraca:
      events: tablica (świeca, kierunek ±1, potwierdzone 0/1)
      state:  stan na każdej świecy
      lag:    lista (kierunek, ułamek ruchu „stracony” do sygnału) — claim 20–25%
      legs:   długości fal w świecach (szczyt→dołek→szczyt…)
    """
    n = len(logc)
    pivots = zigzag(logc, a)
    events = []
    state = np.zeros(n, dtype=np.int8)
    lag = []

    p = 0
    last_hi = prev_hi = last_lo = prev_lo = None
    hi_used = lo_used = True
    cur = 0
    ep_start = ep_signal = ep_best = None

    def close_episode():
        """Ułamek ruchu od początku trendu do jego ekstremum, który minął przed sygnałem."""
        if ep_start is None:
            return
        move = np.exp(ep_best) - np.exp(ep_start)
        if move != 0:
            lag.append((cur, (np.exp(ep_signal) - np.exp(ep_start)) / move))

    for t in range(n):
        while p < len(pivots) and pivots[p][0] <= t:
            _, _, v, kind = pivots[p]
            if kind == 1:
                prev_hi, last_hi, hi_used = last_hi, v, False
            else:
                prev_lo, last_lo, lo_used = last_lo, v, False
            p += 1
        x = logc[t]

        if last_hi is not None and not hi_used and x > last_hi:
            hi_used = True
            ok = last_lo is not None and prev_lo is not None and last_lo > prev_lo
            events.append((t, 1, int(ok)))
            if ok and cur != 1:
                close_episode()
                ep_start, ep_signal, ep_best = prev_lo, x, x
                cur = 1
        elif last_lo is not None and not lo_used and x < last_lo:
            lo_used = True
            ok = last_hi is not None and prev_hi is not None and last_hi < prev_hi
            events.append((t, -1, int(ok)))
            if ok and cur != -1:
                close_episode()
                ep_start, ep_signal, ep_best = prev_hi, x, x
                cur = -1

        # Przełamanie wsparcia/oporu bez potwierdzenia = koniec trendu.
        if cur == 1 and last_lo is not None and x < last_lo:
            close_episode()
            ep_start = None
            cur = 0
        elif cur == -1 and last_hi is not None and x > last_hi:
            close_episode()
            ep_start = None
            cur = 0

        if cur == 1:
            ep_best = max(ep_best, x)
        elif cur == -1:
            ep_best = min(ep_best, x)
        state[t] = cur

    legs = np.diff([pv[1] for pv in pivots]) if len(pivots) > 1 else np.array([])
    ev = np.array(events, dtype=int).reshape(-1, 3)
    return ev, state, lag, legs


# ============================================================
# INNE DEFINICJE (tylko zamknięcia)
# ============================================================

def _switch_events(signal: np.ndarray) -> np.ndarray:
    """signal: +1/-1/0 na świecę (0 = bez zmiany). Zdarzenie = zmiana stanu."""
    events = []
    cur = 0
    for t, s in enumerate(signal):
        if s != 0 and s != cur:
            events.append((t, int(s), 1))
            cur = s
    return np.array(events, dtype=int).reshape(-1, 3)


def _rolling_max_prev(x: np.ndarray, w: int) -> np.ndarray:
    """Maksimum z poprzednich w świec (bez bieżącej)."""
    from numpy.lib.stride_tricks import sliding_window_view
    out = np.full(len(x), np.nan)
    if len(x) > w:
        out[w:] = sliding_window_view(x[:-1], w).max(axis=1)
    return out


def donchian(logc: np.ndarray, w: int) -> np.ndarray:
    """Reguła 4 tygodni: zamknięcie ponad maksimum / pod minimum z w świec."""
    hi = _rolling_max_prev(logc, w)
    lo = -_rolling_max_prev(-logc, w)
    sig = np.where(logc > hi, 1, np.where(logc < lo, -1, 0))
    return _switch_events(sig)


def sma_cross(logc: np.ndarray, w: int) -> np.ndarray:
    """Cena przecina średnią z w zamknięć (liczoną na cenach, nie logach)."""
    price = np.exp(logc)
    sma = np.full(len(price), np.nan)
    if len(price) >= w:
        c = np.cumsum(np.insert(price, 0, 0.0))
        sma[w - 1:] = (c[w:] - c[:-w]) / w
    sig = np.where(price > sma, 1, np.where(price < sma, -1, 0))
    return _switch_events(sig)


def momentum(logc: np.ndarray, w: int) -> np.ndarray:
    """Znak zmiany ceny z ostatnich w świec (time-series momentum)."""
    ret = np.full(len(logc), np.nan)
    ret[w:] = logc[w:] - logc[:-w]
    sig = np.where(ret > 0, 1, np.where(ret < 0, -1, 0))
    return _switch_events(sig)


# ============================================================
# POMIAR: wyścig do progu
# ============================================================

def race(logc: np.ndarray, start: np.ndarray, a: float) -> np.ndarray:
    """
    Dla każdej świecy startowej: co pierwsze — zamknięcie o a wyżej (+1)
    czy o a niżej (-1). 0 = do końca danych żadne (pomijane).
    """
    out = np.zeros(len(start), dtype=np.int8)
    n = len(logc)
    for k, t in enumerate(start):
        up, dn = logc[t] + a, logc[t] - a
        s = t + 1
        step = 64
        while s < n:
            seg = logc[s:s + step]
            hit_up = np.flatnonzero(seg >= up)
            hit_dn = np.flatnonzero(seg <= dn)
            iu = hit_up[0] if len(hit_up) else None
            idn = hit_dn[0] if len(hit_dn) else None
            if iu is not None or idn is not None:
                if idn is None or (iu is not None and iu < idn):
                    out[k] = 1
                else:
                    out[k] = -1
                break
            s += step
            step *= 2
    return out


def variance_ratio(logret: np.ndarray, q: int) -> float:
    """VR(q) = wariancja zmian q-świecowych / (q · wariancja zmian 1-świecowych)."""
    r = logret - logret.mean()
    if len(r) <= q * 2:
        return np.nan
    c = np.cumsum(np.insert(r, 0, 0.0))
    rq = c[q:] - c[:-q]
    return float(np.mean(rq ** 2) / (q * np.mean(r ** 2)))


def sign_flip(logret: np.ndarray, rng) -> np.ndarray:
    """
    Kontrola „moneta”: każdy dzień zostaje na miejscu z tą samą wielkością
    ruchu (od średniej), kierunek losowany ±1. Średni dryf zostaje.
    """
    mu = logret.mean()
    eps = rng.choice(np.array([-1.0, 1.0]), size=len(logret))
    return mu + eps * (logret - mu)
