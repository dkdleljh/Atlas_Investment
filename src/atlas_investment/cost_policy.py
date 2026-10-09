from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from atlas_investment.models import Market


@dataclass(frozen=True)
class MarketCostPolicy:
    commission_rate: float
    slippage_rate: float
    sell_tax_rate: float = 0.0
    fx_spread_rate: float = 0.0


@dataclass(frozen=True)
class CostPolicy:
    base_currency: str
    annual_management_fee_rate: float
    performance_fee_rate: float
    hurdle_rate: float
    high_water_mark_krw: float
    markets: dict[str, MarketCostPolicy]
    custody_admin_annual_rate: float = 0.0
    notes: list[str] | None = None

    def market(self, market: Market | str) -> MarketCostPolicy:
        key = market.value if isinstance(market, Market) else market
        return self.markets.get(key, MarketCostPolicy(commission_rate=0.0005, slippage_rate=0.0005))


@dataclass(frozen=True)
class RecurringFeeAccrual:
    equity_krw: float
    days: int
    management_fee: float
    custody_admin_fee: float
    performance_fee: float
    total_fee: float
    net_equity_krw: float
    notes: list[str]


class FundFeeModel:
    def __init__(self, policy: CostPolicy) -> None:
        self.policy = policy

    def accrue(self, equity_krw: float, days: int, ending_equity_krw: float | None = None) -> RecurringFeeAccrual:
        days = max(days, 0)
        ending_equity = equity_krw if ending_equity_krw is None else ending_equity_krw
        management = equity_krw * self.policy.annual_management_fee_rate * days / 365
        custody = equity_krw * self.policy.custody_admin_annual_rate * days / 365
        hurdle_equity = equity_krw * (1 + self.policy.hurdle_rate * days / 365)
        fee_base = max(0.0, ending_equity - max(self.policy.high_water_mark_krw, hurdle_equity))
        performance = fee_base * self.policy.performance_fee_rate
        total = management + custody + performance
        notes = []
        if self.policy.performance_fee_rate > 0 and self.policy.high_water_mark_krw <= 0:
            notes.append("성과보수율은 있으나 high-water mark가 0입니다. 실제 펀드 운용 전 기준값을 설정해야 합니다.")
        return RecurringFeeAccrual(
            equity_krw=round(equity_krw, 2),
            days=days,
            management_fee=round(management, 2),
            custody_admin_fee=round(custody, 2),
            performance_fee=round(performance, 2),
            total_fee=round(total, 2),
            net_equity_krw=round(ending_equity - total, 2),
            notes=notes + list(self.policy.notes or []),
        )


def load_cost_policy(path: Path) -> CostPolicy:
    payload = json.loads(path.read_text(encoding="utf-8"))
    markets = {
        key: MarketCostPolicy(
            commission_rate=float(value.get("commission_rate", 0.0005)),
            slippage_rate=float(value.get("slippage_rate", 0.0005)),
            sell_tax_rate=float(value.get("sell_tax_rate", 0.0)),
            fx_spread_rate=float(value.get("fx_spread_rate", 0.0)),
        )
        for key, value in payload.get("markets", {}).items()
    }
    return CostPolicy(
        base_currency=str(payload.get("base_currency", "KRW")),
        annual_management_fee_rate=float(payload.get("annual_management_fee_rate", 0.0)),
        performance_fee_rate=float(payload.get("performance_fee_rate", 0.0)),
        hurdle_rate=float(payload.get("hurdle_rate", 0.0)),
        high_water_mark_krw=float(payload.get("high_water_mark_krw", 0.0)),
        markets=markets,
        custody_admin_annual_rate=float(payload.get("custody_admin_annual_rate", 0.0)),
        notes=list(payload.get("notes", [])),
    )
