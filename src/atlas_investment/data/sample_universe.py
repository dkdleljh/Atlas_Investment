from __future__ import annotations

from atlas_investment.models import Asset, AssetKind, Market


def load_sample_universe() -> list[Asset]:
    """Temporary sample universe until official Toss/KRX/US universe loaders are connected."""
    return [
        Asset("005930", "삼성전자", Market.KR, AssetKind.STOCK, "KRW"),
        Asset("000660", "SK하이닉스", Market.KR, AssetKind.STOCK, "KRW"),
        Asset("069500", "KODEX 200", Market.KR, AssetKind.ETF, "KRW"),
        Asset("122630", "KODEX 레버리지", Market.KR, AssetKind.ETF, "KRW", is_leveraged=True),
        Asset("252670", "KODEX 200선물인버스2X", Market.KR, AssetKind.ETF, "KRW", is_leveraged=True, is_inverse=True),
        Asset("AAPL", "Apple", Market.US, AssetKind.STOCK, "USD"),
        Asset("MSFT", "Microsoft", Market.US, AssetKind.STOCK, "USD"),
        Asset("VOO", "Vanguard S&P 500 ETF", Market.US, AssetKind.ETF, "USD"),
        Asset("TQQQ", "ProShares UltraPro QQQ", Market.US, AssetKind.ETF, "USD", is_leveraged=True),
        Asset("SQQQ", "ProShares UltraPro Short QQQ", Market.US, AssetKind.ETF, "USD", is_leveraged=True, is_inverse=True),
    ]

