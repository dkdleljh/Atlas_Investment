from __future__ import annotations

from dataclasses import dataclass, replace

from atlas_investment.models import Asset, Candle


@dataclass(frozen=True)
class CrossSectionalRank:
    symbol: str
    rank: int
    percentile: float
    score: float
    returns: dict[str, float | None]


class CrossSectionalMomentumRanker:
    """Computes true cross-sectional momentum ranks across the loaded universe."""

    LOOKBACKS = {"1m": 21, "3m": 63, "6m": 126, "12m": 252}
    WEIGHTS = {"1m": -0.15, "3m": 0.25, "6m": 0.35, "12m": 0.25}

    def rank(self, assets: list[Asset], candles_by_symbol: dict[str, list[Candle]]) -> list[CrossSectionalRank]:
        rows: list[tuple[Asset, dict[str, float | None], float]] = []
        for asset in assets:
            closes = [candle.close for candle in candles_by_symbol.get(asset.symbol, [])]
            returns = {name: _return(closes, lookback) for name, lookback in self.LOOKBACKS.items()}
            valid = {name: value for name, value in returns.items() if value is not None}
            if len(valid) < 2:
                continue
            score = sum((returns[name] or 0.0) * weight for name, weight in self.WEIGHTS.items())
            rows.append((asset, returns, score))
        rows.sort(key=lambda item: item[2], reverse=True)
        total = max(len(rows), 1)
        ranked: list[CrossSectionalRank] = []
        for index, (asset, returns, score) in enumerate(rows, start=1):
            percentile = 1.0 - ((index - 1) / total)
            ranked.append(CrossSectionalRank(asset.symbol, index, round(percentile, 6), round(score, 6), returns))
        return ranked

    def enrich_assets(self, assets: list[Asset], candles_by_symbol: dict[str, list[Candle]]) -> tuple[list[Asset], list[CrossSectionalRank]]:
        ranks = self.rank(assets, candles_by_symbol)
        by_symbol = {row.symbol: row for row in ranks}
        enriched: list[Asset] = []
        for asset in assets:
            row = by_symbol.get(asset.symbol)
            if row is None:
                enriched.append(asset)
                continue
            metadata = dict(asset.metadata)
            metadata["momentum_rank"] = row.percentile
            metadata["cross_sectional_momentum_score"] = row.score
            metadata["cross_sectional_rank"] = row.rank
            metadata["cross_sectional_returns"] = row.returns
            enriched.append(replace(asset, metadata=metadata))
        return enriched, ranks


def _return(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback or closes[-lookback - 1] <= 0:
        return None
    return closes[-1] / closes[-lookback - 1] - 1
