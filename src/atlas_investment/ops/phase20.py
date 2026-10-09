from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Phase20ReadinessItem:
    name: str
    status: str
    notes: list[str]


@dataclass(frozen=True)
class Phase20ReadinessReport:
    overall_status: str
    items: list[Phase20ReadinessItem]


class Phase20ReadinessAuditor:
    def run(self, root: Path) -> Phase20ReadinessReport:
        toss_readiness = self._load_json(root / "data" / "reports" / "toss_api_readiness.json")
        reconciliation = self._load_json(root / "data" / "reports" / "reconciliation_check.json")
        live_order = self._load_json(root / "data" / "reports" / "toss_live_order.json")
        items = [
            self._path_item("data_lake", root / "data" / "lake"),
            self._path_item("reports", root / "data" / "reports"),
            self._path_item("phase20_roadmap_doc", root / "docs" / "18_초거대_헤지펀드급_고도화_로드맵.md"),
            Phase20ReadinessItem("dart_api_key", "ok" if os.environ.get("API_K_DART") else "degraded", ["API_K_DART가 없으면 실제 DART 조회는 차단됩니다."]),
            self._official_toss_account_api_item(toss_readiness, reconciliation),
            self._live_order_api_item(toss_readiness, live_order),
            Phase20ReadinessItem("margin_credit_policy", "ok", ["미수/신용은 전 전략/전 시장에서 절대 금지입니다."]),
        ]
        if any(item.status == "blocked" for item in items):
            overall = "blocked"
        elif any(item.status == "degraded" for item in items):
            overall = "degraded"
        else:
            overall = "ok"
        return Phase20ReadinessReport(overall, items)

    @staticmethod
    def _path_item(name: str, path: Path) -> Phase20ReadinessItem:
        return Phase20ReadinessItem(name, "ok" if path.exists() else "degraded", [str(path)])

    @staticmethod
    def _load_json(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _official_toss_account_api_item(self, readiness: dict, reconciliation: dict) -> Phase20ReadinessItem:
        if readiness.get("missing_items"):
            return Phase20ReadinessItem(
                "official_toss_account_api",
                "blocked",
                [f"토스 공식 API 설정 누락: {readiness.get('missing_items')}"],
            )
        if readiness.get("official_docs_verified") and reconciliation.get("status") == "ok":
            return Phase20ReadinessItem(
                "official_toss_account_api",
                "ok",
                ["토스 공식 OpenAPI 문서/키가 확인됐고 최신 reconciliation이 ok입니다."],
            )
        if readiness.get("official_docs_verified"):
            return Phase20ReadinessItem(
                "official_toss_account_api",
                "degraded",
                [f"토스 공식 OpenAPI 문서는 확인됐지만 reconciliation 상태가 {reconciliation.get('status', 'unknown')}입니다."],
            )
        return Phase20ReadinessItem(
            "official_toss_account_api",
            "blocked",
            ["토스증권 공식 계좌/포지션/체결 조회 API 문서/키 확인 전까지 실계좌 스냅샷 대사는 차단됩니다."],
        )

    def _live_order_api_item(self, readiness: dict, live_order: dict) -> Phase20ReadinessItem:
        if readiness.get("missing_items"):
            return Phase20ReadinessItem(
                "live_order_api",
                "blocked",
                [f"토스 공식 주문 API 설정 누락: {readiness.get('missing_items')}"],
            )
        if live_order.get("submit_attempted") and live_order.get("status") in {"submitted", "filled", "closed_external"}:
            return Phase20ReadinessItem(
                "live_order_api",
                "ok",
                ["토스 공식 실주문 경로는 수동 승인 1회 주문으로 검증됐습니다. LIVE_AUTO 승격은 promotion evidence에서 별도로 차단합니다."],
            )
        if readiness.get("official_docs_verified"):
            return Phase20ReadinessItem(
                "live_order_api",
                "degraded",
                ["토스 공식 OpenAPI 문서는 확인됐지만 수동 소액 주문 검증 또는 승격 증거가 부족합니다."],
            )
        return Phase20ReadinessItem(
            "live_order_api",
            "blocked",
            ["토스 공식 실주문 API 문서/키 전까지 LIVE_AUTO 주문은 의도적으로 차단합니다."],
        )
