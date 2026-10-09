from __future__ import annotations

from atlas_investment.config import StrategyConfig
from atlas_investment.fx.conversion import FxRates, quote_price_krw
from atlas_investment.models import CommitteeReport, OrderIntent, OrderType, PortfolioSnapshot, Quote, Side


class OrderPlanner:
    def create(self, report: CommitteeReport, quote: Quote, portfolio: PortfolioSnapshot, config: StrategyConfig) -> OrderIntent | None:
        if report.decision == "hold":
            return None

        if report.decision == "sell":
            position = portfolio.positions.get(report.asset.symbol)
            if not position:
                return None
            return OrderIntent(
                asset=report.asset,
                side=Side.SELL,
                quantity=position.quantity,
                order_type=OrderType.LIMIT,
                limit_price=round(quote.price * 0.995, 2),
                reason=f"위원회 점수 {report.score}점으로 매도 판단",
                expected_holding_days=0,
            )

        max_order_amount = min(config.base_order_amount_krw, portfolio.cash_krw * 0.25)
        krw_price = quote_price_krw(quote, report.asset, FxRates())
        quantity = int(max_order_amount // krw_price)
        if quantity <= 0:
            return None
        return OrderIntent(
            asset=report.asset,
            side=Side.BUY,
            quantity=quantity,
            order_type=OrderType.LIMIT,
            limit_price=round(quote.price * 1.002, 2),
            reason=f"위원회 점수 {report.score}점으로 매수 후보",
            expected_holding_days=report.horizon_days,
            uses_margin=False,
            uses_credit=False,
        )
