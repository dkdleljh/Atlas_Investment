from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from atlas_investment.models import Asset, AssetKind, Market


@dataclass(frozen=True)
class InstrumentRecord:
    symbol: str
    name: str
    market: Market
    kind: AssetKind
    currency: str
    tradable: bool
    is_leveraged: bool
    is_inverse: bool
    sector: str
    region: str
    status: str = "active"
    source: str = "sample"

    @classmethod
    def from_asset(cls, asset: Asset, source: str = "sample") -> "InstrumentRecord":
        return cls(
            symbol=asset.symbol,
            name=asset.name,
            market=asset.market,
            kind=asset.kind,
            currency=asset.currency,
            tradable=asset.tradable,
            is_leveraged=asset.is_leveraged,
            is_inverse=asset.is_inverse,
            sector=str(asset.metadata.get("sector", "unknown")),
            region=str(asset.metadata.get("region", "unknown")),
            status=str(asset.metadata.get("status", "active")),
            source=source,
        )

    def to_asset(self) -> Asset:
        return Asset(
            symbol=self.symbol,
            name=self.name,
            market=self.market,
            kind=self.kind,
            currency=self.currency,
            is_leveraged=self.is_leveraged,
            is_inverse=self.is_inverse,
            tradable=self.tradable and self.status == "active",
            metadata={"sector": self.sector, "region": self.region, "status": self.status, "source": self.source},
        )


def _default(value):
    if isinstance(value, Enum):
        return value.value
    raise TypeError(type(value).__name__)


class InstrumentMaster:
    def __init__(self, records: list[InstrumentRecord]) -> None:
        self.records = records

    @classmethod
    def from_assets(cls, assets: list[Asset], source: str = "sample") -> "InstrumentMaster":
        return cls([InstrumentRecord.from_asset(asset, source=source) for asset in assets])

    def tradable_assets(self) -> list[Asset]:
        return [record.to_asset() for record in self.records if record.tradable and record.status == "active"]

    def summary(self) -> dict[str, object]:
        markets: dict[str, int] = {}
        kinds: dict[str, int] = {}
        status: dict[str, int] = {}
        leveraged_inverse = 0
        for record in self.records:
            markets[record.market.value] = markets.get(record.market.value, 0) + 1
            kinds[record.kind.value] = kinds.get(record.kind.value, 0) + 1
            status[record.status] = status.get(record.status, 0) + 1
            if record.is_leveraged or record.is_inverse:
                leveraged_inverse += 1
        return {
            "instrument_count": len(self.records),
            "tradable_count": len(self.tradable_assets()),
            "markets": markets,
            "kinds": kinds,
            "status": status,
            "leveraged_inverse_count": leveraged_inverse,
        }

    def save(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            json.dump([asdict(record) for record in self.records], file, ensure_ascii=False, indent=2, default=_default)
        return path

    @classmethod
    def load(cls, path: Path) -> "InstrumentMaster":
        with path.open("r", encoding="utf-8") as file:
            rows = json.load(file)
        return cls(
            [
                InstrumentRecord(
                    symbol=row["symbol"],
                    name=row["name"],
                    market=Market(row["market"]),
                    kind=AssetKind(row["kind"]),
                    currency=row["currency"],
                    tradable=bool(row["tradable"]),
                    is_leveraged=bool(row["is_leveraged"]),
                    is_inverse=bool(row["is_inverse"]),
                    sector=row["sector"],
                    region=row["region"],
                    status=row.get("status", "active"),
                    source=row.get("source", "sample"),
                )
                for row in rows
            ]
        )
