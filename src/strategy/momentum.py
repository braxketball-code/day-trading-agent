import pandas as pd
import ta

from src.strategy.base import BaseStrategy, Signal, StrategyResult


class MomentumRSIStrategy(BaseStrategy):
    def __init__(
        self,
        ema_fast: int = 9,
        ema_slow: int = 21,
        rsi_period: int = 14,
        rsi_oversold: float = 35,
        rsi_overbought: float = 65,
    ):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

    def analyze(self, df: pd.DataFrame) -> StrategyResult:
        if len(df) < max(self.ema_slow, self.rsi_period) + 5:
            return StrategyResult(
                signal=Signal.HOLD,
                confidence=0.0,
                reason="Insufficient data",
                indicators={},
            )

        close = df["close"]
        ema_fast = ta.trend.EMAIndicator(close, window=self.ema_fast).ema_indicator()
        ema_slow = ta.trend.EMAIndicator(close, window=self.ema_slow).ema_indicator()
        rsi = ta.momentum.RSIIndicator(close, window=self.rsi_period).rsi()
        volume_sma = df["volume"].rolling(window=20).mean()

        latest_ema_fast = ema_fast.iloc[-1]
        latest_ema_slow = ema_slow.iloc[-1]
        prev_ema_fast = ema_fast.iloc[-2]
        prev_ema_slow = ema_slow.iloc[-2]
        latest_rsi = rsi.iloc[-1]
        latest_close = close.iloc[-1]
        latest_volume = df["volume"].iloc[-1]
        avg_volume = volume_sma.iloc[-1]

        indicators = {
            "ema_fast": round(latest_ema_fast, 2),
            "ema_slow": round(latest_ema_slow, 2),
            "rsi": round(latest_rsi, 2),
            "close": round(latest_close, 2),
            "volume_ratio": round(latest_volume / avg_volume, 2) if avg_volume else 0,
        }

        bullish_cross = prev_ema_fast <= prev_ema_slow and latest_ema_fast > latest_ema_slow
        bearish_cross = prev_ema_fast >= prev_ema_slow and latest_ema_fast < latest_ema_slow
        volume_confirmed = latest_volume > avg_volume * 0.8 if avg_volume else True

        if bullish_cross and latest_rsi < self.rsi_overbought and volume_confirmed:
            confidence = min(0.9, 0.5 + (self.rsi_overbought - latest_rsi) / 100)
            return StrategyResult(
                signal=Signal.BUY,
                confidence=confidence,
                reason=f"Bullish EMA cross (RSI {latest_rsi:.1f})",
                indicators=indicators,
            )

        if bearish_cross or latest_rsi > self.rsi_overbought:
            confidence = min(0.9, 0.5 + (latest_rsi - self.rsi_overbought) / 50)
            return StrategyResult(
                signal=Signal.SELL,
                confidence=confidence,
                reason=f"Bearish signal (RSI {latest_rsi:.1f})",
                indicators=indicators,
            )

        if latest_rsi < self.rsi_oversold and latest_ema_fast > latest_ema_slow:
            return StrategyResult(
                signal=Signal.BUY,
                confidence=0.6,
                reason=f"Oversold bounce (RSI {latest_rsi:.1f})",
                indicators=indicators,
            )

        return StrategyResult(
            signal=Signal.HOLD,
            confidence=0.0,
            reason="No clear signal",
            indicators=indicators,
        )