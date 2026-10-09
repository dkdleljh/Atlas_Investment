from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.backtest.validation import StrategyValidator
from atlas_investment.models import Asset, Candle
from atlas_investment.strategy.base import StrategyPlugin


@dataclass(frozen=True)
class ParameterTrial:
    parameters: dict[str, float]
    score: float
    median_return_pct: float
    worst_return_pct: float
    warning_count: int


@dataclass(frozen=True)
class ParameterTuningReport:
    strategy: str
    symbol: str
    method: str
    status: str
    best_parameters: dict[str, float]
    trials: list[ParameterTrial]
    overfit_warnings: list[str]


class StrategyParameterTuner:
    """Walk-forward style deterministic parameter tuner.

    Existing strategy plugins are mostly fixed-rule classes. This tuner produces
    recommended overlay parameters that can be consumed by allocators and
    promotion gates without mutating plugin internals.
    """

    def tune(
        self,
        asset: Asset,
        candles: list[Candle],
        strategy: StrategyPlugin,
        grid: list[dict[str, float]] | None = None,
    ) -> ParameterTuningReport:
        if len(candles) < 120:
            return ParameterTuningReport(strategy.name, asset.symbol, "walk_forward_grid", "blocked", {}, [], ["튜닝에 필요한 가격 이력이 부족합니다."])
        grid = grid or [
            {"score_floor": 52.0, "target_scale": 0.75, "drawdown_penalty": 0.75},
            {"score_floor": 54.0, "target_scale": 1.00, "drawdown_penalty": 1.00},
            {"score_floor": 56.0, "target_scale": 1.10, "drawdown_penalty": 1.15},
            {"score_floor": 58.0, "target_scale": 0.90, "drawdown_penalty": 1.35},
        ]
        validator = StrategyValidator()
        base = validator.validate(asset, candles, strategy, folds=3, trials=80)
        trials: list[ParameterTrial] = []
        for params in grid:
            score_floor = params.get("score_floor", 54.0)
            target_scale = params.get("target_scale", 1.0)
            drawdown_penalty = params.get("drawdown_penalty", 1.0)
            activity_bonus = max(0.0, base.exposure_time_pct / 100.0) * 0.35
            score = (
                base.monte_carlo.median_return_pct * target_scale
                + base.sharpe_ratio * 2.5
                + activity_bonus
                - abs(base.monte_carlo.worst_return_pct) * 0.12 * drawdown_penalty
                - len(base.overfit_warnings) * 0.6
                - max(0.0, score_floor - 54.0) * 0.05
            )
            trials.append(
                ParameterTrial(
                    parameters=params,
                    score=round(score, 4),
                    median_return_pct=base.monte_carlo.median_return_pct,
                    worst_return_pct=base.monte_carlo.worst_return_pct,
                    warning_count=len(base.overfit_warnings),
                )
            )
        trials = sorted(trials, key=lambda item: item.score, reverse=True)
        warnings = list(base.overfit_warnings)
        if len(trials) >= 2 and trials[0].score - trials[-1].score > 8:
            warnings.append("파라미터별 점수 분산이 커서 과최적화 가능성을 점검해야 합니다.")
        if trials and trials[0].warning_count >= 3:
            warnings.append("최고 파라미터도 검증 경고가 많아 live 승격 전 추가 검증이 필요합니다.")
        return ParameterTuningReport(
            strategy.name,
            asset.symbol,
            "walk_forward_grid",
            "ok" if trials else "blocked",
            trials[0].parameters if trials else {},
            trials,
            warnings,
        )
