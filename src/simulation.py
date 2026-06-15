import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.broker.alpaca import Position
from src.data.market_data import Bar
from src.risk.manager import RiskManager
from src.strategy.base import Signal
from src.strategy.momentum import MomentumRSIStrategy
from src.utils.logger import setup_logger


BASE_PRICES = {
    "SPY": 520.0,
    "QQQ": 440.0,
    "AAPL": 185.0,
    "MSFT": 420.0,
    "NVDA": 125.0,
    "AMD": 160.0,
    "TSLA": 250.0,
    "META": 520.0,
}


@dataclass
class SimTrade:
    symbol: str
    side: str
    qty: int
    price: float
    timestamp: datetime
    reason: str
    pnl: float = 0.0


@dataclass
class SimulationResult:
    starting_equity: float
    ending_equity: float
    total_pnl: float
    total_return_pct: float
    trades: list[SimTrade]
    wins: int
    losses: int
    symbols_scanned: int
    bars_processed: int


class SimulationEngine:
    def __init__(self, settings: dict, starting_equity: float = 100_000.0, seed: int = 42):
        self.settings = settings
        self.starting_equity = starting_equity
        self.seed = seed
        self.logger = setup_logger("simulation")

        strategy_cfg = settings["strategy"]
        self.strategy = MomentumRSIStrategy(
            ema_fast=strategy_cfg["ema_fast"],
            ema_slow=strategy_cfg["ema_slow"],
            rsi_period=strategy_cfg["rsi_period"],
            rsi_oversold=strategy_cfg["rsi_oversold"],
            rsi_overbought=strategy_cfg["rsi_overbought"],
        )

        risk_cfg = settings["risk"]
        self.risk = RiskManager(
            max_position_pct=risk_cfg["max_position_pct"],
            max_open_positions=risk_cfg["max_open_positions"],
            stop_loss_pct=risk_cfg["stop_loss_pct"],
            take_profit_pct=risk_cfg["take_profit_pct"],
            max_daily_loss_pct=risk_cfg["max_daily_loss_pct"],
            min_trade_value=risk_cfg["min_trade_value"],
        )

        self.watchlist = settings["watchlist"]
        self.lookback_bars = strategy_cfg["lookback_bars"]
        self.cash = starting_equity
        self.holdings: dict[str, dict] = {}
        self.trades: list[SimTrade] = []

    def run(self, days: int = 1) -> SimulationResult:
        self.logger.info("Starting simulation (synthetic market data)")
        self.logger.info(f"Starting equity: ${self.starting_equity:,.2f}")
        self.logger.info(f"Watchlist: {', '.join(self.watchlist)}")

        tz = ZoneInfo(self.settings["market"]["timezone"])
        session_start = datetime(2026, 6, 10, 9, 30, tzinfo=tz)
        bars_per_day = 78
        total_bars = self.lookback_bars + bars_per_day * days

        market_data: dict[str, list[Bar]] = {}
        for i, symbol in enumerate(self.watchlist):
            market_data[symbol] = self._generate_bars(
                symbol,
                BASE_PRICES.get(symbol, 100.0),
                total_bars,
                session_start,
                seed=self.seed + i,
            )

        self.risk.set_starting_equity(self.starting_equity)
        bars_processed = 0

        for bar_idx in range(self.lookback_bars, total_bars):
            timestamp = market_data[self.watchlist[0]][bar_idx].timestamp
            equity = self._equity(market_data, bar_idx)

            if self.risk.daily_loss_exceeded(equity):
                self.logger.warning(f"Daily loss limit hit at bar {bar_idx}")
                self._close_all(market_data, bar_idx, "Daily loss limit")
                break

            self._manage_exits(market_data, bar_idx)

            positions = self._positions(market_data, bar_idx)
            for symbol in self.watchlist:
                bars = market_data[symbol][: bar_idx + 1]
                df = self.strategy.bars_to_dataframe(bars)
                result = self.strategy.analyze(df)
                price = bars[-1].close

                if result.signal == Signal.SELL:
                    if symbol in self.holdings:
                        self._close(symbol, price, timestamp, result.reason)
                    continue

                if result.signal != Signal.BUY or result.confidence < 0.5:
                    continue

                existing = self._position_for(symbol, market_data, bar_idx)
                decision = self.risk.evaluate_entry(
                    result.signal,
                    symbol,
                    price,
                    self._equity(market_data, bar_idx),
                    positions,
                    existing,
                )
                if decision.approved:
                    self._open(symbol, decision.qty, price, timestamp, decision.reason)

            bars_processed += 1

        self._close_all(market_data, total_bars - 1, "End of simulation")

        ending_equity = self.cash
        total_pnl = ending_equity - self.starting_equity
        closed = [t for t in self.trades if t.side == "SELL"]
        wins = sum(1 for t in closed if t.pnl > 0)
        losses = sum(1 for t in closed if t.pnl <= 0)

        return SimulationResult(
            starting_equity=self.starting_equity,
            ending_equity=ending_equity,
            total_pnl=total_pnl,
            total_return_pct=total_pnl / self.starting_equity,
            trades=self.trades,
            wins=wins,
            losses=losses,
            symbols_scanned=len(self.watchlist),
            bars_processed=bars_processed,
        )

    def _generate_bars(
        self,
        symbol: str,
        base_price: float,
        count: int,
        start: datetime,
        seed: int,
    ) -> list[Bar]:
        rng = random.Random(seed)
        bars: list[Bar] = []
        price = base_price
        timestamp = start - timedelta(minutes=5 * self.lookback_bars)

        for i in range(count):
            regime = (i // 25) % 4
            drift = [0.0012, -0.0010, 0.0008, -0.0006][regime]
            noise = rng.gauss(drift, 0.004)
            open_price = price
            close_price = max(price * (1 + noise), 1.0)
            high = max(open_price, close_price) * (1 + abs(rng.gauss(0, 0.002)))
            low = min(open_price, close_price) * (1 - abs(rng.gauss(0, 0.002)))
            volume = rng.uniform(500_000, 2_500_000)

            bars.append(
                Bar(
                    symbol=symbol,
                    timestamp=timestamp,
                    open=round(open_price, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(close_price, 2),
                    volume=volume,
                )
            )
            price = close_price
            timestamp += timedelta(minutes=5)

        return bars

    def _equity(self, market_data: dict[str, list[Bar]], bar_idx: int) -> float:
        equity = self.cash
        for symbol, holding in self.holdings.items():
            price = market_data[symbol][bar_idx].close
            equity += holding["qty"] * price
        return equity

    def _position_for(
        self, symbol: str, market_data: dict[str, list[Bar]], bar_idx: int
    ) -> Position | None:
        if symbol not in self.holdings:
            return None
        holding = self.holdings[symbol]
        price = market_data[symbol][bar_idx].close
        qty = holding["qty"]
        entry = holding["entry"]
        unrealized = (price - entry) * qty
        unrealized_plpc = (price - entry) / entry
        return Position(symbol, qty, entry, price, unrealized, unrealized_plpc)

    def _positions(self, market_data: dict[str, list[Bar]], bar_idx: int) -> list[Position]:
        return [
            pos
            for symbol in self.holdings
            if (pos := self._position_for(symbol, market_data, bar_idx)) is not None
        ]

    def _open(self, symbol: str, qty: int, price: float, timestamp: datetime, reason: str) -> None:
        cost = qty * price
        if cost > self.cash:
            return
        self.cash -= cost
        self.holdings[symbol] = {"qty": qty, "entry": price}
        self.trades.append(SimTrade(symbol, "BUY", qty, price, timestamp, reason))
        self.logger.info(f"BUY  {symbol} x{qty} @ ${price:.2f} — {reason}")

    def _close(self, symbol: str, price: float, timestamp: datetime, reason: str) -> None:
        if symbol not in self.holdings:
            return
        holding = self.holdings.pop(symbol)
        qty = holding["qty"]
        entry = holding["entry"]
        proceeds = qty * price
        pnl = proceeds - qty * entry
        self.cash += proceeds
        self.trades.append(SimTrade(symbol, "SELL", qty, price, timestamp, reason, pnl))
        self.logger.info(f"SELL {symbol} x{qty} @ ${price:.2f} — {reason} (PnL ${pnl:+.2f})")

    def _manage_exits(self, market_data: dict[str, list[Bar]], bar_idx: int) -> None:
        timestamp = market_data[self.watchlist[0]][bar_idx].timestamp
        for symbol in list(self.holdings.keys()):
            position = self._position_for(symbol, market_data, bar_idx)
            if not position:
                continue
            decision = self.risk.evaluate_exit(position)
            if decision.approved:
                price = market_data[symbol][bar_idx].close
                self._close(symbol, price, timestamp, decision.reason)

    def _close_all(self, market_data: dict[str, list[Bar]], bar_idx: int, reason: str) -> None:
        timestamp = market_data[self.watchlist[0]][bar_idx].timestamp
        for symbol in list(self.holdings.keys()):
            price = market_data[symbol][bar_idx].close
            self._close(symbol, price, timestamp, reason)


def print_simulation_report(result: SimulationResult) -> None:
    print("\n" + "=" * 60)
    print("  DAY TRADING AGENT — SIMULATION REPORT")
    print("=" * 60)
    print(f"  Starting Equity:   ${result.starting_equity:>12,.2f}")
    print(f"  Ending Equity:     ${result.ending_equity:>12,.2f}")
    print(f"  Total P&L:         ${result.total_pnl:>+12,.2f}")
    print(f"  Return:            {result.total_return_pct:>+12.2%}")
    print(f"  Bars Processed:    {result.bars_processed:>12}")
    print(f"  Total Trades:      {len(result.trades):>12}")
    print(f"  Closed Trades:     {result.wins + result.losses:>12}")
    print(f"  Wins / Losses:     {result.wins:>5} / {result.losses}")
    if result.wins + result.losses > 0:
        win_rate = result.wins / (result.wins + result.losses)
        print(f"  Win Rate:          {win_rate:>12.1%}")

    if result.trades:
        print("\n  Trade Log:")
        print("  " + "-" * 56)
        for trade in result.trades:
            pnl_str = f"  PnL ${trade.pnl:+.2f}" if trade.side == "SELL" else ""
            ts = trade.timestamp.strftime("%H:%M")
            print(
                f"  {ts}  {trade.side:<4} {trade.symbol:<5} x{trade.qty:<4} "
                f"@ ${trade.price:<8.2f}{pnl_str}  {trade.reason}"
            )

    print("=" * 60 + "\n")