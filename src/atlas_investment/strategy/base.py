from __future__ import annotations

from abc import ABC, abstractmethod

from atlas_investment.models import Asset, Candle, Signal


class StrategyPlugin(ABC):
    name: str
    description: str
    default_horizon_days: int

    @abstractmethod
    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        raise NotImplementedError

