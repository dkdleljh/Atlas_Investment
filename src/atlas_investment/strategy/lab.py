from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.backtest.engine import BacktestEngine
from atlas_investment.models import Asset, Candle
from atlas_investment.strategy.base import StrategyPlugin


@dataclass(frozen=True)
class StrategyLabResult:
    strategy: str
    symbol: str
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_rate_pct: float
    stability_score: float
    approved_for_paper: bool
    notes: list[str]


class StrategyLab:
    def __init__(self, initial_cash: float = 10_000_000) -> None:
        self.initial_cash = initial_cash

    def run(
        self,
        assets: list[Asset],
        candles_by_symbol: dict[str, list[Candle]],
        strategies: list[StrategyPlugin],
    ) -> list[StrategyLabResult]:
        engine = BacktestEngine(initial_cash=self.initial_cash)
        results: list[StrategyLabResult] = []
        for asset in assets:
            candles = candles_by_symbol.get(asset.symbol, [])
            if len(candles) < 80:
                continue
            for strategy in strategies:
                backtest = engine.run(asset, candles, strategy)
                stability_score = self._score(backtest.total_return_pct, backtest.max_drawdown_pct, backtest.win_rate_pct, backtest.trade_count)
                approved = backtest.trade_count >= 2 and backtest.max_drawdown_pct > -25 and stability_score >= 35
                notes = []
                if not approved:
                    notes.append("PAPER 승격 전 거래 수, 낙폭, 안정성 점수 확인이 필요합니다.")
                if strategy.name == "scalping_simulation":
                    notes.append("스캘핑은 공식 실시간 호가/체결 API 연결 전까지 시뮬레이션 전용입니다.")
                results.append(
                    StrategyLabResult(
                        strategy=strategy.name,
                        symbol=asset.symbol,
                        total_return_pct=round(backtest.total_return_pct, 4),
                        max_drawdown_pct=round(backtest.max_drawdown_pct, 4),
                        trade_count=backtest.trade_count,
                        win_rate_pct=round(backtest.win_rate_pct, 4),
                        stability_score=round(stability_score, 4),
                        approved_for_paper=approved,
                        notes=notes,
                    )
                )
        return sorted(results, key=lambda item: item.stability_score, reverse=True)

    @staticmethod
    def _score(total_return_pct: float, max_drawdown_pct: float, win_rate_pct: float, trade_count: int) -> float:
        trade_penalty = max(0, trade_count - 80) * 0.15
        inactivity_penalty = 12 if trade_count == 0 else 0
        return 50 + total_return_pct * 0.7 + max_drawdown_pct * 1.1 + win_rate_pct * 0.08 - trade_penalty - inactivity_penalty
