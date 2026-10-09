from __future__ import annotations

import tempfile
import unittest
import json
from unittest.mock import patch
from argparse import Namespace
from pathlib import Path

from atlas_investment.brokers.toss_clients import TossApiConfig, TossApiReadiness
from atlas_investment.cli import _governance_record_with_live_approval, _sync_live_order_state_from_broker, algo_execution_plan, child_order_sim, daily_data_refresh, data_sync, ensemble_backtest, execution_sim, global_coverage_model, global_gap_audit, hedgefund_readiness, market_regime, phase20_audit, portfolio_optimizer, promotion_evidence, quant_portfolio, reconciliation_check, strategy_lab, strategy_readiness, toss_platform_fit
from atlas_investment.config import RiskPolicy
from atlas_investment.data.lake import DataLakeSyncConfig, DataLakeSynchronizer
from atlas_investment.data.ohlcv_store import generate_sample_ohlcv
from atlas_investment.data.universe import load_institutional_sample_universe
from atlas_investment.data.vendors import HybridMarketDataVendor, SampleMarketDataVendor
from atlas_investment.execution.router import ExecutionRouter
from atlas_investment.execution.algorithms import AlgorithmicExecutionPlanner
from atlas_investment.execution.child_orders import PaperChildOrderManager
from atlas_investment.fx.multicurrency import MultiCurrencyEngine
from atlas_investment.governance.records import GovernanceRegistry
from atlas_investment.governance.records import GovernanceRecord
from atlas_investment.models import OrderIntent, OrderType, Side, TradingMode
from atlas_investment.ops.hedgefund_readiness import HedgeFundReadinessAuditor
from atlas_investment.ops.phase20 import Phase20ReadinessAuditor
from atlas_investment.ops.promotion import PromotionEvidenceAuditor
from atlas_investment.ops.reconciliation import ReadOnlyReconciler
from atlas_investment.research.memo import InvestmentMemoGenerator
from atlas_investment.risk.fund import FundRiskGovernor
from atlas_investment.portfolio.strategy_allocation import StrategyEnsembleAllocator
from atlas_investment.portfolio.optimizer import PortfolioOptimizer
from atlas_investment.strategy.lab import StrategyLab, StrategyLabResult
from atlas_investment.strategy.readiness import StrategyPromotionGate
from atlas_investment.strategy.registry import all_strategies, get_strategy
from atlas_investment.brokers.mock import MockBroker


class Phase20Tests(unittest.TestCase):
    def test_data_lake_sync_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            results = DataLakeSynchronizer(Path(tmp)).sync_sample_universe(DataLakeSyncConfig(days=80, max_symbols=3))
            self.assertGreaterEqual(len(results), 4)
            self.assertTrue(Path(results[0].output_path).exists())

    def test_strategy_lab_runs_expanded_strategies(self) -> None:
        assets = load_institutional_sample_universe()[:2]
        candles = {asset.symbol: generate_sample_ohlcv(asset.symbol, days=140, start_price=80000) for asset in assets}
        results = StrategyLab().run(assets, candles, [get_strategy("moving_average_cross"), get_strategy("swing_momentum")])
        self.assertGreaterEqual(len(results), 2)
        self.assertIn("swing_momentum", {result.strategy for result in results})

    def test_registry_includes_institutional_strategy_styles(self) -> None:
        strategies = all_strategies()
        for name in {
            "time_series_momentum",
            "cross_sectional_momentum",
            "low_vol_defensive",
            "stat_arb_mean_reversion",
            "equity_long_short_quality",
            "liquidity_market_making_simulation",
            "multifactor_qvm",
            "shareholder_yield_carry",
            "sector_regime_rotation",
            "earnings_revision_event",
            "all_weather_risk_parity",
            "macro_regime_allocation",
            "cta_diversified_trend",
        }:
            self.assertIn(name, strategies)

    def test_fund_risk_governor_reports_actions(self) -> None:
        policy = RiskPolicy(False, False, False, False, True, 0.15, 0.25, 0.08, 1_000_000, 300_000, 10, 65, 35)
        report = FundRiskGovernor().evaluate(MockBroker().get_portfolio(), {asset.symbol: asset for asset in load_institutional_sample_universe()}, policy)
        self.assertIn(report.risk_level, {"green", "yellow", "red"})
        self.assertTrue(report.actions)

    def test_execution_router_blocks_live_without_official_api(self) -> None:
        asset = load_institutional_sample_universe()[0]
        order = OrderIntent(asset, Side.BUY, 1, OrderType.LIMIT, 80000, "test", 5)
        route = ExecutionRouter().route_orders([order], TradingMode.LIVE_AUTO, live_ready=False)[0]
        self.assertEqual(route.status, "blocked")

    def test_algorithmic_execution_blocks_live_and_simulates_paper(self) -> None:
        asset = load_institutional_sample_universe()[0]
        order = OrderIntent(asset, Side.BUY, 12, OrderType.LIMIT, 80000, "test", 5)
        live_plan = AlgorithmicExecutionPlanner().plan([order], "twap", TradingMode.LIVE_AUTO)
        self.assertEqual(live_plan.status, "blocked")
        paper_plan = AlgorithmicExecutionPlanner().plan([order], "pov", TradingMode.PAPER, slices_per_order=4)
        self.assertEqual(paper_plan.status, "simulated")
        self.assertEqual(paper_plan.slice_count, 4)
        self.assertEqual(paper_plan.total_quantity, 12)
        vwap_plan = AlgorithmicExecutionPlanner().plan([order], "vwap", TradingMode.PAPER, slices_per_order=4)
        self.assertEqual(vwap_plan.total_quantity, 12)
        adaptive_plan = AlgorithmicExecutionPlanner().plan([order], "adaptive", TradingMode.PAPER, slices_per_order=4)
        self.assertEqual(adaptive_plan.status, "simulated")
        self.assertGreater(adaptive_plan.slices[0].participation_rate, 0)
        child_report = PaperChildOrderManager().execute_plan(vwap_plan, TradingMode.PAPER, fill_ratio=0.5)
        self.assertEqual(child_report.status, "simulated")
        self.assertLess(child_report.filled_quantity, child_report.planned_quantity)

    def test_multicurrency_and_governance_and_memo(self) -> None:
        fx = MultiCurrencyEngine().analyze(MockBroker().get_portfolio(), usdkrw=1380)
        self.assertGreater(fx.equity_krw, 0)
        controls = GovernanceRegistry().default_phase20_controls()
        self.assertTrue(any(control.record_type == "live_promotion" for control in controls))
        asset = load_institutional_sample_universe()[0]
        signal = all_strategies()["moving_average_cross"].generate_signal(asset, generate_sample_ohlcv(asset.symbol, 140, 80000), 139)
        self.assertIsNotNone(signal)
        memo = InvestmentMemoGenerator().generate(signal)  # type: ignore[arg-type]
        self.assertIn("risk", memo.sections)

    def test_cli_phase20_commands(self) -> None:
        args = Namespace(days=90, max_symbols=2, initial_cash=10_000_000, strategies="moving_average_cross,swing_momentum", mode="dry_run", symbol="005930", vendor="sample")
        self.assertIn(data_sync(args)["status"], {"ok", "degraded"})
        self.assertEqual(strategy_lab(args)["status"], "ok")
        self.assertEqual(execution_sim(args)["status"], "simulated")
        self.assertIn(phase20_audit()["overall_status"], {"ok", "degraded", "blocked"})

    def test_phase20_reflects_official_toss_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "lake").mkdir(parents=True)
            (root / "data" / "reports").mkdir(parents=True)
            (root / "docs").mkdir(parents=True)
            (root / "docs" / "18_초거대_헤지펀드급_고도화_로드맵.md").write_text("# roadmap\n", encoding="utf-8")
            (root / "data" / "reports" / "toss_api_readiness.json").write_text(
                json.dumps({"official_docs_verified": True, "missing_items": [], "status": "manual_review_required"}),
                encoding="utf-8",
            )
            (root / "data" / "reports" / "reconciliation_check.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            (root / "data" / "reports" / "toss_live_order.json").write_text(
                json.dumps({"status": "submitted", "submit_attempted": True}),
                encoding="utf-8",
            )

            report = Phase20ReadinessAuditor().run(root)
            by_name = {item.name: item for item in report.items}

            self.assertEqual(by_name["official_toss_account_api"].status, "ok")
            self.assertEqual(by_name["live_order_api"].status, "ok")

    def test_cli_strategy_readiness_and_algo_plan(self) -> None:
        readiness_args = Namespace(days=180, max_symbols=2, initial_cash=10_000_000, strategy="scalping_simulation", realtime_data_ready=False, shorting_supported=False)
        readiness = strategy_readiness(readiness_args)
        self.assertEqual(readiness["status"], "blocked")
        algo_args = Namespace(symbol="005930", mode="paper", algorithm="twap", slices=3, participation_rate=0.05, limit=9)
        plan = algo_execution_plan(algo_args)
        self.assertEqual(plan["status"], "simulated")
        self.assertEqual(plan["slice_count"], 3)

    def test_strategy_readiness_keeps_rejected_low_trade_symbols_as_warning(self) -> None:
        results = [
            StrategyLabResult("multifactor_qvm", "005930", 3.0, -4.0, 3, 66.0, 55.0, True, []),
            StrategyLabResult("multifactor_qvm", "000660", 2.0, -3.0, 2, 50.0, 50.0, True, []),
            StrategyLabResult("multifactor_qvm", "035420", 0.0, 0.0, 0, 0.0, 38.0, False, []),
        ]

        decision = StrategyPromotionGate().evaluate("multifactor_qvm", results)

        self.assertEqual(decision.status, "approved_for_paper")
        self.assertEqual(decision.reasons, [])
        self.assertIn("035420", decision.warnings[0])

    def test_quant_ensemble_allocator_and_cli(self) -> None:
        asset = load_institutional_sample_universe()[0]
        candles = generate_sample_ohlcv(asset.symbol, days=180, start_price=80000)
        signals = [
            get_strategy("multifactor_qvm").generate_signal(asset, candles, len(candles) - 1),
            get_strategy("sector_regime_rotation").generate_signal(asset, candles, len(candles) - 1),
        ]
        report = StrategyEnsembleAllocator().allocate([signal for signal in signals if signal is not None])
        self.assertIn(report.status, {"ok", "blocked"})
        args = Namespace(days=180, max_symbols=4, strategies="multifactor_qvm,sector_regime_rotation,shareholder_yield_carry,macro_regime_allocation", max_position_weight=0.08, max_sector_weight=0.35)
        result = quant_portfolio(args)
        self.assertIn(result["status"], {"ok", "blocked"})
        self.assertGreaterEqual(result["signal_count"], 1)
        self.assertIn("market_regime", result)
        self.assertIn("risk_overlay_multiplier", result)
        optimizer_report = PortfolioOptimizer().optimize(report.candidates, {asset.symbol: candles}, method="risk_parity")
        self.assertIn(optimizer_report.status, {"ok", "blocked"})

    def test_market_regime_and_ensemble_backtest_cli(self) -> None:
        args = Namespace(
            days=220,
            max_symbols=4,
            initial_cash=10_000_000,
            strategies="multifactor_qvm,cross_sectional_momentum,low_vol_defensive,sector_regime_rotation,all_weather_risk_parity,cta_diversified_trend",
            symbol="005930",
            max_position_weight=0.08,
            max_sector_weight=0.35,
        )
        regime = market_regime(args)
        self.assertIn(regime["status"], {"ok", "insufficient_data"})
        result = ensemble_backtest(args)
        self.assertIn(result["status"], {"ok", "blocked"})
        self.assertIn("rebalance_count", result)
        self.assertIn("total_transaction_cost", result)

    def test_new_autonomous_readiness_cli_commands(self) -> None:
        optimizer_args = Namespace(days=180, max_symbols=6, strategies="multifactor_qvm,sector_regime_rotation,shareholder_yield_carry,all_weather_risk_parity,macro_regime_allocation,cta_diversified_trend", max_position_weight=0.08, max_sector_weight=0.35, max_gross_exposure=1.0, optimizer_method="risk_parity", target_volatility_pct=12.0)
        optimizer_result = portfolio_optimizer(optimizer_args)
        self.assertIn(optimizer_result["status"], {"ok", "blocked"})
        child_args = Namespace(symbol="005930", mode="paper", algorithm="vwap", slices=4, participation_rate=0.08, limit=8, fill_ratio=1.0)
        child_result = child_order_sim(child_args)
        self.assertEqual(child_result["status"], "simulated")
        gap_result = global_gap_audit()
        self.assertIn(gap_result["status"], {"ok", "degraded", "blocked"})
        self.assertIn("code_possible_blockers", gap_result)

    @patch("atlas_investment.data.lake.KoreanStockClient.trade_info")
    def test_daily_data_refresh_reports_safe_status(self, trade_info) -> None:
        trade_info.return_value = {"mock": True}
        args = Namespace(days=80, max_symbols=2, vendor="sample", include_kr_snapshots=True)
        report = daily_data_refresh(args)
        self.assertIn(report["status"], {"ok", "degraded"})
        self.assertGreaterEqual(report["synced"], 2)

    @patch("atlas_investment.data.lake.KoreanStockClient.trade_info")
    def test_daily_data_refresh_sample_default_is_offline(self, trade_info) -> None:
        args = Namespace(days=80, max_symbols=2, vendor="sample")
        report = daily_data_refresh(args)
        self.assertEqual(report["kr_snapshot_count"], 0)
        trade_info.assert_not_called()

    def test_hybrid_vendor_falls_back_on_exception(self) -> None:
        class BrokenVendor(SampleMarketDataVendor):
            name = "broken"

            def load_daily_ohlcv(self, asset, days):  # type: ignore[no-untyped-def]
                raise RuntimeError("network down")

        asset = load_institutional_sample_universe()[0]
        candles = HybridMarketDataVendor(BrokenVendor(), SampleMarketDataVendor()).load_daily_ohlcv(asset, 30)

        self.assertEqual(len(candles), 30)

    def test_hedgefund_readiness_blocks_until_global_live_requirements_exist(self) -> None:
        report = HedgeFundReadinessAuditor().run(Path.cwd())

        self.assertEqual(report.overall_status, "blocked")
        self.assertEqual(report.global_investment_status, "blocked")
        self.assertIn(report.autonomy_24x7_status, {"blocked", "degraded", "ok"})

    def test_hedgefund_readiness_cli(self) -> None:
        result = hedgefund_readiness()

        self.assertEqual(result["overall_status"], "blocked")
        self.assertGreater(result["blocked"], 0)

    def test_toss_readiness_requires_official_docs_url(self) -> None:
        report = TossApiReadiness().check(TossApiConfig(docs_url=None))

        self.assertEqual(report.status, "blocked")
        self.assertFalse(report.official_docs_verified)
        self.assertIn("공식 API 문서 URL", report.missing_items)

    def test_reconciliation_blocks_without_readonly_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = ReadOnlyReconciler().reconcile(Path(tmp))

        self.assertEqual(report.status, "blocked")
        self.assertGreaterEqual(len(report.differences), 1)

    def test_reconciliation_detects_quantity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "orders").mkdir(parents=True)
            (root / "data" / "official_broker_snapshots" / "toss").mkdir(parents=True)
            (root / "data" / "orders" / "runtime_order_state_store.json").write_text(
                json.dumps([
                    {"idempotency_key": "a", "symbol": "005930", "side": "buy", "quantity": 3, "status": "filled", "events": []}
                ]),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "positions.json").write_text(
                json.dumps([{"symbol": "005930", "quantity": 2}]),
                encoding="utf-8",
            )
            report = ReadOnlyReconciler().reconcile(root)

        self.assertEqual(report.status, "blocked")
        self.assertTrue(any(difference.code == "position_quantity_mismatch" for difference in report.differences))

    def test_reconciliation_accepts_account_summary_and_ignores_unfilled_orders_for_positions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "orders").mkdir(parents=True)
            (root / "data" / "official_broker_snapshots" / "toss").mkdir(parents=True)
            (root / "data" / "orders" / "runtime_order_state_store.json").write_text(
                json.dumps([
                    {"idempotency_key": "queued", "symbol": "005930", "side": "buy", "quantity": 3, "status": "queued", "events": []}
                ]),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "positions.json").write_text("[]", encoding="utf-8")
            (root / "data" / "official_broker_snapshots" / "toss" / "account_summary.json").write_text(json.dumps({"cash_krw": 1_000_000}), encoding="utf-8")

            report = ReadOnlyReconciler().reconcile(root)

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.broker_cash_krw, 1_000_000)

    def test_reconciliation_prefers_live_state_over_historical_paper_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "orders").mkdir(parents=True)
            (root / "data" / "official_broker_snapshots" / "toss").mkdir(parents=True)
            (root / "data" / "orders" / "runtime_order_state_store.json").write_text(
                json.dumps(
                    [
                        {
                            "idempotency_key": "paper-filled",
                            "symbol": "005930",
                            "side": "buy",
                            "quantity": 3,
                            "status": "filled",
                            "events": [],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (root / "data" / "orders" / "live_order_state_store.json").write_text("[]", encoding="utf-8")
            (root / "data" / "official_broker_snapshots" / "toss" / "positions.json").write_text("[]", encoding="utf-8")
            (root / "data" / "official_broker_snapshots" / "toss" / "open_orders.json").write_text("[]", encoding="utf-8")
            (root / "data" / "official_broker_snapshots" / "toss" / "fills.json").write_text("[]", encoding="utf-8")
            (root / "data" / "official_broker_snapshots" / "toss" / "account_summary.json").write_text(
                json.dumps({"cash_by_currency": {"KRW": 260.0, "USD": 0.11}}),
                encoding="utf-8",
            )

            report = ReadOnlyReconciler().reconcile(root)

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.internal_order_count, 0)
        self.assertEqual(report.broker_cash_by_currency["KRW"], 260.0)

    def test_reconciliation_checks_open_orders_fills_and_cash_by_currency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "orders").mkdir(parents=True)
            (root / "data" / "official_broker_snapshots" / "toss").mkdir(parents=True)
            (root / "data" / "orders" / "runtime_order_state_store.json").write_text(
                json.dumps(
                    [
                        {"idempotency_key": "filled-1", "symbol": "005930", "side": "buy", "quantity": 3, "status": "filled", "events": []},
                        {"idempotency_key": "open-1", "symbol": "AAPL", "side": "buy", "quantity": 1, "status": "submitted", "events": []},
                    ]
                ),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "positions.json").write_text(
                json.dumps([{"symbol": "005930", "quantity": 3}]),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "open_orders.json").write_text(
                json.dumps([{"client_order_id": "open-1", "symbol": "AAPL", "quantity": 1}]),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "fills.json").write_text(
                json.dumps([{"client_order_id": "filled-1", "symbol": "005930", "quantity": 3}]),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "account.json").write_text(
                json.dumps({"cash_by_currency": {"KRW": 1_000_000, "USD": 250.5}}),
                encoding="utf-8",
            )

            report = ReadOnlyReconciler().reconcile(root)

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.internal_open_order_count, 1)
        self.assertEqual(report.broker_open_order_count, 1)
        self.assertEqual(report.broker_fill_count, 1)
        self.assertEqual(report.broker_cash_by_currency["USD"], 250.5)

    def test_reconciliation_accepts_filled_order_when_position_supports_missing_fills(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "orders").mkdir(parents=True)
            (root / "data" / "official_broker_snapshots" / "toss").mkdir(parents=True)
            (root / "data" / "orders" / "live_order_state_store.json").write_text(
                json.dumps([
                    {"idempotency_key": "filled-1", "symbol": "0177N0", "side": "buy", "quantity": "1", "status": "filled", "events": []}
                ]),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "positions.json").write_text(
                json.dumps([{"symbol": "0177N0", "quantity": "1"}]),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "open_orders.json").write_text("[]", encoding="utf-8")
            (root / "data" / "official_broker_snapshots" / "toss" / "fills.json").write_text("[]", encoding="utf-8")
            (root / "data" / "official_broker_snapshots" / "toss" / "account.json").write_text(
                json.dumps({"cash_by_currency": {"KRW": 984360.0, "USD": 0.11}}),
                encoding="utf-8",
            )

            report = ReadOnlyReconciler().reconcile(root)

        self.assertEqual(report.status, "ok")
        self.assertEqual(report.internal_position_count, 1)
        self.assertEqual(report.broker_position_count, 1)

    def test_live_order_sync_marks_submitted_buy_filled_when_position_appears(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data" / "orders").mkdir(parents=True)
            (root / "data" / "official_broker_snapshots" / "toss").mkdir(parents=True)
            state_path = root / "data" / "orders" / "live_order_state_store.json"
            state_path.write_text(
                json.dumps([
                    {"idempotency_key": "order-1", "symbol": "0177N0", "side": "buy", "quantity": "1", "status": "submitted", "events": []}
                ]),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "positions.json").write_text(
                json.dumps([{"symbol": "0177N0", "quantity": "1"}]),
                encoding="utf-8",
            )
            (root / "data" / "official_broker_snapshots" / "toss" / "open_orders.json").write_text("[]", encoding="utf-8")

            result = _sync_live_order_state_from_broker(root)
            orders = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertEqual(result["updated_orders"], 1)
        self.assertEqual(orders[0]["status"], "filled")
        self.assertEqual(orders[0]["fill_source"], "broker_position_snapshot")

    def test_reconciliation_cli_writes_report(self) -> None:
        result = reconciliation_check()

        self.assertIn(result["status"], {"ok", "degraded", "blocked"})
        self.assertTrue(Path(result["path"]).exists())

    def test_global_coverage_model_has_required_domain_enums(self) -> None:
        result = global_coverage_model()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["missing_markets"], [])
        self.assertEqual(result["missing_asset_kinds"], [])

    def test_promotion_evidence_blocks_without_real_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = PromotionEvidenceAuditor().audit(Path(tmp))

        self.assertEqual(result.status, "blocked")
        self.assertGreater(sum(1 for item in result.requirements if item.status == "blocked"), 0)

    def test_promotion_approval_requires_explicit_signed_live_auto_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "data" / "evidence"
            evidence.mkdir(parents=True)
            (evidence / "dry_run_days.json").write_text(json.dumps({"days": 30}), encoding="utf-8")
            (evidence / "paper_days.json").write_text(json.dumps({"days": 30}), encoding="utf-8")
            (evidence / "reconciliation_days.json").write_text(json.dumps({"days": 10}), encoding="utf-8")
            (evidence / "small_order_trials.json").write_text(json.dumps({"passed_trials": 1}), encoding="utf-8")
            approval = evidence / "live_promotion_approval.json"
            approval.write_text(json.dumps({"approved": False, "approved_for": "live_auto"}), encoding="utf-8")

            blocked = PromotionEvidenceAuditor().audit(root)
            approval.write_text(
                json.dumps(
                    {
                        "approved": True,
                        "approved_for": "live_auto",
                        "signed_by": "owner",
                        "approved_at": "2026-06-16T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            ok = PromotionEvidenceAuditor().audit(root)

            self.assertEqual(blocked.status, "blocked")
            self.assertEqual(ok.status, "ok")

    def test_promotion_approval_can_define_pilot_evidence_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "data" / "evidence"
            evidence.mkdir(parents=True)
            (evidence / "dry_run_days.json").write_text(json.dumps({"days": 3}), encoding="utf-8")
            (evidence / "paper_days.json").write_text(json.dumps({"days": 3}), encoding="utf-8")
            (evidence / "reconciliation_days.json").write_text(json.dumps({"days": 3}), encoding="utf-8")
            (evidence / "small_order_trials.json").write_text(json.dumps({"passed_trials": 1}), encoding="utf-8")
            (evidence / "live_promotion_approval.json").write_text(
                json.dumps(
                    {
                        "approved": True,
                        "approved_for": "live_auto",
                        "signed_by": "owner",
                        "approved_at": "2026-06-16T00:00:00+00:00",
                        "required_evidence": {
                            "dry_run_business_days": 3,
                            "paper_business_days": 3,
                            "read_only_reconciliation_business_days": 3,
                            "manual_small_order_trials": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )

            report = PromotionEvidenceAuditor().audit(root)

            self.assertEqual(report.status, "ok")
            self.assertEqual(report.requirements[0].name, "dry_run_3_business_days")

    def test_governance_live_promotion_record_uses_signed_approval(self) -> None:
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
                        "scope": {"mode": "kr_us_stock_etf_pilot"},
                    }
                ),
                encoding="utf-8",
            )
            record = GovernanceRecord("live_promotion", "라이브 전환 승인 기록", "blocked", True, [])

            updated = _governance_record_with_live_approval(record, root)

            self.assertEqual(updated.status, "ready")
            self.assertIn("kr_us_stock_etf_pilot", updated.notes[1])

    def test_toss_platform_fit_constrains_asset_scope(self) -> None:
        result = toss_platform_fit()

        self.assertEqual(result["status"], "ok")
        self.assertIn("stock", result["supported_asset_kinds"])
        self.assertIn("option", result["supported_asset_kinds"])
        self.assertIn("future", result["excluded_asset_kinds"])

    def test_paper_broker_usd_order_normalizes_cash_to_krw(self) -> None:
        broker = MockBroker()
        asset = next(asset for asset in load_institutional_sample_universe() if asset.symbol == "AAPL")
        before = broker.get_portfolio().cash_krw
        broker.place_order(OrderIntent(asset, Side.BUY, 1, OrderType.LIMIT, 200, "test", 5))
        after = broker.get_portfolio().cash_krw

        self.assertEqual(before - after, 276_000)


if __name__ == "__main__":
    unittest.main()
