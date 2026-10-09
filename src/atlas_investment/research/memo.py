from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import Signal


@dataclass(frozen=True)
class InvestmentMemo:
    symbol: str
    strategy: str
    decision: str
    sections: dict[str, str]
    required_checks: list[str]


class InvestmentMemoGenerator:
    def generate(self, signal: Signal) -> InvestmentMemo:
        asset = signal.asset
        decision = "candidate" if signal.stance == "buy" and signal.score >= 68 else signal.stance
        sections = {
            "pm": f"{asset.symbol} {signal.strategy} 신호는 {signal.score}점, 판단은 {decision}입니다.",
            "quant": "백테스트, 워크포워드, 거래비용 민감도 검증 후 PAPER 승격 여부를 판단합니다.",
            "risk": "미수/신용은 금지이며 단일 종목, 섹터, 레버리지/인버스, 통화 노출 한도를 확인해야 합니다.",
            "execution": "공식 주문 API 전까지 DRY_RUN/PAPER 검증만 허용합니다.",
            "compliance": "투자 판단 근거, 데이터 소스, 모델 변경 이력을 감사 가능하게 남겨야 합니다.",
        }
        return InvestmentMemo(
            symbol=asset.symbol,
            strategy=signal.strategy,
            decision=decision,
            sections=sections,
            required_checks=["data_quality", "strategy_lab", "fund_risk", "execution_route", "governance_record"],
        )
