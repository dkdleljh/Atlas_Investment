from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.backtest.validation import StrategyValidationReport


@dataclass(frozen=True)
class StrategyLifecycleDecision:
    strategy: str
    status: str
    target_weight_multiplier: float
    reasons: list[str]


class StrategyLifecycleManager:
    """Promotes, demotes, or quarantines strategies from validation evidence."""

    def decide(self, report: StrategyValidationReport) -> StrategyLifecycleDecision:
        reasons: list[str] = []
        positive_folds = sum(1 for fold in report.folds if fold.test_return_pct > 0)
        fold_ratio = positive_folds / max(len(report.folds), 1)
        if report.sharpe_ratio < 0:
            reasons.append("Sharpe ratio가 음수입니다.")
        if report.profit_factor < 1 and report.profit_factor != 0:
            reasons.append("Profit factor가 1 미만입니다.")
        if fold_ratio < 0.5:
            reasons.append("워크포워드 양수 fold 비율이 50% 미만입니다.")
        if len(report.overfit_warnings) >= 3:
            reasons.append("과최적화/검증 경고가 많습니다.")
        if len(reasons) >= 3:
            return StrategyLifecycleDecision(report.strategy, "quarantine", 0.0, reasons)
        if reasons:
            return StrategyLifecycleDecision(report.strategy, "paper_only", 0.35, reasons)
        if report.sharpe_ratio >= 0.8 and report.profit_factor >= 1.2 and fold_ratio >= 0.67:
            return StrategyLifecycleDecision(report.strategy, "promote_candidate", 1.1, ["검증 지표가 승격 후보 기준을 만족합니다."])
        return StrategyLifecycleDecision(report.strategy, "lab", 0.75, ["승격 후보에는 부족하지만 폐기 기준은 아닙니다."])
