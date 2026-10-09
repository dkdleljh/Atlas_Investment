# Phase 6 실시간 엔진 문서

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

## 목표

토스증권 WebSocket 또는 다른 시세 공급원을 붙일 때 실시간 이벤트를 안정적으로 처리할 수 있는 구조를 만드는 단계입니다.

## 이번 구현 내용

- `realtime/event_bus.py`
- 인메모리 이벤트 큐
- 시세 이벤트
- 주문 상태 이벤트
- 이벤트 배출 테스트

## 실행 방법

```bash
PYTHONPATH=src python3 -m atlas_investment.cli realtime-smoke
```

## 향후 연결 대상

- 실시간 현재가
- 실시간 호가
- 실시간 체결
- 주문 상태
- 체결 알림
- WebSocket 장애 감지
- 재연결 로직

## 안전 원칙

WebSocket 연결이 끊기거나 주문 상태 확인이 불가능하면 신규 주문을 중단해야 합니다.
