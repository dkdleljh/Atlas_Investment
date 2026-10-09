from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GovernanceRecord:
    record_type: str
    title: str
    status: str
    required_before_live: bool
    notes: list[str]


class GovernanceRegistry:
    def default_phase20_controls(self) -> list[GovernanceRecord]:
        return [
            GovernanceRecord("strategy_approval", "전략 등록/승격/퇴출 기준", "ready", True, ["백테스트, PAPER, 리스크 점수 기준을 모두 기록합니다."]),
            GovernanceRecord("live_promotion", "라이브 전환 승인 기록", "blocked", True, ["토스 공식 주문 API와 수동 승인 절차 전까지 차단합니다."]),
            GovernanceRecord("model_change", "모델/파라미터 변경 이력", "ready", True, ["전략명, 변경 전후, 검증 결과를 남깁니다."]),
            GovernanceRecord("incident_postmortem", "운영 사고 포스트모템", "ready", True, ["장애, 데이터 누락, 주문 차단 이벤트를 추적합니다."]),
            GovernanceRecord("monthly_risk_review", "월간 리스크 리뷰", "ready", False, ["시장/전략/통화/레버리지 한도를 재검토합니다."]),
            GovernanceRecord("kill_switch", "펀드 킬스위치", "ready", True, ["하드 손실 한도, 데이터 장애, 브로커 장애 시 신규 주문을 막습니다."]),
        ]
