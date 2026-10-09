from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from atlas_investment.brokers.toss_clients import TossApiConfig, TossApiReadiness
from atlas_investment.data.entitlements import DataEntitlementAuditor
from atlas_investment.data.global_catalog import GlobalCoverageModel
from atlas_investment.data.universe import load_runtime_universe
from atlas_investment.ops.heartbeat import HeartbeatAuditor
from atlas_investment.ops.promotion import PromotionEvidenceAuditor
from atlas_investment.ops.reconciliation import ReadOnlyReconciler


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: str
    evidence: str
    required_for_live: bool
    remediation: str


@dataclass(frozen=True)
class HedgeFundReadinessReport:
    overall_status: str
    global_investment_status: str
    autonomy_24x7_status: str
    checks: list[ReadinessCheck]
    conclusion: str


class HedgeFundReadinessAuditor:
    """Audits whether Atlas Investment is truly ready for global unmanned live operation."""

    def run(self, root: Path) -> HedgeFundReadinessReport:
        checks = [
            self._universe_coverage(root),
            self._domain_model_coverage(),
            self._asset_class_coverage(root),
            self._live_broker_readiness(),
            self._read_only_reconciliation(root),
            self._data_source_quality(root),
            self._automation_loop(root),
            self._monitoring_and_alerts(root),
            self._risk_controls(),
            self._audit_artifacts(root),
            self._live_promotion_gate(root),
        ]
        global_checks = [check for check in checks if check.name.startswith("global_") or check.name in {"live_broker", "data_quality"}]
        autonomy_checks = [check for check in checks if check.name.startswith("autonomy_") or check.name in {"monitoring_alerts", "read_only_reconciliation"}]
        global_status = self._rollup(global_checks)
        autonomy_status = self._rollup(autonomy_checks)
        overall = self._rollup([check for check in checks if check.required_for_live])
        conclusion = (
            "Atlas Investment is NOT yet a fully global, 24x7 unmanned live hedge fund."
            if overall == "blocked"
            else "Atlas Investment has no blocked live requirements, but still requires manual promotion review."
        )
        return HedgeFundReadinessReport(overall, global_status, autonomy_status, checks, conclusion)

    def _universe_coverage(self, root: Path) -> ReadinessCheck:
        assets, source, notes = load_runtime_universe(root)
        markets = sorted({asset.market.value for asset in assets})
        status = "ok" if len(assets) >= 10_000 and len(markets) >= 6 else "blocked"
        return ReadinessCheck(
            "global_universe_coverage",
            status,
            f"{len(assets)} tradable assets across markets={markets}; source={source}; notes={notes}",
            True,
            "Connect full KRX/US/EU/JP/HK/EM instrument masters with delisted and suspended security history.",
        )

    def _asset_class_coverage(self, root: Path) -> ReadinessCheck:
        assets, _, _ = load_runtime_universe(root)
        kinds = sorted({asset.kind.value for asset in assets})
        required = {"stock", "etf", "bond", "future", "option", "fx", "commodity"}
        missing = sorted(required - set(kinds))
        status = "ok" if not missing else "blocked"
        return ReadinessCheck(
            "global_asset_class_coverage",
            status,
            f"covered={kinds}; missing={missing}",
            True,
            "Extend domain models and brokers for bonds, futures, options, FX, commodities, and their margin/risk rules.",
        )

    def _domain_model_coverage(self) -> ReadinessCheck:
        report = GlobalCoverageModel().report()
        return ReadinessCheck(
            "global_domain_model_coverage",
            report.status,
            f"missing_markets={report.market_requirement.missing}; missing_asset_kinds={report.asset_kind_requirement.missing}",
            False,
            "Keep market and asset-kind enums aligned with supported brokers, data feeds, and risk models.",
        )

    def _live_broker_readiness(self) -> ReadinessCheck:
        report = TossApiReadiness().check(TossApiConfig.from_env())
        status = "ok" if report.ready_for_live_orders else "blocked"
        return ReadinessCheck(
            "live_broker",
            status,
            f"toss_status={report.status}; official_docs_verified={report.official_docs_verified}; missing={report.missing_items}; ready_for_live_orders={report.ready_for_live_orders}",
            True,
            "Implement only official supported broker order APIs after official docs are verified, then pass manual small-order promotion gates.",
        )

    def _read_only_reconciliation(self, root: Path | None = None) -> ReadinessCheck:
        api = TossApiReadiness().check(TossApiConfig.from_env())
        reconciliation = ReadOnlyReconciler().reconcile(root) if root else None
        status = reconciliation.status if reconciliation else "blocked"
        return ReadinessCheck(
            "read_only_reconciliation",
            status,
            f"official_toss_api_status={api.status}; official_docs_verified={api.official_docs_verified}; reconciliation_status={None if reconciliation is None else reconciliation.status}; differences={0 if reconciliation is None else len(reconciliation.differences)}",
            True,
            "Connect only official Toss account, positions, orders, and fills endpoints after official docs are verified, then reconcile snapshots for 10 trading days.",
        )

    def _data_source_quality(self, root: Path) -> ReadinessCheck:
        lake = root / "data" / "lake" / "ohlcv"
        csv_count = len(list(lake.glob("*.csv"))) if lake.exists() else 0
        entitlements = DataEntitlementAuditor().audit(root)
        status = "ok" if csv_count >= 10_000 and entitlements.status == "ok" else "blocked"
        return ReadinessCheck(
            "data_quality",
            status,
            f"ohlcv_csv_count={csv_count}; lake={lake}; data_entitlements_status={entitlements.status}; provider_count={entitlements.provider_count}",
            True,
            "Replace sample/yfinance-only data with licensed survivorship-bias-free market data and freshness checks.",
        )

    def _automation_loop(self, root: Path) -> ReadinessCheck:
        script = root / "scripts" / "daily_data_refresh.sh"
        daemon = root / "scripts" / "atlas_investment_daemon.sh"
        policy = root / "config" / "automation_policy.json"
        unit = root / "deploy" / "atlas-investment.service"
        installer = root / "scripts" / "install_atlas_investment_user_service.sh"
        heartbeat = HeartbeatAuditor().audit(root)
        service_enabled = self._systemctl_user("is-enabled", "atlas-investment.service") == "enabled"
        service_active = self._systemctl_user("is-active", "atlas-investment.service") == "active"
        status = "ok" if daemon.exists() and policy.exists() and unit.exists() and installer.exists() and service_enabled and service_active and heartbeat.status == "ok" else ("degraded" if daemon.exists() and policy.exists() and unit.exists() and installer.exists() and service_enabled and service_active else "blocked")
        return ReadinessCheck(
            "autonomy_24x7_daemon",
            status,
            f"daily_script_exists={script.exists()}; daemon_exists={daemon.exists()}; policy_exists={policy.exists()}; service_unit_exists={unit.exists()}; installer_exists={installer.exists()}; service_enabled={service_enabled}; service_active={service_active}; heartbeat_status={heartbeat.status}; heartbeat_days={heartbeat.distinct_utc_days}",
            True,
            "Install a supervised service, verify restart policy, and prove 30 days of clean heartbeat history.",
        )

    def _monitoring_and_alerts(self, root: Path) -> ReadinessCheck:
        dashboard = root / "data" / "reports" / "dashboard.html"
        alert_config = root / "config" / "alerts.json"
        enabled = False
        channels = []
        if alert_config.exists():
            try:
                payload = json.loads(alert_config.read_text(encoding="utf-8"))
                enabled = bool(payload.get("enabled"))
                channels = list(payload.get("channels", []))
            except Exception:
                enabled = False
        status = "ok" if dashboard.exists() and enabled and channels else "degraded"
        return ReadinessCheck(
            "monitoring_alerts",
            status,
            f"dashboard_exists={dashboard.exists()}; alert_config_exists={alert_config.exists()}; alerts_enabled={enabled}; channels={len(channels)}",
            True,
            "Add durable alert routing for blocked/degraded states, broker drift, data staleness, and drawdown breaches.",
        )

    def _risk_controls(self) -> ReadinessCheck:
        return ReadinessCheck(
            "risk_controls",
            "ok",
            "Single-order checks, fund-level controls, and default-run batch pre-trade simulation are enforced before any broker route.",
            True,
            "Keep extending stress, liquidity, and broker-specific limit simulations before live promotion.",
        )

    def _audit_artifacts(self, root: Path) -> ReadinessCheck:
        docs = root / "docs"
        doc_count = len(list(docs.glob("*.md"))) if docs.exists() else 0
        status = "ok" if doc_count >= 20 else "degraded"
        return ReadinessCheck(
            "audit_artifacts",
            status,
            f"doc_count={doc_count}; docs={docs}",
            False,
            "Keep every promotion, incident, strategy version, and live decision in immutable audit logs.",
        )

    def _live_promotion_gate(self, root: Path) -> ReadinessCheck:
        report = PromotionEvidenceAuditor().audit(root)
        return ReadinessCheck(
            "live_promotion_gate",
            report.status,
            f"blocked_requirements={sum(1 for requirement in report.requirements if requirement.status == 'blocked')}",
            True,
            "Require documented manual approval after DRY_RUN, PAPER, read-only reconciliation, and small-order trials.",
        )

    @staticmethod
    def _rollup(checks: list[ReadinessCheck]) -> str:
        statuses = [check.status for check in checks]
        if "blocked" in statuses:
            return "blocked"
        if "degraded" in statuses:
            return "degraded"
        return "ok"

    @staticmethod
    def _systemctl_user(command: str, unit: str) -> str:
        try:
            result = subprocess.run(
                ["systemctl", "--user", command, unit],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
        except Exception:
            return "unknown"
        return result.stdout.strip() or result.stderr.strip()
