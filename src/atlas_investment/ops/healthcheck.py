from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class HealthCheckItem:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class HealthCheckReport:
    overall_status: str
    items: list[HealthCheckItem]


class HealthCheckEngine:
    def run(self, root: Path) -> HealthCheckReport:
        items = [
            self._path_exists("프로젝트 루트", root),
            self._path_exists("설정 디렉터리", root / "config"),
            self._path_exists("리스크 정책", root / "config" / "risk_policy.json"),
            self._path_exists("전략 설정", root / "config" / "strategy.json"),
            self._path_exists("소스 패키지", root / "src" / "atlas_investment"),
            self._path_exists("문서 디렉터리", root / "docs"),
        ]
        for directory in ["data", "data/reports", "data/backtests", "data/journals", "data/ohlcv"]:
            path = root / directory
            path.mkdir(parents=True, exist_ok=True)
            items.append(self._path_exists(directory, path))
        overall = "ok" if all(item.status == "ok" for item in items) else "blocked"
        return HealthCheckReport(overall, items)

    def _path_exists(self, name: str, path: Path) -> HealthCheckItem:
        if path.exists():
            return HealthCheckItem(name, "ok", str(path))
        return HealthCheckItem(name, "blocked", f"경로가 없습니다: {path}")
