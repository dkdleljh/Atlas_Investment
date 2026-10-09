from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from atlas_investment.models import Candle


@dataclass(frozen=True)
class CorrelationPair:
    left: str
    right: str
    correlation: float


def daily_returns(candles: list[Candle]) -> list[float]:
    returns: list[float] = []
    for previous, current in zip(candles, candles[1:]):
        if previous.close > 0:
            returns.append((current.close / previous.close) - 1)
    return returns


def pearson(left: list[float], right: list[float]) -> float:
    size = min(len(left), len(right))
    if size < 2:
        return 0.0
    x = left[-size:]
    y = right[-size:]
    mean_x = sum(x) / size
    mean_y = sum(y) / size
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    var_x = sum((a - mean_x) ** 2 for a in x)
    var_y = sum((b - mean_y) ** 2 for b in y)
    denominator = sqrt(var_x * var_y)
    return 0.0 if denominator == 0 else cov / denominator


class CorrelationAnalyzer:
    def top_pairs(self, series: dict[str, list[Candle]], threshold: float = 0.75) -> list[CorrelationPair]:
        returns = {symbol: daily_returns(candles) for symbol, candles in series.items()}
        symbols = sorted(returns)
        pairs: list[CorrelationPair] = []
        for index, left in enumerate(symbols):
            for right in symbols[index + 1 :]:
                value = pearson(returns[left], returns[right])
                if abs(value) >= threshold:
                    pairs.append(CorrelationPair(left, right, value))
        return sorted(pairs, key=lambda item: abs(item.correlation), reverse=True)
