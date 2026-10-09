from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FxOverlayDecision:
    pair: str
    stance: str
    target_usd_exposure: float
    reason: str


class FxOverlayEngine:
    """Simple currency overlay placeholder for USD exposure control."""

    def decide(self, usdkrw: float, usdkrw_60d_average: float, current_usd_exposure: float) -> FxOverlayDecision:
        if usdkrw > usdkrw_60d_average * 1.04:
            return FxOverlayDecision("USD/KRW", "reduce_usd_buying", max(0.2, current_usd_exposure - 0.1), "달러가 60일 평균 대비 높아 미국장 신규 매수를 줄입니다.")
        if usdkrw < usdkrw_60d_average * 0.96:
            return FxOverlayDecision("USD/KRW", "allow_usd_buying", min(0.7, current_usd_exposure + 0.1), "달러가 60일 평균 대비 낮아 미국장 매수 여력을 늘립니다.")
        return FxOverlayDecision("USD/KRW", "neutral", current_usd_exposure, "환율이 중립 구간입니다.")
