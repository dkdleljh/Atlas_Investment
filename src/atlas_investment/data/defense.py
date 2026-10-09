from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from atlas_investment.data.quality import DataQualityIssue, DataQualityReport, OhlcvQualityChecker
from atlas_investment.models import Candle


@dataclass(frozen=True)
class DataDefenseReport:
    symbol: str
    status: str
    quality: DataQualityReport
    blocked_reasons: list[str]
    warnings: list[str]


class DataDefenseLayer:
    """Stricter input guard before strategy generation."""

    def inspect(self, symbol: str, candles: list[Candle], today: date | None = None, max_stale_days: int = 10) -> DataDefenseReport:
        quality = OhlcvQualityChecker().check(symbol, candles, min_rows=120)
        blocked = [issue.message for issue in quality.issues if issue.severity == "error"]
        warnings: list[str] = []
        if candles:
            last = _parse_date(candles[-1].date)
            if last and today:
                stale_days = (today - last).days
                if stale_days > max_stale_days:
                    blocked.append(f"마지막 candle이 {stale_days}일 전이라 stale data입니다.")
            for previous, current in zip(candles, candles[1:]):
                if previous.close > 0:
                    gap = current.close / previous.close - 1
                    if abs(gap) > 0.35 and current.volume <= max(previous.volume, 1) * 1.2:
                        warnings.append(f"split-like jump 가능성: {current.date} {gap:.1%}")
                    if current.volume > max(previous.volume, 1) * 8:
                        warnings.append(f"volume anomaly: {current.date}")
        status = "blocked" if blocked else "degraded" if warnings else "ok"
        return DataDefenseReport(symbol, status, quality, blocked, warnings[:20])


def _parse_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value[:10]).date()
    except ValueError:
        return None
