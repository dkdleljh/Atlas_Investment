from __future__ import annotations

from dataclasses import dataclass, field

from atlas_investment.config import RiskPolicy
from atlas_investment.fx.conversion import FxRates, quote_price_krw
from atlas_investment.models import Asset
from atlas_investment.models import OrderIntent, PortfolioSnapshot, Quote, Side


@dataclass(frozen=True)
class BatchRiskBreach:
    code: str
    message: str
    severity: str = "blocked"


@dataclass(frozen=True)
class BatchRiskReport:
    allowed: bool
    total_buy_notional_krw: float
    projected_cash_krw: float
    projected_cash_ratio: float
    projected_open_positions: int
    projected_leveraged_inverse_weight: float
    breaches: list[BatchRiskBreach] = field(default_factory=list)


class BatchRiskEngine:
    """Pre-trade portfolio simulation for a full order batch."""

    def validate(
        self,
        orders: list[OrderIntent],
        quotes: dict[str, Quote],
        portfolio: PortfolioSnapshot,
        policy: RiskPolicy,
        assets_by_symbol: dict[str, Asset] | None = None,
    ) -> BatchRiskReport:
        total_buy = 0.0
        assets_by_symbol = assets_by_symbol or {order.asset.symbol: order.asset for order in orders}
        fx_rates = FxRates({"KRW": 1.0, "USD": policy.usdkrw_reference_rate})
        projected_market_values = {symbol: position.market_value for symbol, position in portfolio.positions.items()}
        projected_leveraged_inverse_value = sum(
            position.market_value for symbol, position in portfolio.positions.items() if self._is_leveraged_inverse_symbol(symbol, orders, assets_by_symbol)
        )

        breaches: list[BatchRiskBreach] = []
        for order in orders:
            quote = quotes[order.asset.symbol]
            notional = quote_price_krw(quote, order.asset, fx_rates) * order.quantity
            current_value = projected_market_values.get(order.asset.symbol, 0.0)
            if order.side == Side.BUY:
                total_buy += notional
                projected_market_values[order.asset.symbol] = current_value + notional
                if order.asset.is_leveraged or order.asset.is_inverse:
                    projected_leveraged_inverse_value += notional
            elif order.side == Side.SELL:
                projected_market_values[order.asset.symbol] = max(0.0, current_value - notional)

        projected_cash = portfolio.cash_krw - total_buy
        equity = max(portfolio.equity_krw, 1.0)
        projected_cash_ratio = projected_cash / equity
        projected_open_positions = sum(1 for value in projected_market_values.values() if value > 0)
        leveraged_inverse_weight = projected_leveraged_inverse_value / equity

        if total_buy > policy.max_daily_order_amount_krw:
            breaches.append(
                BatchRiskBreach(
                    "batch_daily_order_limit",
                    f"주문 묶음 매수금액 {total_buy:,.0f}원이 일일 한도 {policy.max_daily_order_amount_krw:,.0f}원을 초과합니다.",
                )
            )
        if projected_cash < 0:
            breaches.append(BatchRiskBreach("batch_cash_shortfall", "주문 묶음 실행 시 현금 잔고가 음수가 됩니다."))
        if projected_cash_ratio < policy.min_cash_ratio:
            breaches.append(
                BatchRiskBreach(
                    "batch_min_cash_ratio",
                    f"주문 묶음 실행 후 현금 비중 {projected_cash_ratio:.1%}가 최소 비중 {policy.min_cash_ratio:.1%}보다 낮습니다.",
                )
            )
        if projected_open_positions > policy.max_open_positions:
            breaches.append(
                BatchRiskBreach(
                    "batch_open_position_limit",
                    f"주문 묶음 실행 후 보유 종목 수 {projected_open_positions}개가 한도 {policy.max_open_positions}개를 초과합니다.",
                )
            )
        if leveraged_inverse_weight > policy.max_leveraged_inverse_weight:
            breaches.append(
                BatchRiskBreach(
                    "batch_leveraged_inverse_limit",
                    f"레버리지/인버스 예상 비중 {leveraged_inverse_weight:.1%}가 한도 {policy.max_leveraged_inverse_weight:.1%}를 초과합니다.",
                )
            )

        return BatchRiskReport(
            allowed=not breaches,
            total_buy_notional_krw=total_buy,
            projected_cash_krw=projected_cash,
            projected_cash_ratio=projected_cash_ratio,
            projected_open_positions=projected_open_positions,
            projected_leveraged_inverse_weight=leveraged_inverse_weight,
            breaches=breaches,
        )

    @staticmethod
    def _is_leveraged_inverse_symbol(symbol: str, orders: list[OrderIntent], assets_by_symbol: dict[str, Asset]) -> bool:
        asset = assets_by_symbol.get(symbol)
        if asset is not None:
            return asset.is_leveraged or asset.is_inverse
        return any(order.asset.symbol == symbol and (order.asset.is_leveraged or order.asset.is_inverse) for order in orders)
