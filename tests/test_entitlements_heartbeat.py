from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlas_investment.data.entitlements import DataEntitlementAuditor
from atlas_investment.ops.heartbeat import HeartbeatAuditor, HeartbeatRecorder


class EntitlementsHeartbeatTests(unittest.TestCase):
    def test_data_entitlement_blocks_without_real_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "data_entitlements.json").write_text(json.dumps({"providers": []}), encoding="utf-8")

            report = DataEntitlementAuditor().audit(root)

            self.assertEqual(report.status, "blocked")

    def test_data_entitlement_accepts_configured_toss_pilot_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config").mkdir()
            (root / "config" / "data_entitlements.json").write_text(
                json.dumps(
                    {
                        "required_markets": ["KR", "US"],
                        "required_asset_kinds": ["stock", "etf"],
                        "require_survivorship_bias_free": False,
                        "require_corporate_actions_adjusted": False,
                        "providers": [
                            {
                                "name": "toss_official_openapi",
                                "licensed": True,
                                "markets": ["KR", "US"],
                                "asset_kinds": ["stock", "etf"],
                                "realtime_quotes": True,
                                "realtime_order_book": True,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            report = DataEntitlementAuditor().audit(root)

            self.assertEqual(report.status, "ok")

    def test_heartbeat_records_but_does_not_fake_30_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            HeartbeatRecorder().record(root, "ok", "test")
            report = HeartbeatAuditor().audit(root)

            self.assertEqual(report.status, "blocked")
            self.assertEqual(report.distinct_utc_days, 1)

    def test_heartbeat_audit_can_use_signed_pilot_required_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "data" / "evidence"
            evidence.mkdir(parents=True)
            (evidence / "live_promotion_approval.json").write_text(
                json.dumps(
                    {
                        "approved": True,
                        "approved_for": "live_auto",
                        "signed_by": "owner",
                        "approved_at": "2026-06-16T00:00:00+00:00",
                        "required_evidence": {"heartbeat_days": 1},
                    }
                ),
                encoding="utf-8",
            )
            HeartbeatRecorder().record(root, "ok", "test")

            report = HeartbeatAuditor().audit(root)

            self.assertEqual(report.status, "ok")
            self.assertIn("1 distinct UTC days", report.notes[0])


if __name__ == "__main__":
    unittest.main()
