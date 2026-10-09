from __future__ import annotations

import unittest

from atlas_investment.config import RiskPolicy
from atlas_investment.data.universe import load_institutional_sample_universe
from atlas_investment.fx.overlay import FxOverlayEngine
from atlas_investment.models import PortfolioSnapshot, Position, Signal
from atlas_investment.portfolio.manager import PortfolioManager
from atlas_investment.realtime.event_bus import EventBus
from atlas_investment.risk.institutional import InstitutionalRiskEngine


def policy() -> RiskPolicy:
    return RiskPolicy(
        kill_switch=False,
        allow_live_trading=False,
        allow_margin_trading=False,
        allow_credit_trading=False,
        allow_leveraged_inverse=True,
        min_cash_ratio=0.15,
        max_single_position_weight=0.5,
        max_leveraged_inverse_weight=0.2,
        max_daily_order_amount_krw=1_000_000,
        max_daily_loss_krw=300_000,
        max_open_positions=20,
        min_score_to_buy=68,
        min_score_to_sell=35,
    )


class InstitutionalModulesTest(unittest.TestCase):
    def test_portfolio_manager_allocates_buy_signals(self) -> None:
        asset = load_institutional_sample_universe()[0]
        signal = Signal(asset, 75, "buy", ["test"], 20, "unit", target_weight=0.03)
        portfolio = PortfolioSnapshot(cash_krw=10_000_000)
        allocations = PortfolioManager().allocate([signal], portfolio)
        self.assertEqual(len(allocations), 1)
        self.assertGreater(allocations[0].capital_krw, 0)

    def test_institutional_risk_report_detects_exposure(self) -> None:
        assets = {asset.symbol: asset for asset in load_institutional_sample_universe()}
        portfolio = PortfolioSnapshot(cash_krw=1_000_000, positions={"TQQQ": Position("TQQQ", 10, 100000, 1_000_000)})
        report = InstitutionalRiskEngine().exposure_report(portfolio, assets, policy())
        self.assertGreater(report.leveraged_inverse_weight, 0)

    def test_fx_overlay_changes_usd_exposure(self) -> None:
        decision = FxOverlayEngine().decide(usdkrw=1450, usdkrw_60d_average=1350, current_usd_exposure=0.5)
        self.assertEqual(decision.stance, "reduce_usd_buying")

    def test_event_bus_drains_events(self) -> None:
        bus = EventBus()
        bus.publish("quote", "AAPL", {"price": 200})
        self.assertEqual(len(bus), 1)
        self.assertEqual(len(bus.drain()), 1)
        self.assertEqual(len(bus), 0)


if __name__ == "__main__":
    unittest.main()
