from __future__ import annotations

import unittest

from atlas_investment.models import Candle
from atlas_investment.technical.indicators import atr, max_drawdown, rsi, sma


class IndicatorsTest(unittest.TestCase):
    def test_sma(self) -> None:
        self.assertEqual(sma([1, 2, 3, 4], 3), [None, None, 2.0, 3.0])

    def test_rsi_length(self) -> None:
        values = [10, 11, 12, 11, 13, 14, 13, 15, 16, 15, 17, 18, 19, 18, 20]
        self.assertEqual(len(rsi(values, 14)), len(values))

    def test_max_drawdown(self) -> None:
        self.assertAlmostEqual(max_drawdown([100, 120, 90, 130]), -0.25)

    def test_atr(self) -> None:
        candles = [
            Candle("T", "2026-01-01", 10, 12, 9, 11, 1000),
            Candle("T", "2026-01-02", 11, 13, 10, 12, 1000),
            Candle("T", "2026-01-03", 12, 15, 11, 14, 1000),
        ]
        self.assertEqual(atr(candles, 2)[0], None)
        self.assertAlmostEqual(float(atr(candles, 2)[-1]), 3.5)


if __name__ == "__main__":
    unittest.main()
