# API 제외 완성도 재감사

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

작성일: 2026-05-30

## 결론

API 연결을 제외하더라도 Atlas Investment은 아직 “완벽하게 프로그래밍 완료” 상태는 아니다.

정확한 상태는 다음과 같다.

- CLI, 테스트, 문서, 안전 차단, 샘플 데이터 기반 운용 흐름은 정상 동작한다.
- 헤지펀드 OS로 확장하기 위한 모듈 경계와 명령 체계는 잡혀 있다.
- 다만 실제 운용 시스템으로 보기에는 샘플/시뮬레이션/골격 성격이 남아 있다.
- 특히 멀티통화 회계, 실제 데이터 신뢰성, 스캘핑 실시간성, 전략 검증 깊이, 주문 상태 관리, 대시보드 UI는 아직 완성 영역이 아니다.

## 검증한 것

```text
compileall 통과
unittest 35개 통과
pip check 통과
핵심 CLI smoke 통과
DRY_RUN 통과
PAPER 통과
Phase 9-20 명령 통과
```

실행 확인 명령:

```bash
.venv/bin/python -m compileall -q src tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
.venv/bin/python -m atlas_investment.cli integration-check
.venv/bin/python -m atlas_investment.cli data-audit --max-symbols 4 --days 130
.venv/bin/python -m atlas_investment.cli portfolio-backtest --max-symbols 3 --days 120
.venv/bin/python -m atlas_investment.cli risk-report
.venv/bin/python -m atlas_investment.cli fx-overlay --usdkrw 1380 --usdkrw-average 1350
.venv/bin/python -m atlas_investment.cli realtime-smoke
.venv/bin/python -m atlas_investment.cli ops-plan
.venv/bin/python -m atlas_investment.cli healthcheck
.venv/bin/python -m atlas_investment.cli readiness
.venv/bin/python -m atlas_investment.cli ops-report
.venv/bin/python -m atlas_investment.cli data-sync --max-symbols 4 --days 80
.venv/bin/python -m atlas_investment.cli strategy-lab --max-symbols 3 --days 120
.venv/bin/python -m atlas_investment.cli fund-risk
.venv/bin/python -m atlas_investment.cli fx-exposure
.venv/bin/python -m atlas_investment.cli execution-sim --mode live_auto --symbol 005930
.venv/bin/python -m atlas_investment.cli governance-report
.venv/bin/python -m atlas_investment.cli investment-memo --symbol 005930 --strategy moving_average_cross
.venv/bin/python -m atlas_investment.cli phase20-audit
```

## API 제외 후에도 남은 주요 미완성 영역

### 1. 실제 데이터 레이크 미완성

현재 데이터 레이크는 구조와 명령은 있으나, 여전히 샘플 유니버스와 샘플 OHLCV에 크게 의존한다.

필요한 것:

- 전체 KRX/US 종목 마스터
- 상장폐지/거래정지/관리종목 이력
- 배당/분할/액면분할 보정 가격
- 데이터 버전 관리
- 데이터 결측/이상치 자동 복구

### 2. 멀티통화 회계 미완성

현재 포트폴리오 모델은 `equity_krw` 중심이며, USD 포지션의 원화 환산과 원통화 원장 구분이 완전하지 않다.

실제 운용 전 필요한 것:

- 원화 현금, 달러 현금 분리
- 포지션 원통화 평가금액과 원화 환산 평가금액 분리
- 환전 체결 기록
- 환율 기준 시각 기록
- 원화 기준 성과와 달러 기준 성과 분해

### 3. 스캘핑/초단타는 시뮬레이션 전용

스캘핑 전략 플러그인은 존재하지만 일봉 기반 후보 생성이다.

실전 스캘핑에 필요한 것:

- 실시간 호가
- 실시간 체결
- 주문 큐
- 미체결 정정/취소
- 지연시간 측정
- 슬리피지/체결확률 모델

### 4. 전략 검증 깊이 부족

전략 연구소는 여러 전략을 돌리고 랭킹을 만들지만, 아직 기관급 검증은 아니다.

필요한 것:

- 워크포워드 테스트
- 아웃오브샘플 테스트
- 몬테카를로 경로 시뮬레이션
- 파라미터 과최적화 경고
- 시장 국면별 성과 분해
- 전략 간 상관관계 기반 자본 배분

### 5. 주문 상태 머신 미완성

API 연결을 제외하더라도 주문 상태 모델은 더 고도화해야 한다.

필요한 것:

- 주문 생성, 제출 대기, 제출, 부분체결, 전체체결, 정정, 취소, 거부, 만료 상태
- idempotency 저장소
- 중복 주문 방지
- 주문 이벤트 재처리
- 계좌/체결 reconciliation

### 6. 대시보드 UI 미완성

현재는 JSON/Markdown 리포트 중심이다.

필요한 것:

- 웹 대시보드
- 실시간 상태 패널
- 전략별 성과
- 리스크 한도 사용률
- 주문 후보와 차단 사유
- 데이터 품질 상태

## 현재 완성도가 높은 영역

- 안전 기본값
- 미수/신용 차단
- LIVE_AUTO 차단
- DRY_RUN/PAPER 실행 흐름
- CLI 명령 체계
- 단위 테스트 기반 회귀 방지
- 문서화
- 기본 백테스트
- 기본 리스크 검사
- Phase 9-20 모듈 경계

## 최종 판정

```text
API 제외 완성도: 65~70%
개발/검증용 플랫폼 완성도: 높음
실전 무인 운용 완성도: 아직 부족
초거대 헤지펀드급 완성도: 구조는 시작됐지만 핵심 엔진은 추가 필요
```

다음으로 가장 먼저 해야 할 일:

1. 멀티통화 포트폴리오 회계 모델 정리
2. 데이터 레이크를 샘플 데이터에서 실제 데이터 스냅샷 기반으로 전환
3. 주문 상태 머신과 idempotency 저장소 구현
4. 전략 연구소에 워크포워드/몬테카를로/과최적화 진단 추가
5. 운영 대시보드 구현
