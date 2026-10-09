# Phase 5 포트폴리오와 기관급 리스크 문서

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

## 목표

여러 전략이 동시에 낸 신호를 하나의 포트폴리오 관점에서 정리하고, 시장/섹터/레버리지/인버스 노출을 관리합니다.

## 이번 구현 내용

포트폴리오:

- `portfolio/manager.py`
- 전략 신호를 자본 배정으로 변환
- 현금 버퍼 유지
- 목표 비중 기반 주문 후보 생성

기관급 리스크:

- `risk/institutional.py`
- 시장별 비중 계산
- 섹터별 비중 계산
- 레버리지/인버스 총 비중 계산
- 현금 비중 점검
- 한도 초과 항목 기록

## 실행 방법

```bash
PYTHONPATH=src python3 -m atlas_investment.cli risk-report
```

## 결과 위치

```text
data/reports/daily_risk_report.json
```

## 절대 정책

- 미수 금지
- 신용 금지
- 레버리지/인버스 허용
- 단, 레버리지/인버스는 별도 총 비중 한도 필요
