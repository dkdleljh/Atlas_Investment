from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from atlas_investment.brokers.toss_clients import TossApiConfig, TossApiReadiness, TossOfficialApiClient
from atlas_investment.integrations.dart import DartApiError, DartClient, classify_disclosure_event
from atlas_investment.integrations.korean_stock import KoreanStockClient
from atlas_investment.integrations.setup_check import IntegrationSetupChecker
from atlas_investment.integrations.vibe_catalog import RECOMMENDED_VIBE_SKILLS, build_skill_catalog


class IntegrationModulesTest(unittest.TestCase):
    @patch("atlas_investment.integrations.korean_stock.requests.get")
    def test_korean_stock_search_maps_proxy_payload(self, get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"items": [{"market": "KOSPI", "code": "005930", "name": "삼성전자"}]}
        get.return_value = response

        results = KoreanStockClient(base_url="https://example.test").search("삼성전자", bas_dd="20260529")

        self.assertEqual(results[0].code, "005930")
        self.assertEqual(results[0].market, "KOSPI")

    @patch("atlas_investment.integrations.korean_stock.requests.get")
    def test_korean_stock_trade_info_maps_numbers(self, get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"item": {"market": "KOSPI", "code": "005930", "name": "삼성전자", "close_price": "80,000"}}
        get.return_value = response

        snapshot = KoreanStockClient(base_url="https://example.test").trade_info("KOSPI", "005930", bas_dd="20260529")

        self.assertEqual(snapshot.close_price, 80000.0)

    @patch.dict("os.environ", {"API_K_DART": ""}, clear=False)
    def test_dart_readiness_blocks_without_key(self) -> None:
        readiness = DartClient(api_key=None).readiness()
        self.assertEqual(readiness.status, "blocked")

    @patch("atlas_investment.integrations.dart.requests.get")
    def test_dart_disclosures_adds_api_key(self, get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"status": "000", "list": []}
        get.return_value = response

        payload = DartClient(api_key="test-key").disclosures(days=1)

        self.assertEqual(payload["status"], "000")
        self.assertIn("crtfc_key", get.call_args.kwargs["params"])

    @patch("atlas_investment.integrations.dart.requests.get")
    def test_dart_disclosures_raises_on_api_error_status(self, get: Mock) -> None:
        response = Mock()
        response.json.return_value = {"status": "010", "message": "등록되지 않은 키입니다."}
        get.return_value = response

        with self.assertRaises(DartApiError):
            DartClient(api_key="bad-key").disclosures(days=1)

    def test_vibe_catalog_has_operational_recommendations(self) -> None:
        names = {skill.name for skill in RECOMMENDED_VIBE_SKILLS}
        self.assertIn("risk-analysis", names)
        self.assertIn("asset-allocation", names)

    def test_skill_catalog_connects_local_finance_and_mcp_bindings(self) -> None:
        catalog = build_skill_catalog()
        names = {skill.name for skill in catalog}
        self.assertIn("korean-stock-search", names)
        self.assertIn("k-dart", names)
        self.assertIn("github-mcp", names)
        self.assertTrue(any(skill.status == "connected" for skill in catalog if skill.kind == "local_skill"))

    def test_dart_event_signal_classifies_earnings(self) -> None:
        signal = classify_disclosure_event(
            {
                "corp_code": "00126380",
                "corp_name": "삼성전자",
                "report_nm": "영업실적 등에 대한 전망",
                "rcept_dt": "20260531",
                "rcept_no": "20260531000001",
            }
        )
        self.assertEqual(signal.category, "earnings")
        self.assertEqual(signal.importance, "high")

    def test_integration_setup_checker_returns_report(self) -> None:
        report = IntegrationSetupChecker().run()
        self.assertGreaterEqual(len(report.items), 1)
        self.assertIn(report.overall_status, {"ok", "degraded"})
        self.assertIn("local-skills", {item.name for item in report.items})
        self.assertIn("mcp-bindings", {item.name for item in report.items})

    def test_toss_readiness_accepts_official_subdomain(self) -> None:
        config = TossApiConfig(
            docs_url="https://developers.tossinvest.com/llms.txt",
            rest_base_url="https://openapi.tossinvest.com",
            client_id="client",
            client_secret="secret",
        )

        report = TossApiReadiness().check(config)

        self.assertTrue(report.official_docs_verified)
        self.assertEqual(report.status, "manual_review_required")
        self.assertNotIn("공식 WebSocket URL", report.missing_items)
        self.assertIn("latest/openapi.json", config.openapi_spec_url)

    def test_toss_official_rate_limit_policy_matches_docs(self) -> None:
        limits = TossOfficialApiClient.RATE_LIMITS_TPS

        self.assertEqual(limits["AUTH"], 5.0)
        self.assertEqual(limits["ACCOUNT"], 1.0)
        self.assertEqual(limits["ASSET"], 5.0)
        self.assertEqual(limits["STOCK"], 5.0)
        self.assertEqual(limits["MARKET_INFO"], 3.0)
        self.assertEqual(limits["MARKET_DATA"], 10.0)
        self.assertEqual(limits["MARKET_DATA_CHART"], 5.0)
        self.assertEqual(limits["ORDER"], 6.0)
        self.assertEqual(limits["ORDER_HISTORY"], 5.0)
        self.assertEqual(limits["ORDER_INFO"], 6.0)

    def test_toss_official_client_exports_readonly_snapshots(self) -> None:
        config = TossApiConfig(
            rest_base_url="https://api.tossinvest.test",
            client_id="client",
            client_secret="secret",
            rate_limit_enabled=False,
        )
        session = Mock()
        responses = []
        for payload in [
            {"access_token": "token", "token_type": "Bearer", "expires_in": 3600},
            {"result": [{"accountNo": "12345678901", "accountSeq": 1, "accountType": "BROKERAGE"}]},
            {"result": {"currency": "KRW", "cashBuyingPower": "260"}},
            {"result": {"currency": "USD", "cashBuyingPower": "0.11"}},
            {"result": {"items": [{"symbol": "005930", "quantity": "1"}]}},
            {"result": {"orders": [], "nextCursor": None, "hasNext": False}},
        ]:
            response = Mock()
            response.json.return_value = payload
            response.raise_for_status.return_value = None
            response.status_code = 200
            response.headers = {}
            responses.append(response)
        session.request.side_effect = responses

        with tempfile.TemporaryDirectory() as tmp:
            written = TossOfficialApiClient(config, session=session).export_readonly_snapshots(Path(tmp))

            self.assertIn("positions.json", written)
            self.assertIn("accounts.json", written)
            self.assertIn("account_summary.json", written)
            self.assertIn("buying_power.json", written)
            self.assertTrue(Path(written["account.json"]).exists())
            self.assertEqual(session.request.call_count, 6)
            account_call_headers = session.request.call_args_list[2].kwargs["headers"]
            self.assertEqual(account_call_headers["X-Tossinvest-Account"], "1")
            summary = Path(written["account_summary.json"]).read_text(encoding="utf-8")
            self.assertIn('"KRW": 260.0', summary)

    @patch.dict("os.environ", {"TOSS_API_KEY": "api-key", "TOSS_SECRET_KEY": "secret-key", "TOSS_CLIENT_ID": "", "TOSS_CLIENT_SECRET": ""}, clear=False)
    def test_toss_config_reads_api_key_secret_aliases(self) -> None:
        config = TossApiConfig.from_env()

        self.assertEqual(config.client_id, "api-key")
        self.assertEqual(config.client_secret, "secret-key")

    def test_toss_official_client_uses_dynamic_rate_limit_headers(self) -> None:
        config = TossApiConfig(
            rest_base_url="https://api.tossinvest.test",
            client_id="client",
            client_secret="secret",
            rate_limit_enabled=True,
        )
        session = Mock()
        token_response = Mock()
        token_response.json.return_value = {"access_token": "token", "token_type": "Bearer", "expires_in": 3600}
        token_response.raise_for_status.return_value = None
        token_response.status_code = 200
        token_response.headers = {"X-RateLimit-Limit": "2"}
        price_response = Mock()
        price_response.json.return_value = {"result": []}
        price_response.raise_for_status.return_value = None
        price_response.status_code = 200
        price_response.headers = {"X-RateLimit-Limit": "4", "X-RateLimit-Remaining": "1"}
        session.request.side_effect = [token_response, price_response]

        client = TossOfficialApiClient(config, session=session)
        client.get_prices(["005930"])

        self.assertEqual(client._observed_rate_limits["AUTH"], 2.0)
        self.assertEqual(client._observed_rate_limits["MARKET_DATA"], 4.0)
        self.assertEqual(client._rate_limit_for("MARKET_DATA"), 4.0)

    def test_toss_official_order_info_methods_match_docs(self) -> None:
        config = TossApiConfig(
            rest_base_url="https://api.tossinvest.test",
            client_id="client",
            client_secret="secret",
            account_seq="1",
            rate_limit_enabled=False,
        )
        session = Mock()
        responses = []
        for payload in [
            {"access_token": "token", "token_type": "Bearer", "expires_in": 3600},
            {"result": {"currency": "KRW", "cashBuyingPower": "5000000"}},
            {"result": {"sellableQuantity": "100"}},
            {"result": [{"marketCountry": "KR", "commissionRate": "0.015"}]},
        ]:
            response = Mock()
            response.json.return_value = payload
            response.raise_for_status.return_value = None
            response.status_code = 200
            response.headers = {}
            responses.append(response)
        session.request.side_effect = responses

        client = TossOfficialApiClient(config, session=session)

        self.assertEqual(client.get_buying_power("krw")["cashBuyingPower"], "5000000")
        self.assertEqual(client.get_sellable_quantity("005930")["sellableQuantity"], "100")
        self.assertEqual(client.get_commissions()[0]["marketCountry"], "KR")
        self.assertEqual(session.request.call_args_list[1].kwargs["params"], {"currency": "KRW"})
        self.assertEqual(session.request.call_args_list[2].kwargs["params"], {"symbol": "005930"})

    def test_toss_official_client_create_order_matches_docs(self) -> None:
        config = TossApiConfig(
            rest_base_url="https://api.tossinvest.test",
            client_id="client",
            client_secret="secret",
            account_seq="1",
            rate_limit_enabled=False,
        )
        session = Mock()
        responses = []
        for payload in [
            {"access_token": "token", "token_type": "Bearer", "expires_in": 3600},
            {"result": {"orderId": "order-1", "clientOrderId": "atlas-1"}},
        ]:
            response = Mock()
            response.json.return_value = payload
            response.raise_for_status.return_value = None
            response.status_code = 200
            response.headers = {}
            responses.append(response)
        session.request.side_effect = responses

        result = TossOfficialApiClient(config, session=session).create_order(
            symbol="SCHD",
            side="BUY",
            order_type="MARKET",
            order_amount="10",
            client_order_id="atlas-1",
        )

        self.assertEqual(result["orderId"], "order-1")
        order_call = session.request.call_args_list[1]
        self.assertEqual(order_call.args[0], "POST")
        self.assertEqual(order_call.kwargs["headers"]["X-Tossinvest-Account"], "1")
        self.assertEqual(
            order_call.kwargs["json"],
            {
                "symbol": "SCHD",
                "side": "BUY",
                "orderType": "MARKET",
                "orderAmount": "10",
                "clientOrderId": "atlas-1",
            },
        )

    def test_toss_order_payload_requires_quantity_or_amount(self) -> None:
        with self.assertRaises(ValueError):
            TossOfficialApiClient._build_order_payload(
                symbol="SCHD",
                side="BUY",
                order_type="MARKET",
            )


if __name__ == "__main__":
    unittest.main()
