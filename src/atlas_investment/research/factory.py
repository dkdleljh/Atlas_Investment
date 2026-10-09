from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import Asset, Candle


@dataclass(frozen=True)
class FactorFeature:
    name: str
    value: float
    direction: str


@dataclass(frozen=True)
class ResearchFactoryReport:
    symbol: str
    status: str
    features: list[FactorFeature]
    alpha_score: float
    promotion_notes: list[str]


class ResearchFactory:
    """Builds repeatable factor features and a promotion-ready summary."""

    def build(self, asset: Asset, candles: list[Candle]) -> ResearchFactoryReport:
        if len(candles) < 130:
            return ResearchFactoryReport(asset.symbol, "blocked", [], 0.0, ["feature 생성에 필요한 이력이 부족합니다."])
        closes = [candle.close for candle in candles]
        ret_20 = closes[-1] / closes[-21] - 1
        ret_60 = closes[-1] / closes[-61] - 1
        ret_120 = closes[-1] / closes[-121] - 1
        volatility = _realized_volatility(closes[-60:])
        volume_ratio = candles[-1].volume / max(sum(candle.volume for candle in candles[-21:-1]) / 20, 1)
        quality = float(asset.metadata.get("quality_score", 0.5))
        value = float(asset.metadata.get("value_score", 0.5))
        features = [
            FactorFeature("momentum_20", round(ret_20, 6), "higher"),
            FactorFeature("momentum_60", round(ret_60, 6), "higher"),
            FactorFeature("momentum_120", round(ret_120, 6), "higher"),
            FactorFeature("realized_volatility_60", round(volatility, 6), "lower"),
            FactorFeature("volume_ratio_20", round(volume_ratio, 6), "context"),
            FactorFeature("quality_score", round(quality, 6), "higher"),
            FactorFeature("value_score", round(value, 6), "higher"),
        ]
        alpha_score = (
            _clip(0.5 + ret_120 * 1.2 + ret_60 * 0.7 + ret_20 * 0.3)
            * 0.35
            + _clip(1.0 - volatility / 0.05) * 0.20
            + quality * 0.25
            + value * 0.20
        )
        notes = ["feature hash와 validation report를 함께 저장해야 승격 근거로 사용할 수 있습니다."]
        if alpha_score < 0.45:
            notes.append("alpha score가 낮아 후보 전략으로만 유지합니다.")
        return ResearchFactoryReport(asset.symbol, "ok", features, round(alpha_score, 6), notes)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, value))


def _realized_volatility(closes: list[float]) -> float:
    returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes)) if closes[index - 1] > 0]
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    return (sum((value - mean) ** 2 for value in returns) / len(returns)) ** 0.5
