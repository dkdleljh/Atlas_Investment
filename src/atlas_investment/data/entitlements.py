from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DataEntitlementRequirement:
    name: str
    status: str
    evidence: str


@dataclass(frozen=True)
class DataEntitlementReport:
    status: str
    provider_count: int
    requirements: list[DataEntitlementRequirement] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class DataEntitlementAuditor:
    REQUIRED_MARKETS = {"KR", "US", "EU", "JP", "HK", "CN", "EM"}
    REQUIRED_ASSET_KINDS = {"stock", "etf", "bond", "future", "option", "fx", "commodity"}

    def audit(self, root: Path) -> DataEntitlementReport:
        path = root / "config" / "data_entitlements.json"
        if not path.exists():
            return DataEntitlementReport(
                "blocked",
                0,
                [DataEntitlementRequirement("entitlement_config", "blocked", str(path))],
                ["Licensed data entitlement config is missing."],
            )

        payload = json.loads(path.read_text(encoding="utf-8"))
        providers = [provider for provider in payload.get("providers", []) if isinstance(provider, dict)]
        required_markets = set(payload.get("required_markets", self.REQUIRED_MARKETS))
        required_asset_kinds = set(payload.get("required_asset_kinds", self.REQUIRED_ASSET_KINDS))
        require_survivorship = bool(payload.get("require_survivorship_bias_free", True))
        require_corporate_actions = bool(payload.get("require_corporate_actions_adjusted", True))
        covered_markets: set[str] = set()
        covered_kinds: set[str] = set()
        survivorship = False
        corporate_actions = False
        realtime = False
        licensed = False
        for provider in providers:
            if provider.get("licensed") is True:
                licensed = True
            covered_markets.update(str(market) for market in provider.get("markets", []))
            covered_kinds.update(str(kind) for kind in provider.get("asset_kinds", []))
            survivorship = survivorship or bool(provider.get("survivorship_bias_free"))
            corporate_actions = corporate_actions or bool(provider.get("corporate_actions_adjusted"))
            realtime = realtime or bool(provider.get("realtime_quotes")) or bool(provider.get("realtime_order_book"))

        requirements = [
            self._require("licensed_provider", licensed, f"providers={len(providers)}"),
            self._require("required_markets", required_markets <= covered_markets, f"missing={sorted(required_markets - covered_markets)}; required={sorted(required_markets)}"),
            self._require("required_asset_kinds", required_asset_kinds <= covered_kinds, f"missing={sorted(required_asset_kinds - covered_kinds)}; required={sorted(required_asset_kinds)}"),
            self._require("survivorship_bias_free", (not require_survivorship) or survivorship, f"survivorship_bias_free={survivorship}; required={require_survivorship}"),
            self._require("corporate_actions_adjusted", (not require_corporate_actions) or corporate_actions, f"corporate_actions_adjusted={corporate_actions}; required={require_corporate_actions}"),
            self._require("realtime_market_data", realtime, f"realtime={realtime}"),
        ]
        status = "blocked" if any(requirement.status == "blocked" for requirement in requirements) else "ok"
        return DataEntitlementReport(
            status,
            len(providers),
            requirements,
            [
                "This checks declared licensed-data entitlements only.",
                "Provider contracts, credentials, and sample/yfinance fallbacks are not accepted as institutional live-data proof.",
                f"Required markets={sorted(required_markets)}, asset_kinds={sorted(required_asset_kinds)}.",
            ],
        )

    @staticmethod
    def _require(name: str, passed: bool, evidence: str) -> DataEntitlementRequirement:
        return DataEntitlementRequirement(name, "ok" if passed else "blocked", evidence)
