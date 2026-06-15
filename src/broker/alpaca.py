from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

from src.data.market_data import Bar


@dataclass
class Position:
    symbol: str
    qty: float
    avg_entry_price: float
    current_price: float
    unrealized_pl: float
    unrealized_plpc: float


@dataclass
class OrderResult:
    id: str
    symbol: str
    side: str
    qty: float
    status: str


class AlpacaBroker:
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.trading = TradingClient(api_key, secret_key, paper=paper)
        self.data = StockHistoricalDataClient(api_key, secret_key)

    def get_account(self) -> dict:
        account = self.trading.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "daytrade_count": int(account.daytrade_count),
        }

    def get_positions(self) -> list[Position]:
        positions = []
        for pos in self.trading.get_all_positions():
            positions.append(
                Position(
                    symbol=pos.symbol,
                    qty=float(pos.qty),
                    avg_entry_price=float(pos.avg_entry_price),
                    current_price=float(pos.current_price),
                    unrealized_pl=float(pos.unrealized_pl),
                    unrealized_plpc=float(pos.unrealized_plpc),
                )
            )
        return positions

    def get_position(self, symbol: str) -> Optional[Position]:
        try:
            pos = self.trading.get_open_position(symbol)
            return Position(
                symbol=pos.symbol,
                qty=float(pos.qty),
                avg_entry_price=float(pos.avg_entry_price),
                current_price=float(pos.current_price),
                unrealized_pl=float(pos.unrealized_pl),
                unrealized_plpc=float(pos.unrealized_plpc),
            )
        except Exception:
            return None

    def submit_market_order(self, symbol: str, qty: int, side: str) -> OrderResult:
        order_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        request = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )
        order = self.trading.submit_order(request)
        return OrderResult(
            id=str(order.id),
            symbol=order.symbol,
            side=order.side.value,
            qty=float(order.qty),
            status=order.status.value,
        )

    def close_position(self, symbol: str) -> Optional[OrderResult]:
        try:
            order = self.trading.close_position(symbol)
            return OrderResult(
                id=str(order.id),
                symbol=order.symbol,
                side=order.side.value,
                qty=float(order.qty),
                status=order.status.value,
            )
        except Exception:
            return None

    def close_all_positions(self) -> list[OrderResult]:
        results = []
        try:
            orders = self.trading.close_all_positions(cancel_orders=True)
            for order in orders:
                results.append(
                    OrderResult(
                        id=str(order.id),
                        symbol=order.symbol,
                        side=order.side.value,
                        qty=float(order.qty),
                        status=order.status.value,
                    )
                )
        except Exception:
            pass
        return results

    def get_bars(self, symbol: str, timeframe: str, limit: int) -> list[Bar]:
        tf = self._parse_timeframe(timeframe)
        request = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf, limit=limit)
        bars_response = self.data.get_stock_bars(request)

        bars = []
        if symbol not in bars_response.data:
            return bars

        for bar in bars_response.data[symbol]:
            bars.append(
                Bar(
                    symbol=symbol,
                    timestamp=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                )
            )
        return bars

    @staticmethod
    def _parse_timeframe(timeframe: str) -> TimeFrame:
        mapping = {
            "1Min": TimeFrame(1, TimeFrameUnit.Minute),
            "5Min": TimeFrame(5, TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
            "1Day": TimeFrame(1, TimeFrameUnit.Day),
        }
        if timeframe not in mapping:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return mapping[timeframe]