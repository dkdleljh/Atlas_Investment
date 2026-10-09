# Atlas Investment / 아틀라스 인베스트먼트

> 최신 기준(2026-06-12): Atlas Investment의 토스증권 adapter는 공식 개발자 문서(`developers.tossinvest.com/llms.txt`)와 공식 OpenAPI JSON(`openapi-docs/latest/openapi.json`, v1.1.1)을 기준으로 맞췄습니다. 토큰은 OAuth2 Client Credentials Grant, base server는 `https://openapi.tossinvest.com`, 계좌·자산·주문 API는 `X-Tossinvest-Account` 헤더를 사용합니다. 실주문은 read-only 스냅샷 reconciliation, 30일 heartbeat, promotion evidence가 통과된 뒤에만 검토합니다.

Atlas Investment은 한국장과 미국장 전체를 대상으로 하는 완전 자동 주식 운용 시스템을 목표로 하는 프로젝트입니다.

현재 버전은 토스증권 공식 REST API에 붙일 수 있는 **DRY_RUN/PAPER/백테스트 기반 운용 OS**입니다. 토스증권 공식 문서 기준 현재 Open API는 REST only입니다. `TossLiveBroker`는 공식 계좌/보유주식/미체결주문/시세 조회 스냅샷을 받아 reconciliation에 연결하고, 실주문 mutation은 승격 조건 전까지 계속 차단합니다.

## 실행 준비

```bash
cd /home/zenith/Desktop/Atlas_Investment
.venv/bin/python -m pip install -e .
.venv/bin/python -m atlas_investment.cli integration-check
.venv/bin/python -m atlas_investment.cli mcp-catalog
```

현재 셸 PATH에 `.venv/bin`이 자동 포함되어 있지 않으면 `atlas-investment` 대신 `.venv/bin/atlas-investment` 또는 `.venv/bin/python -m atlas_investment.cli`로 실행합니다.

## 토스증권 API 키 설정

토스증권 개발자센터에서 받은 `api key`와 `secret key`는 로컬 `.env`에만 저장합니다.

```bash
TOSS_API_DOCS_URL=https://developers.tossinvest.com/llms.txt
TOSS_API_REST_BASE_URL=https://openapi.tossinvest.com
TOSS_API_KEY=발급받은_api_key
TOSS_SECRET_KEY=발급받은_secret_key
TOSS_ACCOUNT_SEQ=
```

`TOSS_ACCOUNT_SEQ`는 선택사항입니다. 비워두면 Atlas Investment이 `GET /api/v1/accounts`로 계좌 목록을 먼저 읽고 첫 `BROKERAGE` 계좌의 `accountSeq`를 자동으로 사용합니다.

## 현재 가능한 것

- 한국주식 검색/시세 스냅샷 연동 명령
- DART 공시 API 준비도/조회 명령
- yfinance 기반 미국 주식/ETF OHLCV 수집 명령
- Vibe Trading MCP/Skill 추천 카탈로그
- OpenClaw cron 자동화 템플릿 생성
- 매일 데이터 레이크 갱신 루틴
- DART 공시 이벤트 신호 생성
- 토스증권 공식 API 공개 후 연결할 계좌/포지션/주문/체결 스냅샷 대사 경로
- 토스증권 공식 REST endpoint 기반 read-only 스냅샷 수집 명령
- 토스증권 공식 rate limit 기준 클라이언트 측 요청 속도 제한, 응답 헤더 기반 동적 완화, 429 `Retry-After` 재시도
- 샘플 한국/미국 종목 유니버스 로드
- 전략 신호 생성
- 전략 플러그인 구조
- 샘플 OHLCV 데이터 저장소
- 이동평균, RSI, 최대낙폭 등 기술지표
- ATR 기반 변동성 측정
- 단일 종목 백테스트
- 포트폴리오 단위 샘플 백테스트
- 거래비용 모델
- 전략 성과 비교
- 기관급 샘플 유니버스 스냅샷
- 종목 마스터 저장/로드
- OHLCV 데이터 품질 감사
- 포트폴리오 자본 배정 골격
- 기관급 익스포저 리스크 리포트
- 변동성 기반 포지션 사이징
- 포트폴리오 한도 점검 골격
- 상관관계 기반 집중도 분석 골격
- FX 오버레이 의사결정 골격
- 실시간 이벤트 버스 시뮬레이션
- 일일 운영 계획 생성
- 헬스체크
- 토스 API 준비도 점검
- 운영 대시보드용 상태 패널
- 운영 점검 리포트 생성
- 백테스트 성과 리포트 저장
- 투자위원회식 판단 생성
- 주문 후보 생성
- 미수/신용 절대 금지 리스크 차단
- 레버리지/인버스 종목 허용
- PAPER 모드 가상 체결
- JSONL 감사 로그 저장
- Phase 9-20 데이터 레이크/전략 연구소/펀드 리스크/거버넌스 명령
- 다전략 랭킹과 PAPER 승격 후보 평가
- DRY_RUN/PAPER/LIVE_AUTO 실행 라우팅 시뮬레이션
- KRW/USD 멀티통화 노출 분석
- 시장별 비용 정책과 펀드 보수 일할 계산
- 기본 운용 루프의 data lake/instrument master 유니버스 선택
- 기본 운용 루프의 주문 상태 머신 기록
- 투자위원회식 리서치 메모 생성
- 같은 익스포저 ETF 비용 최적화 추천
- USD/KRW 주문금액 정규화 기반 리스크 검사
- blocked/degraded 상태를 반영하는 daemon heartbeat
- 공식 브로커 스냅샷 기반 포지션 수량 불일치 reconciliation 검사
- 글로벌 헤지펀드 갭 통합 감사
- promotion evidence 기록 및 승격 조건 감사
- 리스크 패리티/역변동성/목표변동성 포트폴리오 최적화
- PAPER child-order 상태머신 시뮬레이션

## 빠른 실행

```bash
cd /home/zenith/Desktop/Atlas_Investment
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m atlas_investment.cli --mode paper --once
.venv/bin/python -m atlas_investment.cli backtest --symbol 005930 --strategy moving_average_cross
.venv/bin/python -m atlas_investment.cli portfolio-backtest
.venv/bin/python -m atlas_investment.cli compare --symbol 005930
.venv/bin/python -m atlas_investment.cli universe
.venv/bin/python -m atlas_investment.cli data-audit
.venv/bin/python -m atlas_investment.cli risk-report
.venv/bin/python -m atlas_investment.cli fx-overlay --usdkrw 1380 --usdkrw-average 1350
.venv/bin/python -m atlas_investment.cli realtime-smoke
.venv/bin/python -m atlas_investment.cli ops-plan
.venv/bin/python -m atlas_investment.cli ops-report
.venv/bin/python -m atlas_investment.cli healthcheck
.venv/bin/python -m atlas_investment.cli readiness
.venv/bin/python -m atlas_investment.cli toss-official-snapshot --symbol 005930
.venv/bin/python -m atlas_investment.cli hedgefund-readiness
.venv/bin/python -m atlas_investment.cli heartbeat-audit
.venv/bin/python -m atlas_investment.cli reconciliation-check
```

## Phase 9-20 헤지펀드 OS 명령

```bash
cd /home/zenith/Desktop/Atlas_Investment
.venv/bin/python -m atlas_investment.cli data-sync --max-symbols 4 --days 80
.venv/bin/python -m atlas_investment.cli strategy-lab --max-symbols 3 --days 120
.venv/bin/python -m atlas_investment.cli fund-risk
.venv/bin/python -m atlas_investment.cli fx-exposure
.venv/bin/python -m atlas_investment.cli execution-sim --mode live_auto --symbol 005930
.venv/bin/python -m atlas_investment.cli governance-report
.venv/bin/python -m atlas_investment.cli investment-memo --symbol 005930 --strategy moving_average_cross
.venv/bin/python -m atlas_investment.cli phase20-audit
.venv/bin/python -m atlas_investment.cli hedgefund-readiness
```

## API 제외 핵심 엔진 보강 명령

```bash
cd /home/zenith/Desktop/Atlas_Investment
.venv/bin/python -m atlas_investment.cli accounting-ledger --cash-usd 100 --usdkrw 1380
.venv/bin/python -m atlas_investment.cli cost-report --initial-cash 100000000 --ending-equity 103000000 --days 30
.venv/bin/python -m atlas_investment.cli data-snapshot-audit
.venv/bin/python -m atlas_investment.cli data-entitlements
.venv/bin/python -m atlas_investment.cli order-state-smoke --symbol 005930
.venv/bin/python -m atlas_investment.cli strategy-validate --symbol 005930 --strategy moving_average_cross --days 180
.venv/bin/python -m atlas_investment.cli strategy-readiness --strategy scalping_simulation --max-symbols 4 --days 220
.venv/bin/python -m atlas_investment.cli algo-execution-plan --algorithm vwap --mode paper --symbol 005930 --slices 5 --limit 10
.venv/bin/python -m atlas_investment.cli quant-portfolio --max-symbols 8 --days 220
.venv/bin/python -m atlas_investment.cli quant-portfolio --max-symbols 12 --days 260 --strategies multifactor_qvm,cross_sectional_momentum,all_weather_risk_parity,macro_regime_allocation,cta_diversified_trend,low_vol_defensive
.venv/bin/python -m atlas_investment.cli global-gap-audit
.venv/bin/python -m atlas_investment.cli portfolio-optimizer --max-symbols 6 --days 180 --optimizer-method risk_parity
.venv/bin/python -m atlas_investment.cli market-regime --symbol 005930 --days 260
.venv/bin/python -m atlas_investment.cli ensemble-backtest --max-symbols 8 --days 260
.venv/bin/python -m atlas_investment.cli child-order-sim --mode paper --algorithm adaptive --symbol 005930 --slices 4 --limit 8
.venv/bin/python -m atlas_investment.cli advanced-internal-upgrade --max-symbols 4 --days 220 --amount-krw 1000000
.venv/bin/python -m atlas_investment.cli mcp-catalog
.venv/bin/python -m atlas_investment.cli integration-check
.venv/bin/python -m atlas_investment.cli promotion-evidence-record --evidence-kind dry_run --status blocked --source smoke-test
.venv/bin/python -m atlas_investment.cli dashboard-html
.venv/bin/python -m atlas_investment.cli alerts-check
.venv/bin/python -m atlas_investment.cli heartbeat-audit
.venv/bin/python -m atlas_investment.cli etf-cost-optimizer --exposure-group NASDAQ100_KR_UNHEDGED --amount-krw 10000000 --holding-days 365 --current-symbol 133690
```

## MCP/Skill 연동 명령

```bash
cd /home/zenith/Desktop/Atlas_Investment
.venv/bin/python -m atlas_investment.cli integration-check
.venv/bin/python -m atlas_investment.cli kr-stock-search --query 삼성전자
.venv/bin/python -m atlas_investment.cli kr-stock-snapshot --market KOSPI --symbol 005930
.venv/bin/python -m atlas_investment.cli dart-readiness
.venv/bin/python -m atlas_investment.cli dart-disclosures
.venv/bin/python -m atlas_investment.cli dart-event-signals --days 7 --limit 20
.venv/bin/python -m atlas_investment.cli us-ohlcv --symbol AAPL --days 260
.venv/bin/python -m atlas_investment.cli mcp-catalog
.venv/bin/python -m atlas_investment.cli toss-platform-fit
.venv/bin/python -m atlas_investment.cli toss-official-snapshot --symbol 005930
.venv/bin/python -m atlas_investment.cli reconciliation-check
.venv/bin/python -m atlas_investment.cli cron-template
.venv/bin/python -m atlas_investment.cli daily-data-refresh --vendor hybrid --max-symbols 8 --days 260
.venv/bin/python -m atlas_investment.cli daily-data-refresh --vendor hybrid --include-kr-snapshots --max-symbols 8 --days 260
```

설치형으로 쓰려면:

```bash
cd /home/zenith/Desktop/Atlas_Investment
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
atlas-investment --mode paper --once
atlas-investment backtest --symbol AAPL --strategy breakout_momentum
```

## 중요 원칙

- 미수와 신용은 어떤 경우에도 금지합니다.
- 레버리지/인버스 종목은 허용하되 별도 비중 제한을 둘 수 있게 설계합니다.
- 토스증권 실주문 API가 공개되기 전까지 실거래 코드는 실행하지 않습니다.
- 실거래 연결 후에도 킬스위치, 주문 한도, 감사 로그가 먼저입니다.
- promotion evidence는 실제 `ok` 운용 증거만 승격 일수로 세고, smoke-test나 blocked/degraded 결과는 승격 증거로 세지 않습니다.
- 문서와 CLI 결과가 충돌하면 CLI 결과를 우선하고, 문서를 즉시 고칩니다.

## 문서 인덱스

- `docs/17_MCP_Skill_실제_연동_세팅.md`: 한국주식, DART, yfinance, Vibe, cron 연동 기록
- `docs/19_Phase_9_20_구현_진행기록.md`: Phase 9-20 코드/CLI 구현 기록
- `docs/20_API제외_완성도_재감사.md`: API 제외 기준 완성도와 부족한 영역 감사
- `docs/21_API제외_핵심엔진_보강기록.md`: 멀티통화, 데이터 감사, 주문 상태 머신, 전략 검증, 대시보드 보강
- `docs/22_ETF_비용최적화_엔진.md`: 같은 익스포저 ETF 비용 최적화 엔진
- `docs/23_전체_구현내용_문서화_감사.md`: 전체 구현 기능, 문서화 상태, 비용 체계 한계, CLI 통합 인덱스
- `docs/24_전체_프로그램_재검증_결과.md`: 토스증권 실API 제외 전체 프로그램 재검증 결과
- `docs/25_부족분_통합_보강기록.md`: 비용 정책, 런타임 유니버스, 주문 상태 머신 보강 기록
- `docs/26_운영품질_보강_및_API키_설정.md`: git 초기화, 대시보드, 데이터 갱신, DART 키, 당시 Toss 조회 경로 기록. 현재 비공식 경로는 52번 문서에서 제거됨.
- `docs/27_무인_헤지펀드급_운영_고도화_계획.md`: 무인 자동 운영을 위한 단계별 고도화 계획과 승격 기준
- `docs/28_글로벌_헤지펀드_무인자동화_검증_및_보강결과.md`: 글로벌 헤지펀드/24x7 무인화 검증 결과와 추가 보강 내역
- `docs/29_실거래봇_승격준비_최종보강기록.md`: 배치 리스크, look-ahead 방지, 토스 공식 API 게이트, reconciliation 보강 기록
- `docs/30_글로벌_헤지펀드_수준_재검증_2026-05-31.md`: 토스 API 출시 대비 글로벌 헤지펀드 수준 재검증
- `docs/31_API제외_완벽구현_검증_2026-05-31.md`: 토스 공식 API 제외 후에도 남는 미완성 영역 검증
- `docs/32_글로벌_헤지펀드_완성화_보강_및_한계기록_2026-05-31.md`: 추가 보강 결과와 코드만으로 해결 불가능한 글로벌 운용 한계
- `docs/33_완성요건_추가구현_및_최종검증_2026-05-31.md`: 글로벌 시장/자산군 모델, promotion evidence 감사, 최종 검증 기록
- `docs/34_토스API제외_실운영요건_구현_및_검증_2026-05-31.md`: 라이선스 데이터/heartbeat 감사와 systemd 실제 운영 검증
- `docs/35_전체문서_재검토_및_최종감사_2026-05-31.md`: 전체 문서 표현 수정, 최종 감사, 토스 API 출시 후 동작 가능성 판정
- `docs/36_토스증권_플랫폼_범위_13단계_매핑_2026-05-31.md`: 토스증권 지원 자산군 기준 13단계 매핑과 플랫폼 프로필
- `docs/37_전체문서_최신기준_일괄수정_2026-05-31.md`: 기존 전체 문서에 최신 기준 배너를 반영한 결과
- `docs/38_코드분석_리스크_전면보강_2026-05-31.md`: 코드 분석에서 확인한 리스크와 전면 보강 결과
- `docs/39_전체진행상황_종합문서화_2026-05-31.md`: 전체 구현·검증·커밋·남은 조건을 한 곳에 모은 종합 기록
- `docs/40_실거래수준_전략확장_및_한계기록_2026-05-31.md`: 글로벌 퀀트/헤지펀드 전략군 반영, TWAP/VWAP/POV 집행 계획, 전략 승격 게이트, 실거래 한계 기록
- `docs/41_퀀트전략_실거래수준_확장_및_문서화_2026-05-31.md`: QVM 멀티팩터, carry, 섹터 로테이션, 실적 이벤트, 전략 앙상블/배분 엔진 구현 기록
- `docs/42_완전무인_글로벌_헤지펀드_부족분_감사_2026-05-31.md`: 완전 무인 글로벌 헤지펀드/퀀트 기준 부족분, P0/P1/P2/P3 우선순위, 다음 구현 순서 감사
- `docs/43_API대기_실거래준비_내부인프라_구현_2026-05-31.md`: 토스 공식 API 대기 상태에서 가능한 갭 감사, promotion evidence 기록기, 포트폴리오 최적화, PAPER child-order, 전략 검증 강화 기록
- `docs/44_전체프로그램_문서감사_및_최신운영가이드_2026-05-31.md`: 전체 프로그램 문서 감사, 최신 운영 기준, CLI 지도, 검증 결과, 문서 유지보수 원칙
- `docs/45_핵심한계_해결시도_및_실거래완전자동화_정직한_최종기록_2026-05-31.md`: 핵심 한계 해결 요청에 대한 내부 보강, 외부 blocker, 검증 결과, 실거래 완전자동화 판정 기록
- `docs/46_실거래_완전무인_글로벌헤지펀드_부족분_전체해결상태_2026-05-31.md`: 부족분 전체 목록, 해결된 내부 항목, 외부 완료 조건, live 승격 runbook
- `docs/47_전략엔진_고도화_및_앙상블검증_구현기록_2026-06-01.md`: 시장국면 필터, 크로스섹션 랭킹, adaptive ensemble threshold, risk overlay, All Weather/Global Macro/CTA 전략군, adaptive 집행 계획, 강화 검증 지표, 앙상블 백테스트 구현 기록
- `docs/48_외부조건제외_완전무인글로벌헤지펀드_내부완성도_검증_2026-06-01.md`: 외부 API/데이터/계좌/운용증거 조건을 제외했을 때 내부 코드 blocker가 남아 있는지 검증한 결과
- `docs/49_전략_운영_리스크_AI_고도화_구현기록_2026-06-01.md`: 파라미터 자동 보정, 메타 allocator, 시장충격 비용, 고급 리스크, 전략 lifecycle, 데이터 방어, 이벤트 리플레이, 리서치 팩토리, audit trail, ML alpha 전략 구현 기록
- `docs/50_전체코드점검_MCP_스킬연결_감사_2026-06-01.md`: 전체 코드 점검, repo/workspace/codebase 스킬 사용, 로컬 금융 스킬과 GitHub/Hugging Face/Drive MCP 연결 감사 기록
- `docs/51_의존성_MCP_스킬_설치연결_검증_2026-06-01.md`: Python/Node 의존성, pygount, MCP/스킬 설치 및 연결 검증 기록. 비공식 토스 wrapper 기록은 `docs/52_토스_비공식_API_경로_정리_및_공식API_대기상태_2026-06-01.md`에서 제거로 대체됨.
- `docs/52_토스_비공식_API_경로_정리_및_공식API_대기상태_2026-06-01.md`: 비공식 토스 경로 제거와 공식 API 대기 adapter 상태 기록
- `docs/53_구동의존성_MCP_스킬_실거래직전_검증_2026-06-01.md`: 구동 의존성 재설치, MCP/스킬 연결, 비공식 토스 제거, 실거래 직전 검증 최신 결과

자세한 문서는 `docs/` 폴더를 보시면 됩니다.

<!-- BEGIN RELEASE STATUS -->
## 최신 배포 정보

- 저장소 버전: `v0.1.1`
- [변경사항과 검증 범위](RELEASE_NOTES.md)
- [GitHub 릴리즈](https://github.com/dkdleljh/Atlas_Investment/releases/latest)
<!-- END RELEASE STATUS -->
