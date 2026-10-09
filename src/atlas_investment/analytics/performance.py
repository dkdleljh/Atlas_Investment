from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import BacktestResult


@dataclass(frozen=True)
class StrategyScore:
    strategy: str
    symbol: str
    total_return_pct: float
    max_drawdown_pct: float
    win_rate_pct: float
    trade_count: int
    score: float


def score_backtest(result: BacktestResult) -> StrategyScore:
    return StrategyScore(
        strategy=result.strategy,
        symbol=result.symbol,
        total_return_pct=result.total_return_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        win_rate_pct=result.win_rate_pct,
        trade_count=result.trade_count,
        score=result.total_return_pct + result.max_drawdown_pct * 0.7 + result.win_rate_pct * 0.05,
    )


def rank_backtests(results: list[BacktestResult]) -> list[StrategyScore]:
    return sorted((score_backtest(result) for result in results), key=lambda item: item.score, reverse=True)
