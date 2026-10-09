from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from pathlib import Path

from atlas_investment.models import Candle


class OhlcvStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, symbol: str) -> Path:
        safe_symbol = symbol.replace("/", "_").replace(":", "_")
        return self.root / f"{safe_symbol}.csv"

    def load(self, symbol: str) -> list[Candle]:
        path = self.path_for(symbol)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            return [
                Candle(
                    symbol=row["symbol"],
                    date=row["date"],
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
                for row in reader
            ]

    def save(self, symbol: str, candles: list[Candle]) -> Path:
        path = self.path_for(symbol)
        with path.open("w", encoding="utf-8", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["symbol", "date", "open", "high", "low", "close", "volume"])
            writer.writeheader()
            for candle in candles:
                writer.writerow(
                    {
                        "symbol": candle.symbol,
                        "date": candle.date,
                        "open": candle.open,
                        "high": candle.high,
                        "low": candle.low,
                        "close": candle.close,
                        "volume": candle.volume,
                    }
                )
        return path

    def load_or_generate_sample(self, symbol: str, days: int = 260, start_price: float = 100.0) -> list[Candle]:
        existing = self.load(symbol)
        if existing:
            return existing
        candles = generate_sample_ohlcv(symbol, days=days, start_price=start_price)
        self.save(symbol, candles)
        return candles


def generate_sample_ohlcv(symbol: str, days: int = 260, start_price: float = 100.0) -> list[Candle]:
    rng = random.Random(symbol)
    current = start_price
    today = date.today()
    first_day = today - timedelta(days=days * 1.45)
    candles: list[Candle] = []
    current_day = first_day
    while len(candles) < days:
        if current_day.weekday() >= 5:
            current_day += timedelta(days=1)
            continue
        drift = 0.0007
        shock = rng.gauss(0, 0.018)
        open_price = current * (1 + rng.gauss(0, 0.004))
        close = max(1.0, open_price * (1 + drift + shock))
        high = max(open_price, close) * (1 + abs(rng.gauss(0.006, 0.004)))
        low = min(open_price, close) * (1 - abs(rng.gauss(0.006, 0.004)))
        volume = max(1000, rng.gauss(1_000_000, 250_000))
        candles.append(
            Candle(
                symbol=symbol,
                date=current_day.isoformat(),
                open=round(open_price, 4),
                high=round(high, 4),
                low=round(low, 4),
                close=round(close, 4),
                volume=round(volume, 0),
            )
        )
        current = close
        current_day += timedelta(days=1)
    return candles

