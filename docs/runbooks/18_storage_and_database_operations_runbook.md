# 18. CoinPilot 저장소/DB 운영 Runbook

작성일: 2026-03-07  
상태: Ready  
대상: CoinPilot 운영/개발을 직접 수행하는 사용자(초보~중급)  
관련 문서:
- `docs/PROJECT_CHARTER.md`
- `docs/Data_Flow.md`
- `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`

---

## 0. 이 문서의 목적

이 문서는 CoinPilot에서 사용하는 저장소를 처음부터 끝까지 한 번에 이해하기 위한 운영 문서다.

포함 범위:
1. PostgreSQL, TimescaleDB, pgvector, Redis, Loki, Prometheus의 역할 구분
2. 각 컨테이너가 어떤 저장소를 읽고 쓰는지
3. 주요 테이블/Redis 키가 무슨 의미인지
4. 매수/매도 1건이 발생할 때 저장소가 어떻게 움직이는지
5. 장애가 났을 때 어디부터 봐야 하는지
6. 저장소별 실전 점검 명령어

이 문서의 핵심 원칙은 아래 한 줄이다.

- `정확한 원장 = PostgreSQL`
- `실시간 상태 = Redis`
- `원인 추적용 로그 = Loki`
- `시스템/앱 메트릭 = Prometheus`

---

## 1. 큰 그림

CoinPilot는 "DB가 여러 개"라기보다, 역할이 다른 저장소를 함께 쓰는 구조다.

| 저장소 | 성격 | 역할 | 비고 |
|---|---|---|---|
| PostgreSQL | 관계형 DB | 거래/포지션/시세/AI 판단/비용 원장 | 메인 정본 |
| TimescaleDB | PostgreSQL 확장 | 시계열 데이터 최적화 | 별도 DB 아님 |
| pgvector | PostgreSQL 확장 | 벡터 검색/RAG | 별도 DB 아님 |
| Redis | Key-Value DB | 실시간 상태/캐시/가드레일 카운터 | 메모리 중심 |
| Loki | 로그 저장소 | 컨테이너 로그 저장/검색 | 운영 원인 추적 |
| Prometheus | 메트릭 TSDB | 시스템/앱 메트릭 수집 | 관측 전용 |

중요:
- `TimescaleDB`는 PostgreSQL 안에서 동작하는 시계열 확장이다.
- `pgvector`도 PostgreSQL 안에서 동작하는 벡터 검색 확장이다.
- 즉 CoinPilot의 "진짜 본DB"는 PostgreSQL 하나다.

---

## 2. Redis도 DB인가?

맞다. Redis도 DB다.

다만 PostgreSQL과 성격이 다르다.

| 항목 | PostgreSQL | Redis |
|---|---|---|
| 저장 방식 | 디스크 기반 영속 저장 중심 | 메모리 기반 초고속 저장 중심 |
| 적합한 데이터 | 거래 원장, 판단 이력, 리포트 근거 | 현재 상태, TTL 캐시, 카운터 |
| 조회 목적 | 정확한 복기/분석/정산 | 빠른 현재 상태 확인 |
| 재시작 후 보존 중요도 | 매우 높음 | 상대적으로 낮음 |

실무적으로는 이렇게 기억하면 된다.

- PostgreSQL: "반드시 남아야 하는 데이터"
- Redis: "지금 바로 빨리 읽어야 하는 데이터"

---

## 3. 서비스별 저장소 사용 관계

운영 서비스 정의는 `deploy/cloud/oci/docker-compose.prod.yml` 기준이다.

### 3.1 `coinpilot-db`

- 역할: PostgreSQL 본체
- 저장 데이터:
  - 시세 원본
  - 포지션
  - 거래 이력
  - AI 판단 이력
  - 레짐 이력
  - LLM 사용량/비용 원장
  - RAG 문서 벡터

### 3.2 `coinpilot-redis`

- 역할: 실시간 상태 저장소
- 저장 데이터:
  - 현재 레짐 캐시
  - bot 실시간 상태
  - 변동성 상태
  - HWM
  - AI guardrail/cooldown/usage 카운터

### 3.3 `coinpilot-collector`

- 읽기:
  - 외부 Upbit API
- 쓰기:
  - PostgreSQL `market_data`

핵심 역할:
- 시세 수집기
- 사실상 `market_data writer`

### 3.4 `coinpilot-bot`

- 읽기:
  - PostgreSQL `market_data`, `positions`, `account_state`, `daily_risk_state`
  - Redis `market:regime:*`, `coinpilot:volatility_state`, `ai:guard:*`
- 쓰기:
  - PostgreSQL `regime_history`, `trading_history`, `positions`, `agent_decisions`, `daily_risk_state`
  - Redis `bot:status:*`, `position:{symbol}:hwm`, `market:regime:*`

핵심 역할:
- CoinPilot의 중심 서비스
- 저장소를 가장 많이 읽고 쓰는 컨테이너

### 3.5 `coinpilot-dashboard`

- 읽기:
  - PostgreSQL 원장 데이터
  - Redis 실시간 상태

핵심 역할:
- 느린 정본 조회는 PostgreSQL
- 빠른 상태판 조회는 Redis

### 3.6 `coinpilot-n8n`

- 역할: 알림/워크플로우 자동화
- 비고:
  - CoinPilot 거래 원장을 저장하는 메인 DB는 아님
  - 자체 데이터는 n8n 볼륨에 저장

### 3.7 `coinpilot-prometheus`

- 역할: 메트릭 저장소
- 읽기:
  - bot `/metrics`
  - node-exporter
  - cadvisor
- 쓰기:
  - 자체 TSDB

### 3.8 `coinpilot-grafana`

- 역할: 시각화 도구
- 읽기:
  - Prometheus
  - Loki
- 비고:
  - 거래 원장을 저장하는 핵심 DB는 아님

### 3.9 `coinpilot-loki`

- 역할: 로그 저장소
- 읽기:
  - Promtail이 밀어넣은 로그
- 쓰기:
  - 자체 로그 인덱스/청크

### 3.10 `coinpilot-promtail`, `coinpilot-promtail-targets`

- `promtail-targets`
  - Docker 로그 파일 경로를 찾아 Promtail용 symlink를 만든다.
- `promtail`
  - 로그 파일을 tail해서 Loki로 보낸다.

### 3.11 `coinpilot-node-exporter`, `coinpilot-cadvisor`, `coinpilot-container-map`

- 역할: 시스템/컨테이너 관측
- 저장소 관계:
  - Prometheus에 메트릭을 공급
- 비고:
  - 거래 DB와는 직접 관계 없다.

---

## 4. PostgreSQL 안의 주요 테이블

정의는 `src/common/models.py`, 초기 생성은 `deploy/db/init.sql` 기준이다.

### 4.1 시세/시장 상태

#### `market_data`
- 의미: 1분봉 OHLCV 원본
- 주 쓰기 주체: Collector
- 주 읽기 주체: Bot, Dashboard, 리포트
- 왜 중요하나:
  - Rule Engine과 지표 계산의 입력 정본
  - 백테스트/재현의 기준 데이터

#### `regime_history`
- 의미: 레짐 감지 이력
- 주 쓰기 주체: Scheduler
- 주 읽기 주체: Dashboard, 운영 SQL
- 왜 중요하나:
  - "최근 72시간 동안 실제로 BULL이 많았는가?" 같은 검증에 사용

### 4.2 거래 원장

#### `positions`
- 의미: 현재 보유 포지션 정본
- 주 쓰기 주체: Executor
- 주 읽기 주체: Bot, RiskManager, Dashboard
- 왜 중요하나:
  - 재시작 후에도 포지션 상태가 유지돼야 하기 때문

#### `trading_history`
- 의미: 실제 매수/매도 체결 이력
- 저장 내용:
  - 심볼
  - BUY/SELL
  - 체결 가격/수량
  - 전략명
  - 진입 당시 `signal_info`
  - 레짐
  - `exit_reason`
- 왜 중요하나:
  - 나중에 수익률/청산 사유/전략 검증 근거가 된다.

#### `account_state`
- 의미: Paper Trading 잔고 정본
- 주 쓰기 주체: Executor
- 주 읽기 주체: Bot, Dashboard

#### `daily_risk_state`
- 의미: 일일 손익/연속 손실/쿨다운/거래중단 상태
- 주 쓰기 주체: RiskManager
- 주 읽기 주체: Bot, Dashboard, Daily Report

### 4.3 AI/LLM 원장

#### `agent_decisions`
- 의미: AI Analyst/Guardian 판단 이력
- 저장 내용:
  - `decision`
  - `reasoning`
  - `confidence`
  - `model_used`
  - `price_at_decision`
  - `regime`
- 왜 중요하나:
  - AI가 언제 얼마나 호출됐는지
  - 왜 REJECT했는지
  - BULL/SIDEWAYS별 호출 편차가 있는지
  - 카나리 품질 비교가 가능한 근거 데이터

#### `llm_usage_events`
- 의미: LLM 호출 단위 원장
- 저장 내용:
  - route
  - provider/model
  - input/output/total tokens
  - estimated cost
  - status
  - latency
- 왜 중요하나:
  - 비용 리포트와 호출 품질 관측의 정본

#### `llm_credit_snapshots`
- 의미: provider 잔액/비용 스냅샷
- 왜 중요하나:
  - 내부 usage 원장과 외부 provider 비용 변화를 대조하는 기준

### 4.4 벡터/RAG

#### `document_embeddings`
- 의미: RAG용 문서 벡터 저장소
- 현재 사용처:
  - `src/agents/rag_agent.py`

#### `agent_memory`
- 의미: 과거 성공/실패 사례용 벡터 메모리 예비 테이블
- 현재 상태:
  - 인프라 준비됨
  - 본격 활용은 후속 작업 대상

---

## 5. Redis 안의 주요 키

### 5.1 현재 상태 캐시

#### `market:regime:{symbol}`
- 값: `BULL`, `SIDEWAYS`, `BEAR`, `UNKNOWN`
- 쓰기: Scheduler
- 읽기: Bot
- 목적:
  - 현재 레짐을 빠르게 읽기 위함

#### `bot:status:{symbol}`
- 값: JSON
- 쓰기: Bot
- 읽기: Dashboard
- 목적:
  - 실시간 화면용 상태판

대표 필드:
- 현재 가격
- 레짐
- 포지션 여부
- 최근 action
- 최근 reason

#### `position:{symbol}:hwm`
- 값: 최고가
- 쓰기/읽기: Bot
- 목적:
  - trailing stop 계산 가속

### 5.2 리스크/AI 가드레일

#### `coinpilot:volatility_state`
- 값: JSON
- 쓰기: Volatility Model
- 읽기: RiskManager
- 목적:
  - 고변동성 시 주문 크기 축소

#### `ai:guard:global:block`
- 값: 차단 사유
- 목적:
  - 저크레딧/에러 연속 발생 시 전역 차단

#### `ai:guard:symbol:{symbol}:cooldown`
- 값: TTL 기반 쿨다운
- 목적:
  - 심볼별 과도한 AI 호출 억제

#### `ai:guard:symbol:{symbol}:reject_count`
- 값: 연속 거절 수
- 목적:
  - 연속 REJECT 발생 시 추가 보호장치

#### `ai:usage:hour:*`, `ai:usage:day:*`
- 값: 호출 횟수 카운터
- 목적:
  - 시간/일 단위 상한 관리

---

## 6. 매수 1건이 발생할 때 저장소가 어떻게 움직이는가

예시: `KRW-BTC`에서 BUY 1건 발생

### Step 1. Collector가 시세 적재
- Upbit API에서 1분봉 조회
- PostgreSQL `market_data`에 저장

정본:
- PostgreSQL

### Step 2. Scheduler가 레짐 계산
- 최근 캔들로 MA50/MA200 계산
- Redis `market:regime:KRW-BTC` 갱신
- PostgreSQL `regime_history`에 이력 추가

현재 상태:
- Redis

이력/근거:
- PostgreSQL

### Step 3. Bot이 시장 분석
- PostgreSQL `market_data`에서 최근 캔들 읽음
- 지표 계산
- Redis `market:regime:KRW-BTC` 읽음
- Rule Engine `check_entry_signal()` 수행

### Step 4. RiskManager 검증
- PostgreSQL:
  - `daily_risk_state`
  - `positions`
  - `account_state`
- Redis:
  - `coinpilot:volatility_state`
  - `reference equity` 캐시
  - 일부 HWM/guardrail 상태

### Step 5. AI Decision
- Analyst/Guardian 수행
- 결과를 PostgreSQL `agent_decisions`에 저장

왜 PostgreSQL인가:
- 나중에 BULL/SIDEWAYS별 호출량/거절사유를 복기해야 하기 때문

### Step 6. 주문 실행
- Executor가 PostgreSQL을 갱신
  - `account_state` 잔고 차감
  - `positions` 생성 또는 업데이트
  - `trading_history`에 BUY 기록

이 단계의 정본:
- 무조건 PostgreSQL

### Step 7. 실시간 상태 갱신
- Redis `bot:status:KRW-BTC` 갱신
- 필요 시 Redis `position:KRW-BTC:hwm` 초기화/갱신

화면 표시:
- Dashboard가 Redis 값을 읽어 빠르게 표시

### Step 8. 로그/메트릭 수집
- bot 로그는 stdout/stderr에 남음
- Promtail이 읽어서 Loki에 적재
- Prometheus가 `/metrics` 수집
- Grafana는 둘을 시각화

정리:
- 거래 결과 = PostgreSQL
- 거래 과정 로그 = Loki
- 운영 메트릭 = Prometheus

---

## 7. 매도 1건이 발생할 때 저장소가 어떻게 움직이는가

예시: `KRW-BTC` SELL 1건 발생

### Step 1. Bot이 현재 포지션 조회
- PostgreSQL `positions` 읽음

### Step 2. 청산 조건 평가
- PostgreSQL `market_data` 기반 지표 계산
- HWM은 Redis/DB를 함께 참조

### Step 3. 주문 실행
- PostgreSQL 갱신:
  - `account_state` 잔고 증가
  - `positions` 삭제 또는 수량 감소
  - `trading_history`에 SELL 추가
  - `exit_reason` 기록

### Step 4. 상태 정리
- Redis `position:{symbol}:hwm` 삭제
- Redis `bot:status:{symbol}` 갱신

### Step 5. 로그/메트릭
- SELL 로그는 Loki로 수집
- 메트릭은 Prometheus로 수집

---

## 8. 장애 유형별 우선 점검 순서

### 8.1 거래가 안 나온다
1. `coinpilot-bot` 상태
2. PostgreSQL `market_data` 최신 시각
3. Redis `market:regime:*`
4. bot 로그의 `Entry Signal`, `Risk Rejected`, `AI PreFilter`, `AI Guardrail`
5. PostgreSQL `agent_decisions`

### 8.2 AI Decision 횟수가 적다
1. PostgreSQL `agent_decisions`
2. PostgreSQL `regime_history`
3. bot 로그 `Entry Signal Detected`
4. bot 로그 `AI PreFilter Rejected`, `AI Guardrail Blocked`

### 8.3 대시보드 실시간 상태가 비었다
1. Redis `bot:status:*`
2. bot 로그의 Redis write 에러
3. dashboard 컨테이너 상태

### 8.4 포지션/잔고가 이상하다
1. PostgreSQL `positions`
2. PostgreSQL `account_state`
3. PostgreSQL `trading_history`
4. executor/bot 로그

원칙:
- 이 경우 Redis보다 PostgreSQL이 먼저다.

### 8.5 레짐이 이상하다
1. Redis `market:regime:{symbol}`
2. PostgreSQL `regime_history`
3. bot 로그 Scheduler 출력
4. `market_data` 최신성/충분성

### 8.6 Grafana 패널/로그 패널이 이상하다
1. `scripts/ops/check_24h_monitoring.sh t1h`
2. Prometheus target
3. Loki readiness
4. promtail / promtail-targets 로그
5. Grafana 패널 쿼리

---

## 9. 저장소별 실전 확인 명령어

### 9.1 공통 변수

```bash
cd /opt/coin-pilot
ENV_FILE=/opt/coin-pilot/deploy/cloud/oci/.env
COMPOSE_FILE=/opt/coin-pilot/deploy/cloud/oci/docker-compose.prod.yml
```

### 9.2 PostgreSQL

상태:

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps db
docker exec coinpilot-db pg_isready -U postgres -d coinpilot
```

핵심 데이터:

```bash
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT max(timestamp) AS latest_market_data FROM market_data;
SELECT symbol, quantity, avg_price, regime, opened_at FROM positions ORDER BY opened_at DESC;
SELECT id, balance, updated_at FROM account_state;
SELECT symbol, side, price, quantity, executed_at FROM trading_history ORDER BY executed_at DESC LIMIT 10;
SELECT symbol, decision, confidence, regime, created_at FROM agent_decisions ORDER BY created_at DESC LIMIT 20;
SELECT coin_symbol, regime, detected_at FROM regime_history ORDER BY detected_at DESC LIMIT 20;
"
```

LLM 비용/호출량:

```bash
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT route, provider, model, status, total_tokens, created_at
FROM llm_usage_events
ORDER BY created_at DESC
LIMIT 20;
"
```

### 9.3 Redis

연결:

```bash
docker exec coinpilot-redis redis-cli ping
```

키 확인:

```bash
docker exec coinpilot-redis redis-cli KEYS 'market:regime:*'
docker exec coinpilot-redis redis-cli KEYS 'bot:status:*'
docker exec coinpilot-redis redis-cli KEYS 'ai:guard:*'
```

값 확인:

```bash
docker exec coinpilot-redis redis-cli GET market:regime:KRW-BTC
docker exec coinpilot-redis redis-cli GET bot:status:KRW-BTC
docker exec coinpilot-redis redis-cli GET coinpilot:volatility_state
docker exec coinpilot-redis redis-cli TTL ai:guard:global:block
docker exec coinpilot-redis redis-cli TTL ai:guard:symbol:KRW-BTC:cooldown
```

### 9.4 Bot

상태/로그/헬스:

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps bot
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=20m bot
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T bot \
  sh -lc 'python -c "import urllib.request; print(urllib.request.urlopen(\"http://127.0.0.1:8000/health\").status)"'
```

Entry/AI 흔적:

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=72h bot | grep -c "Entry Signal Detected"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=24h bot | grep -E "AI PreFilter Rejected|AI Guardrail Blocked|Trade Rejected by AI Agent"
```

### 9.5 Loki / Promtail

상태:

```bash
curl -sS http://127.0.0.1:3100/ready
curl -sS -G http://127.0.0.1:3100/loki/api/v1/label/filename/values
```

간단 쿼리:

```bash
curl -sS -G http://127.0.0.1:3100/loki/api/v1/query \
  --data-urlencode 'query=sum(count_over_time({filename=~"/targets/logs/coinpilot-.*\\.log"}[5m]))'
```

로그:

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m loki
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m promtail
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m promtail-targets
```

### 9.6 Prometheus / Grafana

Prometheus:

```bash
curl -sS 'http://127.0.0.1:9090/api/v1/query?query=up'
curl -sS http://127.0.0.1:9090/api/v1/targets
```

운영 점검:

```bash
scripts/ops/check_24h_monitoring.sh t0
scripts/ops/check_24h_monitoring.sh t1h
scripts/ops/check_24h_monitoring.sh t24h
```

Grafana:

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps grafana
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=5m grafana
```

---

## 10. 가장 많이 쓰는 실전 점검 세트

### A. 거래 이상 점검

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps bot
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=30m bot
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT max(timestamp) FROM market_data;
SELECT symbol, decision, regime, created_at FROM agent_decisions ORDER BY created_at DESC LIMIT 20;
SELECT coin_symbol, regime, detected_at FROM regime_history ORDER BY detected_at DESC LIMIT 20;
"
```

### B. 실시간 상태 점검

```bash
docker exec coinpilot-redis redis-cli GET market:regime:KRW-BTC
docker exec coinpilot-redis redis-cli GET bot:status:KRW-BTC
docker exec coinpilot-redis redis-cli GET coinpilot:volatility_state
```

### C. 모니터링 이상 점검

```bash
scripts/ops/check_24h_monitoring.sh t1h
curl -sS http://127.0.0.1:3100/ready
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m promtail
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m loki
```

---

## 11. 빠른 기억법

- 거래/잔고/포지션/AI 판단 이력은 `PostgreSQL` 먼저 본다.
- 현재 레짐/실시간 상태/AI cooldown은 `Redis` 먼저 본다.
- 왜 이런 현상이 났는지 원인을 찾을 때는 `bot 로그`와 `Loki`를 본다.
- 패널/알림/스크랩 상태는 `Prometheus`와 `Grafana`를 본다.

아주 단순화하면 아래처럼 외우면 된다.

- `정확한 원장 = PostgreSQL`
- `현재 상태 = Redis`
- `원인 추적 = Loki`
- `숫자 관측 = Prometheus`
