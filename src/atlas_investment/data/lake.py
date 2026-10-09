from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from atlas_investment.data.instruments import InstrumentMaster
from atlas_investment.data.ohlcv_store import OhlcvStore, generate_sample_ohlcv
from atlas_investment.data.quality import OhlcvQualityChecker
from atlas_investment.data.universe import load_institutional_sample_universe
from atlas_investment.data.vendors import HybridMarketDataVendor, MarketDataVendor, SampleMarketDataVendor, YahooMarketDataVendor
from atlas_investment.integrations.korean_stock import KoreanStockClient
from atlas_investment.models import Market


@dataclass(frozen=True)
class DataLakeSyncConfig:
    days: int = 260
    max_symbols: int = 12
    include_fx: bool = True
    vendor: str = "sample"
    include_kr_snapshots: bool = False


@dataclass(frozen=True)
class DataLakeSyncResult:
    source: str
    market: str
    symbol: str
    candle_count: int
    quality_status: str
    output_path: str
    notes: list[str]


@dataclass(frozen=True)
class DailyDataRefreshReport:
    status: str
    generated_at: str
    vendor: str
    synced: list[DataLakeSyncResult]
    kr_snapshots: list[dict[str, object]]
    notes: list[str]


class DataLakeSynchronizer:
    def __init__(self, root: Path, vendor: MarketDataVendor | None = None) -> None:
        self.root = root
        self.vendor = vendor or SampleMarketDataVendor()
        self.ohlcv_store = OhlcvStore(root / "data" / "lake" / "ohlcv")
        self.fx_store = OhlcvStore(root / "data" / "lake" / "fx")
        self.checker = OhlcvQualityChecker()

    def sync_sample_universe(self, config: DataLakeSyncConfig) -> list[DataLakeSyncResult]:
        assets = load_institutional_sample_universe()[: config.max_symbols]
        master_path = InstrumentMaster.from_assets(assets).save(self.root / "data" / "lake" / "instrument_master.json")
        results: list[DataLakeSyncResult] = []

        for asset in assets:
            notes = [f"instrument master: {master_path}"]
            try:
                candles = self.vendor.load_daily_ohlcv(asset, config.days)
                path = self.ohlcv_store.save(asset.symbol, candles)
                quality = self.checker.check(asset.symbol, candles, min_rows=min(60, config.days))
                status = "ok" if quality.passed else "blocked"
                notes.extend(quality.issues)
            except Exception as error:  # pragma: no cover - defensive vendor guard
                path = self.ohlcv_store.path_for(asset.symbol)
                candles = []
                status = "blocked"
                notes.append(str(error))
            results.append(
                DataLakeSyncResult(
                    source=self.vendor.name,
                    market=asset.market.value,
                    symbol=asset.symbol,
                    candle_count=len(candles),
                    quality_status=status,
                    output_path=str(path),
                    notes=notes,
                )
            )

        if config.include_fx:
            fx_candles = generate_sample_ohlcv("USD_KRW", days=config.days, start_price=1380)
            fx_path = self.fx_store.save("USD_KRW", fx_candles)
            fx_quality = self.checker.check("USD_KRW", fx_candles, min_rows=min(60, config.days))
            results.append(
                DataLakeSyncResult(
                    source="sample_fx",
                    market="FX",
                    symbol="USD_KRW",
                    candle_count=len(fx_candles),
                    quality_status="ok" if fx_quality.passed else "blocked",
                    output_path=str(fx_path),
                    notes=fx_quality.issues,
                )
            )

        return results

    def refresh_daily(self, config: DataLakeSyncConfig) -> DailyDataRefreshReport:
        results = self.sync_sample_universe(config)
        snapshots: list[dict[str, object]] = []
        notes: list[str] = [
            "이 루틴은 안전한 데이터 갱신 전용입니다.",
            "주문 제출은 수행하지 않습니다.",
        ]
        if config.include_kr_snapshots:
            snapshots = self._refresh_kr_snapshots(config.max_symbols)
            if any(snapshot.get("status") != "ok" for snapshot in snapshots):
                notes.append("일부 한국주식 스냅샷 조회가 실패했지만 OHLCV 동기화 결과는 보존했습니다.")
        blocked = [result for result in results if result.quality_status != "ok"]
        snapshot_blocked = [snapshot for snapshot in snapshots if snapshot.get("status") != "ok"]
        status = "ok"
        if blocked:
            status = "degraded"
        if snapshot_blocked and status == "ok":
            status = "degraded"
        return DailyDataRefreshReport(
            status=status,
            generated_at=datetime.now(timezone.utc).isoformat(),
            vendor=self.vendor.name,
            synced=results,
            kr_snapshots=snapshots,
            notes=notes,
        )

    def _refresh_kr_snapshots(self, max_symbols: int) -> list[dict[str, object]]:
        client = KoreanStockClient()
        snapshots: list[dict[str, object]] = []
        kr_assets = [asset for asset in load_institutional_sample_universe() if asset.market == Market.KR][:max_symbols]
        for asset in kr_assets:
            market = str(asset.metadata.get("exchange") or "KOSPI")
            try:
                snapshot = client.trade_info(market, asset.symbol)
                snapshots.append({"status": "ok", "symbol": asset.symbol, "snapshot": snapshot})
            except Exception as error:  # pragma: no cover - network-dependent guard
                snapshots.append({"status": "degraded", "symbol": asset.symbol, "notes": [str(error)]})
        return snapshots


def build_market_data_vendor(name: str) -> MarketDataVendor:
    normalized = name.lower().strip()
    if normalized == "sample":
        return SampleMarketDataVendor()
    if normalized == "yfinance":
        return YahooMarketDataVendor()
    if normalized == "hybrid":
        return HybridMarketDataVendor(primary=YahooMarketDataVendor(), fallback=SampleMarketDataVendor())
    raise ValueError(f"지원하지 않는 데이터 벤더입니다: {name}")
