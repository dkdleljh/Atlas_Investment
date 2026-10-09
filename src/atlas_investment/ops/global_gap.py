from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from atlas_investment.data.entitlements import DataEntitlementAuditor
from atlas_investment.ops.heartbeat import HeartbeatAuditor
from atlas_investment.ops.hedgefund_readiness import HedgeFundReadinessAuditor
from atlas_investment.ops.promotion import PromotionEvidenceAuditor
from atlas_investment.ops.reconciliation import ReadOnlyReconciler


@dataclass(frozen=True)
class GlobalGapItem:
    name: str
    status: str
    category: str
    code_possible: bool
    evidence: str
    next_action: str


@dataclass(frozen=True)
class GlobalGapAuditReport:
    status: str
    blocked: int
    degraded: int
    code_possible_blockers: int
    external_blockers: int
    items: list[GlobalGapItem]
    conclusion: str


class GlobalGapAuditor:
    """Aggregates live-readiness gaps into an implementation roadmap."""

    def audit(self, root: Path) -> GlobalGapAuditReport:
        hedgefund = HedgeFundReadinessAuditor().run(root)
        entitlements = DataEntitlementAuditor().audit(root)
        promotion = PromotionEvidenceAuditor().audit(root)
        reconciliation = ReadOnlyReconciler().reconcile(root)
        heartbeat = HeartbeatAuditor().audit(root)
        items: list[GlobalGapItem] = []

        for check in hedgefund.checks:
            items.append(
                GlobalGapItem(
                    name=check.name,
                    status=check.status,
                    category="hedgefund_readiness",
                    code_possible=check.name
                    not in {
                        "global_universe_coverage",
                        "global_asset_class_coverage",
                        "live_broker",
                        "read_only_reconciliation",
                        "data_quality",
                        "autonomy_24x7_daemon",
                        "live_promotion_gate",
                    },
                    evidence=check.evidence,
                    next_action=check.remediation,
                )
            )
        for requirement in entitlements.requirements:
            items.append(
                GlobalGapItem(
                    name=f"data_entitlement.{requirement.name}",
                    status=requirement.status,
                    category="data_entitlements",
                    code_possible=False,
                    evidence=requirement.evidence,
                    next_action="실제 데이터 벤더 계약, 권리 범위, credential, freshness SLA를 등록합니다.",
                )
            )
        for requirement in promotion.requirements:
            items.append(
                GlobalGapItem(
                    name=f"promotion.{requirement.name}",
                    status=requirement.status,
                    category="promotion_evidence",
                    code_possible=False,
                    evidence=f"{requirement.evidence}; required={requirement.required_value}",
                    next_action="운영 결과에서 자동으로 증거를 누적하고, 수동 승인은 별도 파일로 남깁니다.",
                )
            )

        items.append(
            GlobalGapItem(
                name="reconciliation.summary",
                status=reconciliation.status,
                category="reconciliation",
                code_possible=False,
                evidence=f"differences={len(reconciliation.differences)}; broker_positions={reconciliation.broker_position_count}; internal_positions={reconciliation.internal_position_count}",
                next_action="공식 브로커 스냅샷 adapter를 연결하고 position/cash/fill 차이를 10영업일 무차이로 증명합니다.",
            )
        )
        items.append(
            GlobalGapItem(
                name="heartbeat.summary",
                status=heartbeat.status,
                category="autonomy",
                code_possible=False,
                evidence=f"days={heartbeat.distinct_utc_days}; latest_status={heartbeat.latest_status}; history={heartbeat.history_path}",
                next_action="daemon heartbeat를 30일 이상 누적하고 blocked/degraded 상태 알림을 유지합니다.",
            )
        )

        blocked = sum(1 for item in items if item.status == "blocked")
        degraded = sum(1 for item in items if item.status == "degraded")
        code_possible_blockers = sum(1 for item in items if item.status == "blocked" and item.code_possible)
        external_blockers = sum(1 for item in items if item.status == "blocked" and not item.code_possible)
        status = "blocked" if blocked else "degraded" if degraded else "ok"
        conclusion = (
            "실거래 API를 제외해도 내부 구현으로 줄일 수 있는 blocker가 남아 있습니다."
            if code_possible_blockers
            else "남은 blocker는 주로 외부 API, 데이터 권리, 실제 운용 증거입니다."
        )
        return GlobalGapAuditReport(status, blocked, degraded, code_possible_blockers, external_blockers, items, conclusion)
