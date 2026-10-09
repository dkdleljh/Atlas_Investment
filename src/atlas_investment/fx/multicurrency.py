from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import PortfolioSnapshot


@dataclass(frozen=True)
class CurrencyExposure:
    currency: str
    market_value: float
    market_value_krw: float
    weight: float


@dataclass(frozen=True)
class MultiCurrencyReport:
    equity_krw: float
    usdkrw: float
    exposures: list[CurrencyExposure]
    notes: list[str]


class MultiCurrencyEngine:
    def analyze(self, portfolio: PortfolioSnapshot, usdkrw: float = 1380.0) -> MultiCurrencyReport:
        values: dict[str, float] = {"KRW": portfolio.cash_krw}
        for position in portfolio.positions.values():
            values[position.currency] = values.get(position.currency, 0.0) + position.market_value

        converted = {
            currency: value * usdkrw if currency == "USD" else value
            for currency, value in values.items()
        }
        equity = sum(converted.values()) or 1.0
        exposures = [
            CurrencyExposure(
                currency=currency,
                market_value=round(values[currency], 2),
                market_value_krw=round(value_krw, 2),
                weight=round(value_krw / equity, 4),
            )
            for currency, value_krw in sorted(converted.items())
        ]
        notes = []
        usd_weight = next((item.weight for item in exposures if item.currency == "USD"), 0.0)
        if usd_weight > 0.65:
            notes.append("USD 노출이 높습니다. 신규 미국장 매수는 환율 필터를 통과해야 합니다.")
        if usd_weight < 0.15:
            notes.append("USD 노출이 낮습니다. 미국 ETF 리밸런싱 여지를 검토할 수 있습니다.")
        return MultiCurrencyReport(round(equity, 2), usdkrw, exposures, notes)
