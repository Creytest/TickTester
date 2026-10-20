
from collections.abc import Callable

import pandas as pd

from tick_engine import TickExecutionEngine, build_bars


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
) -> dict:
    """
    Backtest strategii na tickach Bid/Ask.

    tick_source() musi zwracać nowy iterator ticków przy każdym
    wywołaniu.

    Strategia otrzymuje świece Bid OHLC i zwraca kolumny:
    buy, sell oraz opcjonalnie stop_loss i take_profit.

    Sygnał jest wykonywany na pierwszym dostępnym ticku
    po zamknięciu świecy sygnałowej.
    """

    engine = TickExecutionEngine(
        initial_capital=initial_capital,
        commission=commission,
        slippage_ticks=slippage_ticks,
        tick_size=tick_size,
        risk_per_trade=risk_per_trade,
    )

    # ========================================================
    # 1. Budowa świec i generowanie sygnałów
    # ========================================================

    bars = build_bars(tick_source(), timeframe)

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

    signal_events = []

    for i, bar_start in enumerate(bars.index):
        signal_events.append(
            {
                "time": bar_start + pd.Timedelta(timeframe),
                "buy": bool(signals["buy"].iloc[i]),
                "sell": bool(signals["sell"].iloc[i]),
                "stop_loss": (
                    signals["stop_loss"].iloc[i]
                    if "stop_loss" in signals.columns
                    else None
                ),
                "take_profit": (
                    signals["take_profit"].iloc[i]
                    if "take_profit" in signals.columns
                    else None
                ),
            }
        )

    signal_events.sort(key=lambda event: event["time"])
    event_index = 0

    # ========================================================
    # 2. Egzekucja na tickach
    # ========================================================

    current_bar = None
    last_tick = None

    for chunk in tick_source():
        if chunk.empty:
            continue

        for tick in chunk.itertuples(index=False):
            timestamp = pd.Timestamp(tick.timestamp)
            bid = float(tick.bid)
            ask = float(tick.ask)

            if bid <= 0 or ask < bid:
                continue

            last_tick = {
                "timestamp": timestamp,
                "bid": bid,
                "ask": ask,
            }

            # Najpierw sprawdzamy SL/TP istniejącej pozycji.
            engine.check_stops(timestamp, bid, ask)

            # Obsługujemy sygnały, których świece już się zamknęły.
            while (
                event_index < len(signal_events)
                and signal_events[event_index]["time"] <= timestamp
            ):
                event = signal_events[event_index]
                event_index += 1

                if not (event["buy"] or event["sell"]):
                    continue

                # Pomijamy niejednoznaczny sygnał.
                if event["buy"] and event["sell"]:
                    continue

                # Zgodnie z Pine Script wchodzimy tylko bez pozycji.
                if engine.position is not None:
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

            # Zapis equity raz na interwał.
            bar_key = timestamp.floor(timeframe)

            if bar_key != current_bar:
                engine.record_equity(timestamp, bid, ask)
                current_bar = bar_key

    # ========================================================
    # 3. Zamknięcie pozycji na końcu dostępnych danych
    # ========================================================

    if engine.position is not None and last_tick is not None:
        engine.close_position(
            timestamp=last_tick["timestamp"],
            bid=last_tick["bid"],
            ask=last_tick["ask"],
            reason="end_of_data",
        )

        # Zapis końcowego stanu po zamknięciu pozycji.
        engine.record_equity(
            last_tick["timestamp"],
            last_tick["bid"],
            last_tick["ask"],
        )

    # ========================================================
    # 4. Wyniki
    # ========================================================

    return {
        "bars": bars,
        "trades": pd.DataFrame(engine.trades),
        "equity": pd.DataFrame(engine.equity_curve),
        "stats": engine.get_results(),
    }
