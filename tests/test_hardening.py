from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from atlas_investment.accounting.multicurrency import CurrencyCashBook, FxRateBook, MultiCurrencyAccountingEngine
from atlas_investment.backtest.validation import StrategyValidator
from atlas_investment.brokers.mock import MockBroker
from atlas_investment.cli import accounting_ledger, cost_report, dashboard_html, data_snapshot_audit, order_state_smoke, strategy_validate
from atlas_investment.cost_policy import FundFeeModel, load_cost_policy
from atlas_investment.data.audit import DataSnapshotAuditor
from atlas_investment.data.instruments import InstrumentMaster
from atlas_investment.data.ohlcv_store import OhlcvStore, generate_sample_ohlcv
from atlas_investment.data.universe import load_institutional_sample_universe, load_runtime_universe
from atlas_investment.execution.state_machine import OrderStateStore, OrderStatus
from atlas_investment.models import OrderIntent, OrderType, Side
from atlas_investment.strategy.registry import get_strategy


class HardeningTests(unittest.TestCase):
    def test_multicurrency_ledger_separates_cash_and_positions(self) -> None:
        ledger = MultiCurrencyAccountingEngine().build_ledger(
            MockBroker().get_portfolio(),
            FxRateBook(rates_to_krw={"KRW": 1.0, "USD": 1380.0}),
            CurrencyCashBook({"KRW": 5_000_000, "USD": 100}),
        )
        self.assertGreater(ledger.equity_krw, 0)
        self.assertIn("KRW", ledger.currency_weights)
        self.assertIn("USD", ledger.currency_weights)

    def test_order_state_machine_rejects_invalid_transition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            asset = load_institutional_sample_universe()[0]
            order = OrderIntent(asset, Side.BUY, 1, OrderType.LIMIT, 80000, "test", 3)
            store = OrderStateStore(Path(tmp) / "orders.json")
            store.create(order)
            with self.assertRaises(ValueError):
                store.transition(order.idempotency_key, OrderStatus.FILLED, "cannot fill before submit")

    def test_strategy_validator_outputs_walk_forward_and_monte_carlo(self) -> None:
        asset = load_institutional_sample_universe()[0]
        candles = generate_sample_ohlcv(asset.symbol, days=160, start_price=80000)
        report = StrategyValidator().validate(asset, candles, get_strategy("moving_average_cross"), folds=2, trials=50)
        self.assertGreaterEqual(len(report.folds), 1)
        self.assertEqual(report.monte_carlo.trials, 50)
        self.assertIsInstance(report.sharpe_ratio, float)
        self.assertIsInstance(report.profit_factor, float)
        self.assertIsInstance(report.benchmark_beta, float)

    def test_data_snapshot_auditor_records_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = OhlcvStore(Path(tmp))
            store.save("005930", generate_sample_ohlcv("005930", days=80, start_price=80000))
            report = DataSnapshotAuditor().audit(Path(tmp))
            self.assertEqual(report.status, "ok")
            self.assertEqual(len(report.records[0].checksum), 64)

    def test_new_cli_hardening_commands(self) -> None:
        args = Namespace(symbol="005930", strategy="moving_average_cross", days=160, initial_cash=10_000_000, ending_equity=10_500_000, usdkrw=1380, cash_krw=5_000_000, cash_usd=100, folds=2, trials=50)
        self.assertEqual(accounting_ledger(args)["status"], "ok")
        self.assertEqual(cost_report(args)["status"], "ok")
        self.assertIn(order_state_smoke(args)["status"], {"queued", "validated"})
        self.assertIn(strategy_validate(args)["status"], {"ok", "degraded"})
        self.assertIn(data_snapshot_audit()["status"], {"ok", "degraded"})
        self.assertEqual(dashboard_html()["status"], "ok")

    def test_fund_fee_model_accrues_recurring_costs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        policy = load_cost_policy(root / "config" / "cost_policy.json")
        accrual = FundFeeModel(policy).accrue(100_000_000, 30, ending_equity_krw=101_000_000)
        self.assertGreater(accrual.management_fee, 0)
        self.assertGreater(accrual.custody_admin_fee, 0)
        self.assertLess(accrual.net_equity_krw, 101_000_000)

    def test_runtime_universe_does_not_shrink_to_stale_small_lake_master(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            small = load_institutional_sample_universe()[:2]
            InstrumentMaster.from_assets(small).save(root / "data" / "lake" / "instrument_master.json")
            assets, source, notes = load_runtime_universe(root)
            self.assertGreater(len(assets), len(small))
            self.assertEqual(source, "institutional_sample")
            self.assertTrue(any("작습니다" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
