from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import Any

from atlas_investment.risk.institutional import ExposureReport


def _default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


def write_daily_risk_report(report: ExposureReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(asdict(report), file, ensure_ascii=False, indent=2, default=_default)
    return path


def render_markdown_status(title: str, items: dict[str, Any]) -> str:
    lines = [f"# {title}", ""]
    for key, value in items.items():
        lines.append(f"- **{key}**: {value}")
    lines.append("")
    return "\n".join(lines)
