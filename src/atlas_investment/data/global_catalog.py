from __future__ import annotations

from dataclasses import dataclass, field

from atlas_investment.models import AssetKind, Market


@dataclass(frozen=True)
class CoverageRequirement:
    name: str
    required: list[str]
    covered: list[str]

    @property
    def missing(self) -> list[str]:
        return sorted(set(self.required) - set(self.covered))

    @property
    def status(self) -> str:
        return "ok" if not self.missing else "blocked"


@dataclass(frozen=True)
class GlobalCoverageReport:
    status: str
    market_requirement: CoverageRequirement
    asset_kind_requirement: CoverageRequirement
    notes: list[str] = field(default_factory=list)


class GlobalCoverageModel:
    """Static model coverage, separate from live tradable universe coverage."""

    REQUIRED_MARKETS = ["KR", "US", "EU", "JP", "HK", "CN", "EM"]
    REQUIRED_ASSET_KINDS = ["stock", "etf", "bond", "future", "option", "fx", "commodity"]

    def report(self) -> GlobalCoverageReport:
        market_requirement = CoverageRequirement(
            "market_model_coverage",
            self.REQUIRED_MARKETS,
            [market.value for market in Market if market != Market.GLOBAL],
        )
        asset_kind_requirement = CoverageRequirement(
            "asset_kind_model_coverage",
            self.REQUIRED_ASSET_KINDS,
            [kind.value for kind in AssetKind],
        )
        status = "ok" if market_requirement.status == "ok" and asset_kind_requirement.status == "ok" else "blocked"
        return GlobalCoverageReport(
            status=status,
            market_requirement=market_requirement,
            asset_kind_requirement=asset_kind_requirement,
            notes=[
                "This verifies domain model coverage only, not real tradable instrument coverage.",
                "Live readiness still requires a full licensed instrument master and broker support.",
            ],
        )
