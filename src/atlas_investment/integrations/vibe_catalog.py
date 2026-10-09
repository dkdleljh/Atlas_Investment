from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VibeSkillRecommendation:
    name: str
    use_case: str
    atlas_module: str
    kind: str = "skill"
    status: str = "recommended"
    local_path: str | None = None


RECOMMENDED_VIBE_SKILLS = [
    VibeSkillRecommendation("data-routing", "시장/종목별 데이터 소스 선택", "data/vendors.py", "concept"),
    VibeSkillRecommendation("yfinance", "미국 주식/ETF OHLCV와 기본 데이터", "integrations/yahoo.py", "python_package"),
    VibeSkillRecommendation("akshare", "글로벌/중국/HK/FX 보완 데이터", "data/vendors.py", "future_skill"),
    VibeSkillRecommendation("risk-analysis", "VaR, CVaR, 스트레스 테스트", "risk/advanced.py", "concept"),
    VibeSkillRecommendation("factor-research", "IC/IR 기반 팩터 검증", "research/factory.py", "concept"),
    VibeSkillRecommendation("multi-factor", "멀티팩터 종목 랭킹", "strategy/plugins.py", "concept"),
    VibeSkillRecommendation("asset-allocation", "ETF/멀티에셋 자산배분", "portfolio/", "concept"),
    VibeSkillRecommendation("execution-model", "슬리피지와 시장충격 모델", "execution/; backtest/realistic.py", "concept"),
    VibeSkillRecommendation("performance-attribution", "전략/섹터/종목 성과 기여도", "analytics/", "concept"),
    VibeSkillRecommendation("report-generate", "전문 리서치/운영 리포트 생성", "ops/reporting.py", "concept"),
]


LOCAL_SKILL_BINDINGS = [
    VibeSkillRecommendation("korean-stock-search", "KRX 상장종목 검색/일별 시세 proxy", "integrations/korean_stock.py", "local_skill", local_path="/home/zenith/.agents/skills/korean-stock-search"),
    VibeSkillRecommendation("k-dart", "OpenDART 공시/기업개황/재무제표 조회", "integrations/dart.py", "local_skill", local_path="/home/zenith/.agents/skills/k-dart"),
    VibeSkillRecommendation("repo-doctor", "로컬 git 상태/dirty 파일/테스트 힌트 점검", "ops/healthcheck.py", "local_skill", local_path="/home/zenith/.agents/skills/repo-doctor"),
    VibeSkillRecommendation("workspace-map", "워크스페이스 프로젝트/서비스 위치 파악", "docs/", "local_skill", local_path="/home/zenith/.agents/skills/workspace-map"),
    VibeSkillRecommendation("hermes-github-codebase-inspection", "LOC/언어 구성/코드베이스 규모 점검", "docs/", "local_skill", local_path="/home/zenith/.agents/skills/hermes-github-codebase-inspection"),
]


MCP_BINDINGS = [
    VibeSkillRecommendation("github-mcp", "GitHub 원격 저장소/PR/브랜치 메타데이터 조회", "repository governance", "mcp"),
    VibeSkillRecommendation("huggingface-mcp", "ML/AI 논문·모델·데이터셋 탐색", "strategy ML research", "mcp"),
    VibeSkillRecommendation("google-drive-mcp", "운영/감사 문서가 Drive에 있을 때 조회", "docs/audit export", "mcp"),
]


def build_skill_catalog() -> list[VibeSkillRecommendation]:
    rows = [*RECOMMENDED_VIBE_SKILLS, *LOCAL_SKILL_BINDINGS, *MCP_BINDINGS]
    hydrated: list[VibeSkillRecommendation] = []
    for row in rows:
        status = row.status
        if row.local_path:
            status = "connected" if Path(row.local_path).exists() else "missing"
        elif row.kind == "mcp":
            status = "available_in_session"
        hydrated.append(VibeSkillRecommendation(row.name, row.use_case, row.atlas_module, row.kind, status, row.local_path))
    return hydrated
