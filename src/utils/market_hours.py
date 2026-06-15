from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


class MarketHours:
    def __init__(self, timezone: str, open_time: str, close_time: str):
        self.tz = ZoneInfo(timezone)
        open_h, open_m = map(int, open_time.split(":"))
        close_h, close_m = map(int, close_time.split(":"))
        self.market_open = time(open_h, open_m)
        self.market_close = time(close_h, close_m)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def is_market_open(self) -> bool:
        now = self.now()
        if now.weekday() >= 5:
            return False
        current = now.time()
        return self.market_open <= current < self.market_close

    def minutes_until_close(self) -> float:
        now = self.now()
        close_dt = now.replace(
            hour=self.market_close.hour,
            minute=self.market_close.minute,
            second=0,
            microsecond=0,
        )
        if now.time() >= self.market_close:
            return 0.0
        return (close_dt - now).total_seconds() / 60

    def seconds_until_open(self) -> float:
        now = self.now()
        if self.is_market_open():
            return 0.0

        open_dt = now.replace(
            hour=self.market_open.hour,
            minute=self.market_open.minute,
            second=0,
            microsecond=0,
        )

        if now.time() >= self.market_close or now.weekday() >= 5:
            days_ahead = 1
            while True:
                candidate = open_dt + timedelta(days=days_ahead)
                if candidate.weekday() < 5:
                    open_dt = candidate
                    break
                days_ahead += 1
        elif now.time() < self.market_open:
            if now.weekday() >= 5:
                days_ahead = 1
                while True:
                    candidate = open_dt + timedelta(days=days_ahead)
                    if candidate.weekday() < 5:
                        open_dt = candidate
                        break
                    days_ahead += 1

        return max((open_dt - now).total_seconds(), 0.0)