from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import Asset, OrderIntent, OrderType, PortfolioSnapshot, Side, Signal


@dataclass(frozen=True)
class AllocationDecision:
    asset: Asset
    target_weight: float
    capital_krw: float
    reason: str


class PortfolioManager:
    """Combines strategy signals into capital allocations before risk checks."""

    def __init__(self, max_strategy_weight: float = 0.12, cash_buffer: float = 0.15) -> None:
        self.max_strategy_weight = max_strategy_weight
        self.cash_buffer = cash_buffer

    def allocate(self, signals: list[Signal], portfolio: PortfolioSnapshot) -> list[AllocationDecision]:
        buy_signals = sorted((signal for signal in signals if signal.stance == "buy"), key=lambda item: item.score, reverse=True)
        available_capital = max(0.0, portfolio.equity_krw * (1 - self.cash_buffer) - (portfolio.equity_krw - portfolio.cash_krw))
        decisions: list[AllocationDecision] = []
        for signal in buy_signals:
            target_weight = min(signal.target_weight or 0.03, self.max_strategy_weight)
            capital = min(available_capital, portfolio.equity_krw * target_weight)
            if capital <= 0:
                break
            decisions.append(AllocationDecision(signal.asset, target_weight, capital, f"{signal.strategy} 점수 {signal.score} 기반 자본 배정"))
            available_capital -= capital
        return decisions

    def build_orders(self, allocations: list[AllocationDecision], prices: dict[str, float], holding_days: int = 20) -> list[OrderIntent]:
        orders: list[OrderIntent] = []
        for allocation in allocations:
            price = prices.get(allocation.asset.symbol)
            if not price or price <= 0:
                continue
            quantity = int(allocation.capital_krw // price)
            if quantity <= 0:
                continue
            orders.append(OrderIntent(allocation.asset, Side.BUY, quantity, OrderType.LIMIT, price, allocation.reason, holding_days))
        return orders
