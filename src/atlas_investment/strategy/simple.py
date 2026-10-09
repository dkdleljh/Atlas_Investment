from __future__ import annotations

from atlas_investment.models import Asset, PortfolioSnapshot, Quote, Signal


class SimpleSignalEngine:
    """Small deterministic signal engine for first-version paper trading."""

    def generate(self, universe: list[Asset], quotes: dict[str, Quote], portfolio: PortfolioSnapshot) -> list[Signal]:
        signals: list[Signal] = []
        for asset in universe:
            quote = quotes[asset.symbol]
            momentum = 0.0
            if quote.previous_close:
                momentum = (quote.price / quote.previous_close) - 1

            score = 55
            reasons = ["초기 버전의 샘플 전략 점수입니다."]
            horizon_days = 20
            strategy = "quality"

            if momentum > 0.005:
                score += 18
                reasons.append("단기 모멘텀이 양호합니다.")
                strategy = "momentum"
                horizon_days = 15
            if asset.kind.value == "etf":
                score += 4
                reasons.append("ETF는 분산 효과가 있어 기본 가점을 줍니다.")
            if asset.is_leveraged or asset.is_inverse:
                score -= 8
                reasons.append("레버리지/인버스 상품은 허용하되 위험 가중치를 반영합니다.")
                strategy = "inverse_hedge" if asset.is_inverse else "leveraged_momentum"
                horizon_days = 5
            if portfolio.position_weight(asset.symbol) > 0:
                score -= 10
                reasons.append("이미 보유 중인 종목은 추가 매수 점수를 낮춥니다.")

            stance = "buy" if score >= 68 else "hold" if score >= 40 else "sell"
            signals.append(Signal(asset=asset, score=max(0, min(score, 100)), stance=stance, reasons=reasons, horizon_days=horizon_days, strategy=strategy))
        return signals

