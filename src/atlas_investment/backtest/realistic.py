from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import Candle


@dataclass(frozen=True)
class RealisticCostEstimate:
    notional: float
    fee: float
    spread_cost: float
    slippage: float
    market_impact: float
    tax: float
    total_cost: float
    cost_bps: float
    adv_participation: float
    warnings: list[str]


class MarketImpactCostModel:
    """Estimates spread, slippage, tax, and square-root market impact."""

    def estimate(
        self,
        candles: list[Candle],
        notional: float,
        fee_rate: float = 0.0005,
        tax_rate: float = 0.0,
        participation_rate: float = 0.08,
    ) -> RealisticCostEstimate:
        if not candles or notional <= 0:
            return RealisticCostEstimate(notional, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ["가격 이력 또는 주문 금액이 없습니다."])
        recent = candles[-20:]
        adv = sum(candle.close * candle.volume for candle in recent) / max(len(recent), 1)
        spread_proxy = sum((candle.high - candle.low) / max((candle.high + candle.low) / 2, 0.0001) for candle in recent) / len(recent)
        volatility = _realized_volatility([candle.close for candle in recent])
        adv_participation = notional / max(adv, 1.0)
        fee = notional * fee_rate
        spread_cost = notional * spread_proxy * 0.5
        slippage = notional * volatility * min(1.0, participation_rate) * 0.35
        market_impact = notional * volatility * (adv_participation**0.5) * 0.65
        tax = notional * tax_rate
        total = fee + spread_cost + slippage + market_impact + tax
        warnings = []
        if adv_participation > 0.1:
            warnings.append("주문 금액이 ADV 10%를 초과해 시장충격이 커질 수 있습니다.")
        if spread_proxy > 0.03:
            warnings.append("스프레드 프록시가 높습니다.")
        return RealisticCostEstimate(
            notional=round(notional, 4),
            fee=round(fee, 4),
            spread_cost=round(spread_cost, 4),
            slippage=round(slippage, 4),
            market_impact=round(market_impact, 4),
            tax=round(tax, 4),
            total_cost=round(total, 4),
            cost_bps=round(total / notional * 10_000, 4),
            adv_participation=round(adv_participation, 6),
            warnings=warnings,
        )


def _realized_volatility(closes: list[float]) -> float:
    returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes)) if closes[index - 1] > 0]
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    return (sum((value - mean) ** 2 for value in returns) / len(returns)) ** 0.5
