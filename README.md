# CoinPilot

CoinPilot는 Upbit 시장을 대상으로 동작하는 규칙 기반 자동매매 시스템입니다.
핵심 의사결정은 Rule Engine과 Risk Manager가 담당하고, LLM은 보조 판단(신호 검증/리스크 점검/조회 응답)에 사용됩니다.

현재 운영 기준은 **OCI + Docker Compose**입니다.

## Source of Truth
- 프로젝트 기준 문서: `docs/PROJECT_CHARTER.md`
- 남은 작업/우선순위: `docs/checklists/remaining_work_master_checklist.md`

README는 빠른 진입용이고, 운영 정책/정의 변경은 Charter를 우선합니다.

## 현재 운영 상태 요약 (2026-03-07 기준)
- 운영 스택: OCI VM + `deploy/cloud/oci/docker-compose.prod.yml`
- 기본 서비스: `db`, `redis`, `collector`, `bot`, `dashboard`, `n8n`, `prometheus`, `grafana`
- 인프라 관측: `node-exporter`, `cadvisor`, `container-map` (21-05 완료)
- 로그 관측: `loki`, `promtail-targets`, `promtail` (21-07 완료)
  - 운영 확인 기준: `scripts/ops/check_24h_monitoring.sh t1h`에서 `FAIL:0`
  - 로그 유입 기준: `sum(count_over_time({filename=~"/targets/logs/coinpilot-.*\\.log"}[5m])) > 0`
- Grafana 로그 패널화(21-08): `CoinPilot Infra Overview`에 Loki 패널 5종 반영 완료 (`done`)
  - 2026-03-07 OCI 검증: `t1h FAIL:0/WARN:1`, ingest query `187`
  - 후속 보정: 패널 13개 description(한국어 운영 설명) + 임계치 패널 9개(threshold) 적용, 오류 패널 `No data -> 0` 보정
  - 후속 보정(Phase G): Grafana alert rule 7개 provisioning 코드화 + compose alerting 마운트 반영
  - 후속 보정(Phase H): Loki alert 3개 `or vector(0)` + `noDataState=OK`, API mismatch `>=3 for 5m`으로 노이즈 완화
- 모바일 조회 봇: `discord-bot` (24 완료, profile 기반 선택 기동)
- LLM 비용 관측(21-04): Phase 2.1 코드 반영 완료 (`in_progress`)
  - `llm_usage_events`/`llm_provider_cost_snapshots` 스키마 추가
  - AI Decision/Chatbot/Daily Report/RAG embedding(estimated) 경로 usage 계측
  - provider API 기반 비용 스냅샷 자동수집 job(환경변수 기반) 추가
  - 운영 집계 스크립트: `scripts/ops/llm_usage_cost_report.sh`
- CI/보안 스트림(27): 완료(`done`)
  - backend/agent 계열 취약점 정리 완료
  - 잔여 `CVE-2026-25990(pillow)` 1건은 Streamlit 전이 의존성 이슈로 `22`/`23` 스트림에서 제거 예정

## 문서 운영 규칙 (고정)
1. Source of Truth는 항상 `docs/PROJECT_CHARTER.md`입니다.
2. Main 계획 생성/상태 변경/완료 시 `docs/checklists/remaining_work_master_checklist.md`를 같은 변경에서 갱신합니다.
3. **Major 구현 완료 시 README를 같은 변경 묶음에서 반드시 동기화**합니다.
4. 프로젝트 본질과 직접 무관한 관리/메타 작업 문서는 `99-` prefix 번호를 사용합니다.
5. Result/Troubleshooting 문서는 문제 정의와 before/after 정량 증빙(측정 기준/근거 명령 포함)을 필수로 남깁니다.

## 아키텍처 개요

### 트레이딩 파이프라인
1. Collector가 시세/캔들 데이터를 수집
2. Bot이 레짐(BULL/SIDEWAYS/BEAR)과 Rule Engine 조건을 평가
3. Risk Manager가 주문 가능 여부를 1차 차단
4. AI Analyst/Guardian이 보조 검증
5. Executor가 주문 실행(또는 거절)
6. 결과는 DB/Redis/알림 채널(Discord, n8n)로 전파

### 관측/운영 파이프라인
- Prometheus: 메트릭 수집 (`coinpilot-core`, `node-exporter`, `cadvisor`)
- Loki/Promtail: 컨테이너 로그 수집/검색 (`coinpilot-*` 파일 타깃 기반)
- Grafana: 대시보드/알림 라우팅
- `scripts/ops/check_24h_monitoring.sh`: 운영 점검 자동화 (`t0`, `t1h`, `t6h`, `t12h`, `t24h`)

## 리포지토리 구조

```text
coin-pilot/
├── src/
│   ├── bot/            # FastAPI + 스케줄러 + 매매 루프
│   ├── collector/      # 시장 데이터 수집
│   ├── engine/         # Rule Engine / Risk Manager
│   ├── agents/         # Analyst/Guardian/SQL/RAG
│   ├── mobile/         # Discord 조회용 내부 API (/api/mobile/*)
│   ├── discord_bot/    # Discord Slash Command 봇
│   ├── dashboard/      # Streamlit 대시보드
│   ├── analytics/      # 변동성 모델
│   └── common/         # DB/Redis/알림 공통 모듈
├── deploy/
│   ├── cloud/oci/      # 운영용 Compose/모니터링 설정
│   ├── docker/         # 서비스 Dockerfile
│   └── docker-compose.yml  # 로컬 단순 스택(개발/테스트)
├── scripts/
│   ├── ops/            # 운영 점검 자동화
│   ├── backup/         # Postgres/Redis/n8n 백업
│   └── security/       # 사전 보안 점검
├── docs/
│   ├── PROJECT_CHARTER.md
│   ├── runbooks/
│   ├── troubleshooting/
│   ├── work-plans/
│   └── work-result/
└── tests/
```

## 빠른 시작 (OCI 운영 기준)

### 1) 환경 파일 준비
```bash
cd deploy/cloud/oci
cp .env.example .env
chmod 600 .env
```

### 2) 필수 값 설정
최소 아래 항목은 반드시 채워야 합니다.
- `DB_PASSWORD`
- `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`
- `N8N_WEBHOOK_SECRET`
- `N8N_BASIC_AUTH_USER`, `N8N_BASIC_AUTH_PASSWORD`
- `DASHBOARD_ACCESS_PASSWORD`
- `GRAFANA_ADMIN_USER`, `GRAFANA_ADMIN_PASSWORD`
- (모바일 조회봇 사용 시) `COINPILOT_API_SHARED_SECRET`, `DISCORD_BOT_TOKEN`

### 3) 서비스 기동
```bash
docker compose --env-file .env -f docker-compose.prod.yml up -d --build
```

Discord 조회 봇까지 같이 올릴 때:
```bash
docker compose --profile discord-bot --env-file .env -f docker-compose.prod.yml up -d --build bot discord-bot
```

### 4) 상태 확인
```bash
docker compose --env-file .env -f docker-compose.prod.yml ps
```

## 접속 방법
운영 환경은 대부분 `127.0.0.1` 바인딩이므로 SSH 터널로 접속합니다.

```powershell
ssh -N -i "C:\Users\<user>\.ssh\<key>.key" `
  -L 18501:127.0.0.1:8501 `
  -L 13000:127.0.0.1:3000 `
  -L 15678:127.0.0.1:5678 `
  -L 19090:127.0.0.1:9090 `
  ubuntu@<OCI_PUBLIC_IP>
```

로컬 접속 주소:
- Dashboard: `http://localhost:18501`
- Grafana: `http://localhost:13000`
- n8n: `http://localhost:15678`
- Prometheus: `http://localhost:19090`

## 운영 점검 명령

### 기본 헬스 체크
```bash
cd /opt/coin-pilot
scripts/ops/check_24h_monitoring.sh t0
scripts/ops/check_24h_monitoring.sh t1h
```

### 전체 24h 점검
```bash
scripts/ops/check_24h_monitoring.sh all
```

점검 의미:
- `t0`: 컨테이너 기동/치명 로그
- `t1h`: Prometheus target/알림 라우팅 점검 안내
- `t6h`: Entry/AI/Risk 흐름 로그 연속성
- `t12h`: RSS/Daily 배치 실패 키워드 검사
- `t24h`: 백업 파일 생성 및 cron 상태

### LLM 토큰/비용 집계 리포트
```bash
scripts/ops/llm_usage_cost_report.sh 24
```

확인 항목:
- route/provider/model별 `total_tokens`, `cost_usd`, `error_calls`
- `ledger_cost_usd` vs `provider_cost_usd` 대조값(`delta_usd`)

### LLM 계측 스모크 + 비교(권장)
```bash
scripts/ops/llm_usage_smoke_and_compare.sh 1
```

역할:
- 챗봇(classifier/rag/sql/premium-review) + AI Decision(analyst/guardian) 경로를 강제 호출
- 직후 `llm_usage_cost_report`/`ai_decision_canary_report`를 연속 출력

### LLM 비용 스냅샷 1회 수집(선택)
```bash
scripts/ops/llm_credit_snapshot_collect.sh
```

## Discord 모바일 조회 봇 (선택)
서비스: `src/discord_bot/main.py`

Slash Command:
- `/positions`
- `/pnl`
- `/status`
- `/risk`
- `/ask`

주요 환경변수:
- `DISCORD_BOT_TOKEN`
- `COINPILOT_API_SHARED_SECRET`
- `DISCORD_GUILD_ID` (권장)
- `DISCORD_ALLOWED_CHANNEL_IDS`, `DISCORD_ALLOWED_ROLE_IDS` (권한 제한)

## LLM Usage 환경변수
- `LLM_USAGE_ENABLED=true|false`
- `LLM_USAGE_PRICE_TABLE_JSON` (선택)
  - 모델 단가 override JSON (USD / 1M tokens)
  - 예시:
    - `{\"anthropic:claude-haiku-4-5-20251001\":{\"input_per_1m\":0.8,\"output_per_1m\":4.0},\"openai:gpt-4o-mini\":{\"input_per_1m\":0.15,\"output_per_1m\":0.6}}`
- `LLM_COST_SNAPSHOT_ENABLED=true|false` (기본 `false`)
- `LLM_COST_SNAPSHOT_INTERVAL_MIN=60` (최소 5분)
- `LLM_COST_SNAPSHOT_LOOKBACK_HOURS=1`
- `LLM_COST_SNAPSHOT_PROVIDERS=anthropic,openai`
- `LLM_COST_SNAPSHOT_<PROVIDER>_URL_TEMPLATE`
- `LLM_COST_SNAPSHOT_<PROVIDER>_VALUE_JSON_PATH`
- `LLM_COST_SNAPSHOT_<PROVIDER>_HEADERS_JSON`
  - URL template placeholder: `${START_UNIX}`, `${END_UNIX}`, `${START_ISO}`, `${END_ISO}`
  - 예시: `{"Authorization":"Bearer ${OPENAI_ADMIN_KEY}"}`

## 전략/리스크 설정 위치
- 전략/레짐/리스크 설정: `config/strategy_v3.yaml`
- 로딩 코드: `src/config/strategy.py`

최근 운영 변경(요약):
- 포지션 사이징/노출 한도 20%/100% 기반(3중 캡 로직 적용)
- AI 경계 재판단 처리 정책 개선 및 모니터링 보정

## 보안 점검
배포/환경변수 변경 후 반드시 실행:
```bash
./scripts/security/preflight_security_check.sh
```

운영 기준:
- 내부 포트 외부 직접 공개 금지
- `.env` 권한 `600`
- n8n webhook secret 검증 유지

## 현재 우선순위 백로그 (체크리스트 연동)
상세 상태는 항상 `docs/checklists/remaining_work_master_checklist.md`를 기준으로 확인합니다.

1. `21-05` OCI 인프라 리소스 모니터링 고도화 (`done`)
2. `21-07` OCI 로그 관측 체계 강화(Loki/Promtail) (`done`)
3. `21-08` Grafana Loki 로그 패널화 (`done`)
4. `21-03` AI Decision 카나리 실험 (`in_progress`)
5. `21-04` LLM 토큰/비용 관측 대시보드 (`in_progress`)
6. `29` 레짐 전환 구간 전략 평가 + 조건부 핫픽스 (`in_progress`)
7. `22` 대시보드 가독성/실시간성 표준화(Spec-First) (`todo`)
8. `23` Next.js 점진 이관 (`blocked`)

## 관련 문서
- 프로젝트 기준/정의: `docs/PROJECT_CHARTER.md`
- 사용자 운영 가이드: `docs/USER_MANUAL.md`
- 일일 기동 가이드: `docs/daily-startup-guide.md`
- WSL/OCI 통합 운영 Runbook: `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- 트러블슈팅 목록: `docs/troubleshooting/`
- 계획/결과 문서: `docs/work-plans/`, `docs/work-result/`

## 주의
이 프로젝트는 자동매매 연구/운영 도구입니다. 모든 투자 책임은 사용자에게 있습니다.
