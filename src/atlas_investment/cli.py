from __future__ import annotations

import argparse
import json
import os
import shutil
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any

from atlas_investment.analytics.dashboard import build_operations_dashboard
from atlas_investment.analytics.html_dashboard import render_static_dashboard
from atlas_investment.analytics.performance import rank_backtests
from atlas_investment.analytics.report import save_backtest_result, summarize_backtest
from atlas_investment.backtest.engine import BacktestEngine
from atlas_investment.backtest.ensemble import EnsemblePortfolioBacktester
from atlas_investment.backtest.portfolio_engine import PortfolioBacktestEngine
from atlas_investment.backtest.realistic import MarketImpactCostModel
from atlas_investment.backtest.validation import StrategyValidator
from atlas_investment.brokers.mock import MockBroker
from atlas_investment.brokers.paper import PaperBroker
from atlas_investment.brokers.toss_clients import TossApiConfig, TossApiReadiness, TossOfficialApiClient
from atlas_investment.brokers.toss_platform import TossPlatformFitAuditor
from atlas_investment.config import load_risk_policy, load_strategy_config
from atlas_investment.cost_policy import FundFeeModel, load_cost_policy
from atlas_investment.accounting.multicurrency import CurrencyCashBook, FxRateBook, MultiCurrencyAccountingEngine
from atlas_investment.data.audit import DataSnapshotAuditor
from atlas_investment.data.entitlements import DataEntitlementAuditor
from atlas_investment.data.global_catalog import GlobalCoverageModel
from atlas_investment.data.instruments import InstrumentMaster
from atlas_investment.data.defense import DataDefenseLayer
from atlas_investment.data.lake import DataLakeSyncConfig, DataLakeSynchronizer, build_market_data_vendor
from atlas_investment.data.ohlcv_store import OhlcvStore
from atlas_investment.data.quality import OhlcvQualityChecker
from atlas_investment.data.universe import export_universe_snapshot, filter_tradable_universe, load_institutional_sample_universe, load_runtime_universe
from atlas_investment.engine import TradingEngine
from atlas_investment.execution.algorithms import AlgorithmicExecutionPlanner
from atlas_investment.execution.child_orders import PaperChildOrderManager
from atlas_investment.execution.router import ExecutionRouter
from atlas_investment.execution.state_machine import OrderStateStore, OrderStatus
from atlas_investment.fx.overlay import FxOverlayEngine
from atlas_investment.fx.multicurrency import MultiCurrencyEngine
from atlas_investment.governance.records import GovernanceRegistry
from atlas_investment.governance.audit_trail import AuditTrailWriter
from atlas_investment.integrations.dart import DartClient
from atlas_investment.integrations.korean_stock import KoreanStockClient
from atlas_investment.integrations.setup_check import IntegrationSetupChecker
from atlas_investment.integrations.vibe_catalog import build_skill_catalog
from atlas_investment.integrations.yahoo import YahooFinanceClient
from atlas_investment.journal.writer import Journal
from atlas_investment.models import Asset, Market, OrderIntent, OrderType, Side, Signal, TradingMode
from atlas_investment.ops.healthcheck import HealthCheckEngine
from atlas_investment.ops.alerting import AlertEngine
from atlas_investment.ops.global_gap import GlobalGapAuditor
from atlas_investment.ops.heartbeat import HeartbeatAuditor, HeartbeatRecorder
from atlas_investment.ops.hedgefund_readiness import HedgeFundReadinessAuditor
from atlas_investment.ops.phase20 import Phase20ReadinessAuditor
from atlas_investment.ops.promotion import PromotionEvidenceAuditor, PromotionEvidenceRecorder
from atlas_investment.ops.reconciliation import ReadOnlyReconciler
from atlas_investment.ops.reporting import render_markdown_status, write_daily_risk_report
from atlas_investment.ops.scheduler import OpsScheduler
from atlas_investment.portfolio.etf_optimizer import EtfCostOptimizer, ensure_default_etf_config
from atlas_investment.portfolio.optimizer import PortfolioOptimizer
from atlas_investment.portfolio.meta_allocator import MetaStrategyAllocator
from atlas_investment.portfolio.risk_overlay import RiskOverlay
from atlas_investment.portfolio.strategy_allocation import AllocationCandidate, StrategyEnsembleAllocator
from atlas_investment.realtime.event_bus import EventBus
from atlas_investment.realtime.replay import HistoricalEventReplay
from atlas_investment.research.factory import ResearchFactory
from atlas_investment.research.memo import InvestmentMemoGenerator
from atlas_investment.risk.fund import FundRiskGovernor
from atlas_investment.risk.advanced import AdvancedPortfolioRiskEngine
from atlas_investment.risk.institutional import InstitutionalRiskEngine
from atlas_investment.strategy.auto_tune import StrategyParameterTuner
from atlas_investment.strategy.lab import StrategyLab
from atlas_investment.strategy.lifecycle import StrategyLifecycleManager
from atlas_investment.strategy.cross_sectional import CrossSectionalMomentumRanker
from atlas_investment.strategy.regime import MarketRegimeDetector
from atlas_investment.strategy.readiness import StrategyPromotionGate
from atlas_investment.strategy.registry import all_strategies, get_strategy


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_project_env(root: Path | None = None) -> None:
    """Load KEY=VALUE pairs from project .env without overriding real env vars.

    Atlas Investment is usually run via systemd/user shells where a local .env file
    is not automatically sourced. This lightweight loader keeps local developer
    runs and the daemon consistent while preserving externally provided secrets.
    """
    env_path = (root or project_root()) / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, default=json_default)
    return path


def make_broker(mode: TradingMode):
    if mode == TradingMode.PAPER:
        return PaperBroker()
    return MockBroker()


def run_cycle(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    mode = TradingMode(args.mode)
    universe, universe_source, universe_notes = load_runtime_universe(root)
    engine = TradingEngine(
        broker=make_broker(mode),
        policy=load_risk_policy(root / "config" / "risk_policy.json"),
        strategy_config=load_strategy_config(root / "config" / "strategy.json"),
        journal=Journal(root / "data" / "journals" / "atlas_investment.jsonl"),
        mode=mode,
        universe=universe,
        universe_source=universe_source,
        order_state_store=OrderStateStore(root / "data" / "orders" / "runtime_order_state_store.json"),
    )
    result = engine.run_once()
    if universe_notes:
        result["universe_notes"] = universe_notes
    return result


def run_backtest(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    asset = _asset_for_symbol(args.symbol)
    candles = OhlcvStore(root / "data" / "ohlcv").load_or_generate_sample(args.symbol, days=args.days, start_price=80000)
    cost_policy_path = root / "config" / "cost_policy.json"
    engine = BacktestEngine.from_cost_policy(asset, load_cost_policy(cost_policy_path), initial_cash=args.initial_cash) if cost_policy_path.exists() else BacktestEngine(initial_cash=args.initial_cash)
    result = engine.run(asset, candles, get_strategy(args.strategy))
    path = save_backtest_result(result, root / "data" / "backtests" / f"{args.symbol}_{args.strategy}.json")
    return {"summary": summarize_backtest(result), "path": str(path)}


def compare_strategies(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    asset = _asset_for_symbol(args.symbol)
    candles = OhlcvStore(root / "data" / "ohlcv").load_or_generate_sample(args.symbol, days=args.days, start_price=80000)
    results = [
        BacktestEngine(initial_cash=args.initial_cash).run(asset, candles, get_strategy(strategy))
        for strategy in ["moving_average_cross", "momentum_breakout", "mean_reversion"]
    ]
    ranking = rank_backtests(results)
    path = write_json(root / "data" / "reports" / f"strategy_compare_{args.symbol}.json", ranking)
    return {"rankings": ranking, "path": str(path)}


def export_universe() -> dict[str, Any]:
    root = project_root()
    assets = load_institutional_sample_universe()
    tradable = filter_tradable_universe(assets)
    universe_path = export_universe_snapshot(tradable, root / "data" / "universe" / "institutional_sample.json")
    master_path = InstrumentMaster.from_assets(assets).save(root / "data" / "universe" / "instrument_master.json")
    return {"asset_count": len(assets), "tradable_count": len(tradable), "universe_path": str(universe_path), "master_path": str(master_path)}


def data_audit(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    store = OhlcvStore(root / "data" / "ohlcv")
    checker = OhlcvQualityChecker()
    reports = []
    for asset in load_institutional_sample_universe()[: args.max_symbols]:
        candles = store.load_or_generate_sample(asset.symbol, days=args.days, start_price=80000)
        reports.append(checker.check(asset.symbol, candles))
    path = write_json(root / "data" / "reports" / "data_audit.json", reports)
    return {"overall_status": "ok" if all(report.passed for report in reports) else "blocked", "report_count": len(reports), "path": str(path)}


def portfolio_backtest(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    assets = load_institutional_sample_universe()[: args.max_symbols]
    store = OhlcvStore(root / "data" / "ohlcv")
    candles_by_symbol = {asset.symbol: store.load_or_generate_sample(asset.symbol, days=args.days, start_price=80000) for asset in assets}
    result = PortfolioBacktestEngine(initial_cash=args.initial_cash, max_symbols=args.max_symbols).run(assets, candles_by_symbol, get_strategy(args.strategy))
    path = write_json(root / "data" / "backtests" / f"portfolio_{args.strategy}.json", result)
    return {"summary": {"strategy": result.strategy, "symbol_count": result.symbol_count, "final_equity": round(result.final_equity, 2), "total_return_pct": round(result.total_return_pct, 2), "trade_count": result.trade_count}, "path": str(path)}


def cost_report(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    policy = load_cost_policy(root / "config" / "cost_policy.json")
    accrual = FundFeeModel(policy).accrue(args.initial_cash, args.days, ending_equity_krw=args.ending_equity)
    market_costs = {
        market: {
            "commission_rate": costs.commission_rate,
            "slippage_rate": costs.slippage_rate,
            "sell_tax_rate": costs.sell_tax_rate,
            "fx_spread_rate": costs.fx_spread_rate,
        }
        for market, costs in policy.markets.items()
    }
    payload = {"policy": {"base_currency": policy.base_currency, "markets": market_costs}, "fee_accrual": accrual}
    path = write_json(root / "data" / "reports" / "cost_report.json", payload)
    return {"status": "ok", "total_fee": accrual.total_fee, "net_equity_krw": accrual.net_equity_krw, "path": str(path)}


def risk_report() -> dict[str, Any]:
    root = project_root()
    policy = load_risk_policy(root / "config" / "risk_policy.json")
    broker = MockBroker()
    assets = {asset.symbol: asset for asset in load_institutional_sample_universe()}
    report = InstitutionalRiskEngine().exposure_report(broker.get_portfolio(), assets, policy)
    path = write_daily_risk_report(report, root / "data" / "reports" / "daily_risk_report.json")
    return {"status": "ok" if not report.breaches else "blocked", "breaches": report.breaches, "path": str(path)}


def fx_overlay(args: argparse.Namespace) -> dict[str, Any]:
    decision = FxOverlayEngine().decide(args.usdkrw, args.usdkrw_average, args.current_usd_exposure)
    path = write_json(project_root() / "data" / "reports" / "fx_overlay.json", decision)
    return {"decision": decision, "path": str(path)}


def realtime_smoke() -> dict[str, Any]:
    bus = EventBus()
    bus.publish("quote", "005930", {"price": 80000})
    bus.publish("order_status", "005930", {"status": "simulated"})
    events = bus.drain()
    path = write_json(project_root() / "data" / "reports" / "realtime_smoke.json", events)
    return {"status": "ok", "event_count": len(events), "path": str(path)}


def ops_plan() -> dict[str, Any]:
    plan = OpsScheduler().build_daily_plan(date.today())
    path = write_json(project_root() / "data" / "reports" / "ops_plan.json", plan)
    return {"plan_date": plan.plan_date, "step_count": len(plan.steps), "path": str(path)}


def healthcheck() -> dict[str, Any]:
    root = project_root()
    report = HealthCheckEngine().run(root)
    path = write_json(root / "data" / "reports" / "healthcheck.json", report)
    return {"overall_status": report.overall_status, "path": str(path)}


def readiness() -> dict[str, Any]:
    root = project_root()
    report = TossApiReadiness().check(TossApiConfig.from_env())
    path = write_json(root / "data" / "reports" / "toss_api_readiness.json", report)
    return {
        "status": report.status,
        "ready_for_live_orders": report.ready_for_live_orders,
        "official_docs_verified": report.official_docs_verified,
        "missing_items": report.missing_items,
        "path": str(path),
    }


def toss_official_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    client = TossOfficialApiClient(TossApiConfig.from_env())
    report = client.readiness()
    hard_missing = [item for item in report.missing_items if "X-Tossinvest-Account" not in item]
    if hard_missing:
        path = write_json(
            root / "data" / "reports" / "toss_official_snapshot.json",
            {"status": "blocked", "missing_items": hard_missing, "notes": report.notes},
        )
        return {"status": "blocked", "missing_items": hard_missing, "path": str(path)}
    try:
        written = client.export_readonly_snapshots(root)
        quote_path = None
        if args.symbol:
            quote = client.get_quote(args.symbol)
            quote_path = write_json(root / "data" / "official_broker_snapshots" / "toss" / f"quote_{args.symbol}.json", quote)
        reconciliation = ReadOnlyReconciler().reconcile(root)
    except RuntimeError as error:
        path = write_json(
            root / "data" / "reports" / "toss_official_snapshot.json",
            {"status": "blocked", "error": str(error), "notes": report.notes},
        )
        return {"status": "blocked", "error": str(error), "path": str(path)}
    report_path = write_json(
        root / "data" / "reports" / "toss_official_snapshot.json",
        {
            "status": "ok",
            "written": written,
            "quote_path": None if quote_path is None else str(quote_path),
            "reconciliation_status": reconciliation.status,
            "reconciliation_difference_count": len(reconciliation.differences),
        },
    )
    return {
        "status": "ok",
        "snapshot_count": len(written) + (1 if quote_path else 0),
        "reconciliation_status": reconciliation.status,
        "reconciliation_difference_count": len(reconciliation.differences),
        "path": str(report_path),
    }


def toss_live_order(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    client = TossOfficialApiClient(TossApiConfig.from_env())
    readiness_report = client.readiness()
    if readiness_report.missing_items:
        path = write_json(
            root / "data" / "reports" / "toss_live_order.json",
            {
                "status": "blocked",
                "submit_attempted": False,
                "reasons": readiness_report.missing_items,
                "notes": readiness_report.notes,
            },
        )
        return {"status": "blocked", "submit_attempted": False, "reasons": readiness_report.missing_items, "path": str(path)}

    reconciliation = ReadOnlyReconciler().reconcile(root)
    preflight = _toss_order_preflight(client, args, reconciliation)
    if not args.confirm_live_order:
        preflight["reasons"].append("실주문 확인 플래그 --confirm-live-order가 없습니다.")
    if preflight["status"] != "ok" or not args.confirm_live_order:
        preflight["status"] = "blocked"
        preflight["submit_attempted"] = False
        path = write_json(root / "data" / "reports" / "toss_live_order.json", preflight)
        return {
            "status": "blocked",
            "submit_attempted": False,
            "reasons": preflight["reasons"],
            "path": str(path),
        }

    client_order_id = args.client_order_id or f"atlas-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{args.symbol.upper()}"
    result = client.create_order(
        symbol=args.symbol,
        side=args.side,
        order_type=args.order_type,
        quantity=args.quantity,
        price=args.price,
        order_amount=args.order_amount,
        time_in_force=args.time_in_force,
        client_order_id=client_order_id,
        confirm_high_value_order=args.confirm_high_value_order,
    )
    _append_live_order_state(root, args, client_order_id, result)
    payload = {
        "status": "submitted",
        "submit_attempted": True,
        "client_order_id": client_order_id,
        "order_result": result,
        "preflight": preflight,
    }
    path = write_json(root / "data" / "reports" / "toss_live_order.json", payload)
    return {
        "status": "submitted",
        "submit_attempted": True,
        "client_order_id": client_order_id,
        "order_id": result.get("orderId"),
        "path": str(path),
    }


def _toss_order_preflight(client: TossOfficialApiClient, args: argparse.Namespace, reconciliation) -> dict[str, Any]:
    reasons: list[str] = []
    if reconciliation.status != "ok":
        reasons.append(f"reconciliation 상태가 ok가 아닙니다: {reconciliation.status}")
    if bool(args.quantity) == bool(args.order_amount):
        reasons.append("quantity 또는 order_amount 중 정확히 하나를 지정해야 합니다.")
    side = str(args.side).upper()
    order_type = str(args.order_type).upper()
    if side not in {"BUY", "SELL"}:
        reasons.append("side는 BUY 또는 SELL이어야 합니다.")
    if order_type not in {"LIMIT", "MARKET"}:
        reasons.append("order_type은 LIMIT 또는 MARKET이어야 합니다.")
    if order_type == "LIMIT" and not args.price:
        reasons.append("LIMIT 주문에는 price가 필요합니다.")
    if order_type == "MARKET" and args.price:
        reasons.append("MARKET 주문에는 price를 지정하지 않습니다.")
    if side == "SELL" and args.order_amount:
        reasons.append("매도는 수량 기반으로만 허용합니다.")

    quote: dict[str, Any] = {}
    buying_power: dict[str, Any] = {}
    required_amount: Decimal | None = None
    required_currency = "USD" if str(args.symbol).isalpha() else "KRW"
    try:
        if side == "BUY" and args.order_amount:
            required_amount = _decimal(args.order_amount)
            required_currency = "USD"
            buying_power = client.get_buying_power(required_currency)
        elif side == "BUY" and args.quantity:
            quote = client.get_quote(args.symbol)
            required_currency = str(quote.get("currency") or required_currency).upper()
            unit_price = _decimal(args.price or quote.get("lastPrice"))
            required_amount = unit_price * _decimal(args.quantity)
            buying_power = client.get_buying_power(required_currency)
        elif side == "SELL" and args.quantity:
            sellable = client.get_sellable_quantity(args.symbol)
            sellable_quantity = _decimal(sellable.get("sellableQuantity") or "0")
            if _decimal(args.quantity) > sellable_quantity:
                reasons.append(f"매도가능수량이 부족합니다: requested={args.quantity}, sellable={sellable_quantity}")
    except (InvalidOperation, TypeError, ValueError) as error:
        reasons.append(f"주문 수치 검증 실패: {error}")

    cash_buying_power = _decimal(buying_power.get("cashBuyingPower") or "0") if buying_power else Decimal("0")
    if side == "BUY" and required_amount is not None and cash_buying_power < required_amount:
        reasons.append(
            f"{required_currency} 매수가능금액이 부족합니다: required={required_amount}, buying_power={cash_buying_power}"
        )
    return {
        "status": "blocked" if reasons else "ok",
        "submit_attempted": False,
        "symbol": str(args.symbol).upper(),
        "side": side,
        "order_type": order_type,
        "quantity": args.quantity,
        "order_amount": args.order_amount,
        "price": args.price,
        "time_in_force": args.time_in_force,
        "required_amount": None if required_amount is None else str(required_amount),
        "required_currency": required_currency,
        "buying_power": buying_power,
        "quote": quote,
        "reconciliation_status": reconciliation.status,
        "reconciliation_difference_count": len(reconciliation.differences),
        "reasons": reasons,
    }


def _append_live_order_state(root: Path, args: argparse.Namespace, client_order_id: str, result: dict[str, Any]) -> None:
    path = root / "data" / "orders" / "live_order_state_store.json"
    existing: list[dict[str, Any]] = []
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            existing = [item for item in payload if isinstance(item, dict)]
    existing.append(
        {
            "idempotency_key": client_order_id,
            "client_order_id": client_order_id,
            "broker_order_id": result.get("orderId"),
            "symbol": str(args.symbol).upper(),
            "side": str(args.side).lower(),
            "quantity": args.quantity,
            "order_amount": args.order_amount,
            "order_type": str(args.order_type).lower(),
            "price": args.price,
            "status": "submitted",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
            "events": [{"status": "submitted", "message": "submitted to Toss official API"}],
        }
    )
    write_json(path, existing)


def live_order_sync(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    client = TossOfficialApiClient(TossApiConfig.from_env())
    written = client.export_readonly_snapshots(root)
    if args.symbol:
        quote = client.get_quote(args.symbol)
        write_json(root / "data" / "official_broker_snapshots" / "toss" / f"quote_{args.symbol}.json", quote)
    sync_result = _sync_live_order_state_from_broker(root)
    reconciliation = ReadOnlyReconciler().reconcile(root)
    payload = {
        "status": reconciliation.status,
        "updated_orders": sync_result["updated_orders"],
        "unchanged_orders": sync_result["unchanged_orders"],
        "snapshot_count": len(written),
        "reconciliation_difference_count": len(reconciliation.differences),
        "reconciliation_differences": [asdict(diff) for diff in reconciliation.differences],
    }
    path = write_json(root / "data" / "reports" / "live_order_sync.json", payload)
    return {**payload, "path": str(path)}


def _sync_live_order_state_from_broker(root: Path) -> dict[str, int]:
    state_path = root / "data" / "orders" / "live_order_state_store.json"
    broker_root = root / "data" / "official_broker_snapshots" / "toss"
    positions = _load_json_list(broker_root / "positions.json")
    open_orders = _load_json_list(broker_root / "open_orders.json")
    orders = _load_json_list(state_path)
    if not orders:
        return {"updated_orders": 0, "unchanged_orders": 0}

    broker_position_qty = _broker_position_quantities(positions)
    broker_open_keys = {_order_identity(order) for order in open_orders if _order_identity(order)}
    open_statuses = {"submitted", "partially_filled", "cancel_request_requested", "cancel_requested"}
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    unchanged = 0

    for order in orders:
        if str(order.get("status")) not in open_statuses:
            unchanged += 1
            continue
        identity = _order_identity(order)
        if identity and identity in broker_open_keys:
            unchanged += 1
            continue
        symbol = str(order.get("symbol"))
        side = str(order.get("side"))
        try:
            quantity = float(order.get("quantity") or 0)
        except (TypeError, ValueError):
            unchanged += 1
            continue
        if side == "buy" and broker_position_qty.get(symbol, 0.0) + 1e-6 >= quantity:
            order["status"] = "filled"
            order["filled_at"] = now
            order["fill_source"] = "broker_position_snapshot"
            events = order.get("events")
            if not isinstance(events, list):
                events = []
            events.append(
                {
                    "status": "filled",
                    "message": "broker position observed and order absent from open orders",
                    "observed_at": now,
                }
            )
            order["events"] = events
            updated += 1
        else:
            unchanged += 1

    write_json(state_path, orders)
    return {"updated_orders": updated, "unchanged_orders": unchanged}


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("positions", "orders", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _broker_position_quantities(positions: list[dict[str, Any]]) -> dict[str, float]:
    quantities: dict[str, float] = {}
    for position in positions:
        symbol = str(position.get("symbol") or position.get("ticker") or position.get("code"))
        if not symbol or symbol == "None":
            continue
        raw_quantity = position.get("quantity", position.get("qty", position.get("shares", position.get("balance"))))
        try:
            quantities[symbol] = float(raw_quantity)
        except (TypeError, ValueError):
            continue
    return quantities


def _order_identity(order: dict[str, Any]) -> str:
    for key in ("idempotency_key", "client_order_id", "clientOrderId", "order_id", "orderId", "id"):
        value = order.get(key)
        if value:
            return str(value)
    symbol = order.get("symbol") or order.get("ticker") or order.get("code")
    side = order.get("side") or order.get("order_side")
    quantity = order.get("quantity") or order.get("qty") or order.get("shares")
    if symbol and side and quantity:
        return f"{symbol}:{side}:{quantity}"
    return ""


def _decimal(value: Any) -> Decimal:
    if value is None:
        raise ValueError("숫자 값이 필요합니다.")
    return Decimal(str(value))


def toss_platform_fit() -> dict[str, Any]:
    root = project_root()
    report = TossPlatformFitAuditor().audit(root)
    path = write_json(root / "data" / "reports" / "toss_platform_fit.json", report)
    return {
        "status": report.status,
        "supported_markets": report.supported_markets,
        "supported_asset_kinds": report.supported_asset_kinds,
        "excluded_asset_kinds": report.excluded_asset_kinds,
        "api_dependent_steps": report.api_dependent_steps,
        "non_api_steps": report.non_api_steps,
        "path": str(path),
    }


def ops_report() -> dict[str, Any]:
    root = project_root()
    health = HealthCheckEngine().run(root)
    toss = TossApiReadiness().check(TossApiConfig.from_env())
    data = data_audit(argparse.Namespace(max_symbols=4, days=130))
    dashboard = build_operations_dashboard(
        live_trading_enabled=False,
        paper_ready=True,
        data_quality_status=str(data["overall_status"]),
        health_status=health.overall_status,
        toss_readiness_status=toss.status,
    )
    md = render_markdown_status(
        "Atlas Investment 운영 리포트",
        {
            "health": health.overall_status,
            "data_quality": data["overall_status"],
            "toss_api": toss.status,
            "live_orders": "blocked",
            "dashboard_panels": len(dashboard.panels),
        },
    )
    report_path = root / "data" / "reports" / "ops_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(md, encoding="utf-8")
    dashboard_path = write_json(root / "data" / "reports" / "ops_dashboard.json", dashboard)
    return {"status": "ok", "report_path": str(report_path), "dashboard_path": str(dashboard_path)}


def integration_check() -> dict[str, Any]:
    report = IntegrationSetupChecker().run()
    path = write_json(project_root() / "data" / "reports" / "integration_check.json", report)
    return {"overall_status": report.overall_status, "path": str(path), "items": report.items}


def kr_stock_search(args: argparse.Namespace) -> dict[str, Any]:
    results = KoreanStockClient().search(args.query, bas_dd=args.bas_dd, limit=args.limit)
    path = write_json(project_root() / "data" / "reports" / "kr_stock_search.json", results)
    return {"query": args.query, "count": len(results), "path": str(path), "results": results}


def kr_stock_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    snapshot = KoreanStockClient().trade_info(args.market, args.symbol, bas_dd=args.bas_dd)
    path = write_json(project_root() / "data" / "reports" / f"kr_stock_snapshot_{args.symbol}.json", snapshot)
    return {"symbol": args.symbol, "path": str(path), "snapshot": snapshot}


def dart_readiness() -> dict[str, Any]:
    report = DartClient().readiness()
    path = write_json(project_root() / "data" / "reports" / "dart_readiness.json", report)
    return {"status": report.status, "path": str(path), "notes": report.notes}


def dart_disclosures(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    try:
        payload = DartClient().disclosures(corp_code=args.corp_code, days=args.days, page_count=args.limit)
        status = "ok"
        notes: list[str] = []
    except RuntimeError as error:
        payload = {"error": str(error)}
        status = "blocked"
        notes = ["API_K_DART 환경변수를 설정하면 바로 사용할 수 있습니다."]
    path = write_json(root / "data" / "reports" / "dart_disclosures.json", payload)
    return {"status": status, "path": str(path), "notes": notes}


def dart_event_signals(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    try:
        signals = DartClient().event_signals(corp_code=args.corp_code, days=args.days, page_count=args.limit)
        status = "ok"
        notes: list[str] = []
    except RuntimeError as error:
        signals = []
        status = "blocked"
        notes = [str(error), "API_K_DART 환경변수를 설정하면 공시 이벤트 신호를 생성합니다."]
    path = write_json(root / "data" / "reports" / "dart_event_signals.json", {"status": status, "signals": signals, "notes": notes})
    high_count = sum(1 for signal in signals if signal.importance == "high")
    return {"status": status, "signal_count": len(signals), "high_importance_count": high_count, "path": str(path), "notes": notes}


def us_ohlcv(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    candles = YahooFinanceClient().load_daily_ohlcv(args.symbol, days=args.days)
    path = OhlcvStore(root / "data" / "ohlcv_external").save(args.symbol, candles)
    quality = OhlcvQualityChecker().check(args.symbol, candles, min_rows=min(60, args.days))
    quality_path = write_json(root / "data" / "reports" / f"us_ohlcv_quality_{args.symbol}.json", quality)
    return {"symbol": args.symbol, "candle_count": len(candles), "path": str(path), "quality_path": str(quality_path), "quality_status": "ok" if quality.passed else "blocked"}


def mcp_catalog() -> dict[str, Any]:
    catalog = build_skill_catalog()
    path = write_json(project_root() / "data" / "reports" / "mcp_skill_catalog.json", catalog)
    connected = sum(1 for item in catalog if item.status in {"connected", "available_in_session", "recommended"})
    missing = [item.name for item in catalog if item.status == "missing"]
    return {"status": "ok" if not missing else "degraded", "count": len(catalog), "connected": connected, "missing": missing, "path": str(path)}


def reconciliation_check() -> dict[str, Any]:
    root = project_root()
    report = ReadOnlyReconciler().reconcile(root)
    path = write_json(root / "data" / "reports" / "reconciliation_check.json", report)
    return {
        "status": report.status,
        "internal_order_count": report.internal_order_count,
        "broker_position_count": report.broker_position_count,
        "internal_position_count": report.internal_position_count,
        "internal_open_order_count": report.internal_open_order_count,
        "broker_open_order_count": report.broker_open_order_count,
        "broker_fill_count": report.broker_fill_count,
        "cash_currencies": sorted(report.broker_cash_by_currency),
        "difference_count": len(report.differences),
        "path": str(path),
    }


def reconciliation_baseline_init(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    client = TossOfficialApiClient(TossApiConfig.from_env())
    written = client.export_readonly_snapshots(root)
    live_order_state_path = root / "data" / "orders" / "live_order_state_store.json"
    live_order_state_path.parent.mkdir(parents=True, exist_ok=True)
    if not live_order_state_path.exists():
        live_order_state_path.write_text("[]", encoding="utf-8")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    baseline_dir = root / "data" / "reconciliation" / "baselines" / timestamp
    baseline_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for _, source in written.items():
        source_path = Path(source)
        target = baseline_dir / source_path.name
        shutil.copy2(source_path, target)
        copied[source_path.name] = str(target)

    report = ReadOnlyReconciler().reconcile(root, order_state_path=live_order_state_path)
    manifest = {
        "status": report.status,
        "created_at": timestamp,
        "live_order_state_path": str(live_order_state_path),
        "snapshot_files": copied,
        "reconciliation_difference_count": len(report.differences),
        "notes": [
            "This baseline separates live Toss reconciliation from historical PAPER/DRY_RUN runtime order state.",
            "It does not enable live trading or submit orders.",
        ],
    }
    manifest_path = write_json(baseline_dir / "manifest.json", manifest)
    path = write_json(root / "data" / "reports" / "reconciliation_baseline_init.json", manifest)
    return {
        "status": report.status,
        "difference_count": len(report.differences),
        "live_order_state_path": str(live_order_state_path),
        "baseline_dir": str(baseline_dir),
        "manifest_path": str(manifest_path),
        "path": str(path),
    }


def cron_template() -> dict[str, Any]:
    root = project_root()
    python = str(root / ".venv" / "bin" / "python")
    base = f"cd {root} && {python} -m atlas_investment.cli"
    jobs = [
        {
            "name": "Atlas Investment 장전 점검",
            "enabled": False,
            "schedule": {"cron": "0 8 * * 1-5", "timezone": "Asia/Seoul"},
            "command": f"{base} integration-check && {base} daily-data-refresh --vendor hybrid --include-kr-snapshots --max-symbols 8 --days 260 && {base} dart-event-signals --days 3 --limit 20 && {base} readiness",
        },
        {
            "name": "Atlas Investment 장중 헬스체크",
            "enabled": False,
            "schedule": {"cron": "0 10-15 * * 1-5", "timezone": "Asia/Seoul"},
            "command": f"{base} healthcheck && {base} realtime-smoke",
        },
        {
            "name": "Atlas Investment 마감 리포트",
            "enabled": False,
            "schedule": {"cron": "30 16 * * 1-5", "timezone": "Asia/Seoul"},
            "command": f"{base} ops-report",
        },
    ]
    path = write_json(root / "data" / "reports" / "openclaw_cron_template.json", jobs)
    return {"status": "template_ready", "enabled": False, "job_count": len(jobs), "path": str(path)}


def data_sync(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    config = DataLakeSyncConfig(days=args.days, max_symbols=args.max_symbols, include_fx=True, vendor=args.vendor)
    results = DataLakeSynchronizer(root, vendor=build_market_data_vendor(args.vendor)).sync_sample_universe(config)
    path = write_json(root / "data" / "reports" / "data_sync.json", results)
    blocked = [result for result in results if result.quality_status != "ok"]
    return {"status": "ok" if not blocked else "degraded", "vendor": args.vendor, "synced": len(results), "blocked": len(blocked), "path": str(path)}


def daily_data_refresh(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    config = DataLakeSyncConfig(
        days=args.days,
        max_symbols=args.max_symbols,
        include_fx=True,
        vendor=args.vendor,
        include_kr_snapshots=getattr(args, "include_kr_snapshots", False),
    )
    report = DataLakeSynchronizer(root, vendor=build_market_data_vendor(args.vendor)).refresh_daily(config)
    path = write_json(root / "data" / "reports" / "daily_data_refresh.json", report)
    return {
        "status": report.status,
        "vendor": report.vendor,
        "synced": len(report.synced),
        "kr_snapshot_count": len(report.kr_snapshots),
        "path": str(path),
        "notes": report.notes,
    }


def strategy_lab(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    store = OhlcvStore(root / "data" / "lake" / "ohlcv")
    assets = load_institutional_sample_universe()[: args.max_symbols]
    candles_by_symbol = {
        asset.symbol: _load_strategy_candles(root, store, asset.symbol, args.days)
        for asset in assets
    }
    requested = [name.strip() for name in args.strategies.split(",") if name.strip()] if args.strategies else list(all_strategies())
    strategies = [get_strategy(name) for name in requested]
    results = StrategyLab(initial_cash=args.initial_cash).run(assets, candles_by_symbol, strategies)
    path = write_json(root / "data" / "reports" / "strategy_lab.json", results)
    return {"status": "ok", "result_count": len(results), "approved_for_paper": sum(1 for result in results if result.approved_for_paper), "path": str(path)}


def fund_risk(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    broker = MockBroker()
    assets = {asset.symbol: asset for asset in load_institutional_sample_universe()}
    report = FundRiskGovernor().evaluate(
        broker.get_portfolio(),
        assets,
        load_risk_policy(root / "config" / "risk_policy.json"),
        current_drawdown=args.current_drawdown,
    )
    path = write_json(root / "data" / "reports" / "fund_risk.json", report)
    return {"risk_level": report.risk_level, "actions": report.actions, "path": str(path)}


def fx_exposure(args: argparse.Namespace) -> dict[str, Any]:
    report = MultiCurrencyEngine().analyze(MockBroker().get_portfolio(), usdkrw=args.usdkrw)
    path = write_json(project_root() / "data" / "reports" / "fx_exposure.json", report)
    return {"status": "ok", "equity_krw": report.equity_krw, "path": str(path), "notes": report.notes}


def execution_sim(args: argparse.Namespace) -> dict[str, Any]:
    asset = _asset_for_symbol(args.symbol)
    order = OrderIntent(asset, Side.BUY, quantity=1, order_type=OrderType.LIMIT, limit_price=MockBroker().get_quote(asset.symbol).price, reason="Phase 20 execution routing smoke", expected_holding_days=5)
    routes = ExecutionRouter().route_orders([order], TradingMode(args.mode), live_ready=False)
    path = write_json(project_root() / "data" / "reports" / "execution_sim.json", routes)
    return {"status": routes[0].status, "route": routes[0].route, "path": str(path), "reason": routes[0].reason}


def algo_execution_plan(args: argparse.Namespace) -> dict[str, Any]:
    asset = _asset_for_symbol(args.symbol)
    quote = MockBroker().get_quote(asset.symbol)
    order = OrderIntent(asset, Side.BUY, quantity=max(1, args.limit), order_type=OrderType.LIMIT, limit_price=quote.price, reason="algorithmic execution planning smoke", expected_holding_days=5)
    report = AlgorithmicExecutionPlanner().plan([order], algorithm=args.algorithm, mode=TradingMode(args.mode), slices_per_order=args.slices, participation_rate=args.participation_rate)
    path = write_json(project_root() / "data" / "reports" / f"algo_execution_{args.algorithm}.json", report)
    return {"status": report.status, "algorithm": report.algorithm, "slice_count": report.slice_count, "path": str(path), "risk_notes": report.risk_notes}


def strategy_readiness(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    store = OhlcvStore(root / "data" / "lake" / "ohlcv")
    assets = load_institutional_sample_universe()[: args.max_symbols]
    candles_by_symbol = {
        asset.symbol: _load_strategy_candles(root, store, asset.symbol, args.days)
        for asset in assets
    }
    strategy = get_strategy(args.strategy)
    results = StrategyLab(initial_cash=args.initial_cash).run(assets, candles_by_symbol, [strategy])
    decision = StrategyPromotionGate().evaluate(
        strategy.name,
        results,
        realtime_data_ready=args.realtime_data_ready,
        shorting_supported=args.shorting_supported,
    )
    path = write_json(root / "data" / "reports" / f"strategy_readiness_{strategy.name}.json", {"decision": decision, "results": results})
    return {
        "status": decision.status,
        "strategy": strategy.name,
        "approved_symbols": decision.approved_symbols,
        "total_symbols": decision.total_symbols,
        "path": str(path),
        "reasons": decision.reasons,
        "warnings": decision.warnings,
    }


def quant_portfolio(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    store = OhlcvStore(root / "data" / "lake" / "ohlcv")
    assets = load_institutional_sample_universe()[: args.max_symbols]
    candles_by_symbol = {
        asset.symbol: _load_strategy_candles(root, store, asset.symbol, args.days)
        for asset in assets
    }
    assets, cross_sectional_ranks = CrossSectionalMomentumRanker().enrich_assets(assets, candles_by_symbol)
    benchmark_candles = candles_by_symbol.get(assets[0].symbol, []) if assets else []
    regime = MarketRegimeDetector().detect(benchmark_candles)
    overlay = RiskOverlay().decide(regime, current_drawdown_pct=getattr(args, "current_drawdown", 0.0))
    strategy_names = [name.strip() for name in args.strategies.split(",") if name.strip()] if args.strategies else [
        "multifactor_qvm",
        "time_series_momentum",
        "cross_sectional_momentum",
        "all_weather_risk_parity",
        "macro_regime_allocation",
        "cta_diversified_trend",
        "ml_alpha_score",
        "low_vol_defensive",
        "shareholder_yield_carry",
        "sector_regime_rotation",
        "earnings_revision_event",
    ]
    strategies = [get_strategy(name) for name in strategy_names]
    signals: list[Signal] = []
    skipped: list[str] = []
    for asset in assets:
        candles = candles_by_symbol.get(asset.symbol, [])
        if not candles:
            skipped.append(asset.symbol)
            continue
        index = len(candles) - 1
        for strategy in strategies:
            signal = strategy.generate_signal(asset, candles, index)
            if signal:
                signals.append(signal)
    base_weights = {name: regime.strategy_weight_multipliers.get(name, 1.0) for name in strategy_names}
    report = StrategyEnsembleAllocator(max_position_weight=args.max_position_weight, max_sector_weight=args.max_sector_weight).allocate(signals, strategy_weights=base_weights)
    report = _apply_overlay_to_allocation(report, overlay.exposure_multiplier)
    factor_warnings = _factor_data_warnings(assets)
    path = write_json(
        root / "data" / "reports" / "quant_portfolio.json",
        {
            "report": report,
            "signals": signals,
            "skipped": skipped,
            "strategy_names": strategy_names,
            "market_regime": regime,
            "risk_overlay": overlay,
            "cross_sectional_ranks": cross_sectional_ranks,
            "factor_warnings": factor_warnings,
        },
    )
    buy_count = sum(1 for candidate in report.candidates if candidate.stance == "buy")
    return {
        "status": report.status,
        "signal_count": len(signals),
        "candidate_count": report.candidate_count,
        "buy_count": buy_count,
        "path": str(path),
        "blocked_reasons": report.blocked_reasons,
        "market_regime": regime.trend,
        "volatility_regime": regime.volatility,
        "risk_overlay_multiplier": overlay.exposure_multiplier,
        "factor_warnings": factor_warnings,
    }


def _apply_overlay_to_allocation(report, exposure_multiplier: float):
    if exposure_multiplier >= 0.999:
        return report
    adjusted = [
        AllocationCandidate(
            candidate.symbol,
            candidate.name,
            candidate.market,
            candidate.sector,
            candidate.weighted_score,
            candidate.confidence,
            round(candidate.target_weight * exposure_multiplier, 6),
            candidate.stance,
            candidate.strategies,
            candidate.reasons + [f"Risk overlay multiplier {exposure_multiplier:.2%} 적용"],
        )
        for candidate in report.candidates
    ]
    return type(report)(
        report.status,
        report.candidate_count,
        report.max_position_weight,
        report.max_sector_weight,
        adjusted,
        report.blocked_reasons,
    )


def _factor_data_warnings(assets: list[Asset]) -> list[str]:
    required = {"quality_score", "value_score", "earnings_yield", "earnings_revision_3m"}
    warnings: list[str] = []
    missing_count = 0
    sample_source_count = 0
    for asset in assets:
        missing = required - set(asset.metadata)
        if missing:
            missing_count += 1
        if not asset.metadata.get("factor_data_source"):
            sample_source_count += 1
    if missing_count:
        warnings.append(f"{missing_count}개 자산에 QVM/이벤트 필수 팩터 일부가 없습니다.")
    if sample_source_count:
        warnings.append(f"{sample_source_count}개 자산은 공식 팩터 데이터 출처가 없어 샘플 metadata로만 평가됩니다.")
    return warnings


def _load_strategy_candles(root: Path, store: OhlcvStore, symbol: str, days: int, start_price: float = 80000) -> list:
    candles = store.load(symbol)
    if candles and len(candles) >= min(days, 100):
        return candles[-days:]
    return OhlcvStore(root / "data" / "ohlcv").load_or_generate_sample(symbol, days=days, start_price=start_price)


def global_gap_audit() -> dict[str, Any]:
    root = project_root()
    report = GlobalGapAuditor().audit(root)
    path = write_json(root / "data" / "reports" / "global_gap_audit.json", report)
    return {
        "status": report.status,
        "blocked": report.blocked,
        "degraded": report.degraded,
        "code_possible_blockers": report.code_possible_blockers,
        "external_blockers": report.external_blockers,
        "path": str(path),
        "conclusion": report.conclusion,
    }


def portfolio_optimizer(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    store = OhlcvStore(root / "data" / "lake" / "ohlcv")
    quant_args = argparse.Namespace(
        days=args.days,
        max_symbols=args.max_symbols,
        strategies=args.strategies,
        max_position_weight=args.max_position_weight,
        max_sector_weight=args.max_sector_weight,
    )
    quant_portfolio(quant_args)
    payload = json.loads((root / "data" / "reports" / "quant_portfolio.json").read_text(encoding="utf-8"))
    candidates = [item for item in payload.get("report", {}).get("candidates", []) if isinstance(item, dict)]
    allocation_candidates = []
    for item in candidates:
        allocation_candidates.append(
            AllocationCandidate(
                symbol=str(item.get("symbol")),
                name=str(item.get("name")),
                market=str(item.get("market")),
                sector=str(item.get("sector")),
                weighted_score=float(item.get("weighted_score", 0)),
                confidence=float(item.get("confidence", 0)),
                target_weight=float(item.get("target_weight", 0)),
                stance=str(item.get("stance")),
                strategies=list(item.get("strategies", [])),
                reasons=list(item.get("reasons", [])),
            )
        )
    candles_by_symbol = {
        candidate.symbol: _load_strategy_candles(root, store, candidate.symbol, args.days)
        for candidate in allocation_candidates
    }
    report = PortfolioOptimizer().optimize(
        allocation_candidates,
        candles_by_symbol,
        method=args.optimizer_method,
        target_volatility_pct=args.target_volatility_pct,
        max_position_weight=args.max_position_weight,
        max_gross_exposure=getattr(args, "max_gross_exposure", 1.0),
    )
    path = write_json(root / "data" / "reports" / "portfolio_optimizer.json", report)
    return {
        "status": report.status,
        "method": report.method,
        "position_count": len(report.positions),
        "gross_exposure": report.gross_exposure,
        "realized_volatility_pct": report.realized_volatility_pct,
        "path": str(path),
        "warnings": report.warnings,
    }


def market_regime(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    store = OhlcvStore(root / "data" / "lake" / "ohlcv")
    symbol = args.symbol
    candles = _load_strategy_candles(root, store, symbol, args.days)
    report = MarketRegimeDetector().detect(candles)
    path = write_json(root / "data" / "reports" / f"market_regime_{symbol}.json", report)
    return {"status": report.status, "trend": report.trend, "volatility": report.volatility, "exposure_multiplier": report.exposure_multiplier, "path": str(path)}


def ensemble_backtest(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    store = OhlcvStore(root / "data" / "lake" / "ohlcv")
    assets = load_institutional_sample_universe()[: args.max_symbols]
    candles_by_symbol = {
        asset.symbol: _load_strategy_candles(root, store, asset.symbol, args.days)
        for asset in assets
    }
    strategy_names = [name.strip() for name in args.strategies.split(",") if name.strip()] if args.strategies else [
        "multifactor_qvm",
        "time_series_momentum",
        "cross_sectional_momentum",
        "all_weather_risk_parity",
        "macro_regime_allocation",
        "cta_diversified_trend",
        "ml_alpha_score",
        "low_vol_defensive",
        "shareholder_yield_carry",
        "sector_regime_rotation",
        "earnings_revision_event",
    ]
    strategies = [get_strategy(name) for name in strategy_names]
    report = EnsemblePortfolioBacktester(initial_cash=args.initial_cash).run(
        assets,
        candles_by_symbol,
        strategies,
        max_position_weight=args.max_position_weight,
        max_sector_weight=args.max_sector_weight,
    )
    path = write_json(root / "data" / "backtests" / "ensemble_portfolio.json", report)
    return {
        "status": report.status,
        "total_return_pct": report.total_return_pct,
        "max_drawdown_pct": report.max_drawdown_pct,
        "rebalance_count": report.rebalance_count,
        "average_gross_exposure": report.average_gross_exposure,
        "total_transaction_cost": report.total_transaction_cost,
        "average_transaction_cost_bps": report.average_transaction_cost_bps,
        "path": str(path),
        "warnings": report.warnings,
    }


def child_order_sim(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    asset = _asset_for_symbol(args.symbol)
    quote = MockBroker().get_quote(asset.symbol)
    order = OrderIntent(asset, Side.BUY, quantity=max(1, args.limit), order_type=OrderType.LIMIT, limit_price=quote.price, reason="child order simulation", expected_holding_days=5)
    plan = AlgorithmicExecutionPlanner().plan([order], algorithm=args.algorithm, mode=TradingMode(args.mode), slices_per_order=args.slices, participation_rate=args.participation_rate)
    report = PaperChildOrderManager().execute_plan(plan, TradingMode(args.mode), fill_ratio=args.fill_ratio)
    path = write_json(root / "data" / "reports" / "child_order_sim.json", {"plan": plan, "execution": report})
    return {
        "status": report.status,
        "mode": report.mode,
        "algorithm": report.algorithm,
        "planned_slices": report.planned_slices,
        "filled_slices": report.filled_slices,
        "planned_quantity": report.planned_quantity,
        "filled_quantity": report.filled_quantity,
        "path": str(path),
    }


def governance_report() -> dict[str, Any]:
    root = project_root()
    records = [
        _governance_record_with_live_approval(record, root)
        for record in GovernanceRegistry().default_phase20_controls()
    ]
    path = write_json(root / "data" / "reports" / "governance_report.json", records)
    blocked = [record for record in records if record.status == "blocked"]
    return {"status": "blocked" if blocked else "ok", "record_count": len(records), "blocked": len(blocked), "path": str(path)}


def _governance_record_with_live_approval(record, root: Path):
    if record.record_type != "live_promotion":
        return record
    approval = root / "data" / "evidence" / "live_promotion_approval.json"
    if not approval.exists():
        return record
    try:
        payload = json.loads(approval.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return record
    if not isinstance(payload, dict):
        return record
    approved = (
        payload.get("approved") is True
        and payload.get("approved_for") == "live_auto"
        and bool(payload.get("signed_by"))
        and bool(payload.get("approved_at"))
    )
    if not approved:
        return record
    return type(record)(
        record.record_type,
        record.title,
        "ready",
        record.required_before_live,
        [
            f"live_auto pilot approval recorded at {approval}",
            f"scope={payload.get('scope', {}).get('mode', 'unknown') if isinstance(payload.get('scope'), dict) else 'unknown'}",
        ],
    )


def investment_memo(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    asset = _asset_for_symbol(args.symbol)
    candles = OhlcvStore(root / "data" / "ohlcv").load_or_generate_sample(args.symbol, days=args.days, start_price=80000)
    strategy = get_strategy(args.strategy)
    signal = strategy.generate_signal(asset, candles, len(candles) - 1) or Signal(asset, 50, "hold", ["전략 신호가 아직 충분하지 않습니다."], 10, strategy.name)
    memo = InvestmentMemoGenerator().generate(signal)
    path = write_json(root / "data" / "reports" / f"investment_memo_{args.symbol}_{strategy.name}.json", memo)
    return {"decision": memo.decision, "symbol": memo.symbol, "strategy": memo.strategy, "path": str(path)}


def phase20_audit() -> dict[str, Any]:
    root = project_root()
    report = Phase20ReadinessAuditor().run(root)
    path = write_json(root / "data" / "reports" / "phase20_audit.json", report)
    return {"overall_status": report.overall_status, "item_count": len(report.items), "path": str(path)}


def global_coverage_model() -> dict[str, Any]:
    root = project_root()
    report = GlobalCoverageModel().report()
    path = write_json(root / "data" / "reports" / "global_coverage_model.json", report)
    return {
        "status": report.status,
        "missing_markets": report.market_requirement.missing,
        "missing_asset_kinds": report.asset_kind_requirement.missing,
        "path": str(path),
    }


def promotion_evidence() -> dict[str, Any]:
    root = project_root()
    report = PromotionEvidenceAuditor().audit(root)
    path = write_json(root / "data" / "reports" / "promotion_evidence.json", report)
    blocked = sum(1 for requirement in report.requirements if requirement.status == "blocked")
    return {"status": report.status, "blocked": blocked, "path": str(path)}


def promotion_evidence_record(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    result = PromotionEvidenceRecorder().record(root, kind=args.evidence_kind, status=args.status, source=args.source, observed_on=args.observed_on)
    report = PromotionEvidenceAuditor().audit(root)
    path = write_json(root / "data" / "reports" / "promotion_evidence.json", report)
    result["audit_status"] = report.status
    result["audit_path"] = str(path)
    return result


def promotion_evidence_collect(args: argparse.Namespace) -> dict[str, Any]:
    """Run safe daily promotion checks and record only successful evidence."""
    root = project_root()
    recorder = PromotionEvidenceRecorder()
    collected: list[dict[str, Any]] = []

    dry_run_args = argparse.Namespace(**vars(args))
    dry_run_args.mode = "dry_run"
    dry_run_result = run_cycle(dry_run_args)
    if dry_run_result.get("status") == "ok":
        collected.append(recorder.record(root, kind="dry_run", status="ok", source="promotion-evidence-collect:dry_run"))

    paper_args = argparse.Namespace(**vars(args))
    paper_args.mode = "paper"
    paper_result = run_cycle(paper_args)
    if paper_result.get("status") == "ok":
        collected.append(recorder.record(root, kind="paper", status="ok", source="promotion-evidence-collect:paper"))

    snapshot_result = toss_official_snapshot(args)
    reconciliation_result = reconciliation_check()
    if snapshot_result.get("status") == "ok" and reconciliation_result.get("status") == "ok":
        collected.append(recorder.record(root, kind="reconciliation", status="ok", source="promotion-evidence-collect:reconciliation"))
    else:
        recorder.record(root, kind="reconciliation", status="blocked", source="promotion-evidence-collect:reconciliation")

    health = healthcheck()
    integration = integration_check()
    realtime = realtime_smoke()
    if health.get("overall_status") == "ok" and integration.get("overall_status") == "ok" and realtime.get("status") == "ok":
        HeartbeatRecorder().record(root, status="ok", source="promotion-evidence-collect")
    else:
        HeartbeatRecorder().record(root, status="blocked", source="promotion-evidence-collect")

    evidence_report = PromotionEvidenceAuditor().audit(root)
    evidence_path = write_json(root / "data" / "reports" / "promotion_evidence.json", evidence_report)
    heartbeat_report = HeartbeatAuditor().audit(root)
    heartbeat_path = write_json(root / "data" / "reports" / "heartbeat_audit.json", heartbeat_report)
    payload = {
        "status": "ok" if all(item.get("status") == "ok" for item in collected) else "degraded",
        "collected": collected,
        "dry_run_status": dry_run_result.get("status"),
        "paper_status": paper_result.get("status"),
        "snapshot_status": snapshot_result.get("status"),
        "reconciliation_status": reconciliation_result.get("status"),
        "health_status": health.get("overall_status"),
        "integration_status": integration.get("overall_status"),
        "realtime_status": realtime.get("status"),
        "promotion_evidence_status": evidence_report.status,
        "heartbeat_status": heartbeat_report.status,
        "promotion_evidence_path": str(evidence_path),
        "heartbeat_audit_path": str(heartbeat_path),
    }
    path = write_json(root / "data" / "reports" / "promotion_evidence_collect.json", payload)
    return {**payload, "path": str(path)}


def hedgefund_readiness() -> dict[str, Any]:
    root = project_root()
    report = HedgeFundReadinessAuditor().run(root)
    path = write_json(root / "data" / "reports" / "hedgefund_readiness.json", report)
    blocked = sum(1 for check in report.checks if check.status == "blocked")
    degraded = sum(1 for check in report.checks if check.status == "degraded")
    return {
        "overall_status": report.overall_status,
        "global_investment_status": report.global_investment_status,
        "autonomy_24x7_status": report.autonomy_24x7_status,
        "blocked": blocked,
        "degraded": degraded,
        "path": str(path),
        "conclusion": report.conclusion,
    }


def accounting_ledger(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    cash = CurrencyCashBook({"KRW": args.cash_krw, "USD": args.cash_usd})
    rates = FxRateBook(rates_to_krw={"KRW": 1.0, "USD": args.usdkrw})
    report = MultiCurrencyAccountingEngine().build_ledger(MockBroker().get_portfolio(), rates, cash)
    path = write_json(root / "data" / "reports" / "accounting_ledger.json", report)
    return {"status": "ok", "equity_krw": report.equity_krw, "currency_weights": report.currency_weights, "path": str(path)}


def data_snapshot_audit() -> dict[str, Any]:
    root = project_root()
    report = DataSnapshotAuditor().audit(root / "data" / "lake" / "ohlcv")
    path = write_json(root / "data" / "reports" / "data_snapshot_audit.json", report)
    return {"status": report.status, "record_count": len(report.records), "warning_count": len(report.warnings), "path": str(path)}


def data_entitlements() -> dict[str, Any]:
    root = project_root()
    report = DataEntitlementAuditor().audit(root)
    path = write_json(root / "data" / "reports" / "data_entitlements.json", report)
    blocked = sum(1 for requirement in report.requirements if requirement.status == "blocked")
    return {"status": report.status, "provider_count": report.provider_count, "blocked": blocked, "path": str(path)}


def order_state_smoke(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    asset = _asset_for_symbol(args.symbol)
    quote = MockBroker().get_quote(asset.symbol)
    order = OrderIntent(asset, Side.BUY, 1, OrderType.LIMIT, quote.price, "state machine smoke", 5)
    store = OrderStateStore(root / "data" / "orders" / "order_state_store.json")
    managed = store.create(order)
    if managed.status == OrderStatus.CREATED:
        managed = store.transition(order.idempotency_key, OrderStatus.VALIDATED, "risk checks passed")
        managed = store.transition(order.idempotency_key, OrderStatus.QUEUED, "queued for paper/dry-run route")
    reconciliation = store.reconcile({order.idempotency_key})
    path = write_json(root / "data" / "reports" / "order_state_smoke.json", {"order": managed, "reconciliation": reconciliation})
    return {"status": managed.status.value, "event_count": len(managed.events), "path": str(path)}


def strategy_validate(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    asset = _asset_for_symbol(args.symbol)
    candles = OhlcvStore(root / "data" / "ohlcv").load_or_generate_sample(args.symbol, days=max(args.days, 140), start_price=80000)
    report = StrategyValidator(initial_cash=args.initial_cash).validate(asset, candles, get_strategy(args.strategy), folds=args.folds, trials=args.trials)
    path = write_json(root / "data" / "reports" / f"strategy_validation_{args.symbol}_{args.strategy}.json", report)
    return {"status": "ok" if not report.overfit_warnings else "degraded", "folds": len(report.folds), "warning_count": len(report.overfit_warnings), "path": str(path)}


def advanced_internal_upgrade(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    store = OhlcvStore(root / "data" / "lake" / "ohlcv")
    assets = load_institutional_sample_universe()[: args.max_symbols]
    candles_by_symbol = {asset.symbol: _load_strategy_candles(root, store, asset.symbol, max(args.days, 180)) for asset in assets}
    asset = assets[0]
    candles = candles_by_symbol[asset.symbol]
    strategy_names = [
        "multifactor_qvm",
        "cross_sectional_momentum",
        "all_weather_risk_parity",
        "macro_regime_allocation",
        "cta_diversified_trend",
        "ml_alpha_score",
    ]
    validation_reports = [
        StrategyValidator(initial_cash=args.initial_cash).validate(asset, candles, get_strategy(name), folds=3, trials=60)
        for name in strategy_names[:4]
    ]
    tuning = StrategyParameterTuner().tune(asset, candles, get_strategy("ml_alpha_score"))
    meta = MetaStrategyAllocator().allocate(validation_reports)
    cost = MarketImpactCostModel().estimate(candles, notional=args.amount_krw, participation_rate=args.participation_rate)
    broker = MockBroker()
    assets_by_symbol = {item.symbol: item for item in load_institutional_sample_universe()}
    risk = AdvancedPortfolioRiskEngine().analyze(broker.get_portfolio(), assets_by_symbol, candles_by_symbol)
    lifecycle = [StrategyLifecycleManager().decide(report) for report in validation_reports]
    data_defense = [DataDefenseLayer().inspect(item.symbol, candles_by_symbol[item.symbol]) for item in assets[: min(3, len(assets))]]
    replay = HistoricalEventReplay().run(asset, candles, quantity=max(1, args.limit))
    research = ResearchFactory().build(asset, candles)
    ml_signal = get_strategy("ml_alpha_score").generate_signal(asset, candles, len(candles) - 1)
    payload = {
        "parameter_tuning": tuning,
        "meta_allocator": meta,
        "realistic_cost": cost,
        "advanced_risk": risk,
        "strategy_lifecycle": lifecycle,
        "data_defense": data_defense,
        "event_replay": replay,
        "research_factory": research,
        "ml_ai_strategy_check": {
            "existing_before_this_upgrade": False,
            "implemented_strategy": "ml_alpha_score",
            "signal": ml_signal,
            "note": "외부 ML 패키지 없이 feature ensemble 기반 deterministic ML-style alpha 전략을 추가했습니다.",
        },
    }
    path = write_json(root / "data" / "reports" / "advanced_internal_upgrade.json", payload)
    audit = AuditTrailWriter().write(
        root / "data" / "audit" / "advanced_internal_upgrade.jsonl",
        "advanced_internal_upgrade",
        "all_internal_enhancements",
        payload,
        ["parameter tuning", "meta allocator", "market impact", "advanced risk", "lifecycle", "data defense", "event replay", "research factory", "ml alpha"],
    )
    blocked = []
    if tuning.status == "blocked":
        blocked.append("parameter_tuning")
    if meta.status == "blocked":
        blocked.append("meta_allocator")
    if any(report.status == "blocked" for report in data_defense):
        blocked.append("data_defense")
    return {
        "status": "blocked" if blocked else "ok",
        "blocked": blocked,
        "meta_strategy_count": len(meta.weights),
        "cost_bps": cost.cost_bps,
        "advanced_risk_status": risk.status,
        "lifecycle_statuses": {item.strategy: item.status for item in lifecycle},
        "ml_ai_strategy": "ml_alpha_score",
        "path": str(path),
        "audit_hash": audit.payload_hash,
    }


def dashboard_html() -> dict[str, Any]:
    root = project_root()
    path = render_static_dashboard(root / "data" / "reports", root / "data" / "reports" / "dashboard.html")
    return {"status": "ok", "path": str(path)}


def alerts_check() -> dict[str, Any]:
    root = project_root()
    report = AlertEngine().evaluate(root)
    path = write_json(root / "data" / "reports" / "alerts_check.json", report)
    return {
        "status": report.status,
        "enabled": report.enabled,
        "channel_count": report.channel_count,
        "scanned_reports": report.scanned_reports,
        "event_count": len(report.events),
        "path": str(path),
        "outbox_path": report.outbox_path,
    }


def heartbeat_record(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    path = HeartbeatRecorder().record(root, status=args.status, source=args.source)
    return {"status": args.status, "path": str(path)}


def heartbeat_audit() -> dict[str, Any]:
    root = project_root()
    report = HeartbeatAuditor().audit(root)
    path = write_json(root / "data" / "reports" / "heartbeat_audit.json", report)
    return {
        "status": report.status,
        "distinct_utc_days": report.distinct_utc_days,
        "latest_status": report.latest_status,
        "path": str(path),
        "history_path": report.history_path,
    }


def etf_cost_optimizer(args: argparse.Namespace) -> dict[str, Any]:
    root = project_root()
    config_path = ensure_default_etf_config(root / "config" / "etf_equivalence.json")
    optimizer = EtfCostOptimizer(min_liquidity_krw=args.min_liquidity_krw, switch_safety_margin_rate=args.switch_safety_margin_rate)
    report = optimizer.optimize(
        optimizer.load_candidates(config_path),
        exposure_group=args.exposure_group,
        investment_amount_krw=args.amount_krw,
        holding_days=args.holding_days,
        current_symbol=args.current_symbol,
    )
    path = write_json(root / "data" / "reports" / f"etf_cost_optimizer_{args.exposure_group}.json", report)
    recommendation = report.recommendation.candidate.symbol if report.recommendation else None
    return {
        "status": report.status,
        "exposure_group": report.exposure_group,
        "recommendation": recommendation,
        "ranking_count": len(report.rankings),
        "should_switch": None if report.switch_analysis is None else report.switch_analysis.should_switch,
        "path": str(path),
        "warnings": report.warnings,
    }


def _asset_for_symbol(symbol: str) -> Asset:
    for asset in load_institutional_sample_universe():
        if asset.symbol == symbol:
            return asset
    return Asset(symbol=symbol, name=symbol, market=Market.US if symbol.isalpha() else Market.KR)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Atlas Investment 운용 CLI")
    parser.add_argument("command", nargs="?", default="run")
    parser.add_argument("--mode", choices=[mode.value for mode in TradingMode], default=TradingMode.DRY_RUN.value)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--symbol", default="005930")
    parser.add_argument("--side", choices=["BUY", "SELL"], default="BUY")
    parser.add_argument("--order-type", choices=["MARKET", "LIMIT"], default="MARKET")
    parser.add_argument("--quantity", default=None)
    parser.add_argument("--order-amount", default=None)
    parser.add_argument("--price", default=None)
    parser.add_argument("--time-in-force", default=None)
    parser.add_argument("--client-order-id", default=None)
    parser.add_argument("--confirm-live-order", action="store_true")
    parser.add_argument("--confirm-high-value-order", action="store_true")
    parser.add_argument("--strategy", default="moving_average_cross")
    parser.add_argument("--days", type=int, default=180)
    parser.add_argument("--initial-cash", type=float, default=10_000_000)
    parser.add_argument("--ending-equity", type=float, default=None)
    parser.add_argument("--max-symbols", type=int, default=5)
    parser.add_argument("--usdkrw", type=float, default=1380)
    parser.add_argument("--usdkrw-average", type=float, default=1350)
    parser.add_argument("--current-usd-exposure", type=float, default=0.4)
    parser.add_argument("--current-drawdown", type=float, default=0.0)
    parser.add_argument("--strategies", default="")
    parser.add_argument("--cash-krw", type=float, default=5_000_000)
    parser.add_argument("--cash-usd", type=float, default=0.0)
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--exposure-group", default="NASDAQ100_KR_UNHEDGED")
    parser.add_argument("--amount-krw", type=float, default=10_000_000)
    parser.add_argument("--holding-days", type=int, default=365)
    parser.add_argument("--current-symbol", default=None)
    parser.add_argument("--min-liquidity-krw", type=float, default=500_000_000)
    parser.add_argument("--switch-safety-margin-rate", type=float, default=0.0005)
    parser.add_argument("--query", default="삼성전자")
    parser.add_argument("--market", default="KOSPI")
    parser.add_argument("--bas-dd", default=None)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--corp-code", default=None)
    parser.add_argument("--vendor", choices=["sample", "yfinance", "hybrid"], default="sample")
    parser.add_argument("--include-kr-snapshots", action="store_true")
    parser.add_argument("--status", default="ok")
    parser.add_argument("--source", default="manual")
    parser.add_argument("--evidence-kind", choices=["dry_run", "paper", "reconciliation", "small_order"], default="dry_run")
    parser.add_argument("--observed-on", default=None)
    parser.add_argument("--algorithm", choices=["twap", "vwap", "pov", "adaptive"], default="twap")
    parser.add_argument("--slices", type=int, default=6)
    parser.add_argument("--participation-rate", type=float, default=0.08)
    parser.add_argument("--fill-ratio", type=float, default=1.0)
    parser.add_argument("--realtime-data-ready", action="store_true")
    parser.add_argument("--shorting-supported", action="store_true")
    parser.add_argument("--max-position-weight", type=float, default=0.08)
    parser.add_argument("--max-sector-weight", type=float, default=0.35)
    parser.add_argument("--max-gross-exposure", type=float, default=1.0)
    parser.add_argument("--optimizer-method", choices=["risk_parity", "inverse_vol", "equal_weight", "vol_target"], default="risk_parity")
    parser.add_argument("--target-volatility-pct", type=float, default=12.0)
    return parser


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    handlers = {
        "run": lambda: run_cycle(args),
        "backtest": lambda: run_backtest(args),
        "compare": lambda: compare_strategies(args),
        "universe": export_universe,
        "data-audit": lambda: data_audit(args),
        "portfolio-backtest": lambda: portfolio_backtest(args),
        "cost-report": lambda: cost_report(args),
        "risk-report": risk_report,
        "fx-overlay": lambda: fx_overlay(args),
        "realtime-smoke": realtime_smoke,
        "ops-plan": ops_plan,
        "ops-report": ops_report,
        "healthcheck": healthcheck,
        "readiness": readiness,
        "toss-official-snapshot": lambda: toss_official_snapshot(args),
        "toss-live-order": lambda: toss_live_order(args),
        "live-order-sync": lambda: live_order_sync(args),
        "toss-platform-fit": toss_platform_fit,
        "integration-check": integration_check,
        "kr-stock-search": lambda: kr_stock_search(args),
        "kr-stock-snapshot": lambda: kr_stock_snapshot(args),
        "dart-readiness": dart_readiness,
        "dart-disclosures": lambda: dart_disclosures(args),
        "dart-event-signals": lambda: dart_event_signals(args),
        "us-ohlcv": lambda: us_ohlcv(args),
        "mcp-catalog": mcp_catalog,
        "reconciliation-check": reconciliation_check,
        "reconciliation-baseline-init": lambda: reconciliation_baseline_init(args),
        "cron-template": cron_template,
        "data-sync": lambda: data_sync(args),
        "daily-data-refresh": lambda: daily_data_refresh(args),
        "strategy-lab": lambda: strategy_lab(args),
        "fund-risk": lambda: fund_risk(args),
        "fx-exposure": lambda: fx_exposure(args),
        "execution-sim": lambda: execution_sim(args),
        "algo-execution-plan": lambda: algo_execution_plan(args),
        "strategy-readiness": lambda: strategy_readiness(args),
        "quant-portfolio": lambda: quant_portfolio(args),
        "strategy-allocation": lambda: quant_portfolio(args),
        "portfolio-optimizer": lambda: portfolio_optimizer(args),
        "market-regime": lambda: market_regime(args),
        "ensemble-backtest": lambda: ensemble_backtest(args),
        "child-order-sim": lambda: child_order_sim(args),
        "global-gap-audit": global_gap_audit,
        "governance-report": governance_report,
        "investment-memo": lambda: investment_memo(args),
        "phase20-audit": phase20_audit,
        "global-coverage-model": global_coverage_model,
        "promotion-evidence": promotion_evidence,
        "promotion-evidence-record": lambda: promotion_evidence_record(args),
        "promotion-evidence-collect": lambda: promotion_evidence_collect(args),
        "hedgefund-readiness": hedgefund_readiness,
        "global-readiness-audit": hedgefund_readiness,
        "autonomy-audit": hedgefund_readiness,
        "accounting-ledger": lambda: accounting_ledger(args),
        "data-snapshot-audit": data_snapshot_audit,
        "data-entitlements": data_entitlements,
        "order-state-smoke": lambda: order_state_smoke(args),
        "strategy-validate": lambda: strategy_validate(args),
        "advanced-internal-upgrade": lambda: advanced_internal_upgrade(args),
        "dashboard-html": dashboard_html,
        "alerts-check": alerts_check,
        "heartbeat-record": lambda: heartbeat_record(args),
        "heartbeat-audit": heartbeat_audit,
        "etf-cost-optimizer": lambda: etf_cost_optimizer(args),
    }
    try:
        return handlers[args.command]()
    except KeyError as error:
        raise SystemExit(f"Unknown command: {args.command}") from error


def main() -> None:
    load_project_env()
    args = build_parser().parse_args()
    result = dispatch(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=json_default))


if __name__ == "__main__":
    main()
