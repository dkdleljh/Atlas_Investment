from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def render_static_dashboard(report_dir: Path, output_path: Path) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    cards = []
    table_rows = []
    for path in sorted(report_dir.glob("*.json")):
        try:
            payload: Any = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        summary_text = _summarize(payload)
        status = _status_for(payload)
        title = _title_for(path.name)
        metrics = _metrics_for(payload)
        cards.append(
            f"""
            <section class="panel status-{html.escape(status)}">
              <div class="panel-head">
                <h2>{html.escape(title)}</h2>
                <span class="status-chip">{html.escape(status.upper())}</span>
              </div>
              <dl class="metrics">{metrics}</dl>
              <pre>{html.escape(summary_text)}</pre>
            </section>
            """
        )
        table_rows.append(
            f"""
            <tr>
              <td>{html.escape(title)}</td>
              <td><span class="table-status status-{html.escape(status)}">{html.escape(status)}</span></td>
              <td>{html.escape(path.name)}</td>
            </tr>
            """
        )

    generated_at = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    counts = _status_counts([_status_for(_load_json(path)) for path in sorted(report_dir.glob("*.json"))])
    cards_body = "\n".join(cards) if cards else "<p class=\"empty\">No reports found.</p>"
    rows_body = "\n".join(table_rows) if table_rows else "<tr><td colspan=\"3\">No reports found.</td></tr>"
    document = f"""<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Atlas Investment Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f6f8;
      --surface: #ffffff;
      --ink: #17202a;
      --muted: #607085;
      --line: #d9e0e8;
      --ok: #0f7b55;
      --degraded: #9a6200;
      --blocked: #b42318;
      --accent: #2357a5;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--ink); }}
    header {{ padding: 24px clamp(18px, 4vw, 40px); background: #182230; color: #ffffff; border-bottom: 4px solid #2e90fa; }}
    h1 {{ margin: 0; font-size: 24px; letter-spacing: 0; }}
    .subtitle {{ margin: 8px 0 0; color: #d0d8e5; font-size: 14px; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; padding: 20px clamp(18px, 4vw, 40px) 8px; }}
    .summary-card {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .summary-card strong {{ display: block; font-size: 24px; }}
    .summary-card span {{ color: var(--muted); font-size: 12px; }}
    .index {{ padding: 12px clamp(18px, 4vw, 40px); }}
    table {{ width: 100%; border-collapse: collapse; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }}
    th, td {{ padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; font-size: 13px; }}
    th {{ color: var(--muted); background: #f8fafc; font-weight: 600; }}
    tr:last-child td {{ border-bottom: 0; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; padding: 12px clamp(18px, 4vw, 40px) 32px; }}
    .panel {{ background: var(--surface); border: 1px solid var(--line); border-left-width: 5px; border-radius: 8px; padding: 16px; min-height: 220px; box-shadow: 0 8px 20px rgba(16, 24, 40, 0.04); }}
    .panel-head {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 12px; }}
    h2 {{ margin: 0; font-size: 15px; letter-spacing: 0; }}
    pre {{ margin: 12px 0 0; max-height: 320px; overflow: auto; white-space: pre-wrap; word-break: break-word; font-size: 12px; line-height: 1.45; background: #f8fafc; border: 1px solid #e6ebf1; border-radius: 6px; padding: 12px; }}
    .metrics {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 0; }}
    .metrics div {{ min-width: 0; padding: 8px; background: #fbfcfe; border: 1px solid #edf1f5; border-radius: 6px; }}
    .metrics dt {{ color: var(--muted); font-size: 11px; }}
    .metrics dd {{ margin: 3px 0 0; font-size: 13px; font-weight: 600; overflow-wrap: anywhere; }}
    .status-chip, .table-status {{ display: inline-flex; align-items: center; justify-content: center; min-width: 72px; border-radius: 999px; padding: 4px 8px; font-size: 11px; font-weight: 700; }}
    .status-ok {{ border-left-color: var(--ok); }}
    .status-degraded {{ border-left-color: var(--degraded); }}
    .status-blocked {{ border-left-color: var(--blocked); }}
    .status-unknown {{ border-left-color: var(--accent); }}
    .status-ok .status-chip, .table-status.status-ok {{ color: #05603a; background: #d1fadf; }}
    .status-degraded .status-chip, .table-status.status-degraded {{ color: #93370d; background: #fef0c7; }}
    .status-blocked .status-chip, .table-status.status-blocked {{ color: #912018; background: #fee4e2; }}
    .status-unknown .status-chip, .table-status.status-unknown {{ color: #1849a9; background: #d1e9ff; }}
    .empty {{ padding: 20px; color: var(--muted); }}
  </style>
</head>
<body>
  <header>
    <h1>Atlas Investment Operations Dashboard</h1>
    <p class="subtitle">Generated {html.escape(generated_at)} · DRY_RUN/PAPER 중심 운영 상태판</p>
  </header>
  <section class="summary" aria-label="status summary">
    <div class="summary-card"><strong>{counts["ok"]}</strong><span>OK reports</span></div>
    <div class="summary-card"><strong>{counts["degraded"]}</strong><span>Degraded reports</span></div>
    <div class="summary-card"><strong>{counts["blocked"]}</strong><span>Blocked reports</span></div>
    <div class="summary-card"><strong>{counts["unknown"]}</strong><span>Other reports</span></div>
  </section>
  <section class="index">
    <table>
      <thead><tr><th>Report</th><th>Status</th><th>File</th></tr></thead>
      <tbody>{rows_body}</tbody>
    </table>
  </section>
  <main>{cards_body}</main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def _summarize(payload: Any) -> str:
    if isinstance(payload, dict):
        preferred = {key: payload[key] for key in payload if key in {"status", "overall_status", "risk_level", "path", "notes", "warnings", "breaches", "actions", "missing_items", "summary"}}
        return json.dumps(preferred or payload, ensure_ascii=False, indent=2)[:4000]
    if isinstance(payload, list):
        return json.dumps({"count": len(payload), "sample": payload[:3]}, ensure_ascii=False, indent=2)[:4000]
    return str(payload)[:4000]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _title_for(filename: str) -> str:
    return filename.replace("_", " ").replace(".json", "").title()


def _status_for(payload: Any) -> str:
    if isinstance(payload, dict):
        raw = str(payload.get("overall_status") or payload.get("status") or payload.get("risk_level") or "unknown").lower()
        if raw in {"ok", "green", "ready", "template_ready"}:
            return "ok"
        if raw in {"degraded", "yellow", "warning"}:
            return "degraded"
        if raw in {"blocked", "red", "error", "failed"}:
            return "blocked"
    if isinstance(payload, list):
        statuses = [_status_for(item) for item in payload]
        if "blocked" in statuses:
            return "blocked"
        if "degraded" in statuses:
            return "degraded"
        if statuses and all(status == "ok" for status in statuses):
            return "ok"
    return "unknown"


def _status_counts(statuses: list[str]) -> dict[str, int]:
    return {name: statuses.count(name) for name in ["ok", "degraded", "blocked", "unknown"]}


def _metrics_for(payload: Any) -> str:
    if not isinstance(payload, dict):
        if isinstance(payload, list):
            return _metric_html({"count": len(payload)})
        return ""
    keys = [
        "overall_status",
        "status",
        "synced",
        "blocked",
        "report_count",
        "item_count",
        "warning_count",
        "candle_count",
        "quality_status",
        "ready_for_live_orders",
        "recommendation",
        "should_switch",
    ]
    metrics = {key: payload[key] for key in keys if key in payload}
    return _metric_html(metrics)


def _metric_html(metrics: dict[str, Any]) -> str:
    if not metrics:
        return ""
    return "".join(
        f"<div><dt>{html.escape(str(key))}</dt><dd>{html.escape(str(value))}</dd></div>"
        for key, value in metrics.items()
    )
