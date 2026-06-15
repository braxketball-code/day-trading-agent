import time
from datetime import datetime

from src.broker.alpaca import AlpacaBroker
from src.risk.manager import RiskManager
from src.strategy.base import Signal
from src.strategy.momentum import MomentumRSIStrategy
from src.utils.logger import setup_logger
from src.utils.market_hours import MarketHours


class DayTradingAgent:
    def __init__(self, settings: dict):
        self.settings = settings
        self.logger = setup_logger()

        env = settings["env"]
        if not env["api_key"] or not env["secret_key"]:
            raise ValueError(
                "Missing API keys. Copy .env.example to .env and add your Alpaca paper trading keys."
            )

        paper = env["trading_mode"] != "live"
        if not paper:
            self.logger.warning("LIVE TRADING MODE — real money at risk!")

        self.broker = AlpacaBroker(env["api_key"], env["secret_key"], paper=paper)
        self.market_hours = MarketHours(
            settings["market"]["timezone"],
            settings["market"]["open_time"],
            settings["market"]["close_time"],
        )

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
        self.scan_interval = settings["agent"]["scan_interval_seconds"]
        self.close_before_minutes = settings["agent"]["close_positions_before_close_minutes"]
        self.timeframe = strategy_cfg["timeframe"]
        self.lookback_bars = strategy_cfg["lookback_bars"]
        self._running = False

    def run(self) -> None:
        self._running = True
        self.logger.info("Day trading agent started")
        self.logger.info(f"Watchlist: {', '.join(self.watchlist)}")
        self.logger.info(f"Strategy: {self.settings['strategy']['name']}")

        while self._running:
            try:
                self._tick()
            except KeyboardInterrupt:
                self.logger.info("Shutting down...")
                self._running = False
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)

            time.sleep(self.scan_interval)

        self.logger.info("Agent stopped")

    def stop(self) -> None:
        self._running = False

    def _tick(self) -> None:
        if not self.market_hours.is_market_open():
            wait_secs = self.market_hours.seconds_until_open()
            self.logger.info(f"Market closed. Next open in {wait_secs / 3600:.1f} hours")
            return

        account = self.broker.get_account()
        self.risk.set_starting_equity(account["equity"])
        positions = self.broker.get_positions()

        self.logger.info(
            f"Equity: ${account['equity']:,.2f} | "
            f"Positions: {len(positions)} | "
            f"Day trades: {account['daytrade_count']}"
        )

        if self.risk.daily_loss_exceeded(account["equity"]):
            self.logger.warning("Daily loss limit hit — closing all positions and halting")
            self.broker.close_all_positions()
            self._running = False
            return

        if self.market_hours.minutes_until_close() <= self.close_before_minutes:
            self.logger.info("Approaching market close — flattening positions")
            results = self.broker.close_all_positions()
            for result in results:
                self.logger.info(f"Closed {result.symbol}: {result.status}")
            return

        self._manage_positions(positions)
        self._scan_for_entries(account, positions)

    def _manage_positions(self, positions: list) -> None:
        for position in positions:
            exit_decision = self.risk.evaluate_exit(position)
            if exit_decision.approved:
                self.logger.info(f"EXIT {position.symbol}: {exit_decision.reason}")
                result = self.broker.close_position(position.symbol)
                if result:
                    self.logger.info(f"Order {result.id} — {result.status}")

    def _scan_for_entries(self, account: dict, positions: list) -> None:
        for symbol in self.watchlist:
            bars = self.broker.get_bars(symbol, self.timeframe, self.lookback_bars)
            if not bars:
                self.logger.debug(f"No data for {symbol}")
                continue

            df = self.strategy.bars_to_dataframe(bars)
            result = self.strategy.analyze(df)

            self.logger.info(
                f"{symbol}: {result.signal.value} "
                f"(conf {result.confidence:.0%}) — {result.reason} "
                f"| {result.indicators}"
            )

            if result.signal == Signal.SELL:
                existing = self.broker.get_position(symbol)
                if existing and existing.qty > 0:
                    self.logger.info(f"Strategy sell signal for {symbol}")
                    self.broker.close_position(symbol)
                continue

            if result.signal != Signal.BUY or result.confidence < 0.5:
                continue

            price = result.indicators.get("close", bars[-1].close)
            existing = self.broker.get_position(symbol)
            decision = self.risk.evaluate_entry(
                result.signal,
                symbol,
                price,
                account["equity"],
                positions,
                existing,
            )

            if not decision.approved:
                self.logger.debug(f"Skip {symbol}: {decision.reason}")
                continue

            self.logger.info(f"BUY {symbol}: {decision.qty} shares — {decision.reason}")
            order = self.broker.submit_market_order(symbol, decision.qty, "BUY")
            self.logger.info(f"Order {order.id} — {order.status}")

    def status(self) -> dict:
        account = self.broker.get_account()
        positions = self.broker.get_positions()
        return {
            "timestamp": datetime.now().isoformat(),
            "market_open": self.market_hours.is_market_open(),
            "account": account,
            "positions": [
                {
                    "symbol": p.symbol,
                    "qty": p.qty,
                    "entry": p.avg_entry_price,
                    "current": p.current_price,
                    "pnl": p.unrealized_pl,
                    "pnl_pct": p.unrealized_plpc,
                }
                for p in positions
            ],
        }