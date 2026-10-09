# API 제외 핵심 엔진 보강 기록

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

작성일: 2026-05-30

## 목표

`20_API제외_완성도_재감사.md`에서 확인한 부족한 영역을 API 연결 없이 가능한 범위에서 보강한다.

## 보강한 영역

### 1. 멀티통화 포트폴리오 회계

추가 모듈:

- `atlas_investment.accounting.multicurrency`

추가 명령:

```bash
.venv/bin/python -m atlas_investment.cli accounting-ledger --cash-usd 100 --usdkrw 1380
```

기능:

- KRW/USD 현금 분리
- 포지션 원통화 평가금액과 원화 환산 평가금액 분리
- 통화별 비중 계산
- 환율 누락/외화 현금 누락 경고

### 2. 데이터 스냅샷 감사

추가 모듈:

- `atlas_investment.data.audit`

추가 명령:

```bash
.venv/bin/python -m atlas_investment.cli data-snapshot-audit
```

기능:

- 데이터 레이크 CSV 스냅샷 행 수 확인
- 최초/최종 날짜 확인
- 날짜 정렬 확인
- SHA-256 체크섬 생성
- 경고 수 집계

### 3. 주문 상태 머신

추가 모듈:

- `atlas_investment.execution.state_machine`

추가 명령:

```bash
.venv/bin/python -m atlas_investment.cli order-state-smoke --symbol 005930
```

기능:

- 주문 상태 정의
- 허용 전이 검증
- idempotency key 기반 저장
- 이벤트 히스토리 저장
- 간단한 broker reconciliation 비교

상태:

```text
created
validated
queued
submitted
partially_filled
filled
cancel_requested
cancelled
rejected
expired
blocked
```

### 4. 전략 검증 고도화

추가 모듈:

- `atlas_investment.backtest.validation`

추가 명령:

```bash
.venv/bin/python -m atlas_investment.cli strategy-validate --symbol 005930 --strategy moving_average_cross --days 180 --folds 3 --trials 100
```

기능:

- 워크포워드 검증
- fold별 테스트 수익률/최대낙폭/거래 횟수 기록
- 몬테카를로 경로 시뮬레이션
- 손실 확률 계산
- 과최적화/불안정 경고 생성

### 5. 운영 대시보드

추가 모듈:

- `atlas_investment.analytics.html_dashboard`

추가 명령:

```bash
.venv/bin/python -m atlas_investment.cli dashboard-html
```

기능:

- `data/reports/*.json` 요약
- 정적 HTML 대시보드 생성
- 결과 파일: `data/reports/dashboard.html`

## 검증 결과

```text
compileall 통과
unittest 40개 통과
pip check 통과
accounting-ledger 정상
data-snapshot-audit 정상
order-state-smoke 정상
strategy-validate 정상
dashboard-html 정상
```

## 여전히 API 없이는 남는 한계

- 실제 실시간 호가/체결
- 실제 주문 제출/정정/취소
- 실제 계좌 reconciliation
- 전체 시장의 완전한 생존편향 제거 데이터
- 외부 데이터 벤더 수준의 corporate action 보정

하지만 API 제외 내부 엔진 기준으로는 이전보다 훨씬 실전형 구조에 가까워졌다.
