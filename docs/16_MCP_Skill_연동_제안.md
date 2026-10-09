# 최신화 주석(2026-06-01): 현재 토스증권 연동 기준은 공식 API 대기 상태입니다. 이 문서의 과거 toss-securities, tossctl, toss_readonly, toss-readonly 언급은 역사 기록이며 현재 실행 경로에서는 제거되었습니다. 최신 기준은 docs/52_토스_비공식_API_경로_정리_및_공식API_대기상태_2026-06-01.md 및 docs/53_구동의존성_MCP_스킬_실거래직전_검증_2026-06-01.md를 따릅니다.

# Atlas Investment MCP/Skill 연동 제안

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

작성일: 2026-05-30

## 결론

Atlas Investment에 가장 먼저 붙이면 좋은 것은 실거래 주문 MCP가 아니라, 다음 네 가지입니다.

1. 시장 데이터
2. 공시/재무 데이터
3. 리서치/퀀트 분석
4. 운영 자동화

토스증권 실주문은 공식 API 문서와 키가 공개되기 전까지 계속 차단 상태로 유지해야 합니다.

## 1순위: Korean Stock Search

용도:

- KRX 상장 종목 검색
- 종목코드/시장구분 확인
- 종목 기본정보 확인
- 일별 시세 스냅샷 조회

Atlas Investment에 붙일 위치:

- `data/instruments.py`
- `data/vendors.py`
- `data-audit` 명령

기대 효과:

- 샘플 한국 종목 마스터를 실제 KRX 기반 종목 마스터로 대체할 수 있습니다.
- 한국장 유니버스 자동 갱신의 첫 연결점으로 적합합니다.

주의:

- 실시간 호가/체결/분봉은 범위 밖입니다.
- 투자 판단이 아니라 데이터 공급원으로만 써야 합니다.

## 2순위: k-dart

용도:

- DART 공시 검색
- 기업개황
- 재무제표
- 배당
- 증자/감자
- 감사의견
- 소송/전환사채/합병 등 주요 이벤트

Atlas Investment에 붙일 위치:

- `data/fundamentals.py`
- `strategy/event.py`
- `reports/company_report.py`
- 투자위원회 입력 데이터

기대 효과:

- 단순 차트 기반 시스템에서 공시/재무 기반 운용 시스템으로 올라갈 수 있습니다.
- 장기/스윙/이벤트 전략의 품질이 크게 좋아집니다.

주의:

- `API_K_DART` 환경변수가 필요합니다.
- 공시 데이터는 투자 판단의 재료이지 자동 매수 사유가 되면 안 됩니다.

## 3순위: Vibe Trading MCP

확인된 유용 기능:

- `get_market_data`: yfinance/akshare/ccxt/okx/tushare 기반 OHLCV 조회
- `factor_analysis`: 팩터 IC/IR, 상하위 그룹 수익률 분석
- `pattern_recognition`: 차트 패턴 인식
- `load_skill`: 퀀트/리스크/전략 방법론 문서 로드

특히 유용한 내장 금융 스킬:

- `data-routing`: 데이터 소스 선택
- `yfinance`: 미국 주식/ETF 데이터
- `akshare`: 글로벌/중국/미국/HK/FX 등 무료 데이터 보완
- `technical-basic`: 기본 기술지표 묶음
- `risk-analysis`: VaR/CVaR/스트레스 테스트
- `asset-allocation`: 자산배분/리밸런싱
- `factor-research`: 팩터 검증
- `multi-factor`: 멀티팩터 랭킹
- `execution-model`: 슬리피지/시장충격 모델
- `performance-attribution`: 성과 기여도 분석
- `global-macro`: 글로벌 매크로
- `hedging-strategy`: 헤지 전략
- `etf-analysis`: ETF 분석
- `report-generate`: 리서치 리포트 생성

Atlas Investment에 붙일 위치:

- `data/vendors.py`
- `backtest/portfolio_engine.py`
- `risk/`
- `strategy/`
- `analytics/`

기대 효과:

- 미국 주식/ETF 데이터 연결에 바로 쓸 수 있습니다.
- 백테스트, 리스크, 팩터 연구 수준을 빠르게 올릴 수 있습니다.

주의:

- 외부 MCP 결과를 그대로 주문으로 연결하지 말고, 내부 데이터 품질 검사와 리스크 엔진을 반드시 통과시켜야 합니다.

## 4순위: Investment Committee Skill

용도:

- 투자 아이디어를 역할별로 검토
- 매수/보유/관망/회피 판단 메모 생성
- 리스크, 포지션 크기, 진입/청산 조건 정리

Atlas Investment에 붙일 위치:

- `committee/engine.py`
- `reports/investment_memo.py`
- 수동 승인 또는 PAPER 검증 전 단계

기대 효과:

- 자동 신호가 바로 주문 후보가 되는 것을 막고, 감사 가능한 판단 기록을 남길 수 있습니다.

주의:

- 이 스킬도 매매 실행 도구가 아닙니다.
- 최종 주문은 Atlas Investment 리스크 엔진과 모드 정책이 결정해야 합니다.

## 5순위: Toss Securities Skill

용도:

- 토스증권 계좌 요약 조회
- 포트폴리오 조회
- 시세 조회
- 주문/체결 내역 조회
- 관심종목 조회

Atlas Investment에 붙일 위치:

- `brokers/toss_readonly.py`
- `reports/account_snapshot.py`
- `readiness` 명령

기대 효과:

- 실계좌 상태와 Atlas Investment 내부 포트폴리오 상태를 비교할 수 있습니다.
- 주문 실행이 아니라 계좌 상태 검증과 리포트에 유용합니다.

주의:

- 현재 스킬은 read-only입니다.
- 실거래 mutation으로 확장하면 안 됩니다.

## 6순위: Cron MCP / Cron Dashboard

용도:

- 매일 장전/장중/장마감 자동 실행
- 정해진 시간에 데이터 감사/리스크 리포트/운영 리포트 실행
- 실패한 자동화 점검

Atlas Investment에 붙일 위치:

- `ops/scheduler.py`
- `ops/healthcheck.py`
- 향후 `daemon` 또는 외부 cron job

기대 효과:

- 현재 수동 CLI 실행 중심 구조를 실제 무인 운영 루프로 바꿀 수 있습니다.

추천 자동 실행:

- 한국장 장전: `data-audit`, `risk-report`
- 한국장 장중: `realtime-smoke`, 향후 paper monitor
- 한국장 마감: `ops-report`
- 미국장 장전: `data-audit`, `fx-overlay`
- 매일 1회: `healthcheck`, `readiness`

## 7순위: Telegram / Nodes 알림

용도:

- 운영 리포트 전송
- 리스크 차단 알림
- 데이터 품질 장애 알림
- LIVE_AUTO 차단 알림

Atlas Investment에 붙일 위치:

- `ops/alerts.py`
- `ops/reporting.py`

기대 효과:

- 무인 운영에서 사람이 반드시 알아야 할 사건만 알려줄 수 있습니다.

주의:

- 계좌번호, 주문 상세, 개인정보는 과도하게 보내지 않아야 합니다.

## 추천 연동 순서

가장 안전하고 효과적인 순서는 다음입니다.

1. `korean-stock-search`로 한국 종목 마스터/일별 시세 연결
2. `Vibe Trading get_market_data` 또는 `yfinance`로 미국 주식/ETF OHLCV 연결
3. `k-dart`로 공시/재무/이벤트 데이터 연결
4. `Vibe Trading risk-analysis`, `factor-research`, `asset-allocation`로 리스크와 전략 연구 보강
5. `investment-committee`로 주문 후보의 판단 기록 생성
6. `toss-securities` read-only로 실계좌 스냅샷 비교
7. `cron`으로 장전/장중/마감 자동 운영
8. `Telegram/Nodes`로 중요 알림 전송

## 구현 원칙

- MCP/Skill은 데이터와 판단 보조 계층으로 둡니다.
- 주문 실행은 Atlas Investment 내부 브로커 계층만 담당합니다.
- 실거래는 공식 토스 API가 확인되기 전까지 차단합니다.
- 외부 데이터는 반드시 `data-audit`와 리스크 엔진을 통과시킵니다.
- 미수/신용 금지 정책은 어떤 MCP/Skill 결과보다 우선합니다.
