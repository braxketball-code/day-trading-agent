import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


def load_settings() -> dict:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")

    with open(root / "config" / "settings.yaml", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    settings["env"] = {
        "api_key": os.getenv("ALPACA_API_KEY", ""),
        "secret_key": os.getenv("ALPACA_SECRET_KEY", ""),
        "trading_mode": os.getenv("TRADING_MODE", "paper").lower(),
    }
    return settings