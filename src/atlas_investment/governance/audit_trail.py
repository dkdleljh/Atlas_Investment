from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AuditTrailRecord:
    record_type: str
    subject: str
    created_at: str
    payload_hash: str
    notes: list[str]


class AuditTrailWriter:
    def write(self, path: Path, record_type: str, subject: str, payload: Any, notes: list[str] | None = None) -> AuditTrailRecord:
        normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        record = AuditTrailRecord(
            record_type=record_type,
            subject=subject,
            created_at=datetime.now(timezone.utc).isoformat(),
            payload_hash=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
            notes=notes or [],
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record.__dict__, ensure_ascii=False, sort_keys=True) + "\n")
        return record
