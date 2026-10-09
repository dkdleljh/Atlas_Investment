from __future__ import annotations

import math
from dataclasses import dataclass

from atlas_investment.models import Candle
from atlas_investment.portfolio.strategy_allocation import AllocationCandidate


@dataclass(frozen=True)
class OptimizedPosition:
    symbol: str
    stance: str
    raw_weight: float
    optimized_weight: float
    annual_volatility_pct: float
    capacity_notional: float
    notes: list[str]


@dataclass(frozen=True)
class PortfolioOptimizationReport:
    status: str
    method: str
    target_volatility_pct: float
    realized_volatility_pct: float
    gross_exposure: float
    positions: list[OptimizedPosition]
    warnings: list[str]


class PortfolioOptimizer:
    """Production-style portfolio sizing layer for paper/live promotion."""

    def optimize(
        self,
        candidates: list[AllocationCandidate],
        candles_by_symbol: dict[str, list[Candle]],
        method: str = "risk_parity",
        target_volatility_pct: float = 12.0,
        max_position_weight: float = 0.08,
        max_gross_exposure: float = 1.0,
        max_adv_participation: float = 0.05,
    ) -> PortfolioOptimizationReport:
        method = method.lower()
        buy_candidates = [candidate for candidate in candidates if candidate.stance == "buy" and candidate.target_weight > 0]
        if not buy_candidates:
            return PortfolioOptimizationReport("blocked", method, target_volatility_pct, 0.0, 0.0, [], ["매수 후보가 없습니다."])
        if method not in {"risk_parity", "inverse_vol", "equal_weight", "vol_target"}:
            return PortfolioOptimizationReport("blocked", method, target_volatility_pct, 0.0, 0.0, [], [f"지원하지 않는 최적화 방식입니다: {method}"])

        risk_inputs = {candidate.symbol: _risk_input(candles_by_symbol.get(candidate.symbol, [])) for candidate in buy_candidates}
        base_weights = self._base_weights(buy_candidates, risk_inputs, method, max_position_weight)
        realized_vol = _portfolio_volatility_pct(base_weights, risk_inputs)
        scale = 1.0
        if method in {"risk_parity", "inverse_vol", "vol_target"} and realized_vol > 0:
            scale = min(1.0, target_volatility_pct / realized_vol)
        scaled = {symbol: weight * scale for symbol, weight in base_weights.items()}
        gross = sum(scaled.values())
        if gross > max_gross_exposure and gross > 0:
            scaled = {symbol: weight / gross * max_gross_exposure for symbol, weight in scaled.items()}
            gross = max_gross_exposure

        positions: list[OptimizedPosition] = []
        warnings: list[str] = []
        for candidate in buy_candidates:
            risk = risk_inputs[candidate.symbol]
            adv = risk["adv"]
            capacity = adv * max_adv_participation
            notes = []
            if risk["vol"] <= 0:
                notes.append("변동성 계산에 충분한 가격 이력이 없어 보수적으로 낮은 비중을 적용했습니다.")
            if capacity <= 0:
                notes.append("ADV 기반 capacity를 계산할 수 없습니다.")
            positions.append(
                OptimizedPosition(
                    symbol=candidate.symbol,
                    stance=candidate.stance,
                    raw_weight=round(candidate.target_weight, 6),
                    optimized_weight=round(scaled.get(candidate.symbol, 0.0), 6),
                    annual_volatility_pct=round(risk["vol"] * 100, 4),
                    capacity_notional=round(capacity, 2),
                    notes=notes,
                )
            )
        if not any(position.optimized_weight > 0 for position in positions):
            warnings.append("최적화 후 모든 비중이 0입니다.")
        if scale < 1:
            warnings.append(f"목표 변동성 {target_volatility_pct:.2f}%에 맞추기 위해 총 노출을 {scale:.2%}로 축소했습니다.")
        realized_after = _portfolio_volatility_pct({position.symbol: position.optimized_weight for position in positions}, risk_inputs)
        return PortfolioOptimizationReport(
            "ok" if any(position.optimized_weight > 0 for position in positions) else "blocked",
            method,
            target_volatility_pct,
            round(realized_after, 4),
            round(sum(position.optimized_weight for position in positions), 6),
            positions,
            warnings,
        )

    @staticmethod
    def _base_weights(
        candidates: list[AllocationCandidate],
        risk_inputs: dict[str, dict[str, float]],
        method: str,
        max_position_weight: float,
    ) -> dict[str, float]:
        if method == "equal_weight":
            weight = min(max_position_weight, 1 / len(candidates))
            return {candidate.symbol: weight for candidate in candidates}
        scores: dict[str, float] = {}
        for candidate in candidates:
            vol = max(risk_inputs[candidate.symbol]["vol"], 0.01)
            inverse_vol = 1 / vol
            score = inverse_vol
            if method == "risk_parity":
                score *= max(candidate.confidence, 0.1) * max(candidate.weighted_score, 1) / 100
            elif method == "vol_target":
                score = candidate.target_weight / vol
            scores[candidate.symbol] = max(score, 0.0)
        total = sum(scores.values())
        if total <= 0:
            return {candidate.symbol: 0.0 for candidate in candidates}
        return {symbol: min(max_position_weight, score / total) for symbol, score in scores.items()}


def _risk_input(candles: list[Candle]) -> dict[str, float]:
    returns = []
    for previous, current in zip(candles, candles[1:]):
        if previous.close > 0:
            returns.append(current.close / previous.close - 1)
    vol = _stddev(returns) * math.sqrt(252) if len(returns) >= 2 else 0.0
    adv = 0.0
    if candles:
        recent = candles[-20:]
        adv = sum(candle.close * candle.volume for candle in recent) / len(recent)
    return {"vol": vol, "adv": adv}


def _portfolio_volatility_pct(weights: dict[str, float], risk_inputs: dict[str, dict[str, float]]) -> float:
    variance = 0.0
    for symbol, weight in weights.items():
        variance += (weight * risk_inputs.get(symbol, {}).get("vol", 0.0)) ** 2
    return math.sqrt(variance) * 100


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    return math.sqrt(max(variance, 0.0))
