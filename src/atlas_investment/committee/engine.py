from __future__ import annotations

from atlas_investment.config import RiskPolicy
from atlas_investment.models import CommitteeReport, Signal


class InvestmentCommittee:
    def review(self, signal: Signal, policy: RiskPolicy) -> CommitteeReport:
        role_opinions = {
            "Macro": "시장 국면은 별도 거시 데이터 연결 전까지 중립으로 둡니다.",
            "Company": "개별 기업 재무 데이터 연결 전까지 가격/유동성 기반으로 판단합니다.",
            "PortfolioManager": "목표 비중과 기존 보유 비중을 함께 확인해야 합니다.",
            "ExecutionDesk": "초기 버전은 지정가 중심의 보수적 주문 실행을 선호합니다.",
            "Quant": f"{signal.strategy} 전략 점수 {signal.score}점을 부여했습니다.",
            "RiskManager": "미수/신용은 절대 금지이며 레버리지/인버스는 별도 한도를 적용합니다.",
            "Compliance": "토스 공식 API 공개 전까지 실주문은 비활성화합니다.",
        }
        risks = []
        if signal.asset.is_leveraged or signal.asset.is_inverse:
            risks.append("레버리지/인버스 상품은 변동성이 높아 별도 비중 제한이 필요합니다.")
        if signal.score < policy.min_score_to_buy:
            risks.append("매수 기준 점수에 도달하지 못했습니다.")

        if signal.score >= policy.min_score_to_buy:
            decision = "buy"
        elif signal.score <= policy.min_score_to_sell:
            decision = "sell"
        else:
            decision = "hold"

        return CommitteeReport(
            asset=signal.asset,
            score=signal.score,
            decision=decision,
            horizon_days=signal.horizon_days,
            role_opinions=role_opinions,
            risks=risks,
        )

