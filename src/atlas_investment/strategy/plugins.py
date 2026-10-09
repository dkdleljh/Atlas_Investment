from __future__ import annotations

from atlas_investment.models import Asset, Candle, Signal
from atlas_investment.strategy.base import StrategyPlugin
from atlas_investment.technical.indicators import atr, rsi, sma


def _returns(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback or closes[-lookback - 1] <= 0:
        return None
    return closes[-1] / closes[-lookback - 1] - 1


def _realized_volatility(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    daily_returns = [
        closes[index] / closes[index - 1] - 1
        for index in range(len(closes) - lookback, len(closes))
        if closes[index - 1] > 0
    ]
    if not daily_returns:
        return None
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((value - mean) ** 2 for value in daily_returns) / len(daily_returns)
    return variance**0.5


def _metadata_float(asset: Asset, key: str, default: float) -> float:
    try:
        return float(asset.metadata.get(key, default))
    except (TypeError, ValueError):
        return default


class MovingAverageCrossStrategy(StrategyPlugin):
    name = "moving_average_cross"
    description = "20일/60일 이동평균 교차 기반 중기 추세 전략"
    default_horizon_days = 30

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        closes = [candle.close for candle in candles[: index + 1]]
        short = sma(closes, 20)[-1]
        long = sma(closes, 60)[-1]
        if short is None or long is None:
            return None
        score = 50
        reasons = []
        if short > long:
            spread = (short / long) - 1
            score = min(90, 65 + int(spread * 300))
            stance = "buy"
            reasons.append("20일 이동평균이 60일 이동평균 위에 있어 중기 추세가 우호적입니다.")
        else:
            spread = (short / long) - 1
            score = max(20, 45 + int(spread * 300))
            stance = "sell" if score < 35 else "hold"
            reasons.append("20일 이동평균이 60일 이동평균 아래에 있어 추세 확인이 필요합니다.")
        return Signal(asset, score, stance, reasons, self.default_horizon_days, self.name, confidence=0.58, target_weight=0.04, stop_loss_pct=-0.08, take_profit_pct=0.18)


class RsiMeanReversionStrategy(StrategyPlugin):
    name = "rsi_mean_reversion"
    description = "RSI 과매도/과열 기반 단기 평균회귀 전략"
    default_horizon_days = 7

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        closes = [candle.close for candle in candles[: index + 1]]
        current_rsi = rsi(closes, 14)[-1]
        if current_rsi is None:
            return None
        if current_rsi < 30:
            return Signal(asset, 72, "buy", [f"RSI {current_rsi:.1f}로 단기 과매도 구간입니다."], self.default_horizon_days, self.name, confidence=0.55, target_weight=0.025, stop_loss_pct=-0.04, take_profit_pct=0.08)
        if current_rsi > 72:
            return Signal(asset, 30, "sell", [f"RSI {current_rsi:.1f}로 단기 과열 구간입니다."], self.default_horizon_days, self.name, confidence=0.52, target_weight=0.0)
        return Signal(asset, 50, "hold", [f"RSI {current_rsi:.1f}로 중립 구간입니다."], self.default_horizon_days, self.name, confidence=0.4)


class BreakoutMomentumStrategy(StrategyPlugin):
    name = "breakout_momentum"
    description = "60일 신고가 돌파 기반 스윙 모멘텀 전략"
    default_horizon_days = 20

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 60:
            return None
        recent = candles[index - 60 : index]
        current = candles[index]
        prior_high = max(candle.high for candle in recent)
        if current.close > prior_high:
            return Signal(asset, 78, "buy", ["60일 고점을 종가로 돌파했습니다."], self.default_horizon_days, self.name, confidence=0.62, target_weight=0.035, stop_loss_pct=-0.07, take_profit_pct=0.16)
        if current.close < prior_high * 0.9:
            return Signal(asset, 38, "hold", ["60일 고점 대비 조정 구간입니다."], self.default_horizon_days, self.name, confidence=0.42)
        return Signal(asset, 55, "hold", ["돌파 조건을 기다리는 중입니다."], self.default_horizon_days, self.name, confidence=0.35)


class LongTermTrendStrategy(StrategyPlugin):
    name = "long_term_trend"
    description = "120일 장기 추세와 현금 보전 규칙을 함께 보는 장기 투자 전략"
    default_horizon_days = 180

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        closes = [candle.close for candle in candles[: index + 1]]
        long = sma(closes, 120)[-1]
        if long is None:
            return None
        current = closes[-1]
        if current > long * 1.08:
            return Signal(asset, 76, "buy", ["장기 이동평균 위에서 추세가 유지되고 있습니다."], self.default_horizon_days, self.name, confidence=0.64, target_weight=0.06, stop_loss_pct=-0.14, take_profit_pct=0.35)
        if current < long * 0.92:
            return Signal(asset, 34, "sell", ["장기 추세선 이탈로 비중 축소가 필요합니다."], self.default_horizon_days, self.name, confidence=0.6)
        return Signal(asset, 54, "hold", ["장기 추세 확인 구간입니다."], self.default_horizon_days, self.name, confidence=0.42)


class VolatilityBreakoutStrategy(StrategyPlugin):
    name = "volatility_breakout"
    description = "전일 변동폭 돌파를 활용하는 단타/데이 트레이딩 전략"
    default_horizon_days = 1

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 2:
            return None
        prev = candles[index - 1]
        current = candles[index]
        trigger = current.open + (prev.high - prev.low) * 0.55
        if current.close > trigger:
            return Signal(asset, 73, "buy", ["전일 변동폭 기준 돌파 가격을 상회했습니다."], self.default_horizon_days, self.name, confidence=0.52, target_weight=0.018, stop_loss_pct=-0.025, take_profit_pct=0.045)
        return Signal(asset, 48, "hold", ["변동성 돌파 조건 대기 중입니다."], self.default_horizon_days, self.name, confidence=0.32)


class SwingMomentumStrategy(StrategyPlugin):
    name = "swing_momentum"
    description = "20일 수익률과 60일 추세를 결합한 스윙 전략"
    default_horizon_days = 15

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 60:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        momentum_20 = closes[-1] / closes[-21] - 1
        trend_60 = sma(closes, 60)[-1]
        if trend_60 is None:
            return None
        if momentum_20 > 0.06 and closes[-1] > trend_60:
            return Signal(asset, 77, "buy", [f"20일 모멘텀이 {momentum_20:.1%}이고 60일 추세 위입니다."], self.default_horizon_days, self.name, confidence=0.58, target_weight=0.035, stop_loss_pct=-0.06, take_profit_pct=0.14)
        if momentum_20 < -0.08:
            return Signal(asset, 36, "sell", [f"20일 모멘텀이 {momentum_20:.1%}로 약합니다."], self.default_horizon_days, self.name, confidence=0.5)
        return Signal(asset, 51, "hold", ["스윙 진입 조건이 충분하지 않습니다."], self.default_horizon_days, self.name, confidence=0.34)


class ScalpingSimulationStrategy(StrategyPlugin):
    name = "scalping_simulation"
    description = "분봉/호가 API 전까지 일봉 범위로만 검증하는 스캘핑 시뮬레이션 전략"
    default_horizon_days = 1

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 15:
            return None
        current = candles[index]
        ranges = [(candle.high - candle.low) / candle.close for candle in candles[index - 14 : index] if candle.close > 0]
        avg_range = sum(ranges) / len(ranges)
        intraday_strength = (current.close - current.low) / max(current.high - current.low, 0.0001)
        if avg_range > 0.018 and intraday_strength > 0.72:
            return Signal(asset, 70, "buy", ["일중 강도와 평균 변동성이 스캘핑 후보 조건을 만족합니다."], self.default_horizon_days, self.name, confidence=0.38, target_weight=0.006, stop_loss_pct=-0.012, take_profit_pct=0.018)
        return Signal(asset, 45, "hold", ["실시간 호가 연결 전까지 스캘핑은 시뮬레이션 후보만 생성합니다."], self.default_horizon_days, self.name, confidence=0.25)


class EtfRebalanceStrategy(StrategyPlugin):
    name = "etf_rebalance"
    description = "ETF 장기 리밸런싱 후보를 찾는 전략"
    default_horizon_days = 90

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if asset.kind.value != "etf" or index < 80:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        ma80 = sma(closes, 80)[-1]
        if ma80 and closes[-1] > ma80:
            return Signal(asset, 71, "buy", ["ETF가 80일 추세 위에 있어 리밸런싱 편입 후보입니다."], self.default_horizon_days, self.name, confidence=0.54, target_weight=0.08, stop_loss_pct=-0.12, take_profit_pct=0.24)
        return Signal(asset, 46, "hold", ["ETF 리밸런싱 편입 대기 상태입니다."], self.default_horizon_days, self.name, confidence=0.36)


class FactorQualityStrategy(StrategyPlugin):
    name = "factor_quality"
    description = "퀄리티/모멘텀 메타데이터와 가격 추세를 결합하는 팩터 퀀트 전략"
    default_horizon_days = 45

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 60:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        trend = sma(closes, 60)[-1]
        factor_score = float(asset.metadata.get("quality_score", 0.55))
        if trend and closes[-1] > trend and factor_score >= 0.55:
            score = min(86, int(58 + factor_score * 25))
            return Signal(asset, score, "buy", ["퀄리티 팩터와 가격 추세가 동시에 우호적입니다."], self.default_horizon_days, self.name, confidence=0.57, target_weight=0.04, stop_loss_pct=-0.08, take_profit_pct=0.18)
        return Signal(asset, 49, "hold", ["팩터 또는 추세 확인이 더 필요합니다."], self.default_horizon_days, self.name, confidence=0.35)


class FxOverlaySignalStrategy(StrategyPlugin):
    name = "fx_overlay_signal"
    description = "USD/KRW 노출을 고려하는 외환 오버레이 신호 전략"
    default_horizon_days = 20

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 20:
            return None
        volatility = atr(candles[: index + 1], 14)[-1]
        if asset.currency == "USD":
            return Signal(asset, 58, "hold", ["달러 자산은 FX 오버레이 엔진의 환율 필터를 함께 통과해야 합니다."], self.default_horizon_days, self.name, confidence=0.44, target_weight=0.03)
        if volatility and volatility / candles[index].close < 0.035:
            return Signal(asset, 57, "hold", ["원화 자산 변동성이 안정적입니다."], self.default_horizon_days, self.name, confidence=0.4)
        return Signal(asset, 42, "hold", ["외환/변동성 조건 확인 구간입니다."], self.default_horizon_days, self.name, confidence=0.3)


class EventDisclosureStrategy(StrategyPlugin):
    name = "event_disclosure_watch"
    description = "공시/이벤트 데이터 연결 전까지 이벤트 감시 후보를 생성하는 전략"
    default_horizon_days = 10

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 30:
            return None
        current = candles[index]
        avg_volume = sum(candle.volume for candle in candles[index - 20 : index]) / 20
        if current.volume > avg_volume * 1.8 and current.close > current.open:
            return Signal(asset, 69, "buy", ["거래량 급증과 양봉이 동반되어 공시/이벤트 확인 후보입니다."], self.default_horizon_days, self.name, confidence=0.41, target_weight=0.018, stop_loss_pct=-0.05, take_profit_pct=0.1)
        return Signal(asset, 47, "hold", ["특이 거래량 이벤트를 감시 중입니다."], self.default_horizon_days, self.name, confidence=0.28)


class TimeSeriesMomentumStrategy(StrategyPlugin):
    name = "time_series_momentum"
    description = "12개월 추세 추종/CTA 스타일의 시계열 모멘텀 전략"
    default_horizon_days = 90

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 180:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        momentum_120 = _returns(closes, 120)
        momentum_20 = _returns(closes, 20)
        trend_100 = sma(closes, 100)[-1]
        volatility = _realized_volatility(closes, 60)
        if momentum_120 is None or momentum_20 is None or trend_100 is None or volatility is None:
            return None
        vol_adjustment = max(0.4, min(1.2, 0.018 / max(volatility, 0.0001)))
        target_weight = round(0.04 * vol_adjustment, 4)
        if momentum_120 > 0.08 and momentum_20 > -0.04 and closes[-1] > trend_100:
            score = min(84, 62 + int(momentum_120 * 80))
            return Signal(asset, score, "buy", [f"120일 추세 {momentum_120:.1%}, 단기 추세 방어, 변동성 조정 비중 {target_weight:.2%}입니다."], self.default_horizon_days, self.name, confidence=0.6, target_weight=target_weight, stop_loss_pct=-0.1, take_profit_pct=0.28)
        if momentum_120 < -0.08 or closes[-1] < trend_100 * 0.94:
            return Signal(asset, 32, "sell", ["중기 추세가 음수이거나 100일 추세를 크게 이탈했습니다."], self.default_horizon_days, self.name, confidence=0.57)
        return Signal(asset, 52, "hold", ["시계열 모멘텀 조건을 더 확인합니다."], self.default_horizon_days, self.name, confidence=0.36)


class CrossSectionalMomentumStrategy(StrategyPlugin):
    name = "cross_sectional_momentum"
    description = "종목 간 상대 강도를 이용하는 크로스섹션 모멘텀 전략"
    default_horizon_days = 45

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 90:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        momentum_60 = _returns(closes, 60)
        momentum_rank = float(asset.metadata.get("momentum_rank", 0.5))
        if momentum_60 is None:
            return None
        blended_rank = max(momentum_rank, min(1.0, max(0.0, 0.5 + momentum_60)))
        if blended_rank >= 0.72 and momentum_60 > 0.03:
            score = min(86, int(58 + blended_rank * 30))
            return Signal(asset, score, "buy", [f"상대 모멘텀 순위 {blended_rank:.0%}, 60일 수익률 {momentum_60:.1%}입니다."], self.default_horizon_days, self.name, confidence=0.56, target_weight=0.035, stop_loss_pct=-0.075, take_profit_pct=0.18)
        if blended_rank <= 0.25 and momentum_60 < -0.05:
            return Signal(asset, 31, "sell", [f"상대 모멘텀 하위권이고 60일 수익률 {momentum_60:.1%}입니다."], self.default_horizon_days, self.name, confidence=0.54)
        return Signal(asset, 49, "hold", ["상대 강도 우위가 충분하지 않습니다."], self.default_horizon_days, self.name, confidence=0.34)


class LowVolDefensiveStrategy(StrategyPlugin):
    name = "low_vol_defensive"
    description = "저변동성/방어주 스타일 프리미아 전략"
    default_horizon_days = 60

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 80:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        volatility = _realized_volatility(closes, 60)
        trend_80 = sma(closes, 80)[-1]
        dividend_yield = float(asset.metadata.get("dividend_yield", 0.015))
        if volatility is None or trend_80 is None:
            return None
        if volatility < 0.018 and closes[-1] >= trend_80 * 0.97:
            score = min(80, 62 + int(dividend_yield * 450))
            return Signal(asset, score, "buy", [f"60일 변동성 {volatility:.2%}, 방어적 추세 유지, 배당/품질 보조 점검 대상입니다."], self.default_horizon_days, self.name, confidence=0.55, target_weight=0.045, stop_loss_pct=-0.09, take_profit_pct=0.16)
        if volatility > 0.04 and closes[-1] < trend_80:
            return Signal(asset, 35, "sell", ["방어 전략 기준 대비 변동성이 높고 추세가 약합니다."], self.default_horizon_days, self.name, confidence=0.5)
        return Signal(asset, 50, "hold", ["저변동성 방어 조건을 더 확인합니다."], self.default_horizon_days, self.name, confidence=0.33)


class StatArbMeanReversionStrategy(StrategyPlugin):
    name = "stat_arb_mean_reversion"
    description = "페어/통계적 차익거래 전 단계의 z-score 평균회귀 후보 전략"
    default_horizon_days = 5

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 45:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        ma20 = sma(closes, 20)[-1]
        volatility = _realized_volatility(closes, 20)
        if ma20 is None or volatility is None or ma20 <= 0:
            return None
        zscore = float(asset.metadata.get("pair_zscore", (closes[-1] / ma20 - 1) / max(volatility, 0.0001)))
        if zscore <= -1.8:
            return Signal(asset, 73, "buy", [f"평균 대비 z-score {zscore:.2f}로 과매도 평균회귀 후보입니다."], self.default_horizon_days, self.name, confidence=0.5, target_weight=0.015, stop_loss_pct=-0.035, take_profit_pct=0.055)
        if zscore >= 1.8:
            return Signal(asset, 32, "sell", [f"평균 대비 z-score {zscore:.2f}로 과열 축소 후보입니다."], self.default_horizon_days, self.name, confidence=0.48)
        return Signal(asset, 48, "hold", [f"z-score {zscore:.2f}로 차익거래 진입 기준에는 부족합니다."], self.default_horizon_days, self.name, confidence=0.3)


class EquityLongShortQualityStrategy(StrategyPlugin):
    name = "equity_long_short_quality"
    description = "롱/숏 헤지펀드식 퀄리티-모멘텀 스프레드 후보 전략"
    default_horizon_days = 40

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 70:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        quality = float(asset.metadata.get("quality_score", 0.5))
        momentum_60 = _returns(closes, 60)
        if momentum_60 is None:
            return None
        composite = quality * 0.6 + min(1.0, max(0.0, 0.5 + momentum_60)) * 0.4
        if composite >= 0.68:
            return Signal(asset, min(85, int(58 + composite * 30)), "buy", [f"퀄리티/모멘텀 합성 점수 {composite:.2f}로 롱 바스켓 후보입니다."], self.default_horizon_days, self.name, confidence=0.56, target_weight=0.03, stop_loss_pct=-0.08, take_profit_pct=0.17)
        if composite <= 0.32:
            return Signal(asset, 28, "sell", [f"퀄리티/모멘텀 합성 점수 {composite:.2f}로 축소/숏 후보입니다. 실제 공매도는 브로커 지원 전까지 금지합니다."], self.default_horizon_days, self.name, confidence=0.52)
        return Signal(asset, 50, "hold", ["롱/숏 스프레드 후보 점수가 중립입니다."], self.default_horizon_days, self.name, confidence=0.32)


class LiquidityMarketMakingSimulationStrategy(StrategyPlugin):
    name = "liquidity_market_making_simulation"
    description = "호가/스프레드 데이터 전까지 유동성 공급 가능성만 보는 마켓메이킹 시뮬레이션"
    default_horizon_days = 1

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 20:
            return None
        current = candles[index]
        avg_volume = sum(candle.volume for candle in candles[index - 20 : index]) / 20
        turnover_stability = current.volume / max(avg_volume, 1)
        spread_proxy = (current.high - current.low) / max(current.close, 0.0001)
        if 0.8 <= turnover_stability <= 1.6 and 0.004 <= spread_proxy <= 0.025:
            return Signal(asset, 61, "hold", [f"거래량 안정도 {turnover_stability:.2f}, 스프레드 프록시 {spread_proxy:.2%}. 실시간 호가 전까지 마켓메이킹은 비주문 시뮬레이션입니다."], self.default_horizon_days, self.name, confidence=0.24, target_weight=0.0)
        return Signal(asset, 41, "hold", ["유동성 공급 후보 조건이 불충분하거나 호가 데이터가 없습니다."], self.default_horizon_days, self.name, confidence=0.18)


class MultiFactorQvmStrategy(StrategyPlugin):
    name = "multifactor_qvm"
    description = "Quality, Value, Momentum, Low Vol, Yield를 결합하는 멀티팩터 퀀트 전략"
    default_horizon_days = 60

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 120:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        momentum_60 = _returns(closes, 60)
        momentum_120 = _returns(closes, 120)
        volatility = _realized_volatility(closes, 60)
        trend = sma(closes, 80)[-1]
        if momentum_60 is None or momentum_120 is None or volatility is None or trend is None:
            return None
        quality = _metadata_float(asset, "quality_score", 0.55)
        value = _metadata_float(asset, "value_score", 0.5)
        yield_score = min(1.0, max(0.0, _metadata_float(asset, "dividend_yield", 0.018) / 0.06))
        momentum_score = min(1.0, max(0.0, 0.5 + momentum_120 * 1.4 + momentum_60 * 0.6))
        low_vol_score = min(1.0, max(0.0, 1.0 - volatility / 0.045))
        composite = quality * 0.28 + value * 0.22 + momentum_score * 0.25 + low_vol_score * 0.15 + yield_score * 0.10
        reasons = [
            f"QVM 합성점수 {composite:.2f}",
            f"품질 {quality:.2f}, 밸류 {value:.2f}, 모멘텀 {momentum_score:.2f}, 저변동성 {low_vol_score:.2f}, 주주환원 {yield_score:.2f}",
        ]
        if composite >= 0.64 and closes[-1] >= trend * 0.97:
            target_weight = round(0.035 + min(0.035, (composite - 0.64) * 0.12), 4)
            return Signal(asset, min(90, int(55 + composite * 42)), "buy", reasons, self.default_horizon_days, self.name, confidence=0.62, target_weight=target_weight, stop_loss_pct=-0.085, take_profit_pct=0.2)
        if composite <= 0.38 or closes[-1] < trend * 0.9:
            return Signal(asset, max(20, int(48 - (0.38 - composite) * 35)), "sell", reasons + ["멀티팩터 점수 또는 추세가 기준 이하입니다."], self.default_horizon_days, self.name, confidence=0.55)
        return Signal(asset, 52, "hold", reasons + ["멀티팩터 편입 기준까지는 추가 확인이 필요합니다."], self.default_horizon_days, self.name, confidence=0.38)


class ShareholderYieldCarryStrategy(StrategyPlugin):
    name = "shareholder_yield_carry"
    description = "배당, 자사주, 이익수익률을 결합하는 주식형 Carry/Yield 퀀트 전략"
    default_horizon_days = 120

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 90:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        trend = sma(closes, 90)[-1]
        if trend is None:
            return None
        dividend_yield = _metadata_float(asset, "dividend_yield", 0.018)
        buyback_yield = _metadata_float(asset, "buyback_yield", 0.005)
        earnings_yield = _metadata_float(asset, "earnings_yield", 0.045)
        payout_quality = _metadata_float(asset, "payout_quality", _metadata_float(asset, "quality_score", 0.55))
        carry_score = min(1.0, max(0.0, (dividend_yield + buyback_yield + earnings_yield) / 0.12)) * 0.65 + payout_quality * 0.35
        reasons = [f"주주환원/캐리 점수 {carry_score:.2f}", f"배당 {dividend_yield:.1%}, 자사주 {buyback_yield:.1%}, 이익수익률 {earnings_yield:.1%}"]
        if carry_score >= 0.58 and closes[-1] > trend * 0.94:
            return Signal(asset, min(84, int(54 + carry_score * 38)), "buy", reasons, self.default_horizon_days, self.name, confidence=0.57, target_weight=0.045, stop_loss_pct=-0.11, take_profit_pct=0.22)
        if carry_score < 0.34:
            return Signal(asset, 34, "sell", reasons + ["주주환원/캐리 매력이 부족합니다."], self.default_horizon_days, self.name, confidence=0.48)
        return Signal(asset, 50, "hold", reasons + ["캐리 편입 기준을 더 확인합니다."], self.default_horizon_days, self.name, confidence=0.34)


class SectorRegimeRotationStrategy(StrategyPlugin):
    name = "sector_regime_rotation"
    description = "시장 국면에 따라 섹터와 스타일 비중을 전환하는 로테이션 전략"
    default_horizon_days = 45

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 130:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        momentum_120 = _returns(closes, 120)
        volatility = _realized_volatility(closes, 40)
        trend = sma(closes, 100)[-1]
        if momentum_120 is None or volatility is None or trend is None:
            return None
        sector = str(asset.metadata.get("sector", "unknown"))
        risk_on = momentum_120 > 0.04 and closes[-1] >= trend and volatility < 0.035
        risk_off_sector = sector in {"bonds", "hedge", "broad_market"}
        growth_sector = sector in {"technology", "communication", "broad_market"}
        if risk_on and growth_sector:
            return Signal(asset, 74, "buy", [f"리스크온 국면에서 {sector} 섹터/스타일 선호입니다."], self.default_horizon_days, self.name, confidence=0.53, target_weight=0.04, stop_loss_pct=-0.08, take_profit_pct=0.17)
        if not risk_on and risk_off_sector:
            return Signal(asset, 70, "buy", [f"리스크오프 국면에서 {sector} 방어/헤지 역할 후보입니다."], self.default_horizon_days, self.name, confidence=0.5, target_weight=0.035, stop_loss_pct=-0.07, take_profit_pct=0.12)
        if not risk_on and growth_sector:
            return Signal(asset, 36, "sell", [f"리스크오프 국면에서 {sector} 성장 노출을 줄입니다."], self.default_horizon_days, self.name, confidence=0.48)
        return Signal(asset, 50, "hold", [f"{sector} 섹터는 현재 국면에서 중립입니다."], self.default_horizon_days, self.name, confidence=0.32)


class EarningsRevisionEventStrategy(StrategyPlugin):
    name = "earnings_revision_event"
    description = "실적추정 변경, 서프라이즈, 거래량 반응을 결합하는 이벤트 퀀트 전략"
    default_horizon_days = 20

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 40:
            return None
        current = candles[index]
        avg_volume = sum(candle.volume for candle in candles[index - 20 : index]) / 20
        revision = _metadata_float(asset, "earnings_revision_3m", 0.0)
        surprise = _metadata_float(asset, "earnings_surprise", 0.0)
        volume_shock = current.volume / max(avg_volume, 1)
        event_score = revision * 0.45 + surprise * 0.35 + min(1.0, max(0.0, (volume_shock - 1.0) / 2.0)) * 0.20
        reasons = [f"실적 이벤트 점수 {event_score:.2f}", f"추정치 변화 {revision:.1%}, 서프라이즈 {surprise:.1%}, 거래량 배수 {volume_shock:.2f}"]
        if event_score >= 0.18 and current.close > current.open:
            return Signal(asset, 72, "buy", reasons, self.default_horizon_days, self.name, confidence=0.49, target_weight=0.02, stop_loss_pct=-0.055, take_profit_pct=0.11)
        if event_score <= -0.12:
            return Signal(asset, 33, "sell", reasons + ["부정적 실적 이벤트로 축소 후보입니다."], self.default_horizon_days, self.name, confidence=0.47)
        return Signal(asset, 48, "hold", reasons + ["이벤트 강도가 충분하지 않습니다."], self.default_horizon_days, self.name, confidence=0.28)


class AllWeatherRiskParityStrategy(StrategyPlugin):
    name = "all_weather_risk_parity"
    description = "주식, 채권, 원자재, 헤지 자산을 변동성 기준으로 배분하는 올웨더/리스크패리티 전략"
    default_horizon_days = 120

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 120:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        trend = sma(closes, 100)[-1]
        volatility = _realized_volatility(closes, 60)
        momentum_60 = _returns(closes, 60)
        if trend is None or volatility is None or momentum_60 is None:
            return None
        sector = str(asset.metadata.get("sector", "unknown"))
        kind = asset.kind.value
        sleeve_weight = {
            "broad_market": 0.34,
            "bonds": 0.38,
            "commodity": 0.18,
            "hedge": 0.10,
        }.get(sector, 0.0)
        if sleeve_weight <= 0 and kind not in {"etf", "bond", "commodity", "fx", "future"}:
            return None
        vol_scale = max(0.35, min(1.35, 0.012 / max(volatility, 0.0001)))
        target_weight = round(min(0.09, max(0.01, sleeve_weight * 0.18 * vol_scale)), 4)
        trend_ok = closes[-1] >= trend * 0.94 or sector in {"bonds", "hedge", "commodity"}
        score = 50 + int(min(20, max(-12, momentum_60 * 130))) + int(min(12, vol_scale * 6))
        reasons = [f"올웨더 sleeve {sector}, 60일 변동성 {volatility:.2%}", f"리스크패리티 변동성 조정 목표비중 {target_weight:.2%}"]
        if trend_ok and sleeve_weight > 0:
            return Signal(asset, min(82, max(55, score)), "buy", reasons, self.default_horizon_days, self.name, confidence=0.55, target_weight=target_weight, stop_loss_pct=-0.12, take_profit_pct=0.22)
        return Signal(asset, 46, "hold", reasons + ["올웨더 편입 추세 조건을 더 확인합니다."], self.default_horizon_days, self.name, confidence=0.32)


class MacroRegimeAllocationStrategy(StrategyPlugin):
    name = "macro_regime_allocation"
    description = "성장/방어/헤지 자산을 가격 기반 매크로 국면 프록시로 전환하는 글로벌 매크로 전략"
    default_horizon_days = 60

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 140:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        trend_120 = sma(closes, 120)[-1]
        volatility = _realized_volatility(closes, 40)
        momentum_120 = _returns(closes, 120)
        momentum_20 = _returns(closes, 20)
        if trend_120 is None or volatility is None or momentum_120 is None or momentum_20 is None:
            return None
        sector = str(asset.metadata.get("sector", "unknown"))
        risk_on = closes[-1] > trend_120 and momentum_120 > 0.03 and volatility < 0.032
        shock = momentum_20 < -0.06 or volatility > 0.045
        defensive = sector in {"bonds", "hedge", "commodity"}
        growth = sector in {"technology", "communication", "broad_market", "financials"}
        if risk_on and growth:
            return Signal(asset, 76, "buy", [f"리스크온 매크로 프록시: 120일 모멘텀 {momentum_120:.1%}", f"{sector} 성장/시장 베타 sleeve 선호"], self.default_horizon_days, self.name, confidence=0.57, target_weight=0.04, stop_loss_pct=-0.085, take_profit_pct=0.18)
        if (not risk_on or shock) and defensive:
            target_weight = 0.045 if shock else 0.035
            return Signal(asset, 73, "buy", [f"방어/헤지 매크로 프록시: 20일 모멘텀 {momentum_20:.1%}, 변동성 {volatility:.2%}", f"{sector} sleeve로 노출 이전"], self.default_horizon_days, self.name, confidence=0.53, target_weight=target_weight, stop_loss_pct=-0.075, take_profit_pct=0.14)
        if shock and growth:
            return Signal(asset, 31, "sell", [f"매크로 shock 프록시에서 {sector} 위험노출 축소"], self.default_horizon_days, self.name, confidence=0.5)
        return Signal(asset, 50, "hold", [f"매크로 프록시상 {sector} 중립"], self.default_horizon_days, self.name, confidence=0.31)


class CtaDiversifiedTrendStrategy(StrategyPlugin):
    name = "cta_diversified_trend"
    description = "여러 기간 추세와 변동성 타겟팅을 결합하는 CTA/관리선물형 분산 추세 전략"
    default_horizon_days = 90

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 180:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        ret_20 = _returns(closes, 20)
        ret_60 = _returns(closes, 60)
        ret_120 = _returns(closes, 120)
        volatility = _realized_volatility(closes, 60)
        if ret_20 is None or ret_60 is None or ret_120 is None or volatility is None:
            return None
        trend_score = ret_20 * 0.20 + ret_60 * 0.35 + ret_120 * 0.45
        vol_scale = max(0.3, min(1.4, 0.016 / max(volatility, 0.0001)))
        target_weight = round(min(0.07, 0.035 * vol_scale), 4)
        eligible = asset.kind.value in {"etf", "future", "fx", "commodity"} or str(asset.metadata.get("sector")) in {"broad_market", "bonds", "commodity", "hedge"}
        if not eligible:
            return None
        reasons = [f"CTA 합성 추세 {trend_score:.1%}", f"20/60/120일 수익률 {ret_20:.1%}/{ret_60:.1%}/{ret_120:.1%}, 변동성 조정 {target_weight:.2%}"]
        if trend_score > 0.045 and ret_60 > 0:
            return Signal(asset, min(86, 61 + int(trend_score * 150)), "buy", reasons, self.default_horizon_days, self.name, confidence=0.59, target_weight=target_weight, stop_loss_pct=-0.09, take_profit_pct=0.24)
        if trend_score < -0.055:
            return Signal(asset, 30, "sell", reasons + ["CTA 추세가 명확히 음수입니다."], self.default_horizon_days, self.name, confidence=0.55)
        return Signal(asset, 51, "hold", reasons + ["CTA 추세가 중립입니다."], self.default_horizon_days, self.name, confidence=0.34)


class MachineLearningAlphaStrategy(StrategyPlugin):
    name = "ml_alpha_score"
    description = "트리/부스팅/딥러닝 계열 ML alpha를 흉내내는 비선형 feature ensemble 전략"
    default_horizon_days = 30

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index < 130:
            return None
        closes = [candle.close for candle in candles[: index + 1]]
        ret_20 = _returns(closes, 20)
        ret_60 = _returns(closes, 60)
        ret_120 = _returns(closes, 120)
        volatility = _realized_volatility(closes, 60)
        trend = sma(closes, 80)[-1]
        if ret_20 is None or ret_60 is None or ret_120 is None or volatility is None or trend is None:
            return None
        quality = _metadata_float(asset, "quality_score", 0.5)
        value = _metadata_float(asset, "value_score", 0.5)
        revision = _metadata_float(asset, "earnings_revision_3m", 0.0)
        momentum_feature = min(1.0, max(0.0, 0.5 + ret_120 * 1.1 + ret_60 * 0.7 + ret_20 * 0.3))
        low_vol_feature = min(1.0, max(0.0, 1.0 - volatility / 0.055))
        trend_feature = 1.0 if closes[-1] > trend else 0.25
        interaction = momentum_feature * quality * (0.8 + max(-0.2, min(0.4, revision * 2.0)))
        ml_score = (
            momentum_feature * 0.32
            + quality * 0.20
            + value * 0.14
            + low_vol_feature * 0.14
            + trend_feature * 0.10
            + interaction * 0.10
        )
        reasons = [
            f"ML alpha score {ml_score:.2f}",
            f"features momentum={momentum_feature:.2f}, quality={quality:.2f}, value={value:.2f}, low_vol={low_vol_feature:.2f}",
        ]
        if ml_score >= 0.66:
            target_weight = round(min(0.045, 0.02 + (ml_score - 0.66) * 0.10), 4)
            return Signal(asset, min(88, int(52 + ml_score * 48)), "buy", reasons, self.default_horizon_days, self.name, confidence=0.52, target_weight=target_weight, stop_loss_pct=-0.07, take_profit_pct=0.16)
        if ml_score <= 0.35:
            return Signal(asset, 32, "sell", reasons + ["ML alpha score가 하위권입니다."], self.default_horizon_days, self.name, confidence=0.48)
        return Signal(asset, 50, "hold", reasons + ["ML alpha score가 중립입니다."], self.default_horizon_days, self.name, confidence=0.32)
