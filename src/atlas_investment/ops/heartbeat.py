from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class HeartbeatAuditReport:
    status: str
    distinct_utc_days: int
    latest_status: str | None
    latest_at: str | None
    history_path: str
    notes: list[str] = field(default_factory=list)


class HeartbeatRecorder:
    def record(self, root: Path, status: str, source: str = "manual") -> Path:
        history_path = root / "data" / "runtime" / "heartbeat_history.jsonl"
        history_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "source": source,
            "live_orders": "blocked",
        }
        with history_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return history_path


class HeartbeatAuditor:
    def audit(self, root: Path, required_days: int | None = None) -> HeartbeatAuditReport:
        required_days = required_days or self._required_days(root)
        history_path = root / "data" / "runtime" / "heartbeat_history.jsonl"
        if not history_path.exists():
            return HeartbeatAuditReport("blocked", 0, None, None, str(history_path), ["No heartbeat history exists."])

        days: set[date] = set()
        latest_status: str | None = None
        latest_at: str | None = None
        for line in history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                at = datetime.fromisoformat(str(payload["at"]).replace("Z", "+00:00"))
            except Exception:
                continue
            days.add(at.date())
            latest_at = at.isoformat()
            latest_status = str(payload.get("status"))

        status = "ok" if len(days) >= required_days and latest_status == "ok" else "blocked"
        return HeartbeatAuditReport(
            status,
            len(days),
            latest_status,
            latest_at,
            str(history_path),
            [f"Requires at least {required_days} distinct UTC days with latest status ok."],
        )

    @staticmethod
    def _required_days(root: Path) -> int:
        approval = root / "data" / "evidence" / "live_promotion_approval.json"
        if not approval.exists():
            return 30
        try:
            payload = json.loads(approval.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return 30
        if not isinstance(payload, dict):
            return 30
        evidence = payload.get("required_evidence")
        if not isinstance(evidence, dict):
            return 30
        value = evidence.get("heartbeat_days", evidence.get("dry_run_business_days", 30))
        return int(value) if isinstance(value, (int, float)) and int(value) > 0 else 30
