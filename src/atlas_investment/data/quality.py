from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import Candle


@dataclass(frozen=True)
class DataQualityIssue:
    symbol: str
    severity: str
    message: str


@dataclass(frozen=True)
class DataQualityReport:
    symbol: str
    candle_count: int
    issue_count: int
    issues: list[DataQualityIssue]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)


class OhlcvQualityChecker:
    def check(self, symbol: str, candles: list[Candle], min_rows: int = 120) -> DataQualityReport:
        issues: list[DataQualityIssue] = []
        if len(candles) < min_rows:
            issues.append(DataQualityIssue(symbol, "error", f"OHLCV 행 수가 부족합니다: {len(candles)} < {min_rows}"))

        previous_date = ""
        seen_dates: set[str] = set()
        for candle in candles:
            if candle.date in seen_dates:
                issues.append(DataQualityIssue(symbol, "error", f"중복 날짜가 있습니다: {candle.date}"))
            seen_dates.add(candle.date)
            if previous_date and candle.date <= previous_date:
                issues.append(DataQualityIssue(symbol, "error", f"날짜 정렬이 깨졌습니다: {previous_date} -> {candle.date}"))
            previous_date = candle.date

            if min(candle.open, candle.high, candle.low, candle.close) <= 0:
                issues.append(DataQualityIssue(symbol, "error", f"0 이하 가격이 있습니다: {candle.date}"))
            if candle.low > min(candle.open, candle.close) or candle.high < max(candle.open, candle.close):
                issues.append(DataQualityIssue(symbol, "error", f"OHLC 범위가 비정상입니다: {candle.date}"))
            if candle.volume < 0:
                issues.append(DataQualityIssue(symbol, "error", f"거래량이 음수입니다: {candle.date}"))

        return DataQualityReport(symbol=symbol, candle_count=len(candles), issue_count=len(issues), issues=issues)
