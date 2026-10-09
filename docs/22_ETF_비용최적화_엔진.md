# ETF 비용 최적화 엔진

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

Atlas Investment은 같은 익스포저를 제공하는 ETF 후보를 비용 기준으로 비교할 수 있다.

예를 들어 나스닥100 익스포저가 필요할 때 KODEX, TIGER, ACE 계열 후보를 하나의 그룹으로 묶고 다음 비용을 합산한다.

- 총보수, 기타비용, 추적오차
- 매매 수수료
- 매수/매도 스프레드
- 거래대금 부족 패널티
- 괴리율/프리미엄 패널티
- 기존 보유 ETF를 교체할 때의 왕복 거래비용과 안전마진

## 설정 파일

```text
config/etf_equivalence.json
```

현재 값은 로컬 테스트용 샘플이다. 실투자 판단 전에는 운용사, 거래소, 증권사, 데이터 벤더 값으로 갱신해야 한다.

## 명령

```bash
.venv/bin/python -m atlas_investment.cli etf-cost-optimizer \
  --exposure-group NASDAQ100_KR_UNHEDGED \
  --amount-krw 10000000 \
  --holding-days 365 \
  --current-symbol 133690
```

결과 파일:

```text
data/reports/etf_cost_optimizer_NASDAQ100_KR_UNHEDGED.json
```

## 교체 기준

이미 보유한 ETF가 있다면 최저 비용 ETF가 새로 발견되어도 무조건 교체하지 않는다.

```text
예상 절감액 > 교체 거래비용 + 안전마진
```

이 기준을 넘지 못하면 현재 ETF를 유지한다. 장기보유 규모가 크면 작은 보수 차이도 의미가 커지고, 단기/소액 운용이면 교체비용이 절감액보다 클 수 있다.

## 한계

- 현재 ETF 비용 DB는 샘플이다.
- 실시간 호가 스프레드, 실제 체결비용, 실시간 괴리율은 API 연결 후 갱신해야 한다.
- 세금은 상품별/계좌별로 달라질 수 있으므로 설정값으로 분리해서 관리해야 한다.
