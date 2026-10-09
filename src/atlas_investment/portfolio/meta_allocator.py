from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.backtest.validation import StrategyValidationReport


@dataclass(frozen=True)
class MetaStrategyWeight:
    strategy: str
    weight: float
    score: float
    reasons: list[str]


@dataclass(frozen=True)
class MetaAllocationReport:
    status: str
    weights: list[MetaStrategyWeight]
    warnings: list[str]


class MetaStrategyAllocator:
    """Ranks strategies from validation evidence and returns dynamic weights."""

    def allocate(self, reports: list[StrategyValidationReport], min_weight: float = 0.02) -> MetaAllocationReport:
        if not reports:
            return MetaAllocationReport("blocked", [], ["전략 검증 리포트가 없습니다."])
        raw_scores: list[tuple[StrategyValidationReport, float, list[str]]] = []
        for report in reports:
            profitable_folds = sum(1 for fold in report.folds if fold.test_return_pct > 0)
            fold_ratio = profitable_folds / max(len(report.folds), 1)
            drawdown = max(abs(fold.test_max_drawdown_pct) for fold in report.folds) if report.folds else 0.0
            score = (
                report.sharpe_ratio * 1.8
                + report.sortino_ratio * 0.7
                + report.profit_factor * 0.6
                + fold_ratio * 3.0
                + report.benchmark_alpha_pct * 0.08
                - drawdown * 0.10
                - len(report.overfit_warnings) * 0.75
            )
            reasons = [
                f"Sharpe {report.sharpe_ratio:.2f}",
                f"profit factor {report.profit_factor:.2f}",
                f"positive folds {profitable_folds}/{max(len(report.folds), 1)}",
            ]
            if report.overfit_warnings:
                reasons.append(f"warnings {len(report.overfit_warnings)}")
            raw_scores.append((report, max(min_weight, score), reasons))
        total = sum(score for _, score, _ in raw_scores)
        if total <= 0:
            return MetaAllocationReport("blocked", [], ["전략 점수가 모두 0 이하입니다."])
        weights = [
            MetaStrategyWeight(report.strategy, round(score / total, 6), round(score, 4), reasons)
            for report, score, reasons in sorted(raw_scores, key=lambda item: item[1], reverse=True)
        ]
        warnings = []
        if max(item.weight for item in weights) > 0.55:
            warnings.append("단일 전략 메타 가중치가 55%를 초과해 집중 리스크가 있습니다.")
        return MetaAllocationReport("ok", weights, warnings)
