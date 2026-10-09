from __future__ import annotations

from atlas_investment.strategy.base import StrategyPlugin
from atlas_investment.strategy.plugins import (
    AllWeatherRiskParityStrategy,
    BreakoutMomentumStrategy,
    CrossSectionalMomentumStrategy,
    CtaDiversifiedTrendStrategy,
    EtfRebalanceStrategy,
    EarningsRevisionEventStrategy,
    EventDisclosureStrategy,
    EquityLongShortQualityStrategy,
    FactorQualityStrategy,
    FxOverlaySignalStrategy,
    LiquidityMarketMakingSimulationStrategy,
    LongTermTrendStrategy,
    LowVolDefensiveStrategy,
    MacroRegimeAllocationStrategy,
    MachineLearningAlphaStrategy,
    MovingAverageCrossStrategy,
    MultiFactorQvmStrategy,
    RsiMeanReversionStrategy,
    ScalpingSimulationStrategy,
    SectorRegimeRotationStrategy,
    ShareholderYieldCarryStrategy,
    StatArbMeanReversionStrategy,
    SwingMomentumStrategy,
    TimeSeriesMomentumStrategy,
    VolatilityBreakoutStrategy,
)


def all_strategies() -> dict[str, StrategyPlugin]:
    strategies: list[StrategyPlugin] = [
        MovingAverageCrossStrategy(),
        RsiMeanReversionStrategy(),
        BreakoutMomentumStrategy(),
        LongTermTrendStrategy(),
        VolatilityBreakoutStrategy(),
        SwingMomentumStrategy(),
        ScalpingSimulationStrategy(),
        EtfRebalanceStrategy(),
        FactorQualityStrategy(),
        FxOverlaySignalStrategy(),
        EventDisclosureStrategy(),
        TimeSeriesMomentumStrategy(),
        CrossSectionalMomentumStrategy(),
        LowVolDefensiveStrategy(),
        StatArbMeanReversionStrategy(),
        EquityLongShortQualityStrategy(),
        LiquidityMarketMakingSimulationStrategy(),
        MultiFactorQvmStrategy(),
        ShareholderYieldCarryStrategy(),
        SectorRegimeRotationStrategy(),
        EarningsRevisionEventStrategy(),
        AllWeatherRiskParityStrategy(),
        MacroRegimeAllocationStrategy(),
        CtaDiversifiedTrendStrategy(),
        MachineLearningAlphaStrategy(),
    ]
    return {strategy.name: strategy for strategy in strategies}


def get_strategy(name: str) -> StrategyPlugin:
    aliases = {
        "momentum_breakout": "breakout_momentum",
        "mean_reversion": "rsi_mean_reversion",
        "pairs_trading": "stat_arb_mean_reversion",
        "stat_arb": "stat_arb_mean_reversion",
        "market_making": "liquidity_market_making_simulation",
        "long_short": "equity_long_short_quality",
        "qvm": "multifactor_qvm",
        "multi_factor": "multifactor_qvm",
        "carry": "shareholder_yield_carry",
        "yield_carry": "shareholder_yield_carry",
        "sector_rotation": "sector_regime_rotation",
        "regime_rotation": "sector_regime_rotation",
        "earnings_event": "earnings_revision_event",
        "all_weather": "all_weather_risk_parity",
        "risk_parity": "all_weather_risk_parity",
        "global_macro": "macro_regime_allocation",
        "macro": "macro_regime_allocation",
        "cta": "cta_diversified_trend",
        "managed_futures": "cta_diversified_trend",
        "ml": "ml_alpha_score",
        "ai": "ml_alpha_score",
        "machine_learning": "ml_alpha_score",
    }
    name = aliases.get(name, name)
    strategies = all_strategies()
    if name not in strategies:
        available = ", ".join(sorted(strategies))
        raise ValueError(f"Unknown strategy '{name}'. Available strategies: {available}")
    return strategies[name]
