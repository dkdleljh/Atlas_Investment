from __future__ import annotations

from datetime import datetime, timezone

from atlas_investment.brokers.base import Broker
from atlas_investment.fx.conversion import FxRates, quote_price_krw
from atlas_investment.models import Fill, OrderIntent, PortfolioSnapshot, Position, Quote, Side


class MockBroker(Broker):
    def __init__(self) -> None:
        self._portfolio = PortfolioSnapshot(
            cash_krw=5_000_000,
            positions={
                "069500": Position("069500", quantity=10, avg_price=38000, market_value=380000),
                "VOO": Position("VOO", quantity=1, avg_price=420000, market_value=420000),
            },
        )
        self._fills: list[Fill] = []

    def get_portfolio(self) -> PortfolioSnapshot:
        return self._portfolio

    def get_quote(self, symbol: str) -> Quote:
        base_prices = {
            "005930": 80000,
            "000660": 210000,
            "035420": 190000,
            "051910": 320000,
            "069500": 38000,
            "122630": 24000,
            "252670": 1800,
            "AAPL": 200,
            "MSFT": 450,
            "NVDA": 140,
            "JPM": 180,
            "VOO": 470,
            "TLT": 90,
            "GLD": 240,
            "TQQQ": 80,
            "SQQQ": 18,
        }
        currency = "USD" if symbol.isalpha() else "KRW"
        price = float(base_prices.get(symbol, 100 if currency == "USD" else 10000))
        return Quote(symbol=symbol, price=price, currency=currency, as_of=datetime.now(timezone.utc).isoformat(), previous_close=price * 0.99, volume=1_000_000)

    def place_order(self, order: OrderIntent) -> Fill:
        quote = self.get_quote(order.asset.symbol)
        price = order.limit_price or quote.price
        normalized_quote = Quote(
            symbol=quote.symbol,
            price=price,
            currency=quote.currency,
            as_of=quote.as_of,
            previous_close=quote.previous_close,
            volume=quote.volume,
        )
        value_krw = quote_price_krw(normalized_quote, order.asset, FxRates({"KRW": 1.0, "USD": 1380.0})) * order.quantity
        fill = Fill(
            order_id=order.idempotency_key,
            symbol=order.asset.symbol,
            side=order.side,
            quantity=order.quantity,
            price=price,
            currency=quote.currency,
        )
        self._fills.append(fill)
        if order.side == Side.BUY:
            self._portfolio.cash_krw -= value_krw
            existing = self._portfolio.positions.get(order.asset.symbol)
            old_value = existing.market_value if existing else 0
            old_qty = existing.quantity if existing else 0
            new_qty = old_qty + order.quantity
            self._portfolio.positions[order.asset.symbol] = Position(
                order.asset.symbol,
                quantity=new_qty,
                avg_price=price,
                market_value=old_value + value_krw,
                currency=quote.currency,
            )
        else:
            existing = self._portfolio.positions.get(order.asset.symbol)
            if existing:
                sold_qty = min(existing.quantity, order.quantity)
                self._portfolio.cash_krw += quote_price_krw(normalized_quote, order.asset, FxRates({"KRW": 1.0, "USD": 1380.0})) * sold_qty
                remaining_qty = existing.quantity - sold_qty
                if remaining_qty <= 0:
                    self._portfolio.positions.pop(order.asset.symbol, None)
                else:
                    existing.quantity = remaining_qty
                    existing.market_value = remaining_qty * price
        return fill

    def cancel_order(self, order_id: str) -> None:
        return None

    def get_open_orders(self) -> list[OrderIntent]:
        return []

    def get_fills(self) -> list[Fill]:
        return list(self._fills)
