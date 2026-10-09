from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import Signal


DEFAULT_STRATEGY_WEIGHTS = {
    "multifactor_qvm": 0.16,
    "time_series_momentum": 0.11,
    "cross_sectional_momentum": 0.10,
    "all_weather_risk_parity": 0.10,
    "macro_regime_allocation": 0.09,
    "cta_diversified_trend": 0.09,
    "ml_alpha_score": 0.08,
    "low_vol_defensive": 0.09,
    "shareholder_yield_carry": 0.08,
    "sector_regime_rotation": 0.07,
    "factor_quality": 0.05,
    "swing_momentum": 0.03,
    "breakout_momentum": 0.02,
    "earnings_revision_event": 0.01,
}


@dataclass(frozen=True)
class AllocationCandidate:
    symbol: str
    name: str
    market: str
    sector: str
    weighted_score: float
    confidence: float
    target_weight: float
    stance: str
    strategies: list[str]
    reasons: list[str]


@dataclass(frozen=True)
class StrategyAllocationReport:
    status: str
    candidate_count: int
    max_position_weight: float
    max_sector_weight: float
    candidates: list[AllocationCandidate]
    blocked_reasons: list[str]


class StrategyEnsembleAllocator:
    """Combines independent strategy signals into portfolio-level candidates."""

    def __init__(
        self,
        max_position_weight: float = 0.08,
        max_sector_weight: float = 0.35,
        buy_quantile: float = 0.8,
        min_buy_score: float = 54.0,
    ) -> None:
        self.max_position_weight = max_position_weight
        self.max_sector_weight = max_sector_weight
        self.buy_quantile = max(0.5, min(buy_quantile, 0.95))
        self.min_buy_score = min_buy_score

    def allocate(
        self,
        signals: list[Signal],
        strategy_weights: dict[str, float] | None = None,
    ) -> StrategyAllocationReport:
        weights = strategy_weights or DEFAULT_STRATEGY_WEIGHTS
        grouped: dict[str, list[Signal]] = {}
        for signal in signals:
            grouped.setdefault(signal.asset.symbol, []).append(signal)
        candidates: list[AllocationCandidate] = []
        for symbol, items in grouped.items():
            weighted_score_sum = 0.0
            total_weight = 0.0
            confidence_sum = 0.0
            target_weight = 0.0
            strategies: list[str] = []
            reasons: list[str] = []
            for signal in items:
                weight = weights.get(signal.strategy, 0.03)
                confidence_multiplier = 1.0 if signal.stance in {"buy", "sell"} else 0.35
                stance_adjusted_score = 50 + (signal.score - 50) * confidence_multiplier
                weighted_score_sum += stance_adjusted_score * weight
                total_weight += weight
                confidence_sum += signal.confidence * weight
                if signal.stance == "buy":
                    target_weight += (signal.target_weight or 0.01) * weight
                strategies.append(signal.strategy)
                reasons.extend(signal.reasons[:2])
            if total_weight <= 0:
                continue
            asset = items[0].asset
            score = weighted_score_sum / total_weight
            confidence = confidence_sum / total_weight
            normalized_weight = min(self.max_position_weight, max(0.0, target_weight / total_weight))
            stance = "hold" if score >= 45 else "sell"
            if stance == "sell":
                normalized_weight = 0.0
            candidates.append(
                AllocationCandidate(
                    symbol=symbol,
                    name=asset.name,
                    market=asset.market.value,
                    sector=str(asset.metadata.get("sector", "unknown")),
                    weighted_score=round(score, 4),
                    confidence=round(confidence, 4),
                    target_weight=round(normalized_weight, 4),
                    stance=stance,
                    strategies=sorted(set(strategies)),
                    reasons=reasons[:6],
                )
            )
        buy_threshold = self._adaptive_buy_threshold(candidates)
        candidates = [
            _replace_weight(candidate, candidate.target_weight, "buy")
            if candidate.stance != "sell" and candidate.target_weight > 0 and candidate.weighted_score >= buy_threshold
            else candidate
            for candidate in candidates
        ]
        candidates = sorted(candidates, key=lambda item: (item.stance == "buy", item.weighted_score, item.confidence), reverse=True)
        capped, blocked = self._cap_sector_weights(candidates)
        return StrategyAllocationReport(
            status="ok" if capped else "blocked",
            candidate_count=len(capped),
            max_position_weight=self.max_position_weight,
            max_sector_weight=self.max_sector_weight,
            candidates=capped,
            blocked_reasons=blocked,
        )

    def _adaptive_buy_threshold(self, candidates: list[AllocationCandidate]) -> float:
        eligible_scores = sorted(
            [candidate.weighted_score for candidate in candidates if candidate.target_weight > 0 and candidate.stance != "sell"]
        )
        if not eligible_scores:
            return 62.0
        index = min(len(eligible_scores) - 1, max(0, int(len(eligible_scores) * self.buy_quantile) - 1))
        return max(self.min_buy_score, eligible_scores[index])

    def _cap_sector_weights(self, candidates: list[AllocationCandidate]) -> tuple[list[AllocationCandidate], list[str]]:
        sector_weights: dict[str, float] = {}
        capped: list[AllocationCandidate] = []
        blocked: list[str] = []
        for candidate in candidates:
            if candidate.stance != "buy":
                capped.append(candidate)
                continue
            sector = candidate.sector
            current = sector_weights.get(sector, 0.0)
            available = max(0.0, self.max_sector_weight - current)
            target_weight = min(candidate.target_weight, available)
            if target_weight <= 0:
                blocked.append(f"{candidate.symbol}: {sector} 섹터 한도 초과로 신규 편입 제외")
                capped.append(_replace_weight(candidate, 0.0, "hold"))
                continue
            sector_weights[sector] = current + target_weight
            capped.append(_replace_weight(candidate, target_weight, candidate.stance))
        return capped, blocked


def _replace_weight(candidate: AllocationCandidate, target_weight: float, stance: str) -> AllocationCandidate:
    return AllocationCandidate(
        symbol=candidate.symbol,
        name=candidate.name,
        market=candidate.market,
        sector=candidate.sector,
        weighted_score=candidate.weighted_score,
        confidence=candidate.confidence,
        target_weight=round(target_weight, 4),
        stance=stance,
        strategies=candidate.strategies,
        reasons=candidate.reasons,
    )
