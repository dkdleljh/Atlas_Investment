from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostBreakdown:
    gross_amount: float
    fee: float
    tax: float
    slippage: float
    fx_spread: float

    @property
    def total_cost(self) -> float:
        return self.fee + self.tax + self.slippage + self.fx_spread

    @property
    def net_buy_amount(self) -> float:
        return self.gross_amount + self.total_cost

    @property
    def net_sell_amount(self) -> float:
        return self.gross_amount - self.total_cost


@dataclass(frozen=True)
class CostModel:
    fee_rate: float = 0.0005
    slippage_rate: float = 0.0005
    tax_rate: float = 0.0
    fx_spread_rate: float = 0.0

    def estimate_buy(self, gross_amount: float) -> CostBreakdown:
        return self._estimate(gross_amount, include_tax=False)

    def estimate_sell(self, gross_amount: float) -> CostBreakdown:
        return self._estimate(gross_amount, include_tax=True)

    def _estimate(self, gross_amount: float, include_tax: bool) -> CostBreakdown:
        return CostBreakdown(
            gross_amount=gross_amount,
            fee=gross_amount * self.fee_rate,
            tax=gross_amount * self.tax_rate if include_tax else 0.0,
            slippage=gross_amount * self.slippage_rate,
            fx_spread=gross_amount * self.fx_spread_rate,
        )
