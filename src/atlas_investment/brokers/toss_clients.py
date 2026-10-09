from __future__ import annotations

import os
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests


@dataclass(frozen=True)
class TossApiConfig:
    docs_url: str | None = "https://developers.tossinvest.com/llms.txt"
    openapi_spec_url: str = "https://openapi.tossinvest.com/openapi-docs/latest/openapi.json"
    rest_base_url: str = "https://openapi.tossinvest.com"
    client_id: str | None = None
    client_secret: str | None = None
    account_seq: str | None = None
    token_path: str = "/oauth2/token"
    accounts_path: str = "/api/v1/accounts"
    holdings_path: str = "/api/v1/holdings"
    prices_path: str = "/api/v1/prices"
    orders_path: str = "/api/v1/orders"
    stocks_path: str = "/api/v1/stocks"
    orderbook_path: str = "/api/v1/orderbook"
    buying_power_path: str = "/api/v1/buying-power"
    sellable_quantity_path: str = "/api/v1/sellable-quantity"
    commissions_path: str = "/api/v1/commissions"
    timeout_seconds: float = 10.0
    max_retries: int = 2
    rate_limit_enabled: bool = True

    @classmethod
    def from_env(cls) -> "TossApiConfig":
        return cls(
            docs_url=os.getenv("TOSS_API_DOCS_URL") or "https://developers.tossinvest.com/llms.txt",
            openapi_spec_url=os.getenv("TOSS_API_OPENAPI_SPEC_URL")
            or "https://openapi.tossinvest.com/openapi-docs/latest/openapi.json",
            rest_base_url=os.getenv("TOSS_API_REST_BASE_URL") or "https://openapi.tossinvest.com",
            client_id=os.getenv("TOSS_API_KEY") or os.getenv("TOSS_CLIENT_ID") or os.getenv("TOSS_API_CLIENT_ID") or os.getenv("TOSS_API_APP_KEY"),
            client_secret=os.getenv("TOSS_SECRET_KEY") or os.getenv("TOSS_CLIENT_SECRET") or os.getenv("TOSS_API_CLIENT_SECRET") or os.getenv("TOSS_API_APP_SECRET"),
            account_seq=os.getenv("TOSS_ACCOUNT_SEQ") or os.getenv("TOSS_API_ACCOUNT_SEQ") or os.getenv("TOSS_API_ACCOUNT_ID"),
            token_path=os.getenv("TOSS_API_TOKEN_PATH") or "/oauth2/token",
            accounts_path=os.getenv("TOSS_API_ACCOUNTS_PATH") or "/api/v1/accounts",
            holdings_path=os.getenv("TOSS_API_HOLDINGS_PATH") or "/api/v1/holdings",
            prices_path=os.getenv("TOSS_API_PRICES_PATH") or "/api/v1/prices",
            orders_path=os.getenv("TOSS_API_ORDERS_PATH") or "/api/v1/orders",
            stocks_path=os.getenv("TOSS_API_STOCKS_PATH") or "/api/v1/stocks",
            orderbook_path=os.getenv("TOSS_API_ORDERBOOK_PATH") or "/api/v1/orderbook",
            buying_power_path=os.getenv("TOSS_API_BUYING_POWER_PATH") or "/api/v1/buying-power",
            sellable_quantity_path=os.getenv("TOSS_API_SELLABLE_QUANTITY_PATH") or "/api/v1/sellable-quantity",
            commissions_path=os.getenv("TOSS_API_COMMISSIONS_PATH") or "/api/v1/commissions",
            timeout_seconds=float(os.getenv("TOSS_API_TIMEOUT_SECONDS", "10")),
            max_retries=int(os.getenv("TOSS_API_MAX_RETRIES", "2")),
            rate_limit_enabled=os.getenv("TOSS_API_RATE_LIMIT_ENABLED", "1") not in {"0", "false", "False"},
        )


@dataclass(frozen=True)
class TossReadinessReport:
    ready_for_live_orders: bool
    status: str
    missing_items: list[str]
    notes: list[str]
    official_docs_verified: bool = False


class TossApiReadiness:
    OFFICIAL_DOMAIN_SUFFIXES = ("tossinvest.com", "toss.im")

    def check(self, config: TossApiConfig) -> TossReadinessReport:
        missing: list[str] = []
        official_docs_verified = self._is_official_docs_url(config.docs_url)
        if not config.docs_url:
            missing.append("공식 API 문서 URL")
        elif not official_docs_verified:
            missing.append("토스증권 공식 도메인의 API 문서 URL")
        if not self._is_official_docs_url(config.openapi_spec_url):
            missing.append("토스증권 공식 OpenAPI JSON URL")
        if not config.rest_base_url:
            missing.append("공식 REST API base URL")
        if not config.client_id:
            missing.append("공식 API key")
        if not config.client_secret:
            missing.append("공식 secret key")
        notes = [
            "이 점검은 준비도만 확인하며 네트워크 호출이나 주문 전송을 하지 않습니다.",
            "토스증권 공식 문서 기준 Open API는 REST only이며 WebSocket URL은 요구하지 않습니다.",
            f"공식 OpenAPI JSON source of truth: {config.openapi_spec_url}",
            "모든 호출은 OAuth2 Client Credentials Grant로 발급한 access token을 Authorization: Bearer 헤더로 전달합니다.",
            "계좌·자산·주문 API는 X-Tossinvest-Account 헤더가 필요하며, accountSeq가 없으면 계좌 목록에서 첫 BROKERAGE 계좌를 자동 선택합니다.",
            "공식 문서와 지원되는 주문 API가 확인되어도 LIVE_AUTO는 별도 승격 전까지 차단 상태여야 합니다.",
            "비공식/역공학 API, 브라우저 자동화 주문, 화면 스크래핑 주문은 실거래 경로로 인정하지 않습니다.",
            "미수/신용 주문은 API가 제공되더라도 Atlas Investment 정책상 허용하지 않습니다.",
        ]
        if missing:
            return TossReadinessReport(False, "blocked", missing, notes, official_docs_verified)
        return TossReadinessReport(
            False,
            "manual_review_required",
            [],
            notes + ["환경 변수는 있으나 공식 문서 검토와 소액 검증 전까지 자동 실거래는 비활성입니다."],
            official_docs_verified,
        )

    def _is_official_docs_url(self, docs_url: str | None) -> bool:
        if not docs_url:
            return False
        parsed = urlparse(docs_url)
        host = parsed.netloc.lower()
        return parsed.scheme == "https" and any(host == suffix or host.endswith(f".{suffix}") for suffix in self.OFFICIAL_DOMAIN_SUFFIXES)


class TossOfficialApiClient:
    """Official Toss Securities REST client based on OpenAPI v1.1.1."""

    RATE_LIMITS_TPS = {
        "AUTH": 5.0,
        "ACCOUNT": 1.0,
        "ASSET": 5.0,
        "STOCK": 5.0,
        "MARKET_INFO": 3.0,
        "MARKET_DATA": 10.0,
        "MARKET_DATA_CHART": 5.0,
        "ORDER": 6.0,
        "ORDER_HISTORY": 5.0,
        "ORDER_INFO": 6.0,
    }

    def __init__(self, config: TossApiConfig | None = None, session: requests.Session | None = None) -> None:
        self.config = config or TossApiConfig.from_env()
        self.session = session or requests.Session()
        self._access_token: str | None = None
        self._token_expires_at = 0.0
        self._last_request_at: dict[str, float] = {}
        self._accounts_cache: list[dict[str, Any]] | None = None
        self._observed_rate_limits: dict[str, float] = {}
        self._rate_limit_lock = threading.Lock()

    def readiness(self) -> TossReadinessReport:
        return TossApiReadiness().check(self.config)

    def issue_token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token
        if not self.config.client_id or not self.config.client_secret:
            raise RuntimeError("토스증권 공식 API key / secret key가 설정되지 않았습니다.")
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        response = self._request_raw(
            "POST",
            self.config.token_path,
            group="AUTH",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            authenticated=False,
            account_required=False,
        )
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("토스증권 OAuth2 토큰 응답에 access_token이 없습니다.")
        self._access_token = str(token)
        self._token_expires_at = time.time() + float(data.get("expires_in", 0))
        return self._access_token

    def get_accounts(self) -> list[dict[str, Any]]:
        if self._accounts_cache is None:
            self._accounts_cache = self._as_list(self._get(self.config.accounts_path, group="ACCOUNT"))
        return list(self._accounts_cache)

    def get_account(self) -> dict[str, Any]:
        accounts = self.get_accounts()
        return self._select_account(accounts)

    def get_positions(self) -> list[dict[str, Any]]:
        payload = self._get(self.config.holdings_path, group="ASSET", account_required=True)
        result = self._unwrap_result(payload)
        if isinstance(result, dict):
            return self._as_list(result.get("items"))
        return []

    def get_open_orders(self) -> list[dict[str, Any]]:
        payload = self._get(self.config.orders_path, group="ORDER_HISTORY", account_required=True, params={"status": "OPEN"})
        result = self._unwrap_result(payload)
        if isinstance(result, dict):
            return self._as_list(result.get("orders"))
        return []

    def get_fills(self) -> list[dict[str, Any]]:
        # The official v1.1.1 document has no standalone fills endpoint.
        # Executions are embedded under order.execution, and CLOSED history is
        # documented as currently unsupported, so we do not synthesize data here.
        return []

    def get_quote(self, symbol: str) -> dict[str, Any]:
        prices = self.get_prices([symbol])
        return prices[0] if prices else {}

    def get_prices(self, symbols: list[str]) -> list[dict[str, Any]]:
        if not symbols:
            return []
        if len(symbols) > 200:
            raise ValueError("토스증권 현재가 조회는 공식 문서 기준 최대 200개 심볼까지 지원합니다.")
        joined = ",".join(symbol.strip() for symbol in symbols if symbol.strip())
        return self._as_list(self._get(self.config.prices_path, group="MARKET_DATA", params={"symbols": joined}))

    def get_stocks(self, symbols: list[str]) -> list[dict[str, Any]]:
        if not symbols:
            return []
        joined = ",".join(symbol.strip() for symbol in symbols if symbol.strip())
        return self._as_list(self._get(self.config.stocks_path, group="STOCK", params={"symbols": joined}))

    def get_orderbook(self, symbol: str) -> dict[str, Any]:
        return self._unwrap_result(self._get(self.config.orderbook_path, group="MARKET_DATA", params={"symbol": symbol}))

    def get_buying_power(self, currency: str) -> dict[str, Any]:
        payload = self._get(
            self.config.buying_power_path,
            group="ORDER_INFO",
            account_required=True,
            params={"currency": currency.upper()},
        )
        return self._unwrap_result(payload) if isinstance(payload, dict) else {}

    def get_sellable_quantity(self, symbol: str) -> dict[str, Any]:
        payload = self._get(
            self.config.sellable_quantity_path,
            group="ORDER_INFO",
            account_required=True,
            params={"symbol": symbol},
        )
        return self._unwrap_result(payload) if isinstance(payload, dict) else {}

    def get_commissions(self) -> list[dict[str, Any]]:
        return self._as_list(self._get(self.config.commissions_path, group="ORDER_INFO", account_required=True))

    def create_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str | None = None,
        price: str | None = None,
        order_amount: str | None = None,
        time_in_force: str | None = None,
        client_order_id: str | None = None,
        confirm_high_value_order: bool = False,
    ) -> dict[str, Any]:
        payload = self._build_order_payload(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            order_amount=order_amount,
            time_in_force=time_in_force,
            client_order_id=client_order_id,
            confirm_high_value_order=confirm_high_value_order,
        )
        response = self._request_raw(
            "POST",
            self.config.orders_path,
            group="ORDER",
            json_payload=payload,
            account_required=True,
        )
        result = self._unwrap_result(response.json())
        return result if isinstance(result, dict) else {}

    def export_readonly_snapshots(self, root: Path) -> dict[str, str]:
        broker_root = root / "data" / "official_broker_snapshots" / "toss"
        broker_root.mkdir(parents=True, exist_ok=True)
        snapshots: dict[str, Any] = {
            "accounts.json": self.get_accounts(),
        }
        if snapshots["accounts.json"]:
            buying_power = {
                "KRW": self.get_buying_power("KRW"),
                "USD": self.get_buying_power("USD"),
            }
            cash_by_currency = {
                currency: float(payload.get("cashBuyingPower") or 0)
                for currency, payload in buying_power.items()
            }
            snapshots.update(
                {
                    "account.json": self.get_account(),
                    "account_summary.json": {
                        "cash_by_currency": cash_by_currency,
                        "source": "toss_openapi_buying_power",
                    },
                    "buying_power.json": buying_power,
                    "positions.json": self.get_positions(),
                    "open_orders.json": self.get_open_orders(),
                    "fills.json": self.get_fills(),
                }
            )
        written: dict[str, str] = {}
        for filename, payload in snapshots.items():
            path = broker_root / filename
            path.write_text(self._json_dumps(payload), encoding="utf-8")
            written[filename] = str(path)
        return written

    def _get(self, path: str, group: str, params: dict[str, str] | None = None, account_required: bool = False) -> Any:
        response = self._request_raw("GET", path, group=group, params=params, account_required=account_required)
        return response.json()

    def _request_raw(
        self,
        method: str,
        path: str,
        group: str,
        params: dict[str, str] | None = None,
        data: dict[str, str] | None = None,
        json_payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        authenticated: bool = True,
        account_required: bool = False,
    ) -> requests.Response:
        url = self._build_url(path)
        request_headers = {"Accept": "application/json", "User-Agent": "AtlasInvestment/0.1 official-toss-openapi"}
        request_headers.update(headers or {})
        if authenticated:
            request_headers["Authorization"] = f"Bearer {self.issue_token()}"
        if account_required:
            request_headers["X-Tossinvest-Account"] = self._account_seq()
        for attempt in range(self.config.max_retries + 1):
            self._wait_for_rate_limit(group)
            response = self.session.request(
                method,
                url,
                params=params,
                data=data,
                json=json_payload,
                headers=request_headers,
                timeout=self.config.timeout_seconds,
            )
            self._record_rate_limit_headers(group, response)
            if response.status_code != 429 or attempt >= self.config.max_retries:
                self._raise_for_error(response)
                self._slow_down_if_bucket_empty(response)
                return response
            self._sleep_after_429(response, attempt)
        raise RuntimeError("토스증권 API 재시도 처리에 실패했습니다.")

    def _build_url(self, path: str) -> str:
        if not self.config.rest_base_url:
            raise RuntimeError("TOSS_API_REST_BASE_URL이 설정되지 않았습니다.")
        if path.startswith("https://"):
            return path
        return f"{self.config.rest_base_url.rstrip('/')}/{path.lstrip('/')}"

    def _account_seq(self) -> str:
        if self.config.account_seq:
            return str(self.config.account_seq)
        account = self.get_account()
        account_seq = account.get("accountSeq")
        if account_seq is None:
            raise RuntimeError("토스증권 계좌 목록에서 accountSeq를 찾지 못했습니다.")
        return str(account_seq)

    def _select_account(self, accounts: list[dict[str, Any]]) -> dict[str, Any]:
        if self.config.account_seq:
            for account in accounts:
                if str(account.get("accountSeq")) == str(self.config.account_seq):
                    return account
        for account in accounts:
            if str(account.get("accountType")) == "BROKERAGE":
                return account
        return accounts[0] if accounts else {}

    @staticmethod
    def _build_order_payload(
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str | None = None,
        price: str | None = None,
        order_amount: str | None = None,
        time_in_force: str | None = None,
        client_order_id: str | None = None,
        confirm_high_value_order: bool = False,
    ) -> dict[str, Any]:
        normalized_side = side.upper()
        normalized_order_type = order_type.upper()
        if normalized_side not in {"BUY", "SELL"}:
            raise ValueError("side는 BUY 또는 SELL이어야 합니다.")
        if normalized_order_type not in {"LIMIT", "MARKET"}:
            raise ValueError("order_type은 LIMIT 또는 MARKET이어야 합니다.")
        if bool(quantity) == bool(order_amount):
            raise ValueError("quantity 또는 order_amount 중 정확히 하나만 지정해야 합니다.")
        if normalized_order_type == "LIMIT" and not price:
            raise ValueError("LIMIT 주문에는 price가 필요합니다.")
        if normalized_order_type == "MARKET" and price:
            raise ValueError("MARKET 주문에는 price를 지정하지 않습니다.")
        payload: dict[str, Any] = {
            "symbol": symbol.upper(),
            "side": normalized_side,
            "orderType": normalized_order_type,
        }
        if quantity:
            payload["quantity"] = str(quantity)
        if price:
            payload["price"] = str(price)
        if order_amount:
            payload["orderAmount"] = str(order_amount)
        if time_in_force:
            payload["timeInForce"] = time_in_force.upper()
        if client_order_id:
            payload["clientOrderId"] = client_order_id
        if confirm_high_value_order:
            payload["confirmHighValueOrder"] = True
        return payload

    def _wait_for_rate_limit(self, group: str) -> None:
        if not self.config.rate_limit_enabled:
            return
        with self._rate_limit_lock:
            tps = self._rate_limit_for(group)
            if tps <= 0:
                return
            now = time.monotonic()
            min_interval = 1.0 / tps
            last = self._last_request_at.get(group)
            if last is not None:
                wait_seconds = min_interval - (now - last)
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
            self._last_request_at[group] = time.monotonic()

    def _rate_limit_for(self, group: str) -> float:
        documented = 3.0 if group in {"ORDER", "ORDER_INFO"} and self._is_order_peak_time() else self.RATE_LIMITS_TPS.get(group, 1.0)
        observed = self._observed_rate_limits.get(group)
        if observed and observed > 0:
            return min(documented, observed)
        return documented

    def _record_rate_limit_headers(self, group: str, response: requests.Response) -> None:
        limit = response.headers.get("X-RateLimit-Limit")
        if limit is None:
            return
        try:
            parsed = float(limit)
        except ValueError:
            return
        if parsed > 0:
            self._observed_rate_limits[group] = parsed

    @staticmethod
    def _slow_down_if_bucket_empty(response: requests.Response) -> None:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if remaining != "0" or reset is None:
            return
        try:
            delay = float(reset)
        except ValueError:
            return
        if delay > 0:
            time.sleep(min(delay, 2.0))

    @staticmethod
    def _is_order_peak_time() -> bool:
        now = datetime.now(ZoneInfo("Asia/Seoul")).time()
        return now.hour == 9 and 0 <= now.minute < 10

    @staticmethod
    def _sleep_after_429(response: requests.Response, attempt: int) -> None:
        retry_after = response.headers.get("Retry-After")
        try:
            delay = float(retry_after) if retry_after is not None else 0.0
        except ValueError:
            delay = 0.0
        if delay <= 0:
            delay = min(8.0, 2.0**attempt) + random.uniform(0, 0.25)
        time.sleep(delay)

    @staticmethod
    def _raise_for_error(response: requests.Response) -> None:
        if response.status_code < 400:
            return
        code = ""
        message = ""
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                code = str(error.get("code") or "")
                message = str(error.get("message") or "")
            else:
                code = str(payload.get("error") or "")
                message = str(payload.get("error_description") or payload.get("message") or "")
        request_id = response.headers.get("x-request-id") or response.headers.get("X-Request-Id") or response.headers.get("cf-ray")
        detail = str(response.status_code)
        if code:
            detail += f" {code}"
        if message:
            detail += f": {message}"
        if request_id:
            detail += f" (request_id={request_id})"
        raise RuntimeError(f"토스증권 API 호출 실패: {detail}")

    @staticmethod
    def _as_list(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            payload = TossOfficialApiClient._unwrap_result(payload)
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("positions", "orders", "fills", "items", "data", "result"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _unwrap_result(payload: Any) -> Any:
        if isinstance(payload, dict) and "result" in payload:
            return payload["result"]
        return payload

    @staticmethod
    def _json_dumps(payload: Any) -> str:
        import json

        return json.dumps(payload, ensure_ascii=False, indent=2)
