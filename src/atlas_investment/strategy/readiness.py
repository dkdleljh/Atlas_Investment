from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.strategy.lab import StrategyLabResult


REALTIME_REQUIRED = {
    "scalping_simulation",
    "liquidity_market_making_simulation",
}

SHORTING_REQUIRED = {
    "equity_long_short_quality",
}


@dataclass(frozen=True)
class StrategyPromotionDecision:
    strategy: str
    status: str
    approved_symbols: int
    total_symbols: int
    reasons: list[str]
    warnings: list[str]


class StrategyPromotionGate:
    def evaluate(
        self,
        strategy: str,
        results: list[StrategyLabResult],
        realtime_data_ready: bool = False,
        shorting_supported: bool = False,
        min_approved_symbols: int = 2,
        max_drawdown_floor_pct: float = -18.0,
    ) -> StrategyPromotionDecision:
        matching = [result for result in results if result.strategy == strategy]
        if not matching:
            return StrategyPromotionDecision(strategy, "blocked", 0, 0, ["전략 연구소 결과가 없습니다."], [])
        reasons: list[str] = []
        warnings: list[str] = []
        approved = [result for result in matching if result.approved_for_paper and result.max_drawdown_pct >= max_drawdown_floor_pct]
        if len(approved) < min_approved_symbols:
            reasons.append(f"PAPER 후보가 부족합니다: {len(approved)}/{min_approved_symbols}.")
        if strategy in REALTIME_REQUIRED and not realtime_data_ready:
            reasons.append("실시간 호가/체결/미체결 정정·취소 검증 전까지 실거래 승격 금지 전략입니다.")
        if strategy in SHORTING_REQUIRED and not shorting_supported:
            reasons.append("공매도/대차/롱숏 브로커 지원과 규제 확인 전까지 숏 레그는 금지입니다.")
        low_trade_symbols = [result.symbol for result in matching if result.trade_count < 2]
        if low_trade_symbols:
            message = f"거래 횟수가 낮아 제외된 표본이 있습니다: {', '.join(low_trade_symbols[:8])}."
            if len(approved) < min_approved_symbols:
                reasons.append("일부 종목의 거래 횟수가 너무 적어 샘플 신뢰도가 낮습니다.")
            else:
                warnings.append(message)
        status = "approved_for_paper" if not reasons else "blocked"
        return StrategyPromotionDecision(strategy, status, len(approved), len(matching), reasons, warnings)
