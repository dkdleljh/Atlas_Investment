from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from atlas_investment.models import AssetKind, Market


@dataclass(frozen=True)
class TossPlatformProfile:
    supported_markets: list[str]
    supported_asset_kinds: list[str]
    conditional_asset_kinds: dict[str, str] = field(default_factory=dict)
    excluded_asset_kinds: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "TossPlatformProfile":
        payload = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            supported_markets=list(payload.get("supported_markets", [])),
            supported_asset_kinds=list(payload.get("supported_asset_kinds", [])),
            conditional_asset_kinds=dict(payload.get("conditional_asset_kinds", {})),
            excluded_asset_kinds=list(payload.get("excluded_asset_kinds", [])),
            notes=list(payload.get("notes", [])),
        )


@dataclass(frozen=True)
class TossPlatformFitReport:
    status: str
    supported_markets: list[str]
    supported_asset_kinds: list[str]
    excluded_asset_kinds: list[str]
    api_dependent_steps: list[int]
    non_api_steps: list[int]
    notes: list[str]


class TossPlatformFitAuditor:
    """Maps Atlas completion requirements to Toss Securities' public product scope."""

    API_DEPENDENT_STEPS = [7, 8, 9, 10, 11, 12, 13]
    NON_API_STEPS = [1, 2, 3, 4, 5, 6]

    def audit(self, root: Path) -> TossPlatformFitReport:
        profile = TossPlatformProfile.load(root / "config" / "toss_platform_profile.json")
        required_for_toss = {"stock", "etf", "bond", "option"}
        missing = sorted(required_for_toss - set(profile.supported_asset_kinds))
        invalid_market = sorted(set(profile.supported_markets) - {Market.KR.value, Market.US.value})
        status = "ok" if not missing and not invalid_market else "blocked"
        notes = list(profile.notes)
        notes.extend(
            [
                "For Toss, global hedge-fund scope must be constrained to Toss-supported products unless another broker is added.",
                "Direct futures, spot FX, and direct commodities remain out of scope for Toss routing unless official API docs add them.",
                "Commodity exposure should use Toss-supported ETFs; FX should be handled through cash/환전 accounting, not direct FX trading.",
            ]
        )
        return TossPlatformFitReport(
            status=status,
            supported_markets=profile.supported_markets,
            supported_asset_kinds=profile.supported_asset_kinds,
            excluded_asset_kinds=profile.excluded_asset_kinds,
            api_dependent_steps=self.API_DEPENDENT_STEPS,
            non_api_steps=self.NON_API_STEPS,
            notes=notes,
        )
