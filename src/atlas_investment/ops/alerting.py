from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AlertEvent:
    rule: str
    severity: str
    source: str
    message: str


@dataclass(frozen=True)
class AlertReport:
    status: str
    enabled: bool
    channel_count: int
    scanned_reports: int
    events: list[AlertEvent] = field(default_factory=list)
    outbox_path: str | None = None
    notes: list[str] = field(default_factory=list)


class AlertEngine:
    """Local alert evaluator.

    This deliberately writes to a local outbox only. External delivery channels
    can be added after their secrets are stored outside git.
    """

    def evaluate(self, root: Path) -> AlertReport:
        config_path = root / "config" / "alerts.json"
        if not config_path.exists():
            return AlertReport("blocked", False, 0, 0, notes=[f"alert config missing: {config_path}"])

        config = json.loads(config_path.read_text(encoding="utf-8"))
        enabled = bool(config.get("enabled"))
        channels = list(config.get("channels", []))
        ignored_report_names = set(config.get("ignored_report_names", []))
        reports_dir = root / "data" / "reports"
        events: list[AlertEvent] = []
        scanned = 0
        for path in sorted(reports_dir.glob("*.json")) if reports_dir.exists() else []:
            if path.name == "alerts_check.json" or path.name in ignored_report_names:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            scanned += 1
            status = self._status(payload)
            if status == "blocked":
                events.append(AlertEvent("blocked_status", "critical", str(path), "A report is blocked. New live orders must remain disabled."))
            elif status == "degraded":
                events.append(AlertEvent("degraded_status", "warning", str(path), "A required report is degraded and needs review."))

        outbox_path = root / "data" / "reports" / "alerts_outbox.jsonl"
        if enabled and channels:
            outbox_path.parent.mkdir(parents=True, exist_ok=True)
            with outbox_path.open("a", encoding="utf-8") as file:
                for event in events:
                    file.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), **event.__dict__}, ensure_ascii=False) + "\n")

        if not enabled or not channels:
            status = "degraded"
            notes = ["Alert rules exist, but no delivery channel is enabled."]
        elif any(event.severity == "critical" for event in events):
            status = "blocked"
            notes = ["Critical alerts were written to the local outbox."]
        elif events:
            status = "degraded"
            notes = ["Warning alerts were written to the local outbox."]
        else:
            status = "ok"
            notes = ["No blocked/degraded report status found."]

        return AlertReport(status, enabled, len(channels), scanned, events, str(outbox_path) if enabled and channels else None, notes)

    def _status(self, payload: Any) -> str:
        if isinstance(payload, dict):
            for key in ("overall_status", "status", "risk_level"):
                value = payload.get(key)
                if isinstance(value, str) and value.lower() in {"blocked", "degraded", "ok"}:
                    return value.lower()
            statuses = [self._status(value) for value in payload.values()]
        elif isinstance(payload, list):
            statuses = [self._status(value) for value in payload]
        else:
            return "unknown"
        if "blocked" in statuses:
            return "blocked"
        if "degraded" in statuses:
            return "degraded"
        if "ok" in statuses:
            return "ok"
        return "unknown"
