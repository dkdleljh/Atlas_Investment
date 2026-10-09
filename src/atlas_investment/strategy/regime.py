from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import Candle
from atlas_investment.technical.indicators import sma


@dataclass(frozen=True)
class MarketRegime:
    status: str
    trend: str
    volatility: str
    exposure_multiplier: float
    strategy_weight_multipliers: dict[str, float]
    reasons: list[str]


class MarketRegimeDetector:
    """Classifies the current market regime from benchmark daily candles."""

    def detect(self, candles: list[Candle]) -> MarketRegime:
        if len(candles) < 80:
            return MarketRegime(
                "insufficient_data",
                "unknown",
                "unknown",
                0.35,
                {"low_vol_defensive": 1.2, "all_weather_risk_parity": 1.2, "macro_regime_allocation": 1.1},
                ["시장 국면 판단에 필요한 benchmark 이력이 부족합니다."],
            )

        closes = [candle.close for candle in candles]
        ma50 = sma(closes, 50)[-1]
        ma200 = sma(closes, 200)[-1] if len(closes) >= 200 else sma(closes, 80)[-1]
        vol20 = _realized_volatility(closes, 20)
        vol60 = _realized_volatility(closes, 60)
        last = closes[-1]
        trend = "sideways"
        reasons: list[str] = []

        if ma50 is not None and ma200 is not None and last > ma50 > ma200:
            trend = "bull"
            reasons.append("종가가 단기/장기 추세선 위에 있어 상승장 성격입니다.")
        elif ma50 is not None and ma200 is not None and last < ma50 < ma200:
            trend = "bear"
            reasons.append("종가가 단기/장기 추세선 아래에 있어 하락장 성격입니다.")
        else:
            reasons.append("추세선 배열이 명확하지 않아 횡보/전환 국면입니다.")

        volatility = "normal"
        if vol20 > max(0.028, vol60 * 1.45):
            volatility = "high"
            reasons.append(f"20일 변동성 {vol20:.2%}가 높아 리스크 축소가 필요합니다.")
        elif vol20 < 0.014:
            volatility = "low"
            reasons.append(f"20일 변동성 {vol20:.2%}가 낮아 안정 국면입니다.")

        exposure = 1.0
        multipliers = {
            "multifactor_qvm": 1.0,
            "time_series_momentum": 1.0,
            "cross_sectional_momentum": 1.0,
            "low_vol_defensive": 1.0,
            "all_weather_risk_parity": 1.0,
            "macro_regime_allocation": 1.0,
            "cta_diversified_trend": 1.0,
            "ml_alpha_score": 1.0,
            "shareholder_yield_carry": 1.0,
            "sector_regime_rotation": 1.0,
            "earnings_revision_event": 1.0,
        }
        if trend == "bull":
            multipliers.update({"cross_sectional_momentum": 1.2, "time_series_momentum": 1.15, "cta_diversified_trend": 1.15, "ml_alpha_score": 1.1, "macro_regime_allocation": 1.1, "sector_regime_rotation": 1.1})
        elif trend == "bear":
            exposure = 0.45
            multipliers.update({"low_vol_defensive": 1.35, "all_weather_risk_parity": 1.25, "macro_regime_allocation": 1.25, "shareholder_yield_carry": 1.15, "cross_sectional_momentum": 0.65, "ml_alpha_score": 0.8})
        else:
            exposure = 0.75
            multipliers.update({"low_vol_defensive": 1.15, "all_weather_risk_parity": 1.15, "shareholder_yield_carry": 1.1})
        if volatility == "high":
            exposure *= 0.65
            multipliers.update({
                "low_vol_defensive": multipliers.get("low_vol_defensive", 1.0) * 1.25,
                "all_weather_risk_parity": multipliers.get("all_weather_risk_parity", 1.0) * 1.2,
                "macro_regime_allocation": multipliers.get("macro_regime_allocation", 1.0) * 1.15,
                "volatility_breakout": 0.7,
            })
        return MarketRegime(
            "ok",
            trend,
            volatility,
            round(max(0.15, min(exposure, 1.0)), 4),
            {key: round(value, 4) for key, value in multipliers.items()},
            reasons,
        )


def _realized_volatility(closes: list[float], lookback: int) -> float:
    if len(closes) <= lookback:
        return 0.0
    returns = [closes[index] / closes[index - 1] - 1 for index in range(len(closes) - lookback, len(closes)) if closes[index - 1] > 0]
    if not returns:
        return 0.0
    mean = sum(returns) / len(returns)
    return (sum((value - mean) ** 2 for value in returns) / len(returns)) ** 0.5
