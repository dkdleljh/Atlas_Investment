from __future__ import annotations

from abc import ABC, abstractmethod

from atlas_investment.data.ohlcv_store import generate_sample_ohlcv
from atlas_investment.integrations.yahoo import YahooFinanceClient
from atlas_investment.models import Asset, Candle


class MarketDataVendor(ABC):
    name: str

    @abstractmethod
    def load_daily_ohlcv(self, asset: Asset, days: int) -> list[Candle]:
        raise NotImplementedError


class SampleMarketDataVendor(MarketDataVendor):
    name = "sample"

    def load_daily_ohlcv(self, asset: Asset, days: int) -> list[Candle]:
        start_price = 80000 if asset.market.value == "KR" else 250000
        return generate_sample_ohlcv(asset.symbol, days=days, start_price=start_price)


class YahooMarketDataVendor(MarketDataVendor):
    name = "yfinance"

    def __init__(self, client: YahooFinanceClient | None = None) -> None:
        self.client = client or YahooFinanceClient()

    def load_daily_ohlcv(self, asset: Asset, days: int) -> list[Candle]:
        symbol = asset.symbol
        if asset.market.value == "KR" and symbol.isdigit():
            symbol = f"{symbol}.KS"
        return self.client.load_daily_ohlcv(symbol, days=days)


class HybridMarketDataVendor(MarketDataVendor):
    name = "hybrid"

    def __init__(self, primary: MarketDataVendor, fallback: MarketDataVendor) -> None:
        self.primary = primary
        self.fallback = fallback

    def load_daily_ohlcv(self, asset: Asset, days: int) -> list[Candle]:
        try:
            candles = self.primary.load_daily_ohlcv(asset, days)
        except Exception:
            candles = []
        if candles:
            return candles
        return self.fallback.load_daily_ohlcv(asset, days)
