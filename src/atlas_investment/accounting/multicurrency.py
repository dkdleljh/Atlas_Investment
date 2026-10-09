from __future__ import annotations

from dataclasses import dataclass, field

from atlas_investment.models import PortfolioSnapshot, Position


@dataclass(frozen=True)
class CurrencyCashBook:
    balances: dict[str, float] = field(default_factory=lambda: {"KRW": 0.0})

    def balance(self, currency: str) -> float:
        return float(self.balances.get(currency, 0.0))


@dataclass(frozen=True)
class FxRateBook:
    base_currency: str = "KRW"
    rates_to_krw: dict[str, float] = field(default_factory=lambda: {"KRW": 1.0, "USD": 1380.0})

    def to_krw(self, amount: float, currency: str) -> float:
        return amount * self.rates_to_krw.get(currency, 1.0)


@dataclass(frozen=True)
class PositionValuation:
    symbol: str
    currency: str
    native_value: float
    krw_value: float
    weight: float


@dataclass(frozen=True)
class MultiCurrencyLedger:
    base_currency: str
    cash_by_currency: dict[str, float]
    cash_krw_value: float
    positions: list[PositionValuation]
    equity_krw: float
    currency_weights: dict[str, float]
    notes: list[str]


class MultiCurrencyAccountingEngine:
    def build_ledger(
        self,
        portfolio: PortfolioSnapshot,
        fx_rates: FxRateBook | None = None,
        cash_book: CurrencyCashBook | None = None,
    ) -> MultiCurrencyLedger:
        fx_rates = fx_rates or FxRateBook()
        cash_book = cash_book or CurrencyCashBook({"KRW": portfolio.cash_krw})
        cash_krw_value = sum(fx_rates.to_krw(amount, currency) for currency, amount in cash_book.balances.items())
        position_rows = self._position_rows(portfolio.positions, fx_rates)
        equity = cash_krw_value + sum(row.krw_value for row in position_rows)
        equity = max(equity, 1.0)
        position_rows = [
            PositionValuation(row.symbol, row.currency, row.native_value, row.krw_value, round(row.krw_value / equity, 6))
            for row in position_rows
        ]
        weights: dict[str, float] = {}
        for currency, amount in cash_book.balances.items():
            weights[currency] = weights.get(currency, 0.0) + fx_rates.to_krw(amount, currency) / equity
        for row in position_rows:
            weights[row.currency] = weights.get(row.currency, 0.0) + row.krw_value / equity
        notes = []
        if "USD" not in fx_rates.rates_to_krw:
            notes.append("USD 환율이 없어 USD 자산 원화 환산이 부정확할 수 있습니다.")
        if any(row.currency != "KRW" for row in position_rows) and len(cash_book.balances) == 1:
            notes.append("외화 현금 잔고가 분리 입력되지 않아 포지션 평가만 통화별로 분리했습니다.")
        return MultiCurrencyLedger(
            base_currency=fx_rates.base_currency,
            cash_by_currency={key: round(value, 2) for key, value in cash_book.balances.items()},
            cash_krw_value=round(cash_krw_value, 2),
            positions=position_rows,
            equity_krw=round(equity, 2),
            currency_weights={key: round(value, 6) for key, value in sorted(weights.items())},
            notes=notes,
        )

    @staticmethod
    def _position_rows(positions: dict[str, Position], fx_rates: FxRateBook) -> list[PositionValuation]:
        rows = []
        for position in positions.values():
            krw_value = fx_rates.to_krw(position.market_value, position.currency)
            rows.append(PositionValuation(position.symbol, position.currency, round(position.market_value, 2), round(krw_value, 2), 0.0))
        return rows
