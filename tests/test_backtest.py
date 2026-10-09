from __future__ import annotations

import unittest

from atlas_investment.backtest.engine import BacktestEngine
from atlas_investment.data.ohlcv_store import generate_sample_ohlcv
from atlas_investment.models import Asset, Candle, Market, Signal
from atlas_investment.strategy.base import StrategyPlugin
from atlas_investment.strategy.registry import get_strategy


class FirstBarBuyStrategy(StrategyPlugin):
    name = "first_bar_buy"
    description = "test strategy"
    default_horizon_days = 5

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index == 0:
            return Signal(asset, 80, "buy", ["first bar"], 5, self.name, target_weight=0.1)
        return None


class StopSensitiveFirstBarBuyStrategy(StrategyPlugin):
    name = "stop_sensitive_first_bar_buy"
    description = "test strategy"
    default_horizon_days = 5

    def generate_signal(self, asset: Asset, candles: list[Candle], index: int) -> Signal | None:
        if index == 0:
            return Signal(asset, 80, "buy", ["first bar"], 5, self.name, target_weight=0.1, stop_loss_pct=-0.01)
        return None


class BacktestTest(unittest.TestCase):
    def test_backtest_runs(self) -> None:
        asset = Asset("005930", "삼성전자", Market.KR)
        candles = generate_sample_ohlcv(asset.symbol, days=180, start_price=80000)
        result = BacktestEngine(initial_cash=10_000_000).run(asset, candles, get_strategy("moving_average_cross"))
        self.assertEqual(result.symbol, "005930")
        self.assertGreater(result.final_equity, 0)
        self.assertGreaterEqual(result.trade_count, 0)

    def test_signals_execute_on_next_bar_open(self) -> None:
        asset = Asset("TEST", "Test", Market.US)
        candles = [
            Candle(asset.symbol, "2026-01-01", 100, 110, 90, 100, 1000),
            Candle(asset.symbol, "2026-01-02", 120, 130, 115, 125, 1000),
            Candle(asset.symbol, "2026-01-03", 130, 135, 120, 128, 1000),
        ]
        result = BacktestEngine(initial_cash=10_000, fee_rate=0.0, slippage_rate=0.0).run(asset, candles, FirstBarBuyStrategy())

        self.assertEqual(result.trades[0].traded_at, "2026-01-02")
        self.assertEqual(result.trades[0].price, 120)

    def test_stop_loss_does_not_evaluate_before_next_bar_entry(self) -> None:
        asset = Asset("TEST", "Test", Market.US)
        candles = [
            Candle(asset.symbol, "2026-01-01", 100, 110, 90, 100, 1000),
            Candle(asset.symbol, "2026-01-02", 120, 130, 115, 125, 1000),
            Candle(asset.symbol, "2026-01-03", 126, 135, 120, 128, 1000),
        ]
        result = BacktestEngine(initial_cash=10_000, fee_rate=0.0, slippage_rate=0.0).run(asset, candles, StopSensitiveFirstBarBuyStrategy())

        self.assertEqual(result.trades[0].traded_at, "2026-01-02")
        self.assertNotIn("2026-01-01", [trade.traded_at for trade in result.trades])


if __name__ == "__main__":
    unittest.main()
