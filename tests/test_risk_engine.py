from __future__ import annotations

import unittest

from atlas_investment.config import RiskPolicy
from atlas_investment.models import Asset, Market, OrderIntent, OrderType, PortfolioSnapshot, Position, Quote, Side, TradingMode
from atlas_investment.risk.batch import BatchRiskEngine
from atlas_investment.risk.engine import RiskEngine


def base_policy() -> RiskPolicy:
    return RiskPolicy(
        kill_switch=False,
        allow_live_trading=False,
        allow_margin_trading=False,
        allow_credit_trading=False,
        allow_leveraged_inverse=True,
        min_cash_ratio=0.1,
        max_single_position_weight=0.5,
        max_leveraged_inverse_weight=0.2,
        max_daily_order_amount_krw=1_000_000,
        max_daily_loss_krw=300_000,
        max_open_positions=10,
        min_score_to_buy=68,
        min_score_to_sell=35,
    )


class RiskEngineTest(unittest.TestCase):
    def test_margin_is_always_blocked(self) -> None:
        asset = Asset("005930", "삼성전자", Market.KR)
        order = OrderIntent(asset, Side.BUY, 1, OrderType.LIMIT, 80000, "test", 10, uses_margin=True)
        quote = Quote("005930", 80000, "KRW", "now")
        result = RiskEngine().validate(order, quote, PortfolioSnapshot(cash_krw=1_000_000), base_policy(), TradingMode.PAPER)
        self.assertFalse(result.allowed)
        self.assertIn("미수", result.reasons[0])

    def test_leveraged_inverse_is_allowed_when_within_limit(self) -> None:
        asset = Asset("252670", "KODEX 200선물인버스2X", Market.KR, is_leveraged=True, is_inverse=True)
        order = OrderIntent(asset, Side.BUY, 10, OrderType.LIMIT, 1800, "test", 5)
        quote = Quote("252670", 1800, "KRW", "now")
        result = RiskEngine().validate(order, quote, PortfolioSnapshot(cash_krw=1_000_000), base_policy(), TradingMode.PAPER)
        self.assertTrue(result.allowed)

    def test_batch_risk_blocks_aggregate_daily_limit(self) -> None:
        asset = Asset("005930", "삼성전자", Market.KR)
        orders = [
            OrderIntent(asset, Side.BUY, 7, OrderType.LIMIT, 80000, "a", 5),
            OrderIntent(Asset("000660", "SK하이닉스", Market.KR), Side.BUY, 7, OrderType.LIMIT, 80000, "b", 5),
        ]
        quotes = {order.asset.symbol: Quote(order.asset.symbol, 80000, "KRW", "now") for order in orders}
        report = BatchRiskEngine().validate(orders, quotes, PortfolioSnapshot(cash_krw=2_000_000), base_policy())

        self.assertFalse(report.allowed)
        self.assertTrue(any(breach.code == "batch_daily_order_limit" for breach in report.breaches))

    def test_usd_quote_is_converted_to_krw_for_cash_check(self) -> None:
        asset = Asset("AAPL", "Apple", Market.US, currency="USD")
        order = OrderIntent(asset, Side.BUY, 5, OrderType.LIMIT, 100, "test", 5)
        quote = Quote("AAPL", 100, "USD", "now")
        result = RiskEngine().validate(order, quote, PortfolioSnapshot(cash_krw=500_000), base_policy(), TradingMode.PAPER)

        self.assertFalse(result.allowed)
        self.assertIn("현금", result.reasons[0])

    def test_batch_risk_counts_existing_leveraged_inverse_positions(self) -> None:
        tqqq = Asset("TQQQ", "ProShares UltraPro QQQ", Market.US, is_leveraged=True, currency="USD")
        asset = Asset("AAPL", "Apple", Market.US, currency="USD")
        orders = [OrderIntent(asset, Side.BUY, 1, OrderType.LIMIT, 100, "test", 5)]
        quotes = {"AAPL": Quote("AAPL", 100, "USD", "now")}
        portfolio = PortfolioSnapshot(
            cash_krw=700_000,
            positions={"TQQQ": Position("TQQQ", 1, 300_000, 300_000)},
        )
        policy = base_policy()
        report = BatchRiskEngine().validate(orders, quotes, portfolio, policy, assets_by_symbol={"TQQQ": tqqq, "AAPL": asset})

        self.assertFalse(report.allowed)
        self.assertTrue(any(breach.code == "batch_leveraged_inverse_limit" for breach in report.breaches))


if __name__ == "__main__":
    unittest.main()
