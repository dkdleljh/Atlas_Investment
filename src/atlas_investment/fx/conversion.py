from __future__ import annotations

from dataclasses import dataclass, field

from atlas_investment.models import Asset, Quote


@dataclass(frozen=True)
class FxRates:
    """Minimal KRW normalization table for pre-trade risk math."""

    rates_to_krw: dict[str, float] = field(default_factory=lambda: {"KRW": 1.0, "USD": 1380.0})

    def to_krw(self, amount: float, currency: str) -> float:
        normalized = currency.upper()
        if normalized not in self.rates_to_krw:
            raise ValueError(f"KRW 환산율이 없습니다: {currency}")
        return amount * self.rates_to_krw[normalized]


def quote_price_krw(quote: Quote, asset: Asset, fx_rates: FxRates | None = None) -> float:
    rates = fx_rates or FxRates()
    currency = (quote.currency or asset.currency or "KRW").upper()
    return rates.to_krw(quote.price, currency)
