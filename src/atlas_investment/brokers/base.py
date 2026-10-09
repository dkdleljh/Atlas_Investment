from __future__ import annotations

from abc import ABC, abstractmethod

from atlas_investment.models import Fill, OrderIntent, PortfolioSnapshot, Quote


class Broker(ABC):
    @abstractmethod
    def get_portfolio(self) -> PortfolioSnapshot:
        raise NotImplementedError

    @abstractmethod
    def get_quote(self, symbol: str) -> Quote:
        raise NotImplementedError

    @abstractmethod
    def place_order(self, order: OrderIntent) -> Fill:
        raise NotImplementedError

    @abstractmethod
    def cancel_order(self, order_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_open_orders(self) -> list[OrderIntent]:
        raise NotImplementedError

    @abstractmethod
    def get_fills(self) -> list[Fill]:
        raise NotImplementedError

