from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from atlas_investment.models import Candle


@dataclass(frozen=True)
class YahooReadiness:
    status: str
    notes: list[str]


class YahooFinanceClient:
    def readiness(self) -> YahooReadiness:
        try:
            import yfinance  # noqa: F401
        except Exception as error:  # pragma: no cover - depends on local environment
            return YahooReadiness("blocked", [f"yfinance import 실패: {error}"])
        return YahooReadiness("ok", ["yfinance를 사용할 수 있습니다."])

    def load_daily_ohlcv(self, symbol: str, days: int = 260) -> list[Candle]:
        import yfinance as yf

        end = date.today() + timedelta(days=1)
        start = end - timedelta(days=int(days * 1.8))
        frame = yf.download(symbol, start=start.isoformat(), end=end.isoformat(), interval="1d", auto_adjust=False, progress=False)
        candles: list[Candle] = []
        if frame.empty:
            return candles
        if hasattr(frame.columns, "nlevels") and frame.columns.nlevels > 1:
            frame = frame.xs(symbol, axis=1, level=-1, drop_level=True)
        for index, row in frame.tail(days).iterrows():
            candles.append(
                Candle(
                    symbol=symbol,
                    date=index.date().isoformat(),
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=float(row["Volume"]),
                )
            )
        return candles
