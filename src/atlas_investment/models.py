from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class Market(str, Enum):
    KR = "KR"
    US = "US"
    EU = "EU"
    JP = "JP"
    HK = "HK"
    CN = "CN"
    EM = "EM"
    GLOBAL = "GLOBAL"


class AssetKind(str, Enum):
    STOCK = "stock"
    ETF = "etf"
    ETN = "etn"
    BOND = "bond"
    FUTURE = "future"
    OPTION = "option"
    FX = "fx"
    COMMODITY = "commodity"
    CASH = "cash"


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class TradingMode(str, Enum):
    OFF = "off"
    DRY_RUN = "dry_run"
    PAPER = "paper"
    LIVE_AUTO = "live_auto"


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    market: Market
    kind: AssetKind = AssetKind.STOCK
    currency: str = "KRW"
    is_leveraged: bool = False
    is_inverse: bool = False
    tradable: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: float
    currency: str
    as_of: str
    previous_close: float | None = None
    volume: float | None = None


@dataclass
class Position:
    symbol: str
    quantity: float
    avg_price: float
    market_value: float
    currency: str = "KRW"


@dataclass
class PortfolioSnapshot:
    cash_krw: float
    positions: dict[str, Position] = field(default_factory=dict)

    @property
    def equity_krw(self) -> float:
        return self.cash_krw + sum(position.market_value for position in self.positions.values())

    def position_weight(self, symbol: str) -> float:
        if self.equity_krw <= 0:
            return 0.0
        position = self.positions.get(symbol)
        return 0.0 if position is None else position.market_value / self.equity_krw


@dataclass(frozen=True)
class Signal:
    asset: Asset
    score: int
    stance: str
    reasons: list[str]
    horizon_days: int
    strategy: str
    confidence: float = 0.5
    target_weight: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None


@dataclass(frozen=True)
class Candle:
    symbol: str
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    side: Side
    quantity: float
    price: float
    traded_at: str
    reason: str
    strategy: str


@dataclass(frozen=True)
class BacktestResult:
    strategy: str
    symbol: str
    initial_cash: float
    final_equity: float
    total_return_pct: float
    max_drawdown_pct: float
    trade_count: int
    win_rate_pct: float
    trades: list[BacktestTrade]
    equity_curve: list[dict[str, float | str]]


@dataclass(frozen=True)
class CommitteeReport:
    asset: Asset
    score: int
    decision: str
    horizon_days: int
    role_opinions: dict[str, str]
    risks: list[str]


@dataclass(frozen=True)
class OrderIntent:
    asset: Asset
    side: Side
    quantity: float
    order_type: OrderType
    limit_price: float | None
    reason: str
    expected_holding_days: int
    uses_margin: bool = False
    uses_credit: bool = False
    idempotency_key: str = field(default_factory=lambda: str(uuid4()))


@dataclass(frozen=True)
class RiskResult:
    allowed: bool
    reasons: list[str]
    adjusted_order: OrderIntent | None = None


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: Side
    quantity: float
    price: float
    currency: str
    filled_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)
