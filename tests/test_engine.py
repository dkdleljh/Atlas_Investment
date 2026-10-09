from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atlas_investment.brokers.paper import PaperBroker
from atlas_investment.config import load_risk_policy, load_strategy_config
from atlas_investment.engine import TradingEngine
from atlas_investment.journal.writer import Journal
from atlas_investment.models import TradingMode


class EngineTest(unittest.TestCase):
    def test_paper_cycle_runs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tempdir:
            engine = TradingEngine(
                broker=PaperBroker(),
                policy=load_risk_policy(root / "config" / "risk_policy.json"),
                strategy_config=load_strategy_config(root / "config" / "strategy.json"),
                journal=Journal(Path(tempdir) / "journal.jsonl"),
                mode=TradingMode.PAPER,
            )
            summary = engine.run_once()
            self.assertEqual(summary["status"], "ok")
            self.assertGreater(summary["universe_count"], 0)

    def test_live_auto_is_blocked_when_policy_disallows_live_trading(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tempdir:
            engine = TradingEngine(
                broker=PaperBroker(),
                policy=load_risk_policy(root / "config" / "risk_policy.json"),
                strategy_config=load_strategy_config(root / "config" / "strategy.json"),
                journal=Journal(Path(tempdir) / "journal.jsonl"),
                mode=TradingMode.LIVE_AUTO,
            )
            summary = engine.run_once()
            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(summary["mode"], TradingMode.LIVE_AUTO.value)
            self.assertIn("비활성화", summary["reason"])

    def test_off_mode_blocks_cycle(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tempdir:
            engine = TradingEngine(
                broker=PaperBroker(),
                policy=load_risk_policy(root / "config" / "risk_policy.json"),
                strategy_config=load_strategy_config(root / "config" / "strategy.json"),
                journal=Journal(Path(tempdir) / "journal.jsonl"),
                mode=TradingMode.OFF,
            )
            summary = engine.run_once()
            self.assertEqual(summary["status"], "blocked")
            self.assertEqual(summary["mode"], TradingMode.OFF.value)


if __name__ == "__main__":
    unittest.main()
