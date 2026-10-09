from __future__ import annotations

from atlas_investment.models import Candle


def sma(values: list[float], window: int) -> list[float | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    result: list[float | None] = []
    for index in range(len(values)):
        if index + 1 < window:
            result.append(None)
        else:
            chunk = values[index + 1 - window : index + 1]
            result.append(sum(chunk) / window)
    return result


def ema(values: list[float], window: int) -> list[float | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    result: list[float | None] = []
    multiplier = 2 / (window + 1)
    current: float | None = None
    for index, value in enumerate(values):
        if index + 1 < window:
            result.append(None)
            continue
        if current is None:
            current = sum(values[index + 1 - window : index + 1]) / window
        else:
            current = (value - current) * multiplier + current
        result.append(current)
    return result


def rsi(values: list[float], window: int = 14) -> list[float | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    if not values:
        return []
    result: list[float | None] = [None]
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(values)):
        change = values[index] - values[index - 1]
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))
        if index < window:
            result.append(None)
            continue
        recent_gains = gains[-window:]
        recent_losses = losses[-window:]
        avg_gain = sum(recent_gains) / window
        avg_loss = sum(recent_losses) / window
        if avg_loss == 0:
            result.append(100.0)
        else:
            rs = avg_gain / avg_loss
            result.append(100 - (100 / (1 + rs)))
    return result


def atr(candles: list[Candle], window: int = 14) -> list[float | None]:
    if window <= 0:
        raise ValueError("window must be positive")
    true_ranges: list[float] = []
    for index, candle in enumerate(candles):
        if index == 0:
            true_range = candle.high - candle.low
        else:
            previous_close = candles[index - 1].close
            true_range = max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        true_ranges.append(true_range)
    return sma(true_ranges, window)


def max_drawdown(equity_values: list[float]) -> float:
    peak = 0.0
    worst = 0.0
    for value in equity_values:
        peak = max(peak, value)
        if peak > 0:
            drawdown = (value / peak) - 1
            worst = min(worst, drawdown)
    return worst
