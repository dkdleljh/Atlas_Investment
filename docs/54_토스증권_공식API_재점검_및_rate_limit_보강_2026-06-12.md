# 토스증권 공식 API 재점검 및 rate limit 보강

작성 시각: 2026-06-12 KST

## 공식 source of truth

- `https://developers.tossinvest.com/llms.txt`
- `https://openapi.tossinvest.com/openapi-docs/overview.md`
- `https://openapi.tossinvest.com/openapi-docs/latest/openapi.json`
- OpenAPI version: `1.1.1`

## 공식 문서와 대조한 핵심 기준

- 연동 방식: REST only. WebSocket URL은 현재 구동 필수값이 아니다.
- Base API server: `https://openapi.tossinvest.com`
- 인증: OAuth2 Client Credentials Grant, `POST /oauth2/token`, `application/x-www-form-urlencoded`
- 공통 인증 헤더: `Authorization: Bearer {access_token}`
- 계좌·자산·주문/주문정보 헤더: `X-Tossinvest-Account: {accountSeq}`
- 주요 조회 endpoint:
  - `GET /api/v1/accounts`
  - `GET /api/v1/holdings`
  - `GET /api/v1/prices`
  - `GET /api/v1/stocks`
  - `GET /api/v1/orderbook`
  - `GET /api/v1/orders?status=OPEN`
  - `GET /api/v1/buying-power`
  - `GET /api/v1/sellable-quantity`
  - `GET /api/v1/commissions`

## Rate limit 기준

공식 문서 기준 client x API group 단위 TPS:

- `AUTH`: 5 TPS
- `ACCOUNT`: 1 TPS
- `ASSET`: 5 TPS
- `STOCK`: 5 TPS
- `MARKET_INFO`: 3 TPS
- `MARKET_DATA`: 10 TPS
- `MARKET_DATA_CHART`: 5 TPS
- `ORDER`: 6 TPS, 09:00-09:10 KST 피크 3 TPS
- `ORDER_HISTORY`: 5 TPS
- `ORDER_INFO`: 6 TPS, 09:00-09:10 KST 피크 3 TPS

보강 후 클라이언트는 문서상 TPS와 응답 헤더 `X-RateLimit-Limit` 중 더 낮은 값을 사용한다. 429 응답은 `Retry-After`를 우선하고, 정상 응답에서도 `X-RateLimit-Remaining: 0`이면 `X-RateLimit-Reset` 기준으로 짧게 완화한다.

## 수정 사항

- `TOSS_API_OPENAPI_SPEC_URL` 기본값을 공식 최신 JSON 경로로 추가했다.
- `TossOfficialApiClient`에 공식 read-only 및 주문 전 검증 조회 메서드를 보강했다.
- rate limit 처리에 lock과 동적 헤더 반영을 추가했다.
- README, `.env.example`, dashboard, 과거 docs/52의 REST/WebSocket 표현을 REST only 기준으로 정정했다.
- 실주문 mutation은 계좌에 직접 영향이 있으므로 기존대로 promotion evidence/수동 검토 전 차단한다.

## 검증

```text
.venv/bin/python -m unittest discover -s tests
Ran 85 tests ... OK

.venv/bin/python -m compileall -q src tests
OK

.venv/bin/python -m atlas_investment.cli readiness
status=blocked
official_docs_verified=true
missing: client_id, client_secret, accountSeq

.venv/bin/python -m atlas_investment.cli integration-check
overall_status=ok
```

## 구동 방법

`.env` 또는 환경변수에 아래 값만 채우면 공식 read-only 스냅샷/시세 조회 경로가 동작한다.

```text
TOSS_CLIENT_ID=...
TOSS_CLIENT_SECRET=...
TOSS_ACCOUNT_SEQ=...
```

실행:

```bash
.venv/bin/python -m atlas_investment.cli readiness
.venv/bin/python -m atlas_investment.cli toss-official-snapshot --symbol 005930
```
