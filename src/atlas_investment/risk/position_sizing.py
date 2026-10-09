from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.config import RiskPolicy
from atlas_investment.models import Asset, Candle, PortfolioSnapshot
from atlas_investment.technical.indicators import atr


@dataclass(frozen=True)
class PositionSizeDecision:
    symbol: str
    target_weight: float
    capital_krw: float
    quantity: int
    reason: str


class VolatilityPositionSizer:
    def size(
        self,
        asset: Asset,
        candles: list[Candle],
        portfolio: PortfolioSnapshot,
        policy: RiskPolicy,
        price_krw: float,
        base_weight: float = 0.03,
    ) -> PositionSizeDecision:
        if price_krw <= 0:
            return PositionSizeDecision(asset.symbol, 0.0, 0.0, 0, "가격이 0 이하라 포지션을 만들 수 없습니다.")

        max_weight = policy.max_leveraged_inverse_weight if (asset.is_leveraged or asset.is_inverse) else policy.max_single_position_weight
        closes = [candle.close for candle in candles]
        current_atr = atr(candles, 14)[-1] if candles else None
        volatility_ratio = (current_atr / closes[-1]) if current_atr and closes and closes[-1] > 0 else 0.02
        volatility_ratio = max(volatility_ratio, 0.005)
        adjusted_weight = min(base_weight * (0.02 / volatility_ratio), base_weight, max_weight)
        capital = min(portfolio.equity_krw * adjusted_weight, portfolio.cash_krw * (1 - policy.min_cash_ratio))
        quantity = max(0, int(capital // price_krw))
        return PositionSizeDecision(
            symbol=asset.symbol,
            target_weight=adjusted_weight,
            capital_krw=max(0.0, quantity * price_krw),
            quantity=quantity,
            reason=f"ATR 기반 변동성 {volatility_ratio:.2%}, 목표 비중 {adjusted_weight:.2%}",
        )
