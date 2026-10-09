from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.backtest.engine import BacktestEngine
from atlas_investment.models import Asset, BacktestResult, Candle
from atlas_investment.strategy.base import StrategyPlugin
from atlas_investment.technical.indicators import max_drawdown


@dataclass(frozen=True)
class PortfolioBacktestLeg:
    symbol: str
    strategy: str
    allocated_cash: float
    final_equity: float
    total_return_pct: float
    trade_count: int


@dataclass(frozen=True)
class PortfolioBacktestResult:
    strategy: str
    symbol_count: int
    initial_cash: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    legs: list[PortfolioBacktestLeg]
    equity_curve: list[dict[str, float | str]]


class PortfolioBacktestEngine:
    def __init__(self, initial_cash: float = 100_000_000, max_symbols: int | None = None) -> None:
        self.initial_cash = initial_cash
        self.max_symbols = max_symbols

    def run(
        self,
        assets: list[Asset],
        candles_by_symbol: dict[str, list[Candle]],
        strategy: StrategyPlugin,
    ) -> PortfolioBacktestResult:
        eligible_assets = [asset for asset in assets if asset.symbol in candles_by_symbol and candles_by_symbol[asset.symbol]]
        if self.max_symbols is not None:
            eligible_assets = eligible_assets[: self.max_symbols]
        if not eligible_assets:
            return PortfolioBacktestResult(strategy.name, 0, self.initial_cash, self.initial_cash, 0.0, 0.0, 0, [], [])

        allocated_cash = self.initial_cash / len(eligible_assets)
        results: list[BacktestResult] = []
        legs: list[PortfolioBacktestLeg] = []
        for asset in eligible_assets:
            result = BacktestEngine(initial_cash=allocated_cash).run(asset, candles_by_symbol[asset.symbol], strategy)
            results.append(result)
            legs.append(
                PortfolioBacktestLeg(
                    symbol=asset.symbol,
                    strategy=strategy.name,
                    allocated_cash=allocated_cash,
                    final_equity=result.final_equity,
                    total_return_pct=result.total_return_pct,
                    trade_count=result.trade_count,
                )
            )

        equity_curve = self._merge_equity_curves(results)
        final_equity = sum(result.final_equity for result in results)
        total_return_pct = (final_equity / self.initial_cash - 1) * 100
        drawdown = max_drawdown([float(point["equity"]) for point in equity_curve]) * 100 if equity_curve else 0.0
        trade_count = sum(result.trade_count for result in results)
        return PortfolioBacktestResult(
            strategy=strategy.name,
            symbol_count=len(eligible_assets),
            initial_cash=self.initial_cash,
            final_equity=final_equity,
            total_return_pct=total_return_pct,
            max_drawdown_pct=drawdown,
            trade_count=trade_count,
            legs=legs,
            equity_curve=equity_curve,
        )

    def _merge_equity_curves(self, results: list[BacktestResult]) -> list[dict[str, float | str]]:
        if not results:
            return []
        shortest = min(len(result.equity_curve) for result in results)
        merged: list[dict[str, float | str]] = []
        for index in range(shortest):
            date = str(results[0].equity_curve[index]["date"])
            equity = sum(float(result.equity_curve[index]["equity"]) for result in results)
            merged.append({"date": date, "equity": equity})
        return merged
