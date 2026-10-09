from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import requests


def today_yyyymmdd() -> str:
    return date.today().strftime("%Y%m%d")


def recent_business_yyyymmdd() -> str:
    current = date.today()
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current.strftime("%Y%m%d")


@dataclass(frozen=True)
class KoreanStockSearchResult:
    market: str
    code: str
    name: str
    standard_code: str | None = None
    listed_at: str | None = None


@dataclass(frozen=True)
class KoreanStockTradeSnapshot:
    market: str
    code: str
    base_date: str
    name: str
    close_price: float | None
    open_price: float | None
    high_price: float | None
    low_price: float | None
    trading_volume: float | None
    market_cap: float | None
    raw: dict[str, Any]


class KoreanStockClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float = 8.0) -> None:
        self.base_url = (base_url or os.getenv("KSKILL_PROXY_BASE_URL") or "https://k-skill-proxy.nomadamas.org").rstrip("/")
        self.timeout_seconds = timeout_seconds

    def search(self, query: str, bas_dd: str | None = None, limit: int = 10) -> list[KoreanStockSearchResult]:
        payload = self._get("/v1/korean-stock/search", {"q": query, "bas_dd": bas_dd or recent_business_yyyymmdd(), "limit": limit})
        return [
            KoreanStockSearchResult(
                market=str(item.get("market", "")),
                code=str(item.get("code", "")),
                name=str(item.get("name") or item.get("short_name") or ""),
                standard_code=item.get("standard_code"),
                listed_at=item.get("listed_at"),
            )
            for item in payload.get("items", [])
        ]

    def trade_info(self, market: str, code: str, bas_dd: str | None = None) -> KoreanStockTradeSnapshot:
        payload = self._get("/v1/korean-stock/trade-info", {"market": market, "code": code, "bas_dd": bas_dd or recent_business_yyyymmdd()})
        item = payload.get("item") or {}
        return KoreanStockTradeSnapshot(
            market=str(item.get("market") or market),
            code=str(item.get("code") or code),
            base_date=str(item.get("base_date") or bas_dd or today_yyyymmdd()),
            name=str(item.get("name") or ""),
            close_price=_float_or_none(item.get("close_price")),
            open_price=_float_or_none(item.get("open_price")),
            high_price=_float_or_none(item.get("high_price")),
            low_price=_float_or_none(item.get("low_price")),
            trading_volume=_float_or_none(item.get("trading_volume")),
            market_cap=_float_or_none(item.get("market_cap")),
            raw=item,
        )

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(f"{self.base_url}{path}", params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json()


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(str(value).replace(",", ""))
