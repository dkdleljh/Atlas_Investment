# 최신화 주석(2026-06-01): 현재 토스증권 연동 기준은 공식 API 대기 상태입니다. 이 문서의 과거 toss-securities, tossctl, toss_readonly, toss-readonly 언급은 역사 기록이며 현재 실행 경로에서는 제거되었습니다. 최신 기준은 docs/52_토스_비공식_API_경로_정리_및_공식API_대기상태_2026-06-01.md 및 docs/53_구동의존성_MCP_스킬_실거래직전_검증_2026-06-01.md를 따릅니다.

# Atlas Investment MCP/Skill 실제 연동 세팅

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

작성일: 2026-05-30

## 결론

`docs/16_MCP_Skill_연동_제안.md`의 제안 항목을 실제 실행 가능한 CLI와 의존성 기준으로 연결했다.

이번 세팅은 실거래 주문 연결이 아니라 다음 영역을 바로 사용할 수 있게 만드는 작업이다.

- 한국주식 검색/시세 스냅샷
- DART 공시 API 준비도와 공시 조회
- yfinance 기반 미국 주식/ETF OHLCV 수집
- Vibe Trading MCP/Skill 추천 카탈로그
- toss-securities read-only 준비도 점검
- OpenClaw cron 자동화 템플릿 생성

토스증권 실주문은 공식 REST/WebSocket API 문서와 키가 확인되기 전까지 계속 차단한다.

## 설치된 Python 의존성

`pyproject.toml`에 다음 패키지를 추가했다.

- `requests`: Korean Stock Search proxy와 DART OpenAPI 호출
- `yfinance`: 미국 주식/ETF OHLCV 수집
- `pandas`: yfinance 데이터프레임 처리
- `numpy`: 리스크/팩터/데이터 분석 확장 기반

설치 명령:

```bash
cd /home/zenith/Desktop/Atlas_Investment
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

## Node/toss-securities

`toss-securities`는 read-only 계좌/포트폴리오 조회 후보로 설치 대상에 포함했다.

Atlas Investment은 이를 주문 실행 도구로 사용하지 않는다. 현재 연결 계층은 `tossctl` 명령이 있는지만 점검하며, `tossctl`이 없거나 인증이 안 된 경우 `blocked`로 표시한다.

점검 명령:

```bash
.venv/bin/python -m atlas_investment.cli toss-readonly-status
```

현재 상태:

- npm 패키지 `toss-securities@0.4.0` 설치 완료
- `tossctl` 실행 파일은 현재 PATH에서 찾지 못함
- 따라서 Atlas Investment의 toss read-only 점검은 `blocked`로 표시됨
- 실주문에는 사용하지 않음

## 새 CLI 명령

### 통합 점검

```bash
.venv/bin/python -m atlas_investment.cli integration-check
```

확인 항목:

- `requests`
- `yfinance`
- `pandas`
- `numpy`
- `node`
- `npm`
- `tossctl`
- `API_K_DART`
- yfinance import 가능 여부

### 한국주식 검색

```bash
.venv/bin/python -m atlas_investment.cli kr-stock-search --query 삼성전자
```

결과 파일:

```text
data/reports/kr_stock_search.json
```

### 한국주식 시세 스냅샷

```bash
.venv/bin/python -m atlas_investment.cli kr-stock-snapshot --market KOSPI --symbol 005930
```

결과 파일:

```text
data/reports/kr_stock_snapshot_005930.json
```

### DART 준비도

```bash
.venv/bin/python -m atlas_investment.cli dart-readiness
```

`API_K_DART` 환경변수가 없으면 `blocked`로 표시한다. 이는 오류가 아니라 키가 없는 상태를 명확히 표시하는 것이다.

### DART 공시 조회

```bash
.venv/bin/python -m atlas_investment.cli dart-disclosures
```

`API_K_DART`가 있어야 실제 조회가 가능하다.

### 미국 주식/ETF OHLCV

```bash
.venv/bin/python -m atlas_investment.cli us-ohlcv --symbol AAPL --days 260
```

결과 파일:

```text
data/ohlcv_external/AAPL.csv
data/reports/us_ohlcv_quality_AAPL.json
```

### Vibe Trading MCP/Skill 카탈로그

```bash
.venv/bin/python -m atlas_investment.cli mcp-catalog
```

결과 파일:

```text
data/reports/mcp_skill_catalog.json
```

### Cron 템플릿

```bash
.venv/bin/python -m atlas_investment.cli cron-template
```

결과 파일:

```text
data/reports/openclaw_cron_template.json
```

템플릿은 `enabled: false`로 생성한다. 장전/장중/마감 자동 실행은 메시지와 리포트를 발생시킬 수 있으므로, 실제 OpenClaw cron 활성화는 별도 확인 후 켜는 것이 안전하다.

이번 세팅에서는 사용자의 명시 요청에 따라 OpenClaw cron에도 실제 작업을 등록했다. 모두 `delivery.mode=none`으로 설정해서 정상 상태에서는 채팅에 메시지를 보내지 않고, 작업 자체도 실주문이 아닌 점검/리포트 생성만 수행한다.

등록된 작업:

- `Atlas Investment 장전 통합 점검`: 평일 08:40 KST
- `Atlas Investment 장중 헬스체크`: 평일 10:00-15:00 KST 매시 정각
- `Atlas Investment 마감 운영 리포트`: 평일 16:35 KST

각 작업은 `.venv/bin/python -m atlas_investment.cli ...` 명령만 실행하며 실거래 주문, 예약, 결제, 외부 mutation은 금지한다.

## 안전 원칙

- MCP/Skill 결과는 데이터와 판단 보조로만 사용한다.
- 외부 데이터는 `data-audit`와 리스크 엔진을 통과해야 한다.
- `toss-securities`는 read-only 조회 후보로만 사용한다.
- 실주문은 Atlas Investment 내부 브로커 계층만 담당한다.
- 토스 공식 주문 API 전까지 `LIVE_AUTO`는 차단 상태를 유지한다.
- 미수/신용 금지는 모든 외부 MCP/Skill보다 우선한다.
