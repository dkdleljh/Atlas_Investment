from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time

from atlas_investment.models import Market


@dataclass(frozen=True)
class MarketSession:
    market: Market
    is_trading_day: bool
    phase: str
    local_date: str


class TradingCalendar:
    def __init__(self, kr_holidays: set[date] | None = None, us_holidays: set[date] | None = None) -> None:
        self.kr_holidays = kr_holidays or set()
        self.us_holidays = us_holidays or set()

    def is_trading_day(self, day: date, market: Market) -> bool:
        if day.weekday() >= 5:
            return False
        holidays = self.kr_holidays if market == Market.KR else self.us_holidays
        return day not in holidays

    def session(self, now: datetime, market: Market) -> MarketSession:
        if not self.is_trading_day(now.date(), market):
            return MarketSession(market, False, "closed", now.date().isoformat())
        current_time = now.time()
        if market == Market.KR:
            phase = self._phase(current_time, time(8, 30), time(9, 0), time(15, 30), time(16, 10))
        else:
            phase = self._phase(current_time, time(21, 30), time(22, 30), time(5, 0), time(6, 0))
        return MarketSession(market, True, phase, now.date().isoformat())

    def _phase(self, current: time, pre_start: time, open_time: time, close_time: time, post_end: time) -> str:
        if pre_start <= current < open_time:
            return "pre_market"
        if open_time <= current <= close_time:
            return "intraday"
        if close_time < current <= post_end:
            return "post_market"
        return "closed"
