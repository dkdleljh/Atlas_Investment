from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.config import RiskPolicy
from atlas_investment.models import Asset, PortfolioSnapshot
from atlas_investment.risk.institutional import InstitutionalRiskEngine


@dataclass(frozen=True)
class FundRiskBudget:
    max_gross_exposure: float = 0.95
    max_leveraged_inverse_weight: float = 0.08
    min_cash_ratio: float = 0.15
    max_drawdown_soft: float = -0.08
    max_drawdown_hard: float = -0.15


@dataclass(frozen=True)
class FundRiskReport:
    equity_krw: float
    cash_ratio: float
    gross_exposure: float
    leveraged_inverse_weight: float
    risk_level: str
    actions: list[str]
    limit_usage: dict[str, float]
    breaches: list[str]


class FundRiskGovernor:
    def evaluate(
        self,
        portfolio: PortfolioSnapshot,
        assets: dict[str, Asset],
        policy: RiskPolicy,
        budget: FundRiskBudget | None = None,
        current_drawdown: float = 0.0,
    ) -> FundRiskReport:
        budget = budget or FundRiskBudget(
            max_leveraged_inverse_weight=policy.max_leveraged_inverse_weight,
            min_cash_ratio=policy.min_cash_ratio,
        )
        exposure = InstitutionalRiskEngine().exposure_report(portfolio, assets, policy)
        gross_exposure = max(0.0, 1.0 - exposure.cash_ratio)
        breaches = list(exposure.breaches)
        actions = ["allow_research_and_paper"]

        if gross_exposure > budget.max_gross_exposure:
            breaches.append("총 익스포저가 펀드 한도를 초과했습니다.")
        if exposure.cash_ratio < budget.min_cash_ratio:
            breaches.append("펀드 현금 버퍼가 부족합니다.")
        if exposure.leveraged_inverse_weight > budget.max_leveraged_inverse_weight:
            breaches.append("레버리지/인버스 펀드 한도를 초과했습니다.")
        if current_drawdown <= budget.max_drawdown_hard:
            breaches.append("하드 손실 한도에 도달했습니다.")
            actions = ["block_new_orders", "paper_only", "require_manual_review"]
        elif current_drawdown <= budget.max_drawdown_soft:
            actions = ["de_risk", "reduce_order_size", "paper_only_for_new_strategies"]

        if breaches and "block_new_orders" not in actions:
            actions.append("block_breaching_orders")

        risk_level = "green"
        if breaches:
            risk_level = "red" if any("하드" in breach or "초과" in breach for breach in breaches) else "yellow"
        elif current_drawdown <= budget.max_drawdown_soft:
            risk_level = "yellow"

        return FundRiskReport(
            equity_krw=round(exposure.equity_krw, 2),
            cash_ratio=round(exposure.cash_ratio, 4),
            gross_exposure=round(gross_exposure, 4),
            leveraged_inverse_weight=round(exposure.leveraged_inverse_weight, 4),
            risk_level=risk_level,
            actions=actions,
            limit_usage={
                "gross_exposure": round(gross_exposure / budget.max_gross_exposure, 4) if budget.max_gross_exposure else 0,
                "cash_buffer": round(budget.min_cash_ratio / exposure.cash_ratio, 4) if exposure.cash_ratio else 999,
                "leveraged_inverse": round(exposure.leveraged_inverse_weight / budget.max_leveraged_inverse_weight, 4) if budget.max_leveraged_inverse_weight else 0,
            },
            breaches=breaches,
        )
