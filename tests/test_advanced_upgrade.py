from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from atlas_investment.backtest.realistic import MarketImpactCostModel
from atlas_investment.cli import advanced_internal_upgrade
from atlas_investment.data.defense import DataDefenseLayer
from atlas_investment.data.ohlcv_store import generate_sample_ohlcv
from atlas_investment.data.universe import load_institutional_sample_universe
from atlas_investment.governance.audit_trail import AuditTrailWriter
from atlas_investment.models import PortfolioSnapshot, Position
from atlas_investment.portfolio.meta_allocator import MetaStrategyAllocator
from atlas_investment.realtime.replay import HistoricalEventReplay
from atlas_investment.research.factory import ResearchFactory
from atlas_investment.risk.advanced import AdvancedPortfolioRiskEngine
from atlas_investment.strategy.auto_tune import StrategyParameterTuner
from atlas_investment.strategy.lifecycle import StrategyLifecycleManager
from atlas_investment.strategy.registry import all_strategies, get_strategy
from atlas_investment.backtest.validation import StrategyValidator


class AdvancedUpgradeTests(unittest.TestCase):
    def test_ml_strategy_is_registered_and_generates_signal(self) -> None:
        asset = load_institutional_sample_universe()[0]
        candles = generate_sample_ohlcv(asset.symbol, days=180, start_price=80000)
        self.assertIn("ml_alpha_score", all_strategies())
        signal = get_strategy("ml").generate_signal(asset, candles, len(candles) - 1)
        self.assertIsNotNone(signal)

    def test_advanced_modules_smoke(self) -> None:
        asset = load_institutional_sample_universe()[0]
        candles = generate_sample_ohlcv(asset.symbol, days=180, start_price=80000)
        strategy = get_strategy("ml_alpha_score")
        validation = StrategyValidator().validate(asset, candles, strategy, trials=20)
        tuning = StrategyParameterTuner().tune(asset, candles, strategy)
        self.assertIn(tuning.status, {"ok", "blocked"})
        meta = MetaStrategyAllocator().allocate([validation])
        self.assertEqual(meta.status, "ok")
        cost = MarketImpactCostModel().estimate(candles, notional=1_000_000)
        self.assertGreater(cost.cost_bps, 0)
        defense = DataDefenseLayer().inspect(asset.symbol, candles)
        self.assertIn(defense.status, {"ok", "degraded", "blocked"})
        replay = HistoricalEventReplay().run(asset, candles)
        self.assertEqual(replay.status, "ok")
        research = ResearchFactory().build(asset, candles)
        self.assertEqual(research.status, "ok")
        decision = StrategyLifecycleManager().decide(validation)
        self.assertIn(decision.status, {"quarantine", "paper_only", "promote_candidate", "lab"})

    def test_advanced_risk_and_audit_trail(self) -> None:
        asset = load_institutional_sample_universe()[0]
        candles = generate_sample_ohlcv(asset.symbol, days=180, start_price=80000)
        portfolio = PortfolioSnapshot(1_000_000, {asset.symbol: Position(asset.symbol, 10, 80000, 800000)})
        report = AdvancedPortfolioRiskEngine().analyze(portfolio, {asset.symbol: asset}, {asset.symbol: candles})
        self.assertIn(report.status, {"ok", "degraded"})
        with tempfile.TemporaryDirectory() as tmp:
            record = AuditTrailWriter().write(Path(tmp) / "audit.jsonl", "test", asset.symbol, report)
            self.assertEqual(len(record.payload_hash), 64)

    def test_advanced_internal_upgrade_cli(self) -> None:
        args = Namespace(days=180, max_symbols=4, initial_cash=10_000_000, amount_krw=1_000_000, participation_rate=0.08, limit=5)
        result = advanced_internal_upgrade(args)
        self.assertIn(result["status"], {"ok", "blocked"})
        self.assertEqual(result["ml_ai_strategy"], "ml_alpha_score")
        self.assertIn("audit_hash", result)


if __name__ == "__main__":
    unittest.main()
