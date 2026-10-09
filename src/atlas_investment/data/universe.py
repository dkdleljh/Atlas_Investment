from __future__ import annotations

import json
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from atlas_investment.models import Asset, AssetKind, Market
from atlas_investment.data.instruments import InstrumentMaster


def load_institutional_sample_universe() -> list[Asset]:
    """Broad sample universe used until real KRX/US/ETF master data is connected."""
    return [
        Asset("005930", "삼성전자", Market.KR, AssetKind.STOCK, "KRW", metadata={"sector": "technology", "region": "korea", "quality_score": 0.68, "value_score": 0.58, "dividend_yield": 0.019, "earnings_yield": 0.055, "earnings_revision_3m": 0.04}),
        Asset("000660", "SK하이닉스", Market.KR, AssetKind.STOCK, "KRW", metadata={"sector": "technology", "region": "korea", "quality_score": 0.62, "value_score": 0.5, "dividend_yield": 0.006, "earnings_yield": 0.06, "earnings_revision_3m": 0.07}),
        Asset("035420", "NAVER", Market.KR, AssetKind.STOCK, "KRW", metadata={"sector": "communication", "region": "korea", "quality_score": 0.57, "value_score": 0.46, "dividend_yield": 0.004, "earnings_yield": 0.04, "earnings_revision_3m": 0.02}),
        Asset("051910", "LG화학", Market.KR, AssetKind.STOCK, "KRW", metadata={"sector": "materials", "region": "korea", "quality_score": 0.48, "value_score": 0.54, "dividend_yield": 0.011, "earnings_yield": 0.038, "earnings_revision_3m": -0.02}),
        Asset("069500", "KODEX 200", Market.KR, AssetKind.ETF, "KRW", metadata={"sector": "broad_market", "region": "korea", "quality_score": 0.58, "value_score": 0.52, "dividend_yield": 0.015, "earnings_yield": 0.045}),
        Asset("122630", "KODEX 레버리지", Market.KR, AssetKind.ETF, "KRW", is_leveraged=True, metadata={"sector": "broad_market", "region": "korea"}),
        Asset("252670", "KODEX 200선물인버스2X", Market.KR, AssetKind.ETF, "KRW", is_leveraged=True, is_inverse=True, metadata={"sector": "hedge", "region": "korea"}),
        Asset("AAPL", "Apple", Market.US, AssetKind.STOCK, "USD", metadata={"sector": "technology", "region": "us", "quality_score": 0.78, "value_score": 0.45, "dividend_yield": 0.005, "buyback_yield": 0.035, "earnings_yield": 0.032, "earnings_revision_3m": 0.03}),
        Asset("MSFT", "Microsoft", Market.US, AssetKind.STOCK, "USD", metadata={"sector": "technology", "region": "us", "quality_score": 0.82, "value_score": 0.42, "dividend_yield": 0.007, "buyback_yield": 0.012, "earnings_yield": 0.028, "earnings_revision_3m": 0.04}),
        Asset("NVDA", "NVIDIA", Market.US, AssetKind.STOCK, "USD", metadata={"sector": "technology", "region": "us", "quality_score": 0.76, "value_score": 0.36, "dividend_yield": 0.001, "buyback_yield": 0.006, "earnings_yield": 0.026, "earnings_revision_3m": 0.09}),
        Asset("JPM", "JPMorgan Chase", Market.US, AssetKind.STOCK, "USD", metadata={"sector": "financials", "region": "us", "quality_score": 0.66, "value_score": 0.62, "dividend_yield": 0.021, "buyback_yield": 0.018, "earnings_yield": 0.072, "earnings_revision_3m": 0.01}),
        Asset("VOO", "Vanguard S&P 500 ETF", Market.US, AssetKind.ETF, "USD", metadata={"sector": "broad_market", "region": "us", "quality_score": 0.62, "value_score": 0.5, "dividend_yield": 0.013, "earnings_yield": 0.042}),
        Asset("TLT", "iShares 20+ Year Treasury Bond ETF", Market.US, AssetKind.ETF, "USD", metadata={"sector": "bonds", "region": "us", "quality_score": 0.55, "value_score": 0.5, "dividend_yield": 0.037, "earnings_yield": 0.037}),
        Asset("GLD", "SPDR Gold Shares", Market.US, AssetKind.ETF, "USD", metadata={"sector": "commodity", "region": "us", "quality_score": 0.5, "value_score": 0.5, "dividend_yield": 0.0, "earnings_yield": 0.0}),
        Asset("TQQQ", "ProShares UltraPro QQQ", Market.US, AssetKind.ETF, "USD", is_leveraged=True, metadata={"sector": "technology", "region": "us"}),
        Asset("SQQQ", "ProShares UltraPro Short QQQ", Market.US, AssetKind.ETF, "USD", is_leveraged=True, is_inverse=True, metadata={"sector": "hedge", "region": "us"}),
    ]


def filter_tradable_universe(assets: list[Asset]) -> list[Asset]:
    return [asset for asset in assets if asset.tradable]


def load_runtime_universe(root: Path, prefer_lake: bool = True) -> tuple[list[Asset], str, list[str]]:
    """Load the best available tradable universe for runtime decisions.

    The live trading API is still blocked, but the decision loop should not be
    hard-wired to the smallest sample list once a data-lake instrument master
    exists.
    """
    notes: list[str] = []
    candidates = [
        root / "data" / "lake" / "instrument_master.json",
        root / "data" / "universe" / "instrument_master.json",
    ] if prefer_lake else []
    sample_assets = filter_tradable_universe(load_institutional_sample_universe())
    best_assets = sample_assets
    best_source = "institutional_sample"
    for path in candidates:
        if not path.exists():
            continue
        try:
            assets = InstrumentMaster.load(path).tradable_assets()
        except Exception as error:  # pragma: no cover - defensive corrupt-file guard
            notes.append(f"{path} 로드 실패: {error}")
            continue
        if assets:
            if len(assets) > len(best_assets):
                best_assets = assets
                best_source = str(path)
            elif len(assets) < len(sample_assets):
                notes.append(f"{path}의 tradable 자산 수가 {len(assets)}개라 내장 샘플 {len(sample_assets)}개보다 작습니다.")
            elif best_source == "institutional_sample":
                best_assets = assets
                best_source = str(path)
            continue
        notes.append(f"{path}에 tradable 자산이 없습니다.")
    if best_source == "institutional_sample":
        notes.append("더 넓은 instrument master가 없어 내장 샘플 유니버스를 사용합니다.")
    return best_assets, best_source, notes


def export_universe_snapshot(assets: list[Asset], path: Path) -> Path:
    def normalize(value):
        if isinstance(value, Enum):
            return value.value
        raise TypeError(type(value).__name__)

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump([asdict(asset) for asset in assets], file, ensure_ascii=False, indent=2, default=normalize)
    return path
