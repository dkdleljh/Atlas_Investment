from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.strategy.regime import MarketRegime


@dataclass(frozen=True)
class RiskOverlayDecision:
    status: str
    exposure_multiplier: float
    max_gross_exposure: float
    reasons: list[str]


class RiskOverlay:
    """Portfolio-level exposure haircut driven by regime and drawdown."""

    def decide(self, regime: MarketRegime, current_drawdown_pct: float = 0.0, base_max_gross: float = 1.0) -> RiskOverlayDecision:
        multiplier = regime.exposure_multiplier
        reasons = list(regime.reasons)
        if current_drawdown_pct <= -12:
            multiplier *= 0.35
            reasons.append(f"현재 낙폭 {current_drawdown_pct:.1f}%가 커서 신규 위험 노출을 크게 줄입니다.")
        elif current_drawdown_pct <= -7:
            multiplier *= 0.6
            reasons.append(f"현재 낙폭 {current_drawdown_pct:.1f}%로 위험 노출을 줄입니다.")
        max_gross = round(max(0.05, min(base_max_gross, base_max_gross * multiplier)), 6)
        return RiskOverlayDecision("ok", round(multiplier, 6), max_gross, reasons)
