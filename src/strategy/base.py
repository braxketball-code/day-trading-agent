from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

import pandas as pd


class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass
class StrategyResult:
    signal: Signal
    confidence: float
    reason: str
    indicators: dict


class BaseStrategy(ABC):
    @abstractmethod
    def analyze(self, df: pd.DataFrame) -> StrategyResult:
        pass

    @staticmethod
    def bars_to_dataframe(bars: list) -> pd.DataFrame:
        if not bars:
            return pd.DataFrame()

        records = [
            {
                "timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in bars
        ]
        df = pd.DataFrame(records)
        df.set_index("timestamp", inplace=True)
        df.sort_index(inplace=True)
        return df