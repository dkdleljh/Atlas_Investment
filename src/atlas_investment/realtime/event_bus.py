from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class MarketEvent:
    event_type: str
    symbol: str
    payload: dict[str, Any]
    received_at: str


class EventBus:
    """In-memory event queue used until WebSocket infrastructure is connected."""

    def __init__(self, maxlen: int = 10000) -> None:
        self._events: deque[MarketEvent] = deque(maxlen=maxlen)

    def publish(self, event_type: str, symbol: str, payload: dict[str, Any]) -> MarketEvent:
        event = MarketEvent(event_type, symbol, payload, datetime.now(timezone.utc).isoformat())
        self._events.append(event)
        return event

    def drain(self) -> list[MarketEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def __len__(self) -> int:
        return len(self._events)
