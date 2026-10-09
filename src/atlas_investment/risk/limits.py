from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.config import RiskPolicy
from atlas_investment.models import Asset, OrderIntent, PortfolioSnapshot


@dataclass(frozen=True)
class LimitCheck:
    passed: bool
    breaches: list[str]


class PortfolioLimitChecker:
    def check_order(self, order: OrderIntent, price_krw: float, portfolio: PortfolioSnapshot, asset: Asset, policy: RiskPolicy) -> LimitCheck:
        breaches: list[str] = []
        equity = max(portfolio.equity_krw, 1)
        order_value = price_krw * order.quantity
        current_value = portfolio.positions.get(asset.symbol).market_value if asset.symbol in portfolio.positions else 0.0
        projected_weight = (current_value + order_value) / equity
        max_weight = policy.max_leveraged_inverse_weight if (asset.is_leveraged or asset.is_inverse) else policy.max_single_position_weight

        if projected_weight > max_weight:
            breaches.append(f"{asset.symbol} 예상 비중 {projected_weight:.2%}가 한도 {max_weight:.2%}를 초과합니다.")
        if portfolio.cash_krw - order_value < equity * policy.min_cash_ratio:
            breaches.append("주문 후 현금 비중이 최소 기준보다 낮아집니다.")
        if order_value > policy.max_daily_order_amount_krw:
            breaches.append("주문 금액이 일일 주문 한도를 초과합니다.")

        return LimitCheck(passed=not breaches, breaches=breaches)
