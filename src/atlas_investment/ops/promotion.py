from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class PromotionRequirement:
    name: str
    status: str
    evidence: str
    required_value: str


@dataclass(frozen=True)
class PromotionEvidenceReport:
    status: str
    requirements: list[PromotionRequirement] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class PromotionEvidenceAuditor:
    """Checks non-code evidence required before live promotion."""

    def audit(self, root: Path) -> PromotionEvidenceReport:
        evidence_dir = root / "data" / "evidence"
        dry_run_days = self._read_count(evidence_dir / "dry_run_days.json", "days")
        paper_days = self._read_count(evidence_dir / "paper_days.json", "days")
        reconciliation_days = self._read_count(evidence_dir / "reconciliation_days.json", "days")
        small_order_trials = self._read_count(evidence_dir / "small_order_trials.json", "passed_trials")
        approval = evidence_dir / "live_promotion_approval.json"
        approval_payload = self._read_approval_payload(approval)
        evidence_policy = approval_payload.get("required_evidence", {}) if isinstance(approval_payload, dict) else {}
        dry_run_required = self._policy_int(evidence_policy, "dry_run_business_days", 30)
        paper_required = self._policy_int(evidence_policy, "paper_business_days", 30)
        reconciliation_required = self._policy_int(evidence_policy, "read_only_reconciliation_business_days", 10)
        small_order_required = self._policy_int(evidence_policy, "manual_small_order_trials", 1)

        requirements = [
            self._days(f"dry_run_{dry_run_required}_business_days", dry_run_days, dry_run_required, evidence_dir / "dry_run_days.json"),
            self._days(f"paper_{paper_required}_business_days", paper_days, paper_required, evidence_dir / "paper_days.json"),
            self._days(f"read_only_reconciliation_{reconciliation_required}_business_days", reconciliation_days, reconciliation_required, evidence_dir / "reconciliation_days.json"),
            self._days("manual_small_order_trials", small_order_trials, small_order_required, evidence_dir / "small_order_trials.json"),
            self._approval_requirement(approval, approval_payload),
        ]
        status = "blocked" if any(item.status == "blocked" for item in requirements) else "ok"
        return PromotionEvidenceReport(
            status=status,
            requirements=requirements,
            notes=[
                "Promotion evidence is intentionally file-backed so it cannot be inferred from code alone.",
                "Do not create fake evidence files to bypass live gates.",
            ],
        )

    def _days(self, name: str, actual: int, required: int, path: Path) -> PromotionRequirement:
        return PromotionRequirement(
            name=name,
            status="ok" if actual >= required else "blocked",
            evidence=f"{actual} recorded at {path}",
            required_value=f">= {required}",
        )

    @staticmethod
    def _read_count(path: Path, key: str) -> int:
        if not path.exists():
            return 0
        payload = json.loads(path.read_text(encoding="utf-8"))
        value = payload.get(key, 0) if isinstance(payload, dict) else 0
        return int(value) if isinstance(value, (int, float)) else 0

    @staticmethod
    def _policy_int(payload: object, key: str, default: int) -> int:
        if not isinstance(payload, dict):
            return default
        value = payload.get(key, default)
        return int(value) if isinstance(value, (int, float)) and int(value) > 0 else default

    @staticmethod
    def _read_approval_payload(path: Path) -> dict[str, object]:
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _approval_requirement(self, path: Path, payload: dict[str, object] | None = None) -> PromotionRequirement:
        required = "approved=true, approved_for=live_auto, signed_by, approved_at"
        if not path.exists():
            return PromotionRequirement("manual_live_promotion_approval", "blocked", str(path), required)
        payload = payload if payload is not None else self._read_approval_payload(path)
        if not payload:
            return PromotionRequirement("manual_live_promotion_approval", "blocked", f"{path} not an object", required)
        ok = (
            payload.get("approved") is True
            and payload.get("approved_for") == "live_auto"
            and bool(payload.get("signed_by"))
            and bool(payload.get("approved_at"))
        )
        return PromotionRequirement("manual_live_promotion_approval", "ok" if ok else "blocked", str(path), required)


class PromotionEvidenceRecorder:
    """Records real observations without fabricating promotion evidence."""

    DAY_FILES = {
        "dry_run": ("dry_run_days.json", "days"),
        "paper": ("paper_days.json", "days"),
        "reconciliation": ("reconciliation_days.json", "days"),
        "small_order": ("small_order_trials.json", "passed_trials"),
    }

    def record(self, root: Path, kind: str, status: str, source: str = "manual", observed_on: str | None = None) -> dict[str, object]:
        kind = kind.lower()
        if kind not in self.DAY_FILES:
            return {"status": "blocked", "kind": kind, "recorded": False, "reason": f"unsupported evidence kind: {kind}"}
        if status != "ok":
            self._append_log(root, kind, status, source, observed_on, recorded=False)
            return {"status": "blocked", "kind": kind, "recorded": False, "reason": "status가 ok가 아니므로 승격 증거에 반영하지 않았습니다."}
        evidence_dir = root / "data" / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        filename, key = self.DAY_FILES[kind]
        path = evidence_dir / filename
        day = observed_on or date.today().isoformat()
        payload = self._read_payload(path, key)
        observed_days = set(str(item) for item in payload.get("observed_days", []))
        observed_days.add(day)
        count = len(observed_days)
        if kind == "small_order":
            count = max(int(payload.get(key, 0)), count)
        payload.update(
            {
                key: count,
                "observed_days": sorted(observed_days),
                "last_source": source,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._append_log(root, kind, status, source, day, recorded=True)
        return {"status": "ok", "kind": kind, "recorded": True, key: count, "path": str(path)}

    @staticmethod
    def _read_payload(path: Path, key: str) -> dict[str, object]:
        if not path.exists():
            return {key: 0, "observed_days": []}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {key: 0, "observed_days": []}

    @staticmethod
    def _append_log(root: Path, kind: str, status: str, source: str, observed_on: str | None, recorded: bool) -> None:
        path = root / "data" / "evidence" / "promotion_observations.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "kind": kind,
            "status": status,
            "source": source,
            "observed_on": observed_on or date.today().isoformat(),
            "recorded": recorded,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
