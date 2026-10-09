from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import Fill, OrderIntent


@dataclass(frozen=True)
class ExecutionPlan:
    order_count: int
    notional_krw: float
    order_ids: list[str]


class ExecutionEngine:
    """Separates order routing from strategy decisions."""

    def plan(self, orders: list[OrderIntent], prices: dict[str, float]) -> ExecutionPlan:
        notional = sum(prices.get(order.asset.symbol, order.limit_price or 0.0) * order.quantity for order in orders)
        return ExecutionPlan(len(orders), notional, [order.idempotency_key for order in orders])

    def paper_fill(self, orders: list[OrderIntent], prices: dict[str, float]) -> list[Fill]:
        fills: list[Fill] = []
        for order in orders:
            price = prices.get(order.asset.symbol, order.limit_price or 0.0)
            if price <= 0:
                continue
            fills.append(Fill(order.idempotency_key, order.asset.symbol, order.side, order.quantity, price, order.asset.currency))
        return fills
