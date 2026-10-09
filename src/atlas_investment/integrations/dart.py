from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import requests


@dataclass(frozen=True)
class DartReadiness:
    status: str
    has_api_key: bool
    notes: list[str]


@dataclass(frozen=True)
class DartEventSignal:
    corp_code: str | None
    corp_name: str
    report_name: str
    received_at: str
    category: str
    importance: str
    action: str
    url: str | None
    notes: list[str]


class DartApiError(RuntimeError):
    pass


class DartClient:
    def __init__(self, api_key: str | None = None, base_url: str = "https://opendart.fss.or.kr/api", timeout_seconds: float = 10.0) -> None:
        self.api_key = api_key or os.getenv("API_K_DART")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def readiness(self) -> DartReadiness:
        if not self.api_key:
            return DartReadiness("blocked", False, ["API_K_DART 환경변수가 없습니다. DART 호출은 건너뜁니다."])
        return DartReadiness("ok", True, ["API_K_DART 환경변수가 설정되어 있습니다."])

    def disclosures(self, corp_code: str | None = None, days: int = 30, page_count: int = 10) -> dict[str, Any]:
        self._require_key()
        end = date.today()
        begin = end - timedelta(days=days)
        params: dict[str, Any] = {
            "bgn_de": begin.strftime("%Y%m%d"),
            "end_de": end.strftime("%Y%m%d"),
            "page_count": page_count,
            "sort": "date",
            "sort_mth": "desc",
        }
        if corp_code:
            params["corp_code"] = corp_code
        return self._get("list.json", params)

    def event_signals(self, corp_code: str | None = None, days: int = 7, page_count: int = 20) -> list[DartEventSignal]:
        payload = self.disclosures(corp_code=corp_code, days=days, page_count=page_count)
        items = payload.get("list") or []
        return [classify_disclosure_event(item) for item in items]

    def company(self, corp_code: str) -> dict[str, Any]:
        self._require_key()
        return self._get("company.json", {"corp_code": corp_code})

    def financials(self, corp_code: str, year: int, report_code: str = "11011", fs_div: str = "CFS") -> dict[str, Any]:
        self._require_key()
        return self._get(
            "fnlttSinglAcntAll.json",
            {"corp_code": corp_code, "bsns_year": year, "reprt_code": report_code, "fs_div": fs_div},
        )

    def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        params = {"crtfc_key": self.api_key, **params}
        response = requests.get(f"{self.base_url}/{endpoint}", params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise DartApiError("OpenDART 응답 형식이 JSON 객체가 아닙니다.")
        status = str(payload.get("status") or "")
        if status and status not in {"000", "013"}:
            message = str(payload.get("message") or "OpenDART API 오류")
            raise DartApiError(f"OpenDART status={status}: {message}")
        return payload

    def _require_key(self) -> None:
        if not self.api_key:
            raise RuntimeError("API_K_DART 환경변수가 필요합니다.")


def classify_disclosure_event(item: dict[str, Any]) -> DartEventSignal:
    report_name = str(item.get("report_nm") or "")
    lower = report_name.lower()
    category = "general"
    importance = "normal"
    action = "watch"
    notes: list[str] = []
    if any(keyword in report_name for keyword in ["잠정실적", "영업실적", "매출액", "손익구조"]):
        category = "earnings"
        importance = "high"
        action = "refresh_memo"
        notes.append("실적/손익 관련 공시입니다. 투자 메모와 추정치를 갱신하세요.")
    elif any(keyword in report_name for keyword in ["유상증자", "무상증자", "전환사채", "신주인수권", "감자"]):
        category = "capital_action"
        importance = "high"
        action = "risk_review"
        notes.append("자본 구조 변화 가능성이 있어 희석/재무 리스크 검토가 필요합니다.")
    elif any(keyword in report_name for keyword in ["합병", "분할", "영업양수", "영업양도", "주식교환"]):
        category = "corporate_action"
        importance = "high"
        action = "event_review"
        notes.append("기업 이벤트 공시입니다. 이벤트 드리븐 리스크를 확인하세요.")
    elif any(keyword in report_name for keyword in ["조회공시", "풍문", "보도"]):
        category = "rumor_inquiry"
        importance = "medium"
        action = "headline_monitor"
        notes.append("풍문/보도/조회공시 계열입니다. 가격 변동성과 후속 답변을 확인하세요.")
    elif "정정" in report_name or "correction" in lower:
        category = "correction"
        importance = "medium"
        action = "diff_review"
        notes.append("정정 공시입니다. 기존 공시와 변경점을 비교하세요.")
    url = item.get("rcept_no")
    return DartEventSignal(
        corp_code=item.get("corp_code"),
        corp_name=str(item.get("corp_name") or ""),
        report_name=report_name,
        received_at=str(item.get("rcept_dt") or ""),
        category=category,
        importance=importance,
        action=action,
        url=f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={url}" if url else None,
        notes=notes or ["일반 공시입니다. 워치리스트 종목이면 확인하세요."],
    )
