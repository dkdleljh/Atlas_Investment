from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EtfCandidate:
    symbol: str
    name: str
    exposure_group: str
    currency: str = "KRW"
    hedged: bool = False
    annual_expense_rate: float = 0.0
    other_expense_rate: float = 0.0
    tracking_error_rate: float = 0.0
    estimated_spread_rate: float = 0.0
    trade_fee_rate: float = 0.00015
    sell_tax_rate: float = 0.0
    average_daily_value_krw: float = 0.0
    discount_premium_rate: float = 0.0
    notes: list[str] | None = None

    @property
    def annual_total_cost_rate(self) -> float:
        return self.annual_expense_rate + self.other_expense_rate + self.tracking_error_rate


@dataclass(frozen=True)
class EtfCostScore:
    candidate: EtfCandidate
    investment_amount_krw: float
    holding_days: int
    annual_holding_cost_krw: float
    prorated_holding_cost_krw: float
    round_trip_trade_cost_krw: float
    liquidity_penalty_krw: float
    discount_premium_penalty_krw: float
    total_estimated_cost_krw: float
    total_estimated_cost_rate: float
    reasons: list[str]


@dataclass(frozen=True)
class EtfSwitchAnalysis:
    current_symbol: str | None
    recommended_symbol: str
    should_switch: bool
    current_cost_krw: float | None
    recommended_cost_krw: float
    estimated_savings_krw: float | None
    switch_cost_krw: float | None
    break_even_days: float | None
    reasons: list[str]


@dataclass(frozen=True)
class EtfOptimizerReport:
    exposure_group: str
    investment_amount_krw: float
    holding_days: int
    status: str
    recommendation: EtfCostScore | None
    rankings: list[EtfCostScore]
    switch_analysis: EtfSwitchAnalysis | None
    warnings: list[str]


class EtfCostOptimizer:
    """Compare ETFs that provide the same exposure and choose the lowest real cost route."""

    def __init__(self, min_liquidity_krw: float = 500_000_000, switch_safety_margin_rate: float = 0.0005) -> None:
        self.min_liquidity_krw = min_liquidity_krw
        self.switch_safety_margin_rate = switch_safety_margin_rate

    def load_candidates(self, path: Path) -> list[EtfCandidate]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = payload["candidates"] if isinstance(payload, dict) and "candidates" in payload else payload
        return [EtfCandidate(**item) for item in items]

    def optimize(
        self,
        candidates: list[EtfCandidate],
        exposure_group: str,
        investment_amount_krw: float,
        holding_days: int,
        current_symbol: str | None = None,
    ) -> EtfOptimizerReport:
        group_candidates = [candidate for candidate in candidates if candidate.exposure_group == exposure_group]
        warnings: list[str] = []
        if not group_candidates:
            return EtfOptimizerReport(exposure_group, investment_amount_krw, holding_days, "blocked", None, [], None, [f"{exposure_group} 후보 ETF가 없습니다."])

        if holding_days <= 0:
            warnings.append("holding_days가 0 이하라 1일로 보정했습니다.")
            holding_days = 1
        if investment_amount_krw <= 0:
            return EtfOptimizerReport(exposure_group, investment_amount_krw, holding_days, "blocked", None, [], None, ["투자금액은 0보다 커야 합니다."])

        rankings = sorted(
            [self.score(candidate, investment_amount_krw, holding_days) for candidate in group_candidates],
            key=lambda score: score.total_estimated_cost_krw,
        )
        recommendation = rankings[0]
        switch_analysis = self._analyze_switch(rankings, current_symbol, investment_amount_krw, holding_days)
        status = "ok" if not warnings else "degraded"
        return EtfOptimizerReport(exposure_group, investment_amount_krw, holding_days, status, recommendation, rankings, switch_analysis, warnings)

    def score(self, candidate: EtfCandidate, investment_amount_krw: float, holding_days: int) -> EtfCostScore:
        annual_holding_cost = investment_amount_krw * candidate.annual_total_cost_rate
        prorated_holding_cost = annual_holding_cost * holding_days / 365
        round_trip_trade_cost = investment_amount_krw * (
            candidate.trade_fee_rate * 2 + candidate.estimated_spread_rate * 2 + candidate.sell_tax_rate
        )
        liquidity_penalty = self._liquidity_penalty(candidate, investment_amount_krw)
        discount_premium_penalty = investment_amount_krw * abs(candidate.discount_premium_rate)
        total = prorated_holding_cost + round_trip_trade_cost + liquidity_penalty + discount_premium_penalty
        reasons = [
            f"연간 총보유비용률 {candidate.annual_total_cost_rate:.4%}",
            f"{holding_days}일 보유비용 {prorated_holding_cost:,.0f}원",
            f"왕복 예상 거래비용 {round_trip_trade_cost:,.0f}원",
        ]
        if liquidity_penalty > 0:
            reasons.append(f"거래대금 부족 패널티 {liquidity_penalty:,.0f}원")
        if discount_premium_penalty > 0:
            reasons.append(f"괴리율/프리미엄 패널티 {discount_premium_penalty:,.0f}원")
        if candidate.notes:
            reasons.extend(candidate.notes)
        return EtfCostScore(
            candidate=candidate,
            investment_amount_krw=investment_amount_krw,
            holding_days=holding_days,
            annual_holding_cost_krw=annual_holding_cost,
            prorated_holding_cost_krw=prorated_holding_cost,
            round_trip_trade_cost_krw=round_trip_trade_cost,
            liquidity_penalty_krw=liquidity_penalty,
            discount_premium_penalty_krw=discount_premium_penalty,
            total_estimated_cost_krw=total,
            total_estimated_cost_rate=total / investment_amount_krw,
            reasons=reasons,
        )

    def _analyze_switch(
        self,
        rankings: list[EtfCostScore],
        current_symbol: str | None,
        investment_amount_krw: float,
        holding_days: int,
    ) -> EtfSwitchAnalysis | None:
        if current_symbol is None:
            return None
        current = next((score for score in rankings if score.candidate.symbol == current_symbol), None)
        recommended = rankings[0]
        if current is None:
            return EtfSwitchAnalysis(
                current_symbol=current_symbol,
                recommended_symbol=recommended.candidate.symbol,
                should_switch=False,
                current_cost_krw=None,
                recommended_cost_krw=recommended.total_estimated_cost_krw,
                estimated_savings_krw=None,
                switch_cost_krw=None,
                break_even_days=None,
                reasons=[f"현재 보유 ETF {current_symbol}가 {recommended.candidate.exposure_group} 후보 목록에 없습니다."],
            )

        savings = current.total_estimated_cost_krw - recommended.total_estimated_cost_krw
        switch_cost = investment_amount_krw * (
            current.candidate.trade_fee_rate
            + current.candidate.estimated_spread_rate
            + current.candidate.sell_tax_rate
            + recommended.candidate.trade_fee_rate
            + recommended.candidate.estimated_spread_rate
            + self.switch_safety_margin_rate
        )
        daily_savings = max((current.annual_holding_cost_krw - recommended.annual_holding_cost_krw) / 365, 0)
        break_even_days = None if daily_savings <= 0 else switch_cost / daily_savings
        should_switch = recommended.candidate.symbol != current.candidate.symbol and savings > switch_cost
        reasons = [
            f"현재 후보 예상비용 {current.total_estimated_cost_krw:,.0f}원",
            f"추천 후보 예상비용 {recommended.total_estimated_cost_krw:,.0f}원",
            f"교체 예상비용+안전마진 {switch_cost:,.0f}원",
        ]
        if should_switch:
            reasons.append("예상 절감액이 교체 비용보다 커서 교체 후보입니다.")
        elif recommended.candidate.symbol == current.candidate.symbol:
            reasons.append("현재 보유 ETF가 이미 최저 실질비용 후보입니다.")
        else:
            reasons.append("비용 차이가 교체 비용을 넘지 않아 유지가 유리합니다.")
        return EtfSwitchAnalysis(
            current_symbol=current_symbol,
            recommended_symbol=recommended.candidate.symbol,
            should_switch=should_switch,
            current_cost_krw=current.total_estimated_cost_krw,
            recommended_cost_krw=recommended.total_estimated_cost_krw,
            estimated_savings_krw=savings,
            switch_cost_krw=switch_cost,
            break_even_days=break_even_days,
            reasons=reasons,
        )

    def _liquidity_penalty(self, candidate: EtfCandidate, investment_amount_krw: float) -> float:
        if candidate.average_daily_value_krw <= 0:
            return investment_amount_krw * 0.001
        if candidate.average_daily_value_krw >= self.min_liquidity_krw:
            return 0.0
        shortfall_ratio = (self.min_liquidity_krw - candidate.average_daily_value_krw) / self.min_liquidity_krw
        return investment_amount_krw * shortfall_ratio * 0.001


def default_etf_equivalence_payload() -> dict[str, Any]:
    return {
        "schema": "atlas_investment.etf_equivalence.v1",
        "data_note": "Sample values for local optimization smoke tests. Refresh expense/liquidity figures before live investment decisions.",
        "candidates": [
            {
                "symbol": "379810",
                "name": "KODEX 미국나스닥100TR",
                "exposure_group": "NASDAQ100_KR_UNHEDGED",
                "annual_expense_rate": 0.0005,
                "other_expense_rate": 0.0006,
                "tracking_error_rate": 0.0004,
                "estimated_spread_rate": 0.0007,
                "trade_fee_rate": 0.00015,
                "average_daily_value_krw": 4_000_000_000,
                "discount_premium_rate": 0.0002,
                "notes": ["샘플 값입니다. 실제 보수/거래대금은 운용사·거래소 데이터로 갱신해야 합니다."],
            },
            {
                "symbol": "133690",
                "name": "TIGER 미국나스닥100",
                "exposure_group": "NASDAQ100_KR_UNHEDGED",
                "annual_expense_rate": 0.0007,
                "other_expense_rate": 0.0005,
                "tracking_error_rate": 0.0003,
                "estimated_spread_rate": 0.0005,
                "trade_fee_rate": 0.00015,
                "average_daily_value_krw": 9_000_000_000,
                "discount_premium_rate": 0.0001,
                "notes": ["거래대금과 스프레드가 좋은 후보로 가정한 샘플입니다."],
            },
            {
                "symbol": "367380",
                "name": "ACE 미국나스닥100",
                "exposure_group": "NASDAQ100_KR_UNHEDGED",
                "annual_expense_rate": 0.0004,
                "other_expense_rate": 0.0004,
                "tracking_error_rate": 0.0005,
                "estimated_spread_rate": 0.0009,
                "trade_fee_rate": 0.00015,
                "average_daily_value_krw": 1_200_000_000,
                "discount_premium_rate": 0.0002,
                "notes": ["보유비용은 낮지만 스프레드/유동성도 함께 확인해야 하는 샘플입니다."],
            },
            {
                "symbol": "069500",
                "name": "KODEX 200",
                "exposure_group": "KOSPI200_KR",
                "annual_expense_rate": 0.00015,
                "other_expense_rate": 0.0002,
                "tracking_error_rate": 0.0002,
                "estimated_spread_rate": 0.0002,
                "trade_fee_rate": 0.00015,
                "average_daily_value_krw": 20_000_000_000,
                "discount_premium_rate": 0.00005,
            },
        ],
    }


def ensure_default_etf_config(path: Path) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default_etf_equivalence_payload(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
