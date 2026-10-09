# Phase 4 전략 라이브러리 문서

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

## 목표

스캘핑, 초단타, 단타, 스윙, 장기 투자, ETF, 인버스, FX 오버레이 전략을 모두 플러그인으로 추가할 수 있게 만드는 단계입니다.

## 이번 구현 내용

현재 구현된 전략:

- `moving_average_cross`: 20일/60일 이동평균 교차 전략
- `rsi_mean_reversion`: RSI 평균회귀 전략
- `breakout_momentum`: 60일 신고가 돌파 전략

추가된 기능:

- 전략별 백테스트
- 같은 종목에 여러 전략을 적용해 성과 비교
- 전략 점수 산출 및 순위화

## 실행 방법

```bash
PYTHONPATH=src python3 -m atlas_investment.cli compare --symbol 005930
PYTHONPATH=src python3 -m atlas_investment.cli compare --symbol AAPL
```

## 결과 위치

```text
data/reports/{종목코드}_strategy_ranking.json
```

## 중요한 원칙

초단타와 스캘핑은 가장 나중에 실전 투입합니다. 이유는 실시간 호가 품질, 주문 지연, API 호출 제한, 체결 품질에 매우 민감하기 때문입니다.
