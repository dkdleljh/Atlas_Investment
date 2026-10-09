from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.backtest.realistic import MarketImpactCostModel
from atlas_investment.models import Asset, Candle
from atlas_investment.portfolio.strategy_allocation import StrategyEnsembleAllocator
from atlas_investment.strategy.base import StrategyPlugin
from atlas_investment.strategy.cross_sectional import CrossSectionalMomentumRanker
from atlas_investment.strategy.regime import MarketRegimeDetector
from atlas_investment.technical.indicators import max_drawdown


@dataclass(frozen=True)
class EnsembleBacktestResult:
    status: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    rebalance_count: int
    average_gross_exposure: float
    total_transaction_cost: float
    average_transaction_cost_bps: float
    equity_curve: list[dict[str, float | str]]
    warnings: list[str]


class EnsemblePortfolioBacktester:
    """Walks forward a multi-strategy ensemble allocation at rebalance dates."""

    def __init__(self, initial_cash: float = 10_000_000, rebalance_interval: int = 20) -> None:
        self.initial_cash = initial_cash
        self.rebalance_interval = max(5, rebalance_interval)

    def run(
        self,
        assets: list[Asset],
        candles_by_symbol: dict[str, list[Candle]],
        strategies: list[StrategyPlugin],
        max_position_weight: float = 0.08,
        max_sector_weight: float = 0.35,
        apply_realistic_costs: bool = True,
        partial_fill_ratio: float = 0.95,
    ) -> EnsembleBacktestResult:
        if not assets or not strategies:
            return EnsembleBacktestResult("blocked", self.initial_cash, self.initial_cash, 0.0, 0.0, 0, 0.0, 0.0, 0.0, [], ["자산 또는 전략이 없습니다."])
        min_len = min((len(candles_by_symbol.get(asset.symbol, [])) for asset in assets), default=0)
        if min_len < 100:
            return EnsembleBacktestResult("blocked", self.initial_cash, self.initial_cash, 0.0, 0.0, 0, 0.0, 0.0, 0.0, [], ["앙상블 백테스트에 필요한 가격 이력이 부족합니다."])

        cash = self.initial_cash
        positions: dict[str, float] = {}
        equity_curve: list[dict[str, float | str]] = []
        gross_values: list[float] = []
        transaction_costs: list[float] = []
        turnover_values: list[float] = []
        rebalance_count = 0
        allocator = StrategyEnsembleAllocator(max_position_weight=max_position_weight, max_sector_weight=max_sector_weight)
        cost_model = MarketImpactCostModel()

        for index in range(80, min_len):
            prices = {asset.symbol: candles_by_symbol[asset.symbol][index].close for asset in assets}
            equity = cash + sum(quantity * prices.get(symbol, 0.0) for symbol, quantity in positions.items())
            if (index - 80) % self.rebalance_interval == 0:
                window = {asset.symbol: candles_by_symbol[asset.symbol][: index + 1] for asset in assets}
                enriched_assets, _ = CrossSectionalMomentumRanker().enrich_assets(assets, window)
                benchmark = window.get(enriched_assets[0].symbol, [])
                regime = MarketRegimeDetector().detect(benchmark)
                strategy_weights = {strategy.name: regime.strategy_weight_multipliers.get(strategy.name, 1.0) for strategy in strategies}
                signals = []
                for asset in enriched_assets:
                    candles = window.get(asset.symbol, [])
                    for strategy in strategies:
                        signal = strategy.generate_signal(asset, candles, len(candles) - 1)
                        if signal:
                            signals.append(signal)
                report = allocator.allocate(signals, strategy_weights=strategy_weights)
                target_weights = {candidate.symbol: candidate.target_weight * regime.exposure_multiplier for candidate in report.candidates if candidate.stance == "buy"}
                previous_values = {symbol: quantity * prices.get(symbol, 0.0) for symbol, quantity in positions.items()}
                cash = 0.0
                positions = {}
                invested = 0.0
                for asset in assets:
                    target = min(max_position_weight, target_weights.get(asset.symbol, 0.0))
                    price = prices[asset.symbol]
                    value = equity * target * max(0.0, min(partial_fill_ratio, 1.0))
                    turnover_notional = abs(value - previous_values.get(asset.symbol, 0.0))
                    if apply_realistic_costs and turnover_notional > 0:
                        estimate = cost_model.estimate(window.get(asset.symbol, []), turnover_notional)
                        transaction_costs.append(estimate.total_cost)
                        turnover_values.append(turnover_notional)
                        equity -= estimate.total_cost
                        value = min(value, max(0.0, equity))
                    if price > 0 and value > 0:
                        positions[asset.symbol] = value / price
                        invested += value
                cash = max(0.0, equity - invested)
                gross_values.append(invested / max(equity, 1.0))
                rebalance_count += 1
            equity = cash + sum(quantity * prices.get(symbol, 0.0) for symbol, quantity in positions.items())
            equity_curve.append({"date": candles_by_symbol[assets[0].symbol][index].date, "equity": round(equity, 4)})

        final_equity = float(equity_curve[-1]["equity"]) if equity_curve else self.initial_cash
        equity_values = [float(point["equity"]) for point in equity_curve]
        warnings = []
        if not positions and final_equity == self.initial_cash:
            warnings.append("매수 후보가 거의 없어 현금 비중이 높았습니다.")
        if partial_fill_ratio < 1:
            warnings.append("부분체결 프록시가 적용되어 목표 비중보다 낮게 체결됐습니다.")
        total_cost = sum(transaction_costs)
        turnover_base = max(sum(turnover_values), 1.0)
        return EnsembleBacktestResult(
            "ok" if equity_curve else "blocked",
            self.initial_cash,
            round(final_equity, 4),
            round((final_equity / self.initial_cash - 1) * 100, 4),
            round(max_drawdown(equity_values) * 100, 4),
            rebalance_count,
            round(sum(gross_values) / len(gross_values), 6) if gross_values else 0.0,
            round(total_cost, 4),
            round(total_cost / turnover_base * 10_000, 4) if total_cost > 0 else 0.0,
            equity_curve,
            warnings,
        )
