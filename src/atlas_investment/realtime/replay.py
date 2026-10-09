from __future__ import annotations

from dataclasses import dataclass

from atlas_investment.execution.algorithms import AlgorithmicExecutionPlanner
from atlas_investment.execution.child_orders import PaperChildOrderManager
from atlas_investment.models import Asset, Candle, OrderIntent, OrderType, Side, TradingMode
from atlas_investment.realtime.event_bus import EventBus


@dataclass(frozen=True)
class ReplayReport:
    status: str
    event_count: int
    child_order_status: str
    filled_quantity: float
    warnings: list[str]


class HistoricalEventReplay:
    """Replays historical candles through quote/order simulation paths."""

    def run(self, asset: Asset, candles: list[Candle], quantity: float = 5.0) -> ReplayReport:
        if len(candles) < 30:
            return ReplayReport("blocked", 0, "blocked", 0.0, ["리플레이에 필요한 candle 수가 부족합니다."])
        bus = EventBus()
        for candle in candles[-30:]:
            bus.publish("quote", asset.symbol, {"date": candle.date, "price": candle.close, "volume": candle.volume})
        order = OrderIntent(asset, Side.BUY, quantity, OrderType.LIMIT, candles[-1].close, "historical replay child order", 5)
        plan = AlgorithmicExecutionPlanner().plan([order], "adaptive", TradingMode.PAPER, slices_per_order=4)
        child = PaperChildOrderManager().execute_plan(plan, TradingMode.PAPER, fill_ratio=0.75)
        bus.publish("order_status", asset.symbol, {"status": child.status, "filled_quantity": child.filled_quantity})
        events = bus.drain()
        warnings = list(child.risk_notes)
        if child.filled_quantity < quantity:
            warnings.append("리플레이에서 부분체결 상황을 재현했습니다.")
        return ReplayReport("ok", len(events), child.status, child.filled_quantity, warnings)
