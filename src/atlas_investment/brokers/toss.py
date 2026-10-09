from __future__ import annotations

from datetime import datetime, timezone

from atlas_investment.brokers.base import Broker
from atlas_investment.brokers.toss_clients import TossApiConfig, TossOfficialApiClient
from atlas_investment.models import Fill, OrderIntent, PortfolioSnapshot, Position, Quote


class TossLiveBroker(Broker):
    """Official Toss Securities broker adapter.

    Read-only account, position, order, fill, and quote calls are enabled when
    official endpoint paths and credentials are configured. Mutating live orders
    remain blocked until the official order spec and Atlas promotion gates are
    explicitly completed.
    """

    def __init__(self, config: TossApiConfig | None = None, client: TossOfficialApiClient | None = None) -> None:
        self.config = config or TossApiConfig.from_env()
        self.client = client or TossOfficialApiClient(self.config)

    def get_portfolio(self) -> PortfolioSnapshot:
        positions = {
            symbol: Position(
                symbol=symbol,
                quantity=self._number(raw.get("quantity")),
                avg_price=self._number(raw.get("averagePurchasePrice")),
                market_value=self._market_value(raw),
                currency=str(raw.get("currency", "KRW")),
            )
            for raw in self.client.get_positions()
            for symbol in [str(raw.get("symbol") or "")]
            if symbol
        }
        return PortfolioSnapshot(cash_krw=0.0, positions=positions)

    def get_quote(self, symbol: str) -> Quote:
        payload = self.client.get_quote(symbol)
        price = self._number(payload.get("lastPrice"))
        return Quote(
            symbol=str(payload.get("symbol") or symbol),
            price=price,
            currency=str(payload.get("currency", "KRW")),
            as_of=str(payload.get("timestamp") or datetime.now(timezone.utc).isoformat()),
        )

    def place_order(self, order: OrderIntent) -> Fill:
        raise RuntimeError("토스증권 실주문은 공식 주문 endpoint 검토, 소액 검증, promotion evidence 완료 전까지 차단됩니다.")

    def cancel_order(self, order_id: str) -> None:
        raise RuntimeError("토스증권 주문 취소는 공식 주문 endpoint 검토, 소액 검증, promotion evidence 완료 전까지 차단됩니다.")

    def get_open_orders(self) -> list[OrderIntent]:
        raise RuntimeError("토스증권 미체결 주문은 스냅샷/reconciliation 경로에서만 조회합니다.")

    def get_fills(self) -> list[Fill]:
        raise RuntimeError("토스증권 체결 내역은 스냅샷/reconciliation 경로에서만 조회합니다.")

    @staticmethod
    def _market_value(raw: dict) -> float:
        market_value = raw.get("marketValue")
        if isinstance(market_value, dict):
            return TossLiveBroker._number(market_value.get("amount"))
        return TossLiveBroker._number(market_value)

    @staticmethod
    def _number(value: object) -> float:
        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
