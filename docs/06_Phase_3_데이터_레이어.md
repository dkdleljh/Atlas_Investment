# Phase 3 데이터 레이어 문서

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

## 목표

한국장, 미국장, ETF/ETN, 레버리지/인버스, 향후 외환 데이터까지 담을 수 있는 데이터 계층을 만드는 단계입니다.

## 이번 구현 내용

- `data/universe.py`
- 기관급 샘플 유니버스
- 거래 가능 종목 필터
- 유니버스 JSON 스냅샷 저장
- 기존 `ohlcv_store.py`와 연결 가능한 구조

## 실행 방법

```bash
cd /home/zenith/Desktop/Atlas_Investment
PYTHONPATH=src python3 -m atlas_investment.cli universe
```

## 결과 위치

```text
data/universe/institutional_sample_universe.json
```

## 아직 남은 일

- KRX 공식 종목 마스터 연결
- 미국장 종목 마스터 연결
- ETF/ETN 메타데이터 자동 갱신
- 거래정지/관리종목/저유동성 필터
- 실제 일봉/분봉 데이터 공급원 연결
