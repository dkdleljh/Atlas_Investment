from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.models import Asset, Candle, PortfolioSnapshot


@dataclass(frozen=True)
class AdvancedRiskReport:
    status: str
    cvar_95_pct: float
    expected_shortfall_pct: float
    volatility_target_multiplier: float
    correlation_shock_loss_pct: float
    sector_exposure: dict[str, float]
    fx_exposure: dict[str, float]
    warnings: list[str]


class AdvancedPortfolioRiskEngine:
    def analyze(
        self,
        portfolio: PortfolioSnapshot,
        assets: dict[str, Asset],
        candles_by_symbol: dict[str, list[Candle]],
        target_volatility_pct: float = 12.0,
    ) -> AdvancedRiskReport:
        returns = _portfolio_returns(portfolio, candles_by_symbol)
        cvar = _cvar(returns, 0.95)
        realized_vol = _stddev(returns) * (252**0.5) * 100 if returns else 0.0
        vol_multiplier = 1.0 if realized_vol <= 0 else max(0.1, min(1.2, target_volatility_pct / realized_vol))
        equity = max(portfolio.equity_krw, 1.0)
        sector: dict[str, float] = {}
        fx: dict[str, float] = {}
        for symbol, position in portfolio.positions.items():
            asset = assets.get(symbol)
            sector_name = str(asset.metadata.get("sector", "unknown")) if asset else "unknown"
            currency = asset.currency if asset else position.currency
            sector[sector_name] = sector.get(sector_name, 0.0) + position.market_value / equity
            fx[currency] = fx.get(currency, 0.0) + position.market_value / equity
        shock_loss = sum(abs(weight) for weight in sector.values()) * max(0.0, abs(cvar)) * 1.35
        warnings = []
        if cvar < -3.0:
            warnings.append("95% CVaR가 -3%보다 낮아 tail risk가 큽니다.")
        if vol_multiplier < 0.5:
            warnings.append("실현 변동성이 목표보다 높아 노출 축소가 필요합니다.")
        if any(weight > 0.4 for weight in sector.values()):
            warnings.append("섹터 집중도가 높습니다.")
        return AdvancedRiskReport(
            "degraded" if warnings else "ok",
            round(cvar, 4),
            round(cvar, 4),
            round(vol_multiplier, 4),
            round(shock_loss, 4),
            {key: round(value, 6) for key, value in sector.items()},
            {key: round(value, 6) for key, value in fx.items()},
            warnings,
        )


def _portfolio_returns(portfolio: PortfolioSnapshot, candles_by_symbol: dict[str, list[Candle]]) -> list[float]:
    if not portfolio.positions:
        return []
    min_len = min((len(candles_by_symbol.get(symbol, [])) for symbol in portfolio.positions), default=0)
    if min_len < 2:
        return []
    equity = max(portfolio.equity_krw, 1.0)
    weights = {symbol: position.market_value / equity for symbol, position in portfolio.positions.items()}
    rows: list[float] = []
    for index in range(1, min_len):
        value = 0.0
        for symbol, weight in weights.items():
            candles = candles_by_symbol.get(symbol, [])
            if candles[index - 1].close > 0:
                value += weight * (candles[index].close / candles[index - 1].close - 1)
        rows.append(value)
    return rows


def _cvar(returns: list[float], confidence: float) -> float:
    if not returns:
        return 0.0
    sorted_returns = sorted(returns)
    cutoff = max(1, int(len(sorted_returns) * (1 - confidence)))
    tail = sorted_returns[:cutoff]
    return sum(tail) / len(tail) * 100


def _stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((value - mean) ** 2 for value in values) / (len(values) - 1)) ** 0.5
