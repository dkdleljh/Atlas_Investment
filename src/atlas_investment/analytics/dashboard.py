from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DashboardPanel:
    title: str
    status: str
    detail: str


@dataclass(frozen=True)
class DashboardSnapshot:
    title: str
    panels: list[DashboardPanel]


def build_operations_dashboard(
    live_trading_enabled: bool,
    paper_ready: bool,
    data_quality_status: str,
    health_status: str,
    toss_readiness_status: str,
) -> DashboardSnapshot:
    panels = [
        DashboardPanel("실거래", "disabled" if not live_trading_enabled else "enabled", "공식 API 연결 전까지 비활성 유지"),
        DashboardPanel("PAPER 운용", "ok" if paper_ready else "blocked", "가상 체결과 감사 로그 점검"),
        DashboardPanel("데이터 품질", data_quality_status, "OHLCV 누락/중복/가격 이상 여부"),
        DashboardPanel("시스템 헬스체크", health_status, "설정/데이터/문서/패키지 경로 점검"),
        DashboardPanel("토스 API 준비도", toss_readiness_status, "공식 REST/OAuth2/계좌 헤더 준비 상태"),
    ]
    return DashboardSnapshot("Atlas Investment 운영 대시보드", panels)
