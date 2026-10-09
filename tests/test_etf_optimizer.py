from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from atlas_investment.cli import etf_cost_optimizer
from atlas_investment.portfolio.etf_optimizer import EtfCandidate, EtfCostOptimizer, ensure_default_etf_config


class EtfCostOptimizerTests(unittest.TestCase):
    def test_optimizer_prefers_lower_total_real_cost_not_just_low_fee(self) -> None:
        candidates = [
            EtfCandidate(
                symbol="LOWFEE",
                name="Low Fee Thin ETF",
                exposure_group="NASDAQ100",
                annual_expense_rate=0.0001,
                estimated_spread_rate=0.0020,
                average_daily_value_krw=100_000_000,
            ),
            EtfCandidate(
                symbol="BALANCED",
                name="Balanced ETF",
                exposure_group="NASDAQ100",
                annual_expense_rate=0.0005,
                estimated_spread_rate=0.0002,
                average_daily_value_krw=10_000_000_000,
            ),
        ]
        report = EtfCostOptimizer().optimize(candidates, "NASDAQ100", 10_000_000, 365)
        self.assertEqual(report.status, "ok")
        self.assertIsNotNone(report.recommendation)
        self.assertEqual(report.recommendation.candidate.symbol, "BALANCED")

    def test_switch_analysis_requires_savings_to_exceed_switch_cost(self) -> None:
        candidates = [
            EtfCandidate(
                symbol="CURRENT",
                name="Current ETF",
                exposure_group="NASDAQ100",
                annual_expense_rate=0.0010,
                estimated_spread_rate=0.0002,
                average_daily_value_krw=10_000_000_000,
            ),
            EtfCandidate(
                symbol="CHEAPER",
                name="Cheaper ETF",
                exposure_group="NASDAQ100",
                annual_expense_rate=0.0009,
                estimated_spread_rate=0.0002,
                average_daily_value_krw=10_000_000_000,
            ),
        ]
        report = EtfCostOptimizer().optimize(candidates, "NASDAQ100", 1_000_000, 365, current_symbol="CURRENT")
        self.assertIsNotNone(report.switch_analysis)
        self.assertFalse(report.switch_analysis.should_switch)

    def test_default_config_and_cli_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = ensure_default_etf_config(Path(tmp) / "etf_equivalence.json")
            self.assertTrue(path.exists())
        args = Namespace(
            exposure_group="NASDAQ100_KR_UNHEDGED",
            amount_krw=10_000_000,
            holding_days=365,
            current_symbol="133690",
            min_liquidity_krw=500_000_000,
            switch_safety_margin_rate=0.0005,
        )
        result = etf_cost_optimizer(args)
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(result["ranking_count"], 3)
        self.assertIsNotNone(result["recommendation"])


if __name__ == "__main__":
    unittest.main()
