from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlas_investment.ops.alerting import AlertEngine


class AlertingTests(unittest.TestCase):
    def test_alert_engine_writes_local_outbox_for_blocked_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "data" / "reports").mkdir(parents=True)
            (root / "config" / "alerts.json").write_text(
                json.dumps({"enabled": True, "channels": [{"type": "local_file", "path": "data/reports/alerts_outbox.jsonl"}]}),
                encoding="utf-8",
            )
            (root / "data" / "reports" / "sample.json").write_text(json.dumps({"status": "blocked"}), encoding="utf-8")

            report = AlertEngine().evaluate(root)

            self.assertEqual(report.status, "blocked")
            self.assertEqual(len(report.events), 1)
            self.assertTrue((root / "data" / "reports" / "alerts_outbox.jsonl").exists())

    def test_alert_engine_ignores_its_own_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "data" / "reports").mkdir(parents=True)
            (root / "config" / "alerts.json").write_text(
                json.dumps({"enabled": True, "channels": [{"type": "local_file", "path": "data/reports/alerts_outbox.jsonl"}]}),
                encoding="utf-8",
            )
            (root / "data" / "reports" / "alerts_check.json").write_text(json.dumps({"status": "blocked"}), encoding="utf-8")

            report = AlertEngine().evaluate(root)

            self.assertEqual(report.status, "ok")
            self.assertEqual(report.events, [])

    def test_alert_engine_honors_configured_ignored_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "data" / "reports").mkdir(parents=True)
            (root / "config" / "alerts.json").write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "channels": [{"type": "local_file", "path": "data/reports/alerts_outbox.jsonl"}],
                        "ignored_report_names": ["lab_only_strategy.json"],
                    }
                ),
                encoding="utf-8",
            )
            (root / "data" / "reports" / "lab_only_strategy.json").write_text(json.dumps({"status": "blocked"}), encoding="utf-8")

            report = AlertEngine().evaluate(root)

            self.assertEqual(report.status, "ok")
            self.assertEqual(report.events, [])


if __name__ == "__main__":
    unittest.main()
