from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass

from atlas_investment.integrations.dart import DartClient
from atlas_investment.integrations.vibe_catalog import build_skill_catalog
from atlas_investment.integrations.yahoo import YahooFinanceClient


@dataclass(frozen=True)
class IntegrationCheckItem:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class IntegrationCheckReport:
    overall_status: str
    items: list[IntegrationCheckItem]


class IntegrationSetupChecker:
    def run(self) -> IntegrationCheckReport:
        items = [
            self._python_package("requests"),
            self._python_package("yfinance"),
            self._python_package("pandas"),
            self._python_package("numpy"),
            self._command("node"),
            self._command("npm"),
            self._dart(),
            self._yfinance(),
            self._skills(),
            self._mcp_catalog(),
        ]
        overall = "ok" if all(item.status == "ok" for item in items) else "degraded"
        return IntegrationCheckReport(overall, items)

    def _python_package(self, package: str) -> IntegrationCheckItem:
        if importlib.util.find_spec(package) is None:
            return IntegrationCheckItem(package, "blocked", f"Python 패키지 미설치: {package}")
        return IntegrationCheckItem(package, "ok", "설치됨")

    def _command(self, command: str) -> IntegrationCheckItem:
        path = shutil.which(command)
        if path:
            return IntegrationCheckItem(command, "ok", path)
        return IntegrationCheckItem(command, "blocked", f"명령을 찾을 수 없습니다: {command}")

    def _dart(self) -> IntegrationCheckItem:
        readiness = DartClient().readiness()
        return IntegrationCheckItem("k-dart", readiness.status, "; ".join(readiness.notes))

    def _yfinance(self) -> IntegrationCheckItem:
        readiness = YahooFinanceClient().readiness()
        return IntegrationCheckItem("yfinance-data", readiness.status, "; ".join(readiness.notes))

    def _skills(self) -> IntegrationCheckItem:
        catalog = build_skill_catalog()
        local = [item for item in catalog if item.kind == "local_skill"]
        missing = [item.name for item in local if item.status != "connected"]
        if missing:
            return IntegrationCheckItem("local-skills", "degraded", f"missing={missing}")
        return IntegrationCheckItem("local-skills", "ok", f"connected={len(local)}")

    def _mcp_catalog(self) -> IntegrationCheckItem:
        catalog = build_skill_catalog()
        mcp = [item for item in catalog if item.kind == "mcp"]
        return IntegrationCheckItem("mcp-bindings", "ok", f"available_in_session={[item.name for item in mcp]}")
