# Phase 8 기관급 운영체계 문서

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

## 목표

Atlas Investment을 단순 실행 프로그램이 아니라 매일 점검하고 기록하는 운용 시스템으로 만드는 단계입니다.

## 이번 구현 내용

- `ops/reporting.py`
- 일일 리스크 리포트 저장
- 운영 점검 Markdown 리포트 생성
- 운영 상태 명령 추가

## 실행 방법

```bash
PYTHONPATH=src python3 -m atlas_investment.cli ops-report
```

## 결과 위치

```text
data/reports/ops_status.md
```

## 매일 점검해야 할 항목

- 실거래 모드가 의도치 않게 켜져 있지 않은지
- 킬스위치 상태
- 미수/신용 금지 정책
- 레버리지/인버스 비중
- 일간 손실
- 월간 손실
- 주문 실패
- 데이터 지연
- WebSocket 연결
- 브로커 API 오류

## 완전 자동 운용 전 필수 조건

- 최소 수개월 PAPER 검증
- 전략별 성과 리포트
- 리스크 차단 로그 검토
- 실제 API 장애 테스트
- 소액 실거래 테스트
- 실시간 모니터링
- 수동 킬스위치
