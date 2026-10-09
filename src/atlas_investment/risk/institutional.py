from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.config import RiskPolicy
from atlas_investment.models import Asset, PortfolioSnapshot


@dataclass(frozen=True)
class ExposureReport:
    equity_krw: float
    cash_ratio: float
    market_weights: dict[str, float]
    sector_weights: dict[str, float]
    leveraged_inverse_weight: float
    breaches: list[str]


class InstitutionalRiskEngine:
    def exposure_report(self, portfolio: PortfolioSnapshot, assets: dict[str, Asset], policy: RiskPolicy) -> ExposureReport:
        equity = max(portfolio.equity_krw, 1)
        market_values: dict[str, float] = {}
        sector_values: dict[str, float] = {}
        leveraged_inverse_value = 0.0
        breaches: list[str] = []

        for symbol, position in portfolio.positions.items():
            asset = assets.get(symbol)
            market = asset.market.value if asset else "unknown"
            sector = str(asset.metadata.get("sector", "unknown")) if asset else "unknown"
            market_values[market] = market_values.get(market, 0.0) + position.market_value
            sector_values[sector] = sector_values.get(sector, 0.0) + position.market_value
            if asset and (asset.is_leveraged or asset.is_inverse):
                leveraged_inverse_value += position.market_value
            if position.market_value / equity > policy.max_single_position_weight:
                breaches.append(f"{symbol} 단일 종목 비중이 한도를 초과했습니다.")

        cash_ratio = portfolio.cash_krw / equity
        leveraged_inverse_weight = leveraged_inverse_value / equity
        if cash_ratio < policy.min_cash_ratio:
            breaches.append("현금 비중이 최소 기준보다 낮습니다.")
        if leveraged_inverse_weight > policy.max_leveraged_inverse_weight:
            breaches.append("레버리지/인버스 총 비중이 한도를 초과했습니다.")

        return ExposureReport(
            equity_krw=portfolio.equity_krw,
            cash_ratio=cash_ratio,
            market_weights={key: value / equity for key, value in market_values.items()},
            sector_weights={key: value / equity for key, value in sector_values.items()},
            leveraged_inverse_weight=leveraged_inverse_weight,
            breaches=breaches,
        )
