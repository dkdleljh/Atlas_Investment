from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from atlas_investment.data.ohlcv_store import OhlcvStore


@dataclass(frozen=True)
class DataSnapshotRecord:
    symbol: str
    path: str
    row_count: int
    first_date: str | None
    last_date: str | None
    checksum: str
    warnings: list[str]


@dataclass(frozen=True)
class DataSnapshotAudit:
    status: str
    root: str
    records: list[DataSnapshotRecord]
    warnings: list[str]


class DataSnapshotAuditor:
    def audit(self, root: Path) -> DataSnapshotAudit:
        store = OhlcvStore(root)
        records: list[DataSnapshotRecord] = []
        warnings: list[str] = []
        for path in sorted(root.glob("*.csv")):
            symbol = path.stem
            candles = store.load(symbol)
            row_warnings = []
            if len(candles) < 60:
                row_warnings.append("행 수가 60개 미만입니다.")
            if candles:
                dates = [candle.date for candle in candles]
                if dates != sorted(dates):
                    row_warnings.append("날짜 정렬이 올바르지 않습니다.")
            else:
                row_warnings.append("캔들 데이터가 비어 있습니다.")
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            records.append(
                DataSnapshotRecord(
                    symbol=symbol,
                    path=str(path),
                    row_count=len(candles),
                    first_date=candles[0].date if candles else None,
                    last_date=candles[-1].date if candles else None,
                    checksum=checksum,
                    warnings=row_warnings,
                )
            )
            warnings.extend(f"{symbol}: {warning}" for warning in row_warnings)
        if not records:
            warnings.append("감사할 CSV 스냅샷이 없습니다.")
        status = "ok" if not warnings else "degraded"
        return DataSnapshotAudit(status, str(root), records, warnings)
