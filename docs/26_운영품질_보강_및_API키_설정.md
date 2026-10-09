# 최신화 주석(2026-06-01): 현재 토스증권 연동 기준은 공식 API 대기 상태입니다. 이 문서의 과거 toss-securities, tossctl, toss_readonly, toss-readonly 언급은 역사 기록이며 현재 실행 경로에서는 제거되었습니다. 최신 기준은 docs/52_토스_비공식_API_경로_정리_및_공식API_대기상태_2026-06-01.md 및 docs/53_구동의존성_MCP_스킬_실거래직전_검증_2026-06-01.md를 따릅니다.

# 운영품질 보강 및 API 키 설정

> 최신 기준(2026-05-31): Atlas Investment은 토스증권 공식 API 출시 전 안전한 PAPER/DRY_RUN 운용 OS입니다. 완성된 글로벌 헤지펀드 또는 실거래 봇으로 판정하지 않습니다. 토스 플랫폼 범위는 KR/US 주식·ETF·채권·미국주식 옵션 중심이며, 직접 선물·현물 FX·직접 원자재 거래는 공식 지원 전까지 제외합니다. 실거래는 공식 API adapter 구현, read-only reconciliation, 30일 heartbeat, promotion evidence 통과 후에만 검토합니다.

작성일: 2026-05-31

## 목적

이 문서는 Atlas Investment을 실거래 전 안전 운용 플랫폼으로 더 다루기 쉽게 만들기 위한 운영 보강 기록이다.

이번 보강 범위는 다음 다섯 가지다.

1. git 저장소 초기화와 변경 이력 관리
2. 사람이 보기 좋은 HTML 운영 대시보드
3. DART 공시 이벤트 신호 강화
4. yfinance/한국주식 기반 데이터 레이크 정기 갱신 루틴
5. Toss 공식 API 전 read-only 계좌/포트폴리오 동기화 경로

토스 실주문 API는 여전히 공식 문서와 키가 공개되기 전까지 연결하지 않는다.

## 1. Git 저장소 초기화

프로젝트 루트:

```bash
/home/zenith/Desktop/Atlas_Investment
```

초기화 후 첫 커밋을 남긴다.

```bash
cd /home/zenith/Desktop/Atlas_Investment
git status --short --branch
```

주의:

- `.env`, `.venv`, 테스트 캐시, 보고서 산출물 일부는 `.gitignore`로 제외한다.
- API 키, 계좌번호, 토큰은 커밋하지 않는다.
- 실거래 API 연결 전까지 `LIVE_AUTO` 차단 정책은 유지한다.

## 2. HTML 운영 대시보드

명령:

```bash
cd /home/zenith/Desktop/Atlas_Investment
.venv/bin/python -m atlas_investment.cli dashboard-html
```

출력:

```text
data/reports/dashboard.html
```

개선 내용:

- OK/degraded/blocked 상태 요약
- 리포트 인덱스 테이블
- 리포트별 상태 배지
- 핵심 메트릭 표시
- JSON 요약의 스크롤 가능한 패널 표시

브라우저에서 `data/reports/dashboard.html`을 열면 운영 상태를 한눈에 볼 수 있다.

## 3. DART API 키 설정

Atlas Investment은 DART 키를 코드에 저장하지 않고 환경변수 `API_K_DART`로 읽는다.

### 발급

1. OpenDART 사이트 접속: `https://opendart.fss.or.kr/`
2. 회원가입/로그인
3. 인증키 신청
4. 발급된 인증키를 복사

### 일회성 입력

터미널에서 현재 세션에만 적용하려면:

```bash
export API_K_DART="발급받은_인증키"
cd /home/zenith/Desktop/Atlas_Investment
.venv/bin/python -m atlas_investment.cli dart-readiness
```

정상 설정되면 `status`가 `ok`로 나온다.

### 프로젝트 `.env`에 저장

```bash
cd /home/zenith/Desktop/Atlas_Investment
cp .env.example .env
nano .env
```

`.env`에서 아래 줄을 채운다.

```bash
API_K_DART=발급받은_인증키
```

사용할 때:

```bash
set -a
source .env
set +a
.venv/bin/python -m atlas_investment.cli dart-readiness
```

`.env`는 `.gitignore`에 포함되어야 하며 커밋하면 안 된다.

### 공시 이벤트 신호

키 설정 후:

```bash
.venv/bin/python -m atlas_investment.cli dart-event-signals --days 7 --limit 20
```

출력:

```text
data/reports/dart_event_signals.json
```

분류 예시:

- 실적/손익 공시: `earnings`, 중요도 `high`, 액션 `refresh_memo`
- 유상증자/CB/감자: `capital_action`, 중요도 `high`, 액션 `risk_review`
- 합병/분할/영업양수도: `corporate_action`, 중요도 `high`, 액션 `event_review`
- 조회공시/풍문/보도: `rumor_inquiry`, 중요도 `medium`, 액션 `headline_monitor`
- 정정공시: `correction`, 중요도 `medium`, 액션 `diff_review`

## 4. 데이터 레이크 정기 갱신

새 명령:

```bash
.venv/bin/python -m atlas_investment.cli daily-data-refresh --vendor hybrid --max-symbols 8 --days 260
```

`--vendor` 옵션:

- `sample`: 네트워크 없이 샘플 OHLCV 생성
- `yfinance`: yfinance만 사용
- `hybrid`: yfinance를 먼저 시도하고 빈 결과나 예외가 발생하면 샘플 데이터로 fallback

한국주식 스냅샷까지 함께 조회하려면 명시적으로 플래그를 붙인다.

```bash
.venv/bin/python -m atlas_investment.cli daily-data-refresh --vendor hybrid --include-kr-snapshots --max-symbols 8 --days 260
```

출력:

```text
data/reports/daily_data_refresh.json
data/lake/ohlcv/*.csv
data/lake/fx/USD_KRW.csv
data/lake/instrument_master.json
```

한국주식 스냅샷은 `KSKILL_PROXY_BASE_URL` 기반으로 조회한다. 실패해도 전체 루틴은 `degraded`로 남기고 OHLCV 결과를 보존한다. 단, 기본 `sample` 실행은 네트워크 호출 없이 끝나도록 스냅샷 조회를 켜지 않는다.

OpenClaw cron 템플릿에도 장전 루틴이 보강되어 있다.

```bash
.venv/bin/python -m atlas_investment.cli cron-template
```

## 5. Toss read-only 동기화 경로

상태 확인:

```bash
.venv/bin/python -m atlas_investment.cli toss-readonly-status
```

스냅샷 동기화:

```bash
.venv/bin/python -m atlas_investment.cli toss-readonly-sync
```

출력:

```text
data/reports/toss_readonly_sync.json
data/toss_readonly/account_summary.json
data/toss_readonly/positions.json
data/toss_readonly/allocation.json
```

현재 `tossctl`이 없으면 `blocked`로 기록된다. 이 상태는 정상이다.

중요:

- 이 경로는 주문 제출을 하지 않는다.
- 계좌/포트폴리오 조회만 목표로 한다.
- Toss 공식 실주문 API가 공개되기 전까지 `LIVE_AUTO` 주문은 계속 차단한다.

## 검증 명령

```bash
cd /home/zenith/Desktop/Atlas_Investment
.venv/bin/python -m compileall -q src tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip check
.venv/bin/python -m atlas_investment.cli dashboard-html
.venv/bin/python -m atlas_investment.cli daily-data-refresh --vendor sample --max-symbols 3 --days 90
.venv/bin/python -m atlas_investment.cli daily-data-refresh --vendor sample --include-kr-snapshots --max-symbols 3 --days 90
.venv/bin/python -m atlas_investment.cli dart-event-signals --days 7 --limit 20
.venv/bin/python -m atlas_investment.cli toss-readonly-sync
```

## 현재 판정

이번 보강 후 Atlas Investment은 실거래 전 운영 관찰성이 좋아졌다.

남은 외부 의존성은 명확하다.

- DART: `API_K_DART` 입력 필요
- Toss read-only: `tossctl` 설치/로그인 경로 필요
- Toss live order: 공식 API 문서와 실주문 키 필요
- 전체 시장 고품질 데이터: survivorship-bias-free 데이터 공급원 필요

## 6. 추가 보강 사항

- 운영 산출물은 `.gitignore`에 분리한다. `data/reports`, `data/lake`, `data/orders`, `data/toss_readonly`, 외부 OHLCV 캐시는 커밋하지 않는다.
- OpenDART HTTP 성공 응답 안의 `status` 값도 검사한다. 정상 `000`과 데이터 없음 `013` 외의 상태는 명시적 오류로 처리한다.
- Toss read-only 동기화는 일부 하위 조회가 실패해도 가능한 스냅샷은 저장하고 전체 상태를 `degraded`로 남긴다.
