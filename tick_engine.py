
import pandas as pd

from dataclasses import dataclass
from typing import Literal


# ============================================================
# 1. GENEROWANIE ŚWIEC OHLC Z TICKÓW
# ============================================================

def build_bars(tick_chunks, timeframe: str) -> pd.DataFrame:
    """
    Generuje świece OHLC na podstawie cen Bid oraz kolumnę volume:
    liczbę ticków w świecy (wolumen tickowy, jak w TradingView
    dla rynków bez wolumenu giełdowego).

    tick_chunks: iterator DataFrame z kolumnami timestamp, bid, ask.
    timeframe: np. '1min', '5min', '15min', '30min', '1h'.

    Przetwarza dane partiami i zachowuje ticki ostatniej,
    potencjalnie niekompletnej świecy do kolejnej partii.
    """
    completed = []
    pending = None

    for chunk in tick_chunks:
        if chunk.empty:
            continue

        if pending is not None:
            chunk = pd.concat([pending, chunk], ignore_index=True)

        # Sortujemy tylko w razie potrzeby i budujemy indeks z samej
        # kolumny bid — przy setkach milionów ticków każda kopia
        # całej tabeli to kilka GB pamięci.
        if not chunk["timestamp"].is_monotonic_increasing:
            chunk = chunk.sort_values("timestamp", kind="stable")

        chunk = pd.Series(
            chunk["bid"].to_numpy(),
            index=pd.DatetimeIndex(chunk["timestamp"]),
            name="bid",
        ).rename_axis("timestamp")
        grouped = _ohlc_volume(chunk, timeframe)

        if grouped.empty:
            pending = chunk.reset_index()
            continue

        last_bar_start = grouped.index[-1]
        pending = chunk.loc[chunk.index >= last_bar_start].reset_index()

        finished_bars = grouped.iloc[:-1]
        if not finished_bars.empty:
            completed.append(finished_bars)

    if pending is not None and not pending.empty:
        final = _ohlc_volume(
            pending.set_index("timestamp")["bid"], timeframe
        )
        if not final.empty:
            completed.append(final)

    if not completed:
        return pd.DataFrame(
            columns=["open", "high", "low", "close", "volume"]
        )

    result = pd.concat(completed)
    result = result[~result.index.duplicated(keep="last")]
    return result.sort_index()


def _ohlc_volume(bid: pd.Series, timeframe: str) -> pd.DataFrame:
    """Świece OHLC z cen Bid i liczba ticków; bez pustych świec."""
    resampled = bid.resample(timeframe)
    bars = resampled.ohlc()
    bars["volume"] = resampled.count().astype(float)
    return bars.dropna()


# ============================================================
# 2. MODEL OTWARTEJ POZYCJI
# ============================================================

@dataclass
class Position:
    side: Literal["long", "short"]
    quantity: float
    entry_price: float
    entry_time: pd.Timestamp
    entry_commission: float
    stop_loss: float | None = None
    take_profit: float | None = None


# ============================================================
# 3. SILNIK EGZEKUCJI TRANSAKCJI
# ============================================================

class TickExecutionEngine:
    """
    Bazowa egzekucja na rzeczywistych tickach Bid/Ask.

    Long: wejście Ask, wyjście Bid.
    Short: wejście Bid, wyjście Ask.

    Prowizja: 0,05% wartości każdej strony.
    Poślizg: liczba ticków * tick_size.

    Wielkość pozycji jest na razie podawana jawnie.
    """

    def __init__(
        self,
        initial_capital: float = 10_000.0,
        commission: float = 0.0005,
        slippage_ticks: int = 1,
        tick_size: float = 0.01,
        risk_per_trade: float = 0.01,
    ):
        if initial_capital <= 0:
            raise ValueError("Kapitał początkowy musi być dodatni.")
        if commission < 0 or slippage_ticks < 0:
            raise ValueError("Prowizja i poślizg nie mogą być ujemne.")
        if tick_size <= 0:
            raise ValueError("tick_size musi być dodatni.")
        if not 0 < risk_per_trade <= 1:
            raise ValueError("risk_per_trade musi należeć do (0, 1].")

        self.initial_capital = float(initial_capital)
        self.capital = float(initial_capital)
        self.commission = float(commission)
        self.slippage_ticks = int(slippage_ticks)
        self.tick_size = float(tick_size)
        self.risk_per_trade = float(risk_per_trade)

        self.position: Position | None = None
        self.trades: list[dict] = []
        self.equity_curve: list[dict] = []

    @property
    def slippage(self) -> float:
        return self.slippage_ticks * self.tick_size

    def _commission(self, price: float, quantity: float) -> float:
        return abs(price * quantity) * self.commission
    
    def calculate_position_size(
        self,
        side: Literal["long", "short"],
        bid: float,
        ask: float,
        stop_loss: float,
    ) -> float:
        if self.position is not None:
            raise RuntimeError("Pozycja jest już otwarta.")

        if bid <= 0 or ask < bid or stop_loss <= 0:
            raise ValueError("Nieprawidłowe ceny lub stop loss.")

        if side == "long":
            entry_price = ask + self.slippage
            stop_exit_price = stop_loss - self.slippage

            if stop_loss >= entry_price:
                raise ValueError("SL dla long musi być poniżej wejścia.")

            price_loss = entry_price - stop_exit_price

        elif side == "short":
            entry_price = bid - self.slippage
            stop_exit_price = stop_loss + self.slippage

            if stop_loss <= entry_price:
                raise ValueError("SL dla short musi być powyżej wejścia.")

            price_loss = stop_exit_price - entry_price

        else:
            raise ValueError("Nieprawidłowy kierunek pozycji.")

        fees = (
            entry_price * self.commission
            + stop_exit_price * self.commission
        )
        risk_per_unit = price_loss + fees

        if risk_per_unit <= 0:
            raise ValueError("Nieprawidłowe ryzyko na jednostkę.")

        risk_budget = self.capital * self.risk_per_trade
        return risk_budget / risk_per_unit

    
    def open_position(
        self,
        side: Literal["long", "short"],
        timestamp,
        bid: float,
        ask: float,
        quantity: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> Position:
        if self.position is not None:
            raise RuntimeError("Pozycja jest już otwarta.")
        if side not in ("long", "short"):
            raise ValueError("side musi być 'long' albo 'short'.")
        if bid <= 0 or ask < bid:
            raise ValueError("Nieprawidłowe ceny Bid/Ask.")
        if quantity <= 0:
            raise ValueError("quantity musi być dodatnie.")

        if side == "long":
            entry_price = ask + self.slippage
            if stop_loss is not None and stop_loss >= entry_price:
                raise ValueError("SL dla long musi być poniżej wejścia.")
            if take_profit is not None and take_profit <= entry_price:
                raise ValueError("TP dla long musi być powyżej wejścia.")
        else:
            entry_price = bid - self.slippage
            if stop_loss is not None and stop_loss <= entry_price:
                raise ValueError("SL dla short musi być powyżej wejścia.")
            if take_profit is not None and take_profit >= entry_price:
                raise ValueError("TP dla short musi być poniżej wejścia.")

        entry_commission = self._commission(entry_price, quantity)
        self.capital -= entry_commission

        self.position = Position(
            side=side,
            quantity=float(quantity),
            entry_price=float(entry_price),
            entry_time=pd.Timestamp(timestamp),
            entry_commission=entry_commission,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
        return self.position


    def close_position(
        self,
        timestamp,
        bid: float,
        ask: float,
        reason: str = "signal",
    ) -> dict:
        if self.position is None:
            raise RuntimeError("Brak otwartej pozycji.")
        if bid <= 0 or ask < bid:
            raise ValueError("Nieprawidłowe ceny Bid/Ask.")

        pos = self.position

        if pos.side == "long":
            exit_price = bid - self.slippage
            gross_pnl = (exit_price - pos.entry_price) * pos.quantity
        else:
            exit_price = ask + self.slippage
            gross_pnl = (pos.entry_price - exit_price) * pos.quantity

        exit_commission = self._commission(exit_price, pos.quantity)
        net_pnl = gross_pnl - pos.entry_commission - exit_commission

        self.capital += gross_pnl - exit_commission

        # Szacowana strata, gdyby SL został wykonany na poziomie
        # stop loss z uwzględnieniem skonfigurowanego poślizgu.
        planned_loss_at_sl = None
        stop_gap = 0.0

        if pos.stop_loss is not None:
            if pos.side == "long":
                planned_exit = pos.stop_loss - self.slippage
                stop_gap = max(0.0, planned_exit - exit_price)
                planned_gross_loss = (
                    pos.entry_price - planned_exit
                ) * pos.quantity
            else:
                planned_exit = pos.stop_loss + self.slippage
                stop_gap = max(0.0, exit_price - planned_exit)
                planned_gross_loss = (
                    planned_exit - pos.entry_price
                ) * pos.quantity

            planned_exit_commission = self._commission(
                planned_exit, pos.quantity
            )

            planned_loss_at_sl = (
                planned_gross_loss
                + pos.entry_commission
                + planned_exit_commission
            )

        trade = {
            "side": pos.side,
            "entry_time": pos.entry_time,
            "exit_time": pd.Timestamp(timestamp),
            "quantity": pos.quantity,
            "entry_price": pos.entry_price,
            "exit_price": float(exit_price),
            "stop_loss": pos.stop_loss,
            "take_profit": pos.take_profit,
            "stop_gap": float(stop_gap),
            "planned_loss_at_sl": (
                float(planned_loss_at_sl)
                if planned_loss_at_sl is not None
                else None
            ),
            "gross_pnl": float(gross_pnl),
            "entry_commission": float(pos.entry_commission),
            "exit_commission": float(exit_commission),
            "net_pnl": float(net_pnl),
            "capital": float(self.capital),
            "reason": reason,
        }

        self.trades.append(trade)
        self.position = None
        return trade


    def check_stops(
        self,
        timestamp,
        bid: float,
        ask: float,
    ) -> dict | None:
        """Sprawdza SL/TP na bieżącym ticku."""
        pos = self.position
        if pos is None:
            return None

        if pos.side == "long":
            if pos.stop_loss is not None and bid <= pos.stop_loss:
                return self.close_position(timestamp, bid, ask, "stop_loss")
            if pos.take_profit is not None and bid >= pos.take_profit:
                return self.close_position(timestamp, bid, ask, "take_profit")
        else:
            if pos.stop_loss is not None and ask >= pos.stop_loss:
                return self.close_position(timestamp, bid, ask, "stop_loss")
            if pos.take_profit is not None and ask <= pos.take_profit:
                return self.close_position(timestamp, bid, ask, "take_profit")

        return None

    def record_equity(self, timestamp, bid: float, ask: float) -> float:
        """Zapisuje kapitał wraz z niezrealizowanym wynikiem pozycji."""
        equity = self.capital

        if self.position is not None:
            pos = self.position
            if pos.side == "long":
                unrealized = (bid - pos.entry_price) * pos.quantity
            else:
                unrealized = (pos.entry_price - ask) * pos.quantity

            equity += unrealized

        self.equity_curve.append({
            "timestamp": pd.Timestamp(timestamp),
            "equity": float(equity),
        })
        return float(equity)

   
    def get_results(self) -> dict:
        """Statystyki zamkniętych transakcji i obsunięcia kapitału."""
        trades = pd.DataFrame(self.trades)

        result = {
            "initial_capital": self.initial_capital,
            "final_capital": self.capital,
            "net_profit": self.capital - self.initial_capital,
            "return_pct": (self.capital / self.initial_capital - 1) * 100,
            "trades": len(trades),
            "win_rate_pct": 0.0,
            "profit_factor": None,
            "max_drawdown_pct": 0.0,
        }

        if not trades.empty:
            wins = trades.loc[trades["net_pnl"] > 0, "net_pnl"].sum()
            losses = trades.loc[trades["net_pnl"] < 0, "net_pnl"].sum()

            result["win_rate_pct"] = (
                trades["net_pnl"].gt(0).mean() * 100
            )

            result["profit_factor"] = (
                float(wins / abs(losses))
                if losses < 0
                else (float("inf") if wins > 0 else None)
            )

        if self.equity_curve:
            equity = pd.Series(
                [point["equity"] for point in self.equity_curve],
                dtype=float,
            )

            # Uwzględnij kapitał początkowy przy obliczaniu szczytu.
            equity = pd.concat(
                [pd.Series([self.initial_capital]), equity],
                ignore_index=True,
            )

            peaks = equity.cummax()
            drawdown = (equity / peaks - 1.0) * 100.0
            result["max_drawdown_pct"] = float(drawdown.min())

        return result

