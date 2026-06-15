import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.agent import DayTradingAgent
from src.config import load_settings
from src.simulation import SimulationEngine, print_simulation_report


def main():
    parser = argparse.ArgumentParser(description="Autonomous day trading agent")
    parser.add_argument(
        "--status",
        action="store_true",
        help="Print current account status and exit",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config and API connection without trading",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Run a backtest simulation with synthetic market data (no API keys needed)",
    )
    parser.add_argument(
        "--equity",
        type=float,
        default=100_000.0,
        help="Starting equity for simulation (default: 100000)",
    )
    args = parser.parse_args()

    settings = load_settings()

    if args.simulate:
        engine = SimulationEngine(settings, starting_equity=args.equity)
        result = engine.run()
        print_simulation_report(result)
        return

    agent = DayTradingAgent(settings)

    if args.status:
        print(json.dumps(agent.status(), indent=2))
        return

    if args.dry_run:
        status = agent.status()
        print("Connection OK")
        print(f"  Mode: {settings['env']['trading_mode']}")
        print(f"  Equity: ${status['account']['equity']:,.2f}")
        print(f"  Market open: {status['market_open']}")
        print(f"  Positions: {len(status['positions'])}")
        return

    agent.run()


if __name__ == "__main__":
    main()