from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import tempfile
import unittest

from atlas_investment.backtest.costs import CostModel
from atlas_investment.backtest.portfolio_engine import PortfolioBacktestEngine
from atlas_investment.brokers.toss_clients import TossApiConfig, TossApiReadiness
from atlas_investment.config import RiskPolicy
from atlas_investment.data.instruments import InstrumentMaster
from atlas_investment.data.ohlcv_store import generate_sample_ohlcv
from atlas_investment.data.quality import OhlcvQualityChecker
from atlas_investment.data.universe import load_institutional_sample_universe
from atlas_investment.models import Market, PortfolioSnapshot
from atlas_investment.ops.healthcheck import HealthCheckEngine
from atlas_investment.ops.scheduler import OpsScheduler
from atlas_investment.ops.trading_calendar import TradingCalendar
from atlas_investment.risk.correlation import CorrelationAnalyzer
from atlas_investment.risk.position_sizing import VolatilityPositionSizer
from atlas_investment.strategy.registry import get_strategy


def policy() -> RiskPolicy:
    return RiskPolicy(
        kill_switch=False,
        allow_live_trading=False,
        allow_margin_trading=False,
        allow_credit_trading=False,
        allow_leveraged_inverse=True,
        min_cash_ratio=0.15,
        max_single_position_weight=0.3,
        max_leveraged_inverse_weight=0.1,
        max_daily_order_amount_krw=1_000_000,
        max_daily_loss_krw=300_000,
        max_open_positions=20,
        min_score_to_buy=68,
        min_score_to_sell=35,
    )


class EnhancementModulesTest(unittest.TestCase):
    def test_instrument_master_round_trip(self) -> None:
        assets = load_institutional_sample_universe()
        master = InstrumentMaster.from_assets(assets)
        with tempfile.TemporaryDirectory() as tempdir:
            path = master.save(Path(tempdir) / "instrument_master.json")
            loaded = InstrumentMaster.load(path)
        self.assertEqual(loaded.summary()["instrument_count"], len(assets))
        self.assertGreater(len(loaded.tradable_assets()), 0)

    def test_ohlcv_quality_checker_passes_sample_data(self) -> None:
        candles = generate_sample_ohlcv("005930", days=130, start_price=80000)
        report = OhlcvQualityChecker().check("005930", candles, min_rows=120)
        self.assertTrue(report.passed)

    def test_cost_model_estimations(self) -> None:
        costs = CostModel(fee_rate=0.001, slippage_rate=0.001, tax_rate=0.002)
        buy = costs.estimate_buy(1_000_000)
        sell = costs.estimate_sell(1_000_000)
        self.assertEqual(buy.tax, 0)
        self.assertGreater(sell.tax, 0)

    def test_volatility_position_sizer_returns_quantity(self) -> None:
        asset = load_institutional_sample_universe()[0]
        candles = generate_sample_ohlcv(asset.symbol, days=130, start_price=80000)
        decision = VolatilityPositionSizer().size(asset, candles, PortfolioSnapshot(cash_krw=10_000_000), policy(), price_krw=80000)
        self.assertGreaterEqual(decision.quantity, 0)
        self.assertLessEqual(decision.target_weight, policy().max_single_position_weight)

    def test_portfolio_backtest_runs_multiple_symbols(self) -> None:
        assets = load_institutional_sample_universe()[:3]
        candles_by_symbol = {asset.symbol: generate_sample_ohlcv(asset.symbol, days=140, start_price=80000) for asset in assets}
        result = PortfolioBacktestEngine(initial_cash=9_000_000).run(assets, candles_by_symbol, get_strategy("moving_average_cross"))
        self.assertEqual(result.symbol_count, 3)
        self.assertGreater(result.final_equity, 0)

    def test_correlation_analyzer_detects_pairs(self) -> None:
        candles = generate_sample_ohlcv("A", days=130, start_price=100)
        pairs = CorrelationAnalyzer().top_pairs({"A": candles, "B": candles})
        self.assertEqual(len(pairs), 1)
        self.assertGreater(pairs[0].correlation, 0.9)

    def test_ops_scheduler_and_calendar(self) -> None:
        plan = OpsScheduler().build_daily_plan(date(2026, 5, 30))
        self.assertGreater(len(plan.steps), 0)
        session = TradingCalendar().session(datetime(2026, 5, 29, 9, 30), Market.KR)
        self.assertEqual(session.phase, "intraday")

    def test_healthcheck_and_toss_readiness_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            (root / "config").mkdir()
            (root / "config" / "risk_policy.json").write_text("{}", encoding="utf-8")
            (root / "config" / "strategy.json").write_text("{}", encoding="utf-8")
            (root / "src" / "atlas_investment").mkdir(parents=True)
            (root / "docs").mkdir()
            health = HealthCheckEngine().run(root)
        readiness = TossApiReadiness().check(TossApiConfig())
        self.assertEqual(health.overall_status, "ok")
        self.assertFalse(readiness.ready_for_live_orders)
        self.assertEqual(readiness.status, "blocked")


if __name__ == "__main__":
    unittest.main()
