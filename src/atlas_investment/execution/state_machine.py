from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from atlas_investment.models import OrderIntent


class OrderStatus(str, Enum):
    CREATED = "created"
    VALIDATED = "validated"
    QUEUED = "queued"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"
    BLOCKED = "blocked"


ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.VALIDATED, OrderStatus.BLOCKED, OrderStatus.REJECTED},
    OrderStatus.VALIDATED: {OrderStatus.QUEUED, OrderStatus.BLOCKED, OrderStatus.REJECTED},
    OrderStatus.QUEUED: {OrderStatus.SUBMITTED, OrderStatus.CANCEL_REQUESTED, OrderStatus.EXPIRED, OrderStatus.BLOCKED},
    OrderStatus.SUBMITTED: {OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED, OrderStatus.CANCEL_REQUESTED, OrderStatus.REJECTED, OrderStatus.EXPIRED},
    OrderStatus.PARTIALLY_FILLED: {OrderStatus.FILLED, OrderStatus.CANCEL_REQUESTED, OrderStatus.EXPIRED},
    OrderStatus.CANCEL_REQUESTED: {OrderStatus.CANCELLED, OrderStatus.REJECTED},
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
    OrderStatus.EXPIRED: set(),
    OrderStatus.BLOCKED: set(),
}


@dataclass(frozen=True)
class OrderStateEvent:
    status: OrderStatus
    reason: str
    at: str


@dataclass
class ManagedOrder:
    idempotency_key: str
    symbol: str
    side: str
    quantity: float
    status: OrderStatus
    events: list[OrderStateEvent]


class OrderStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.orders: dict[str, ManagedOrder] = {}
        self._load()

    def create(self, order: OrderIntent, reason: str = "created") -> ManagedOrder:
        if order.idempotency_key in self.orders:
            return self.orders[order.idempotency_key]
        managed = ManagedOrder(
            idempotency_key=order.idempotency_key,
            symbol=order.asset.symbol,
            side=order.side.value,
            quantity=order.quantity,
            status=OrderStatus.CREATED,
            events=[self._event(OrderStatus.CREATED, reason)],
        )
        self.orders[order.idempotency_key] = managed
        self._save()
        return managed

    def transition(self, idempotency_key: str, status: OrderStatus, reason: str) -> ManagedOrder:
        if idempotency_key not in self.orders:
            raise KeyError(f"unknown order: {idempotency_key}")
        managed = self.orders[idempotency_key]
        if status not in ALLOWED_TRANSITIONS[managed.status]:
            raise ValueError(f"invalid transition: {managed.status.value} -> {status.value}")
        managed.status = status
        managed.events.append(self._event(status, reason))
        self._save()
        return managed

    def reconcile(self, broker_order_ids: set[str]) -> dict[str, list[str]]:
        known = set(self.orders)
        return {
            "missing_in_broker": sorted(known - broker_order_ids),
            "unknown_in_broker": sorted(broker_order_ids - known),
        }

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        for item in payload:
            events = [OrderStateEvent(OrderStatus(event["status"]), event["reason"], event["at"]) for event in item["events"]]
            self.orders[item["idempotency_key"]] = ManagedOrder(
                item["idempotency_key"],
                item["symbol"],
                item["side"],
                float(item["quantity"]),
                OrderStatus(item["status"]),
                events,
            )

    def _save(self) -> None:
        payload = []
        for order in self.orders.values():
            row = asdict(order)
            row["status"] = order.status.value
            row["events"] = [{"status": event.status.value, "reason": event.reason, "at": event.at} for event in order.events]
            payload.append(row)
        temp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temp_path, self.path)

    @staticmethod
    def _event(status: OrderStatus, reason: str) -> OrderStateEvent:
        return OrderStateEvent(status, reason, datetime.now(timezone.utc).isoformat())
