from __future__ import annotations

import random
from dataclasses import dataclass

from atlas_investment.backtest.engine import BacktestEngine
from atlas_investment.models import Asset, Candle
from atlas_investment.strategy.base import StrategyPlugin


@dataclass(frozen=True)
class WalkForwardFold:
    fold: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    test_return_pct: float
    test_max_drawdown_pct: float
    trade_count: int
    purge_bars: int = 0


@dataclass(frozen=True)
class MonteCarloReport:
    trials: int
    median_return_pct: float
    worst_return_pct: float
    best_return_pct: float
    loss_probability_pct: float


@dataclass(frozen=True)
class StrategyValidationReport:
    strategy: str
    symbol: str
    folds: list[WalkForwardFold]
    monte_carlo: MonteCarloReport
    capacity_notional: float
    estimated_slippage_bps: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    profit_factor: float
    turnover: float
    exposure_time_pct: float
    benchmark_alpha_pct: float
    benchmark_beta: float
    overfit_warnings: list[str]


class StrategyValidator:
    def __init__(self, initial_cash: float = 10_000_000) -> None:
        self.initial_cash = initial_cash

    def validate(
        self,
        asset: Asset,
        candles: list[Candle],
        strategy: StrategyPlugin,
        folds: int = 3,
        trials: int = 200,
        purge_bars: int = 5,
    ) -> StrategyValidationReport:
        if len(candles) < 90:
            raise ValueError("at least 90 candles are required for validation")
        fold_rows = self._walk_forward(asset, candles, strategy, folds, purge_bars)
        monte_carlo = self._monte_carlo(asset, candles, strategy, trials)
        full_result = BacktestEngine(initial_cash=self.initial_cash).run(asset, candles, strategy)
        metrics = self._metrics(full_result.equity_curve, full_result.trades, candles)
        capacity_notional = self._capacity_notional(candles)
        estimated_slippage_bps = self._estimated_slippage_bps(candles)
        warnings = []
        if len(fold_rows) < folds:
            warnings.append("데이터가 부족해 요청한 fold 수를 모두 만들지 못했습니다.")
        if fold_rows and sum(1 for fold in fold_rows if fold.test_return_pct > 0) / len(fold_rows) < 0.5:
            warnings.append("워크포워드 양수 수익 fold 비율이 낮습니다.")
        if monte_carlo.loss_probability_pct > 45:
            warnings.append("몬테카를로 손실 확률이 높습니다.")
        if any(fold.trade_count == 0 for fold in fold_rows):
            warnings.append("일부 검증 구간에서 거래가 발생하지 않았습니다.")
        if capacity_notional <= 0:
            warnings.append("ADV 기반 capacity를 계산할 수 없습니다.")
        if estimated_slippage_bps > 50:
            warnings.append("거래비용/슬리피지 추정치가 높습니다.")
        if metrics["sharpe_ratio"] < 0:
            warnings.append("Sharpe ratio가 음수입니다.")
        if metrics["profit_factor"] < 1 and metrics["profit_factor"] != 0:
            warnings.append("Profit factor가 1 미만입니다.")
        return StrategyValidationReport(
            strategy.name,
            asset.symbol,
            fold_rows,
            monte_carlo,
            round(capacity_notional, 2),
            round(estimated_slippage_bps, 4),
            round(metrics["sharpe_ratio"], 4),
            round(metrics["sortino_ratio"], 4),
            round(metrics["calmar_ratio"], 4),
            round(metrics["profit_factor"], 4),
            round(metrics["turnover"], 4),
            round(metrics["exposure_time_pct"], 4),
            round(metrics["benchmark_alpha_pct"], 4),
            round(metrics["benchmark_beta"], 4),
            warnings,
        )

    def _walk_forward(self, asset: Asset, candles: list[Candle], strategy: StrategyPlugin, folds: int, purge_bars: int) -> list[WalkForwardFold]:
        rows: list[WalkForwardFold] = []
        test_size = max(20, len(candles) // (folds + 3))
        train_size = max(60, test_size * 2)
        engine = BacktestEngine(initial_cash=self.initial_cash)
        start = 0
        for fold in range(1, folds + 1):
            train_start = start
            train_end = train_start + train_size
            test_start = min(len(candles), train_end + max(0, purge_bars))
            test_end = test_start + test_size
            if test_end > len(candles):
                break
            test = candles[test_start:test_end]
            result = engine.run(asset, test, strategy)
            rows.append(
                WalkForwardFold(
                    fold,
                    candles[train_start].date,
                    candles[train_end - 1].date,
                    test[0].date,
                    test[-1].date,
                    round(result.total_return_pct, 4),
                    round(result.max_drawdown_pct, 4),
                    result.trade_count,
                    purge_bars,
                )
            )
            start += test_size
        return rows

    def _monte_carlo(self, asset: Asset, candles: list[Candle], strategy: StrategyPlugin, trials: int) -> MonteCarloReport:
        engine = BacktestEngine(initial_cash=self.initial_cash)
        base = engine.run(asset, candles, strategy)
        daily_returns = []
        curve = base.equity_curve
        for previous, current in zip(curve, curve[1:]):
            prev = float(previous["equity"])
            curr = float(current["equity"])
            if prev > 0:
                daily_returns.append(curr / prev - 1)
        if not daily_returns:
            return MonteCarloReport(trials, 0.0, 0.0, 0.0, 0.0)
        rng = random.Random(f"{asset.symbol}:{strategy.name}")
        returns = []
        for _ in range(trials):
            equity = self.initial_cash
            for value in (rng.choice(daily_returns) for _ in daily_returns):
                equity *= 1 + value
            returns.append((equity / self.initial_cash - 1) * 100)
        returns.sort()
        median = returns[len(returns) // 2]
        losses = sum(1 for value in returns if value < 0)
        return MonteCarloReport(trials, round(median, 4), round(returns[0], 4), round(returns[-1], 4), round(losses / trials * 100, 4))

    @staticmethod
    def _capacity_notional(candles: list[Candle], participation_rate: float = 0.05) -> float:
        if not candles:
            return 0.0
        recent = candles[-20:]
        adv = sum(candle.close * candle.volume for candle in recent) / len(recent)
        return adv * participation_rate

    @staticmethod
    def _estimated_slippage_bps(candles: list[Candle]) -> float:
        if not candles:
            return 0.0
        recent = candles[-20:]
        spreads = []
        for candle in recent:
            mid = (candle.high + candle.low) / 2
            if mid > 0:
                spreads.append((candle.high - candle.low) / mid * 10_000)
        return sum(spreads) / len(spreads) if spreads else 0.0

    def _metrics(self, equity_curve: list[dict[str, float | str]], trades: list, candles: list[Candle]) -> dict[str, float]:
        returns = []
        for previous, current in zip(equity_curve, equity_curve[1:]):
            prev = float(previous["equity"])
            curr = float(current["equity"])
            if prev > 0:
                returns.append(curr / prev - 1)
        if not returns:
            return {
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "calmar_ratio": 0.0,
                "profit_factor": 0.0,
                "turnover": 0.0,
                "exposure_time_pct": 0.0,
                "benchmark_alpha_pct": 0.0,
                "benchmark_beta": 0.0,
            }
        mean = sum(returns) / len(returns)
        std = _stddev(returns)
        downside = _stddev([value for value in returns if value < 0])
        annual_return = (1 + mean) ** 252 - 1
        max_dd = max((0.0, self._max_drawdown_from_curve(equity_curve)))
        benchmark_returns = []
        for previous, current in zip(candles, candles[1:]):
            if previous.close > 0:
                benchmark_returns.append(current.close / previous.close - 1)
        aligned_benchmark = benchmark_returns[-len(returns) :] if len(benchmark_returns) >= len(returns) else benchmark_returns
        aligned_returns = returns[-len(aligned_benchmark) :] if aligned_benchmark else []
        beta = _beta(aligned_returns, aligned_benchmark) if aligned_benchmark else 0.0
        benchmark_total = (candles[-1].close / candles[0].close - 1) * 100 if candles and candles[0].close > 0 else 0.0
        strategy_total = (float(equity_curve[-1]["equity"]) / float(equity_curve[0]["equity"]) - 1) * 100 if equity_curve else 0.0
        gross_profit = 0.0
        gross_loss = 0.0
        buy_count = sum(1 for trade in trades if getattr(trade, "side", None).value == "buy")
        sell_count = sum(1 for trade in trades if getattr(trade, "side", None).value == "sell")
        for value in returns:
            if value >= 0:
                gross_profit += value
            else:
                gross_loss += abs(value)
        return {
            "sharpe_ratio": (mean / std * (252**0.5)) if std > 0 else 0.0,
            "sortino_ratio": (mean / downside * (252**0.5)) if downside > 0 else 0.0,
            "calmar_ratio": (annual_return / abs(max_dd)) if max_dd < 0 else 0.0,
            "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0),
            "turnover": (buy_count + sell_count) / max(len(equity_curve), 1),
            "exposure_time_pct": min(100.0, (buy_count / max(sell_count, 1)) * 100) if trades else 0.0,
            "benchmark_alpha_pct": strategy_total - benchmark_total * beta,
            "benchmark_beta": beta,
        }

    @staticmethod
    def _max_drawdown_from_curve(equity_curve: list[dict[str, float | str]]) -> float:
        peak = 0.0
        worst = 0.0
        for point in equity_curve:
            equity = float(point["equity"])
            peak = max(peak, equity)
            if peak > 0:
                worst = min(worst, equity / peak - 1)
        return worst


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return variance**0.5


def _beta(strategy_returns: list[float], benchmark_returns: list[float]) -> float:
    if len(strategy_returns) < 2 or len(strategy_returns) != len(benchmark_returns):
        return 0.0
    mean_strategy = sum(strategy_returns) / len(strategy_returns)
    mean_benchmark = sum(benchmark_returns) / len(benchmark_returns)
    variance = sum((value - mean_benchmark) ** 2 for value in benchmark_returns)
    if variance <= 0:
        return 0.0
    covariance = sum((s - mean_strategy) * (b - mean_benchmark) for s, b in zip(strategy_returns, benchmark_returns))
    return covariance / variance
