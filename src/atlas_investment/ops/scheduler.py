from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class OpsStep:
    name: str
    market: str
    phase: str
    command: str
    required: bool = True


@dataclass(frozen=True)
class DailyOpsPlan:
    plan_date: str
    steps: list[OpsStep]


class OpsScheduler:
    def build_daily_plan(self, plan_date: date) -> DailyOpsPlan:
        steps = [
            OpsStep("한국장 장전 데이터 감사", "KR", "pre_market", "python3 -m atlas_investment.cli data-audit"),
            OpsStep("한국장 장전 리스크 점검", "KR", "pre_market", "python3 -m atlas_investment.cli risk-report"),
            OpsStep("한국장 장중 이벤트 버스 점검", "KR", "intraday", "python3 -m atlas_investment.cli realtime-smoke"),
            OpsStep("한국장 마감 운영 리포트", "KR", "post_market", "python3 -m atlas_investment.cli ops-report"),
            OpsStep("미국장 장전 데이터 감사", "US", "pre_market", "python3 -m atlas_investment.cli data-audit"),
            OpsStep("미국장 장전 FX 오버레이", "US", "pre_market", "python3 -m atlas_investment.cli fx-overlay"),
            OpsStep("미국장 마감 운영 리포트", "US", "post_market", "python3 -m atlas_investment.cli ops-report"),
            OpsStep("토스 API 준비도 점검", "ALL", "daily", "python3 -m atlas_investment.cli readiness", required=False),
            OpsStep("헬스체크", "ALL", "daily", "python3 -m atlas_investment.cli healthcheck"),
        ]
        return DailyOpsPlan(plan_date=plan_date.isoformat(), steps=steps)
