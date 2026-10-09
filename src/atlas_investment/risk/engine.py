from __future__ import annotations

from atlas_investment.config import RiskPolicy
from atlas_investment.fx.conversion import FxRates, quote_price_krw
from atlas_investment.models import OrderIntent, PortfolioSnapshot, Quote, RiskResult, Side, TradingMode


class RiskEngine:
    def validate(self, order: OrderIntent, quote: Quote, portfolio: PortfolioSnapshot, policy: RiskPolicy, mode: TradingMode) -> RiskResult:
        reasons: list[str] = []

        if policy.kill_switch:
            return RiskResult(False, ["킬스위치가 켜져 있어 모든 주문을 차단합니다."])
        if mode == TradingMode.OFF:
            return RiskResult(False, ["실행 모드가 OFF입니다."])
        if mode == TradingMode.LIVE_AUTO and not policy.allow_live_trading:
            return RiskResult(False, ["LIVE_AUTO는 정책상 비활성화되어 있습니다."])
        if order.uses_margin or policy.allow_margin_trading:
            return RiskResult(False, ["미수 거래는 절대 금지입니다."])
        if order.uses_credit or policy.allow_credit_trading:
            return RiskResult(False, ["신용 거래는 절대 금지입니다."])
        if (order.asset.is_leveraged or order.asset.is_inverse) and not policy.allow_leveraged_inverse:
            return RiskResult(False, ["레버리지/인버스 상품이 정책상 허용되지 않습니다."])

        fx_rates = FxRates({"KRW": 1.0, "USD": policy.usdkrw_reference_rate})
        order_value = quote_price_krw(quote, order.asset, fx_rates) * order.quantity
        if order.side == Side.BUY:
            if order_value > policy.max_daily_order_amount_krw:
                return RiskResult(False, [f"주문 금액 {order_value:,.0f}원이 하루 주문 한도 {policy.max_daily_order_amount_krw:,.0f}원을 초과합니다."])
            if order_value > portfolio.cash_krw:
                return RiskResult(False, ["현금 잔고를 초과하는 주문입니다. 미수 방지를 위해 차단합니다."])
            projected_cash_ratio = (portfolio.cash_krw - order_value) / max(portfolio.equity_krw, 1)
            if projected_cash_ratio < policy.min_cash_ratio:
                return RiskResult(False, ["주문 후 최소 현금 비중을 밑돌아 차단합니다."])
            projected_weight = (portfolio.positions.get(order.asset.symbol).market_value if order.asset.symbol in portfolio.positions else 0) + order_value
            projected_weight = projected_weight / max(portfolio.equity_krw, 1)
            max_weight = policy.max_leveraged_inverse_weight if (order.asset.is_leveraged or order.asset.is_inverse) else policy.max_single_position_weight
            if projected_weight > max_weight:
                return RiskResult(False, [f"주문 후 예상 비중 {projected_weight:.1%}가 허용 한도 {max_weight:.1%}를 초과합니다."])
            if len(portfolio.positions) >= policy.max_open_positions and order.asset.symbol not in portfolio.positions:
                return RiskResult(False, ["최대 보유 종목 수를 초과합니다."])

        if order.asset.is_leveraged or order.asset.is_inverse:
            reasons.append("레버리지/인버스 상품입니다. 허용하되 별도 한도 검사를 통과했습니다.")
        reasons.append("리스크 검사를 통과했습니다.")
        return RiskResult(True, reasons, adjusted_order=order)
