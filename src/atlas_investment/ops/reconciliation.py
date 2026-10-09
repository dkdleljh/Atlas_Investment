from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ReconciliationDifference:
    code: str
    message: str
    severity: str = "blocked"


@dataclass(frozen=True)
class ReconciliationReport:
    status: str
    internal_order_count: int
    broker_position_count: int
    internal_position_count: int = 0
    internal_open_order_count: int = 0
    broker_open_order_count: int = 0
    broker_fill_count: int = 0
    broker_cash_krw: float | None = None
    broker_cash_by_currency: dict[str, float] = field(default_factory=dict)
    differences: list[ReconciliationDifference] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class ReadOnlyReconciler:
    """Compares internal state with official broker snapshots before live promotion."""

    def reconcile(self, root: Path, order_state_path: Path | None = None) -> ReconciliationReport:
        order_state_path = order_state_path or self._default_order_state_path(root)
        broker_root = root / "data" / "official_broker_snapshots" / "toss"
        broker_positions_path = broker_root / "positions.json"
        broker_open_orders_path = broker_root / "open_orders.json"
        broker_fills_path = broker_root / "fills.json"
        broker_account_path = self._first_existing(
            broker_root / "account_summary.json",
            broker_root / "account.json",
        )
        differences: list[ReconciliationDifference] = []

        internal_orders = self._load_json_list(order_state_path)
        broker_positions = self._load_json_list(broker_positions_path)
        broker_open_orders = self._load_json_list(broker_open_orders_path)
        broker_fills = self._load_json_list(broker_fills_path)
        broker_account = self._load_json_dict(broker_account_path)

        if not order_state_path.exists():
            differences.append(ReconciliationDifference("missing_internal_order_state", f"내부 주문 상태 파일이 없습니다: {order_state_path}"))
        if not broker_positions_path.exists():
            differences.append(ReconciliationDifference("missing_broker_positions", f"토스 공식 API 포지션 스냅샷이 없습니다: {broker_positions_path}"))

        active_internal_symbols = {str(order.get("symbol")) for order in internal_orders if str(order.get("status")) == "filled"}
        broker_symbols = {str(position.get("symbol") or position.get("ticker") or position.get("code")) for position in broker_positions}
        broker_symbols.discard("None")
        internal_position_qty = self._internal_filled_quantities(internal_orders)
        internal_open_orders = self._internal_open_orders(internal_orders)
        broker_position_qty = self._broker_quantities(broker_positions)
        broker_open_keys = self._broker_order_keys(broker_open_orders)
        broker_fill_keys = self._broker_order_keys(broker_fills)
        broker_cash_by_currency = self._extract_cash_by_currency(broker_account)
        broker_cash_krw = self._extract_cash_krw(broker_account)

        missing_in_broker = sorted(active_internal_symbols - broker_symbols)
        unknown_in_internal = sorted(broker_symbols - active_internal_symbols) if active_internal_symbols else sorted(broker_symbols)
        if missing_in_broker:
            differences.append(ReconciliationDifference("missing_in_broker_snapshot", f"내부 활성 주문/보유 종목이 broker 스냅샷에 없습니다: {missing_in_broker}"))
        if unknown_in_internal:
            differences.append(ReconciliationDifference("unknown_broker_positions", f"broker 포지션이 내부 주문 상태와 연결되지 않습니다: {unknown_in_internal}", "degraded"))
        for symbol, quantity in internal_position_qty.items():
            broker_quantity = broker_position_qty.get(symbol)
            if broker_quantity is None:
                differences.append(ReconciliationDifference("filled_position_missing_in_broker", f"내부 filled 수량이 broker 포지션에 없습니다: {symbol} {quantity}"))
            elif abs(quantity - broker_quantity) > 1e-6:
                differences.append(
                    ReconciliationDifference(
                        "position_quantity_mismatch",
                        f"{symbol} 수량 불일치: internal={quantity}, broker={broker_quantity}",
                    )
                )
        if broker_cash_krw is None and broker_account_path.exists():
            differences.append(ReconciliationDifference("broker_cash_unreadable", f"broker account 스냅샷에서 현금 값을 읽지 못했습니다: {broker_account_path}", "degraded"))
        if broker_account_path.exists() and not broker_cash_by_currency:
            differences.append(ReconciliationDifference("broker_cash_by_currency_unreadable", f"broker account 스냅샷에서 통화별 현금 값을 읽지 못했습니다: {broker_account_path}", "degraded"))
        if internal_open_orders and not broker_open_orders_path.exists():
            differences.append(ReconciliationDifference("missing_broker_open_orders", f"내부 미체결/제출 주문이 있지만 broker open orders 스냅샷이 없습니다: {broker_open_orders_path}"))
        if broker_open_orders_path.exists():
            missing_open = sorted(self._order_identity(order) for order in internal_open_orders if self._order_identity(order) not in broker_open_keys)
            unknown_open = sorted(broker_open_keys - {self._order_identity(order) for order in internal_open_orders})
            if missing_open:
                differences.append(ReconciliationDifference("open_order_missing_in_broker", f"내부 open order가 broker 스냅샷에 없습니다: {missing_open}"))
            if unknown_open:
                differences.append(ReconciliationDifference("unknown_broker_open_orders", f"broker open order가 내부 주문 상태와 연결되지 않습니다: {unknown_open}", "degraded"))
        filled_orders = [order for order in internal_orders if str(order.get("status")) == "filled"]
        filled_keys = {self._order_identity(order) for order in filled_orders}
        position_supported_filled_keys = {
            self._order_identity(order)
            for order in filled_orders
            if self._filled_order_supported_by_position(order, broker_position_qty)
        }
        if filled_keys and not broker_fills_path.exists():
            missing_without_position = sorted(filled_keys - position_supported_filled_keys)
            if missing_without_position:
                differences.append(ReconciliationDifference("missing_broker_fills", f"내부 filled 주문이 있지만 broker fills 스냅샷이 없습니다: {broker_fills_path}"))
        if broker_fills_path.exists():
            missing_fills = sorted(filled_keys - broker_fill_keys - position_supported_filled_keys)
            if missing_fills:
                differences.append(ReconciliationDifference("filled_order_missing_in_broker_fills", f"내부 filled 주문이 broker fills에 없습니다: {missing_fills}"))

        status = "blocked" if any(diff.severity == "blocked" for diff in differences) else ("degraded" if differences else "ok")
        return ReconciliationReport(
            status=status,
            internal_order_count=len(internal_orders),
            broker_position_count=len(broker_positions),
            internal_position_count=len(internal_position_qty),
            internal_open_order_count=len(internal_open_orders),
            broker_open_order_count=len(broker_open_orders),
            broker_fill_count=len(broker_fills),
            broker_cash_krw=broker_cash_krw,
            broker_cash_by_currency=broker_cash_by_currency,
            differences=differences,
            notes=[
                "이 검사는 공식 브로커 API에서 생성한 스냅샷만 사용하며 주문을 전송하지 않습니다.",
                f"내부 주문 상태 기준 파일: {order_state_path}",
                "실거래 승격 전 최소 10거래일 동안 내부 주문/포지션/현금/미체결/체결 스냅샷의 차이가 없어야 합니다.",
            ],
        )

    @staticmethod
    def _default_order_state_path(root: Path) -> Path:
        live_path = root / "data" / "orders" / "live_order_state_store.json"
        if live_path.exists():
            return live_path
        return root / "data" / "orders" / "runtime_order_state_store.json"

    @staticmethod
    def _load_json_list(path: Path) -> list[dict]:
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("positions", "orders", "items", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _first_existing(*paths: Path) -> Path:
        for path in paths:
            if path.exists():
                return path
        return paths[0]

    @staticmethod
    def _load_json_dict(path: Path) -> dict:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _internal_filled_quantities(orders: list[dict]) -> dict[str, float]:
        quantities: dict[str, float] = {}
        for order in orders:
            if str(order.get("status")) != "filled":
                continue
            symbol = str(order.get("symbol"))
            quantity = float(order.get("quantity") or 0)
            side = str(order.get("side"))
            quantities[symbol] = quantities.get(symbol, 0.0) + (quantity if side == "buy" else -quantity)
        return {symbol: quantity for symbol, quantity in quantities.items() if quantity > 1e-6}

    @staticmethod
    def _internal_open_orders(orders: list[dict]) -> list[dict]:
        open_statuses = {"submitted", "partially_filled", "cancel_request_requested", "cancel_requested"}
        return [order for order in orders if str(order.get("status")) in open_statuses]

    @staticmethod
    def _filled_order_supported_by_position(order: dict, broker_position_qty: dict[str, float]) -> bool:
        symbol = str(order.get("symbol"))
        if not symbol or symbol == "None":
            return False
        if str(order.get("side")) != "buy":
            return False
        try:
            quantity = float(order.get("quantity") or 0)
        except (TypeError, ValueError):
            return False
        broker_quantity = broker_position_qty.get(symbol)
        return broker_quantity is not None and broker_quantity + 1e-6 >= quantity

    @staticmethod
    def _broker_quantities(positions: list[dict]) -> dict[str, float]:
        quantities: dict[str, float] = {}
        for position in positions:
            symbol = str(position.get("symbol") or position.get("ticker") or position.get("code"))
            if symbol == "None":
                continue
            raw_quantity = position.get("quantity", position.get("qty", position.get("shares", position.get("balance"))))
            try:
                quantities[symbol] = float(raw_quantity)
            except (TypeError, ValueError):
                continue
        return quantities

    @classmethod
    def _broker_order_keys(cls, orders: list[dict]) -> set[str]:
        return {cls._order_identity(order) for order in orders if cls._order_identity(order)}

    @staticmethod
    def _order_identity(order: dict) -> str:
        for key in ("idempotency_key", "client_order_id", "clientOrderId", "order_id", "orderId", "id"):
            value = order.get(key)
            if value:
                return str(value)
        symbol = order.get("symbol") or order.get("ticker") or order.get("code")
        side = order.get("side") or order.get("order_side")
        quantity = order.get("quantity") or order.get("qty") or order.get("shares")
        if symbol and side and quantity:
            return f"{symbol}:{side}:{quantity}"
        return ""

    @staticmethod
    def _extract_cash_by_currency(account: dict) -> dict[str, float]:
        result: dict[str, float] = {}
        direct = account.get("cash_by_currency")
        if isinstance(direct, dict):
            for currency, value in direct.items():
                try:
                    result[str(currency).upper()] = float(value)
                except (TypeError, ValueError):
                    continue
        balances = account.get("balances") or account.get("cash_balances") or account.get("cash")
        if isinstance(balances, list):
            for row in balances:
                if not isinstance(row, dict):
                    continue
                currency = row.get("currency") or row.get("ccy")
                value = row.get("cash") or row.get("amount") or row.get("balance") or row.get("available")
                if currency is None:
                    continue
                try:
                    result[str(currency).upper()] = float(value)
                except (TypeError, ValueError):
                    continue
        for currency, key in {"KRW": "cash_krw", "USD": "cash_usd"}.items():
            if currency in result:
                continue
            value = account.get(key)
            try:
                if value is not None:
                    result[currency] = float(value)
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    def _extract_cash_krw(account: dict) -> float | None:
        cash_by_currency = ReadOnlyReconciler._extract_cash_by_currency(account)
        if "KRW" in cash_by_currency:
            return cash_by_currency["KRW"]
        for key in ("cash_krw", "krw_cash", "available_cash_krw", "withdrawable_krw"):
            value = account.get(key)
            try:
                return None if value is None else float(value)
            except (TypeError, ValueError):
                continue
        return None
