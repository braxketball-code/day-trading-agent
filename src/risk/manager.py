from dataclasses import dataclass

from src.broker.alpaca import Position
from src.strategy.base import Signal


@dataclass
class TradeDecision:
    approved: bool
    qty: int
    reason: str


class RiskManager:
    def __init__(
        self,
        max_position_pct: float = 0.10,
        max_open_positions: int = 3,
        stop_loss_pct: float = 0.015,
        take_profit_pct: float = 0.03,
        max_daily_loss_pct: float = 0.03,
        min_trade_value: float = 100,
    ):
        self.max_position_pct = max_position_pct
        self.max_open_positions = max_open_positions
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.min_trade_value = min_trade_value
        self._starting_equity: float | None = None

    def set_starting_equity(self, equity: float) -> None:
        if self._starting_equity is None:
            self._starting_equity = equity

    def daily_loss_exceeded(self, current_equity: float) -> bool:
        if self._starting_equity is None:
            return False
        loss_pct = (self._starting_equity - current_equity) / self._starting_equity
        return loss_pct >= self.max_daily_loss_pct

    def evaluate_entry(
        self,
        signal: Signal,
        symbol: str,
        price: float,
        equity: float,
        open_positions: list[Position],
        existing_position: Position | None,
    ) -> TradeDecision:
        if signal != Signal.BUY:
            return TradeDecision(False, 0, "Not a buy signal")

        if existing_position and existing_position.qty > 0:
            return TradeDecision(False, 0, f"Already holding {symbol}")

        if len(open_positions) >= self.max_open_positions:
            return TradeDecision(False, 0, "Max open positions reached")

        position_value = equity * self.max_position_pct
        if position_value < self.min_trade_value:
            return TradeDecision(False, 0, "Position value below minimum")

        qty = int(position_value / price)
        if qty < 1:
            return TradeDecision(False, 0, "Cannot afford 1 share")

        return TradeDecision(True, qty, f"Approved: {qty} shares @ ${price:.2f}")

    def evaluate_exit(self, position: Position) -> TradeDecision:
        if position.unrealized_plpc <= -self.stop_loss_pct:
            return TradeDecision(
                True,
                int(abs(position.qty)),
                f"Stop loss hit ({position.unrealized_plpc:.2%})",
            )

        if position.unrealized_plpc >= self.take_profit_pct:
            return TradeDecision(
                True,
                int(abs(position.qty)),
                f"Take profit hit ({position.unrealized_plpc:.2%})",
            )

        return TradeDecision(False, 0, "Hold position")