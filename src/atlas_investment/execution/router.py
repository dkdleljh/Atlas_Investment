from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import OrderIntent, TradingMode


@dataclass(frozen=True)
class ExecutionRoute:
    order_id: str
    symbol: str
    route: str
    status: str
    reason: str


class ExecutionRouter:
    def route_orders(self, orders: list[OrderIntent], mode: TradingMode, live_ready: bool = False) -> list[ExecutionRoute]:
        routes: list[ExecutionRoute] = []
        for order in orders:
            if order.uses_margin or order.uses_credit:
                routes.append(ExecutionRoute(order.idempotency_key, order.asset.symbol, "none", "blocked", "미수/신용 주문은 절대 금지입니다."))
                continue
            if mode == TradingMode.LIVE_AUTO:
                status = "ready" if live_ready else "blocked"
                reason = "공식 브로커 API 준비 완료" if live_ready else "토스 공식 실주문 API 준비 전까지 LIVE 주문은 차단합니다."
                routes.append(ExecutionRoute(order.idempotency_key, order.asset.symbol, "official_broker_api", status, reason))
            elif mode == TradingMode.PAPER:
                routes.append(ExecutionRoute(order.idempotency_key, order.asset.symbol, "paper_broker", "queued", "가상 체결 엔진으로만 라우팅합니다."))
            elif mode == TradingMode.DRY_RUN:
                routes.append(ExecutionRoute(order.idempotency_key, order.asset.symbol, "dry_run", "simulated", "주문 검증만 수행하고 체결하지 않습니다."))
            else:
                routes.append(ExecutionRoute(order.idempotency_key, order.asset.symbol, "none", "blocked", "OFF 모드입니다."))
        return routes
