
from collections.abc import Callable

import numpy as np
import pandas as pd

from tick_engine import TickExecutionEngine, build_bars


def _find_exit(
    side: str,
    stop_loss: float | None,
    take_profit: float | None,
    bid: np.ndarray,
    ask: np.ndarray,
    start: int,
) -> tuple[int, str | None]:
    """
    Zwraca indeks pierwszego ticku od `start`, na którym zadziała
    SL lub TP, oraz powód zamknięcia. (-1, None), jeśli żaden.

    Szuka w rosnących oknach, aby nie przeglądać całej tablicy
    dla transakcji zamykanych po kilku tickach.
    """
    if stop_loss is None and take_profit is None:
        return -1, None

    n = len(bid)
    pos = start
    window = 4096

    while pos < n:
        stop = min(n, pos + window)
        prices = bid[pos:stop] if side == "long" else ask[pos:stop]

        if side == "long":
            hit_sl = (
                prices <= stop_loss
                if stop_loss is not None
                else np.zeros(len(prices), dtype=bool)
            )
            hit_tp = (
                prices >= take_profit
                if take_profit is not None
                else np.zeros(len(prices), dtype=bool)
            )
        else:
            hit_sl = (
                prices >= stop_loss
                if stop_loss is not None
                else np.zeros(len(prices), dtype=bool)
            )
            hit_tp = (
                prices <= take_profit
                if take_profit is not None
                else np.zeros(len(prices), dtype=bool)
            )

        hit = hit_sl | hit_tp

        if hit.any():
            k = int(hit.argmax())
            # Na tym samym ticku SL ma pierwszeństwo przed TP.
            reason = "stop_loss" if hit_sl[k] else "take_profit"
            return pos + k, reason

        pos = stop
        window *= 2

    return -1, None


def run_backtest(
    tick_source: Callable,
    strategy: Callable[[pd.DataFrame], pd.DataFrame],
    timeframe: str = "5min",
    initial_capital: float = 10_000.0,
    commission: float = 0.0005,
    slippage_ticks: int = 1,
    tick_size: float = 0.01,
    risk_per_trade: float = 0.01,
    fixed_quantity: float = 1.0,
    trade_start=None,
    opposite_signal: str = "ignore",
    same_signal: str = "ignore",
) -> dict:
    """
    Backtest strategii na tickach Bid/Ask.

    tick_source() musi zwracać nowy iterator ticków przy każdym
    wywołaniu.

    Strategia otrzymuje świece Bid OHLC i zwraca kolumny:
    buy, sell oraz opcjonalnie stop_loss i take_profit.

    Sygnał jest wykonywany na pierwszym dostępnym ticku
    po zamknięciu świecy sygnałowej.

    trade_start: opcjonalny początek handlu, np. START_DATE.
    Ticki i świece wcześniejsze służą tylko do rozgrzania
    wskaźników — przed tą chwilą nie otwieramy pozycji.

    Sygnał przy otwartej pozycji (odpowiedniki Pine Script):
    opposite_signal="reverse" — przeciwny sygnał zamyka pozycję
        i otwiera odwrotną (strategy.entry w drugą stronę),
    same_signal="update_exits" — sygnał w tę samą stronę nie
        dokłada pozycji, ale przestawia jej SL i TP (ponowne
        strategy.exit z tym samym id),
    "ignore" — sygnał jest pomijany.

    Zamiast przechodzić w Pythonie przez każdy tick, silnik
    wyszukuje na tablicach numpy tylko ticki, na których coś
    się dzieje: wejście po sygnale oraz pierwsze trafienie SL/TP.
    Wynik jest taki sam jak przy przetwarzaniu tick po ticku.
    """

    engine = TickExecutionEngine(
        initial_capital=initial_capital,
        commission=commission,
        slippage_ticks=slippage_ticks,
        tick_size=tick_size,
        risk_per_trade=risk_per_trade,
    )

    # ========================================================
    # 1. Wczytanie ticków do pamięci
    # ========================================================

    chunks = [chunk for chunk in tick_source() if not chunk.empty]

    if not chunks:
        raise ValueError("Nie udało się utworzyć świec z ticków.")

    ticks = pd.concat(chunks, ignore_index=True)
    ticks = ticks.sort_values("timestamp", kind="stable")
    ticks = ticks.reset_index(drop=True)

    # ========================================================
    # 2. Budowa świec i generowanie sygnałów
    # ========================================================

    bars = build_bars([ticks], timeframe)

    if bars.empty:
        raise ValueError("Nie udało się utworzyć świec z ticków.")

    signals = strategy(bars.copy())

    if not signals.index.equals(bars.index):
        raise ValueError(
            "Indeks sygnałów musi być identyczny z indeksem świec."
        )

    if not {"buy", "sell"}.issubset(signals.columns):
        raise ValueError(
            "Strategia musi zwracać kolumny 'buy' i 'sell'."
        )

    # Zdarzenia tworzymy tylko dla świec z sygnałem — pozostałe
    # i tak byłyby pominięte w pętli egzekucji.
    buy = signals["buy"].astype(bool).to_numpy()
    sell = signals["sell"].astype(bool).to_numpy()
    close_times = bars.index + pd.Timedelta(timeframe)
    stop_losses = (
        signals["stop_loss"].to_numpy()
        if "stop_loss" in signals.columns
        else None
    )
    take_profits = (
        signals["take_profit"].to_numpy()
        if "take_profit" in signals.columns
        else None
    )

    signal_events = []

    for i in np.flatnonzero(buy | sell):
        signal_events.append(
            {
                "time": close_times[i],
                "buy": bool(buy[i]),
                "sell": bool(sell[i]),
                "stop_loss": (
                    stop_losses[i]
                    if stop_losses is not None
                    else None
                ),
                "take_profit": (
                    take_profits[i]
                    if take_profits is not None
                    else None
                ),
            }
        )

    signal_events.sort(key=lambda event: event["time"])

    # ========================================================
    # 3. Egzekucja na tickach
    # ========================================================

    valid = (ticks["bid"] > 0) & (ticks["ask"] >= ticks["bid"])
    ticks = ticks.loc[valid].reset_index(drop=True)

    timestamps = ticks["timestamp"].to_numpy()

    if trade_start is not None:
        trade_start = (
            pd.Timestamp(trade_start)
            .to_datetime64()
            .astype(timestamps.dtype)
        )
    bids = ticks["bid"].to_numpy(dtype=float)
    asks = ticks["ask"].to_numpy(dtype=float)
    n_ticks = len(ticks)

    def tick_at(i: int) -> tuple[pd.Timestamp, float, float]:
        return (
            pd.Timestamp(timestamps[i]),
            float(bids[i]),
            float(asks[i]),
        )

    # Indeks ticku, na którym otwarta pozycja zostanie zamknięta
    # przez SL/TP (-1: do końca danych).
    exit_index = -1
    exit_reason = None

    # Dla krzywej kapitału: (indeks wejścia, indeks wyjścia).
    # Wyjście na końcu danych zapisujemy jako n_ticks.
    trade_spans = []

    def close_at_exit():
        engine.close_position(*tick_at(exit_index), exit_reason)
        trade_spans[-1][1] = exit_index

    for event in signal_events:
        if not (event["buy"] or event["sell"]):
            continue

        # Pomijamy niejednoznaczny sygnał.
        if event["buy"] and event["sell"]:
            continue

        # Pierwszy tick w chwili zamknięcia świecy lub później.
        i = int(
            np.searchsorted(
                timestamps,
                event["time"].to_datetime64().astype(timestamps.dtype),
                side="left",
            )
        )

        if i >= n_ticks:
            break

        # W okresie rozgrzewki nie otwieramy pozycji.
        if trade_start is not None and timestamps[i] < trade_start:
            continue

        desired_side = "long" if event["buy"] else "short"

        sl = event["stop_loss"]
        tp = event["take_profit"]

        sl = (
            None
            if sl is None or pd.isna(sl)
            else float(sl)
        )
        tp = (
            None
            if tp is None or pd.isna(tp)
            else float(tp)
        )

        # SL/TP sprawdzane są przed sygnałami na tym samym ticku,
        # więc pozycja zamknięta na ticku i zwalnia miejsce.
        if engine.position is not None:
            if exit_index != -1 and exit_index <= i:
                close_at_exit()
            elif engine.position.side == desired_side:
                if same_signal == "update_exits":
                    # Nowe poziomy działają od tego ticku; jeśli są
                    # już przekroczone, pozycja zamyka się od razu.
                    engine.position.stop_loss = sl
                    engine.position.take_profit = tp
                    exit_index, exit_reason = _find_exit(
                        desired_side, sl, tp, bids, asks, i
                    )
                continue
            elif opposite_signal == "reverse":
                engine.close_position(*tick_at(i), "reverse")
                trade_spans[-1][1] = i
            else:
                # Zgodnie z Pine Script wchodzimy tylko bez pozycji.
                continue

        timestamp, bid, ask = tick_at(i)

        # Weryfikujemy SL i TP względem oczekiwanej ceny wejścia.
        if desired_side == "long":
            expected_entry = (
                ask + slippage_ticks * tick_size
            )
            valid_sl = sl is None or sl < expected_entry
            valid_tp = tp is None or tp > expected_entry
        else:
            expected_entry = (
                bid - slippage_ticks * tick_size
            )
            valid_sl = sl is None or sl > expected_entry
            valid_tp = tp is None or tp < expected_entry

        if not valid_sl or not valid_tp:
            continue

        # Nie otwieramy pozycji, jeżeli SL jest już naruszony.
        if (
            desired_side == "long"
            and sl is not None
            and bid <= sl
        ):
            continue

        if (
            desired_side == "short"
            and sl is not None
            and ask >= sl
        ):
            continue

        # Wielkość pozycji: 1% kapitału ryzykowanego przy SL.
        if sl is not None:
            quantity = engine.calculate_position_size(
                side=desired_side,
                bid=bid,
                ask=ask,
                stop_loss=sl,
            )
        else:
            quantity = fixed_quantity

        if quantity <= 0:
            continue

        engine.open_position(
            side=desired_side,
            timestamp=timestamp,
            bid=bid,
            ask=ask,
            quantity=quantity,
            stop_loss=sl,
            take_profit=tp,
        )
        trade_spans.append([i, n_ticks])

        # SL/TP sprawdzamy od następnego ticku po wejściu.
        exit_index, exit_reason = _find_exit(
            desired_side, sl, tp, bids, asks, i + 1
        )

    # ========================================================
    # 4. Zamknięcie pozycji na końcu dostępnych danych
    # ========================================================

    closed_at_end = False

    if engine.position is not None and exit_index != -1:
        close_at_exit()

    if engine.position is not None and n_ticks > 0:
        engine.close_position(*tick_at(n_ticks - 1), "end_of_data")
        closed_at_end = True

    # ========================================================
    # 5. Krzywa kapitału
    # ========================================================

    engine.equity_curve = _equity_curve(
        engine,
        timestamps,
        bids,
        asks,
        timeframe,
        trade_spans,
    )

    if closed_at_end:
        # Zapis końcowego stanu po zamknięciu pozycji.
        engine.record_equity(*tick_at(n_ticks - 1))

    # ========================================================
    # 6. Wyniki
    # ========================================================

    return {
        "bars": bars,
        "trades": pd.DataFrame(engine.trades),
        "equity": pd.DataFrame(engine.equity_curve),
        "stats": engine.get_results(),
    }


def _equity_curve(
    engine: TickExecutionEngine,
    timestamps: np.ndarray,
    bids: np.ndarray,
    asks: np.ndarray,
    timeframe: str,
    trade_spans: list,
) -> list[dict]:
    """
    Kapitał wraz z niezrealizowanym wynikiem, zapisywany na
    pierwszym ticku każdego interwału (po jego przetworzeniu).
    """
    if len(timestamps) == 0:
        return []

    unit = np.datetime_data(timestamps.dtype)[0]
    step = pd.Timedelta(timeframe) // pd.Timedelta(1, unit=unit)
    keys = timestamps.astype("int64") // step
    sample = np.flatnonzero(
        np.concatenate(([True], keys[1:] != keys[:-1]))
    )

    # Zmiany kapitału zrealizowanego w kolejności ticków.
    # Na tym samym ticku zamknięcie następuje przed wejściem.
    changes = []

    for trade, (entry_index, exit_index) in zip(
        engine.trades, trade_spans
    ):
        changes.append(
            (entry_index, 1, -trade["entry_commission"])
        )
        changes.append(
            (
                exit_index,
                0,
                trade["gross_pnl"] - trade["exit_commission"],
            )
        )

    changes.sort(key=lambda change: (change[0], change[1]))

    change_index = np.array([c[0] for c in changes], dtype=np.int64)
    capital_path = np.cumsum(
        [engine.initial_capital] + [c[2] for c in changes]
    )

    capital = capital_path[
        np.searchsorted(change_index, sample, side="right")
    ]
    equity = capital.astype(float)

    for trade, (entry_index, exit_index) in zip(
        engine.trades, trade_spans
    ):
        first = np.searchsorted(sample, entry_index, side="left")
        last = np.searchsorted(sample, exit_index, side="left")

        if first >= last:
            continue

        points = sample[first:last]

        if trade["side"] == "long":
            unrealized = (
                bids[points] - trade["entry_price"]
            ) * trade["quantity"]
        else:
            unrealized = (
                trade["entry_price"] - asks[points]
            ) * trade["quantity"]

        equity[first:last] = equity[first:last] + unrealized

    times = pd.DatetimeIndex(timestamps[sample])

    return [
        {"timestamp": time, "equity": float(value)}
        for time, value in zip(times, equity)
    ]
