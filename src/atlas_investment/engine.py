from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from atlas_investment.brokers.base import Broker
from atlas_investment.committee.engine import InvestmentCommittee
from atlas_investment.config import RiskPolicy, StrategyConfig
from atlas_investment.data.sample_universe import load_sample_universe
from atlas_investment.execution.state_machine import OrderStateStore, OrderStatus
from atlas_investment.guardian.market_guard import MarketGuard
from atlas_investment.journal.writer import Journal
from atlas_investment.models import TradingMode
from atlas_investment.orders.planner import OrderPlanner
from atlas_investment.risk.batch import BatchRiskEngine
from atlas_investment.risk.engine import RiskEngine
from atlas_investment.strategy.simple import SimpleSignalEngine


class TradingEngine:
    def __init__(
        self,
        broker: Broker,
        policy: RiskPolicy,
        strategy_config: StrategyConfig,
        journal: Journal,
        mode: TradingMode,
        universe: list | None = None,
        universe_source: str = "sample",
        order_state_store: OrderStateStore | None = None,
    ) -> None:
        self.broker = broker
        self.policy = policy
        self.strategy_config = strategy_config
        self.journal = journal
        self.mode = mode
        self.universe = universe
        self.universe_source = universe_source
        self.order_state_store = order_state_store
        self.guard = MarketGuard()
        self.signal_engine = SimpleSignalEngine()
        self.committee = InvestmentCommittee()
        self.order_planner = OrderPlanner()
        self.risk_engine = RiskEngine()
        self.batch_risk_engine = BatchRiskEngine()

    def run_once(self) -> dict:
        allowed, reason = self.guard.can_start_cycle(self.policy)
        if not allowed:
            self.journal.write("cycle_blocked", {"reason": reason})
            return {"status": "blocked", "reason": reason}
        if self.mode == TradingMode.OFF:
            reason = "실행 모드가 OFF입니다."
            self.journal.write("cycle_blocked", {"reason": reason, "mode": self.mode.value})
            return {"status": "blocked", "mode": self.mode.value, "reason": reason}
        if self.mode == TradingMode.LIVE_AUTO and not self.policy.allow_live_trading:
            reason = "LIVE_AUTO는 정책상 비활성화되어 있습니다."
            self.journal.write("cycle_blocked", {"reason": reason, "mode": self.mode.value})
            return {"status": "blocked", "mode": self.mode.value, "reason": reason}

        portfolio = self.broker.get_portfolio()
        base_universe = self.universe if self.universe is not None else load_sample_universe()
        universe = [asset for asset in base_universe if asset.market.value in self.strategy_config.markets and asset.tradable]
        quotes = {asset.symbol: self.broker.get_quote(asset.symbol) for asset in universe}
        signals = self.signal_engine.generate(universe, quotes, portfolio)

        reports = [self.committee.review(signal, self.policy) for signal in signals]
        orders = []
        risk_results = []
        managed_by_key = {}
        fills = []

        for report in reports:
            quote = quotes[report.asset.symbol]
            order = self.order_planner.create(report, quote, portfolio, self.strategy_config)
            if order is None:
                continue
            managed = self.order_state_store.create(order) if self.order_state_store else None
            risk_result = self.risk_engine.validate(order, quote, portfolio, self.policy, self.mode)
            risk_results.append({"order": order, "risk": risk_result})
            if risk_result.allowed and risk_result.adjusted_order:
                if managed is not None and managed.status == OrderStatus.CREATED:
                    managed = self.order_state_store.transition(order.idempotency_key, OrderStatus.VALIDATED, "risk checks passed")
                orders.append(risk_result.adjusted_order)
                if managed is not None:
                    managed_by_key[order.idempotency_key] = managed
            elif managed is not None and managed.status == OrderStatus.CREATED:
                self.order_state_store.transition(order.idempotency_key, OrderStatus.BLOCKED, "; ".join(risk_result.reasons))

        assets_by_symbol = {asset.symbol: asset for asset in universe}
        batch_risk = self.batch_risk_engine.validate(orders, quotes, portfolio, self.policy, assets_by_symbol=assets_by_symbol)
        if not batch_risk.allowed:
            reason = "; ".join(breach.message for breach in batch_risk.breaches)
            for order in orders:
                managed = managed_by_key.get(order.idempotency_key)
                if managed is not None and managed.status == OrderStatus.VALIDATED:
                    self.order_state_store.transition(order.idempotency_key, OrderStatus.BLOCKED, reason)
            orders = []
        else:
            for order in orders:
                managed = managed_by_key.get(order.idempotency_key)
                if self.mode == TradingMode.PAPER:
                    if managed is not None and managed.status == OrderStatus.VALIDATED:
                        managed = self.order_state_store.transition(order.idempotency_key, OrderStatus.QUEUED, "batch risk passed; queued for paper broker")
                        managed = self.order_state_store.transition(order.idempotency_key, OrderStatus.SUBMITTED, "submitted to paper broker")
                    fills.append(self.broker.place_order(order))
                    if managed is not None and managed.status == OrderStatus.SUBMITTED:
                        self.order_state_store.transition(order.idempotency_key, OrderStatus.FILLED, "paper fill completed")
                elif managed is not None and managed.status == OrderStatus.VALIDATED:
                    self.order_state_store.transition(order.idempotency_key, OrderStatus.QUEUED, "batch risk passed; validated for dry-run route")

        summary = {
            "status": "ok",
            "mode": self.mode.value,
            "universe_source": self.universe_source,
            "universe_count": len(universe),
            "signal_count": len(signals),
            "order_candidate_count": len(risk_results),
            "approved_order_count": len(orders),
            "fill_count": len(fills),
            "reports": reports,
            "risk_results": risk_results,
            "batch_risk": batch_risk,
            "fills": fills,
            "portfolio_equity_krw": portfolio.equity_krw,
        }
        self.journal.write("cycle_completed", summary)
        return summary
