# 21-04. LLM 토큰/비용 관측 대시보드 구현 결과

작성일: 2026-03-04
작성자: Codex
관련 계획서: docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md
상태: In Progress (Phase 1 + Phase 2 + Phase 2.1 Code Implemented)
완료 범위: Phase 1, Phase 2, Phase 2.1(코드 반영)
선반영/추가 구현: 있음(Phase 2 OCI 운영 검증/실계정 endpoint 연결은 후속)
관련 트러블슈팅(있다면): `docs/troubleshooting/21-06_ai_canary_env_injection_and_observability_gap.md`

---

## 1. 개요
- 구현 범위 요약:
  - 호출 단위 usage 원장 스키마 + 공통 수집 유틸 + AI Decision/Chatbot/Report 계측 + 운영 리포트 스크립트까지 반영
- 목표(요약):
  - 계정 잔여 크레딧만 보던 방식에서 벗어나, route/provider/model 단위 토큰/비용 원인 분리가 가능하도록 전환
- 이번 구현이 해결한 문제(한 줄):
  - "어떤 기능이 얼마나 비용을 쓰는지 모르는 상태"를 "호출 단위로 추적 가능한 상태"로 전환

---

## 2. 구현 내용(핵심 위주)
### 2.1 LLM usage ledger 스키마 추가
- 파일/모듈:
  - `src/common/models.py`
  - `migrations/v3_3_2_llm_usage_observability.sql`
  - `deploy/db/init.sql`
- 변경 내용:
  - `llm_usage_events` 테이블 추가: route/feature/provider/model/status/tokens/cost/latency/meta 저장
  - `llm_credit_snapshots` 테이블 추가: provider별 잔여 크레딧 스냅샷 저장
  - `llm_provider_cost_snapshots` 테이블 추가: provider 구간 비용 스냅샷 저장
  - 인덱스/unique(request_id) 반영
- 효과/의미:
  - 모델 비교/비용 이상징후 탐지/재집계가 가능한 기본 데이터 구조 확보

### 2.2 공통 usage 캡처/비용 추정 모듈 추가
- 파일/모듈:
  - `src/common/llm_usage.py` (신규)
- 변경 내용:
  - LangChain callback(`UsageCaptureCallback`) 기반 usage 수집
  - 응답 메타데이터/LLMResult 호환 파서
  - 모델별 단가표 기반 추정 비용 계산(`LLM_USAGE_PRICE_TABLE_JSON` override 지원)
  - DB 저장 soft-fail 처리(기능 중단 방지)
- 효과/의미:
  - 호출부는 최소 코드로 계측 가능, provider별 메타데이터 편차를 공통 계층에서 흡수

### 2.3 호출 지점 계측 반영
- 파일/모듈:
  - `src/agents/analyst.py`
  - `src/agents/guardian.py`
  - `src/agents/runner.py`
  - `src/agents/router.py`
  - `src/agents/sql_agent.py`
  - `src/agents/rag_agent.py`
  - `src/agents/daily_reporter.py`
  - `src/agents/factory.py`
- 변경 내용:
  - AI Decision: `ai_decision_analyst`, `ai_decision_guardian`, `ai_decision_pipeline` 이벤트 기록
  - Chatbot: `chat_classifier`, `chat_sql_agent`, `chat_rag_generation`, `chat_premium_review` 기록
  - Daily report: `daily_report_summary` 기록
  - Embedding 경로(RAG query embedding): 벤더 usage 부재로 `embedding_query`를 `status=estimated`로 기록
- 효과/의미:
  - AI Decision과 챗봇/리포트/임베딩 비용 분리가 가능해짐

### 2.4 운영 집계 스크립트/환경변수 반영
- 파일/모듈:
  - `scripts/ops/llm_usage_cost_report.sh` (신규)
  - `scripts/ops/llm_usage_smoke_and_compare.sh` (신규)
  - `.env.example`
  - `deploy/cloud/oci/.env.example`
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/docker-compose.yml`
  - `docs/runbooks/18_data_migration_runbook.md`
- 변경 내용:
  - 최근 N시간 기준 route/provider/model별 호출수/토큰/비용/오류율 집계 SQL 자동화
  - ledger 합계 vs provider cost snapshot 합계 대조 SQL 포함
  - cost snapshot freshness(최근 시점/지연 분) 구간 추가
  - 권장 확인 절차 자동화를 위해 chat/rag/sql/premium-review + ai_decision(analyst/guardian) 경로를 강제 호출하고 usage/canary 리포트를 연속 출력하는 smoke 스크립트 추가
  - one-shot 수집 스크립트 `scripts/ops/llm_credit_snapshot_collect.sh` 추가(파일명 유지, 내부는 cost snapshot 수집)
  - `LLM_USAGE_ENABLED`, `LLM_USAGE_PRICE_TABLE_JSON`, `LLM_COST_SNAPSHOT_*` 환경변수 반영
- 효과/의미:
  - 운영자가 OCI에서 단일 명령으로 비용/오류 분포를 즉시 확인 가능
  - provider 비용 스냅샷 자동수집을 scheduler에 붙일 수 있는 운영 경로 확보

---

## 3. 변경 파일 목록
### 3.1 수정
1) `src/common/models.py`
2) `src/agents/factory.py`
3) `src/agents/analyst.py`
4) `src/agents/guardian.py`
5) `src/agents/runner.py`
6) `src/agents/router.py`
7) `src/agents/sql_agent.py`
8) `src/agents/rag_agent.py`
9) `src/agents/daily_reporter.py`
10) `deploy/db/init.sql`
11) `deploy/cloud/oci/docker-compose.prod.yml`
12) `deploy/docker-compose.yml`
13) `.env.example`
14) `deploy/cloud/oci/.env.example`
15) `docs/runbooks/18_data_migration_runbook.md`
16) `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`
17) `docs/checklists/remaining_work_master_checklist.md`
18) `docs/PROJECT_CHARTER.md`
19) `README.md`
20) `scripts/ops/llm_credit_snapshot_collect.sh`

### 3.2 신규
1) `src/common/llm_usage.py`
2) `migrations/v3_3_2_llm_usage_observability.sql`
3) `scripts/ops/llm_usage_cost_report.sh`
4) `scripts/ops/llm_usage_smoke_and_compare.sh`
5) `tests/utils/test_llm_usage.py`
6) `scripts/ops/llm_credit_snapshot_collect.sh`

---

## 4. DB/스키마 변경
- 변경 사항:
  - `llm_usage_events`, `llm_credit_snapshots`, `llm_provider_cost_snapshots` 테이블/인덱스 추가
- 마이그레이션:
  - `migrations/v3_3_2_llm_usage_observability.sql`
- 롤백 전략/주의점:
  - 코드 롤백 시에도 테이블은 데이터 보존 관점에서 유지 가능
  - 완전 롤백이 필요하면 `DROP TABLE llm_provider_cost_snapshots, llm_credit_snapshots, llm_usage_events;` 순서로 명시 수행

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `DB_PASSWORD=postgres DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot .venv/bin/python -m pytest tests/agents/ tests/utils/test_llm_usage.py -q`
  - `DB_PASSWORD=postgres DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot .venv/bin/python -m pytest tests/utils/test_metrics.py -q`
- 결과:
  - 통과(59 passed, 4 passed)

### 5.2 테스트 검증
- 실행 명령:
  - `DB_PASSWORD=postgres DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot .venv/bin/python -m pytest tests/utils/test_llm_usage.py tests/agents/test_router_intent.py tests/agents/test_factory_canary.py tests/agents/test_phase5_chat_guardrails.py tests/agents/test_daily_reporter.py -q`
- 결과:
  - 26 passed / 0 failed

### 5.4 Phase 2 코드 검증 (2026-03-05)
- 실행 명령:
  - `.venv/bin/python -m pytest tests/utils/test_llm_usage.py -q`
  - `.venv/bin/python -m pytest tests/agents/test_factory_canary.py -q`
  - `.venv/bin/python -m py_compile src/common/llm_usage.py src/bot/main.py`
  - `bash -n scripts/ops/llm_usage_cost_report.sh && bash -n scripts/ops/llm_usage_smoke_and_compare.sh && bash -n scripts/ops/llm_credit_snapshot_collect.sh`
- 결과:
  - 통과(`test_llm_usage`: 10 passed, `test_factory_canary`: 4 passed, py_compile/bash syntax OK)

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - `scripts/ops/llm_usage_smoke_and_compare.sh 1`
  - `scripts/ops/llm_usage_cost_report.sh 1`
- 결과:
  - OCI에서 smoke 실행 완료(챗봇/AI Decision/임베딩 route 커버리지 확인).
  - `llm_usage_cost_report.sh 1` 기준 6개 route 집계 확인.
  - `chat_premium_review` timeout 1건은 `error_type=TimeoutError`로 기록 확인.

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `docker exec -i -u postgres coinpilot-db psql -d coinpilot < /opt/coin-pilot/migrations/v3_3_2_llm_usage_observability.sql` 실행
2) `docker compose --env-file .env -f docker-compose.prod.yml up -d --build bot`로 bot 재기동
3) `scripts/ops/llm_usage_cost_report.sh 24`에서 route/provider/model 행이 출력되는지 확인
4) `scripts/ops/llm_usage_smoke_and_compare.sh 1` 실행 후 `llm_usage_events`에 `chat_sql_agent`/`chat_rag_generation`/`ai_decision_analyst` 등 route가 저장되는지 확인
5) README 동기화 검증: `rg -n "llm_usage_cost_report|llm_usage_smoke_and_compare|llm_credit_snapshot_collect|LLM_COST_SNAPSHOT_ENABLED" README.md`
6) cost snapshot one-shot 검증: `scripts/ops/llm_credit_snapshot_collect.sh`
7) scheduler env 확인: `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'echo LLM_COST_SNAPSHOT_ENABLED=$LLM_COST_SNAPSHOT_ENABLED; echo LLM_COST_SNAPSHOT_PROVIDERS=$LLM_COST_SNAPSHOT_PROVIDERS'`

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - DB 이벤트 원장 + soft-fail 수집 + 운영 SQL 리포트
- 고려했던 대안:
  1) 잔여 크레딧 조회만 사용
  2) Prometheus counter만 누적
  3) DB 원장 + 크레딧 스냅샷 대조(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) route별 비용 분리가 가능해 AI Decision vs Chatbot 비용 혼선을 제거
  2) 과거 구간 재집계가 가능해 카나리/모델 전환 검증에 유리
  3) 벤더 메타데이터 편차를 공통 계층에서 흡수해 호출부 단순화
- 트레이드오프(단점)와 보완/완화:
  1) DB write 오버헤드 증가: soft-fail + 최소 필드 저장으로 완화
  2) 임베딩 usage 메타데이터 부재: `status=estimated` 분리로 명시

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `src/common/llm_usage.py` callback/파싱/추정 로직의 의도와 실패 모드
  2) `src/agents/analyst.py`/`src/agents/guardian.py` 계측 경로의 운영 의도
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 불변조건(invariants)
  - 엣지케이스/실패 케이스
  - 대안 대비 판단 근거(필요 시)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 스키마/공통 유틸/호출 계측/운영 집계 스크립트 범위 일치
- 변경/추가된 부분(왜 바뀌었는지):
  - `ainvoke(config=...)` 미지원 mock/구현체를 위한 TypeError fallback 추가(테스트/호환성 안정화)
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 21-04 Phase 1(데이터 수집/집계 기반) 구현 완료
- 후속 작업(다음 plan 번호로 넘길 것):
  1) Grafana 패널(토큰/비용/오류율) 시각화 반영
  2) provider별 실제 cost API endpoint/path/header를 OCI `.env`에 연결하고 24h 대조 오차 관측
  3) 대조 오차 알람 rule(허용 오차 초과 시 경고) 연동

---

## 11. (선택) Phase 2+ 선반영/추가 구현 결과
- 추가 변경 요약:
  - 운영 hotfix 1건 반영: `scripts/ops/llm_usage_smoke_and_compare.sh`의 계측 플래그 출력 구문에서 `python -c` 따옴표 충돌로 발생하던 `SyntaxError`를 제거.
  - 변경 전: `f"LLM_USAGE_ENABLED={os.getenv(""LLM_USAGE_ENABLED"", ""unset"")}"` (OCI bash에서 구문 깨짐)
  - 변경 후: `"LLM_USAGE_ENABLED=" + os.getenv("LLM_USAGE_ENABLED", "unset")` (따옴표 충돌 없음)
  - 개선 효과: smoke 스크립트 실행이 시작 단계에서 즉시 중단되던 상태에서 정상 진행 가능한 상태로 복구.

- 추가 검증 결과:
  - 권장 명령:
    - `scripts/ops/llm_usage_smoke_and_compare.sh 1`
  - 기대 결과:
    - 시작부 `SyntaxError` 없이 `[INFO] LLM usage smoke start` 이후 챗봇/AI Decision 호출 단계로 진행

---

## 12. Phase 2 운영 관측 업데이트 (2026-03-04)
- 운영 검증 요약:
  - `scripts/ops/llm_usage_smoke_and_compare.sh 1` 실행이 정상 완료되었고, 챗봇/AI Decision/임베딩 route 커버리지가 출력됨.
  - `llm_usage_cost_report.sh 1` 기준 route 커버리지는 6개(`chat_sql_agent`, `chat_rag_generation`, `chat_premium_review`, `ai_decision_analyst`, `ai_decision_guardian`, `embedding_query`) 확인.
  - `chat_premium_review`는 1건 `TimeoutError`가 기록됐고, timeout 상향 env(`CHAT_PREMIUM_REVIEW_TIMEOUT_SEC=20`)를 컨테이너에 반영함.
  - `llm_credit_snapshots`는 여전히 0건으로, reconciliation의 `credit_delta_usd`는 참고치(0)로만 해석해야 함.
- 운영 쿼리 정정 사항:
  - `llm_usage_events`에는 `error_message` 컬럼이 없고 `error_type`, `meta`를 조회해야 함.
  - OCI 기본 환경에 `rg`가 없어서 로그 필터는 `grep -E` 기준으로 운영.
- 정량 관측(운영 로그 기반):

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| smoke 스크립트 완료 여부(성공=1, 실패=0) | 0 | 1 | +1 | +100.0 |
| `llm_usage_cost_report.sh 1` 집계 행 수 | 0 | 6 | +6 | N/A |
| `llm_credit_snapshots` 행 수 | 0 | 0 | 0 | 0.0 |

- 상태 판단:
  - Phase 1 구현은 완료됐지만, `llm_credit_snapshots` 자동 수집/대조 고도화가 남아 있으므로 `21-04`는 `in_progress`를 유지한다.

---

## 13. References
- 링크:
  - `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`
  - `docs/troubleshooting/21-06_ai_canary_env_injection_and_observability_gap.md`
  - `scripts/ops/llm_usage_cost_report.sh`
  - `scripts/ops/llm_usage_smoke_and_compare.sh`
  - `scripts/ops/llm_credit_snapshot_collect.sh`
  - `migrations/v3_3_2_llm_usage_observability.sql`
  - `migrations/v3_3_3_llm_provider_cost_snapshots.sql`

---

## 14. Phase 2 구현 반영 (2026-03-05)
- 구현 요약:
  - `src/common/llm_usage.py`에 provider API 기반 credit snapshot 수집/저장 로직을 추가했다.
    - env-driven config(`LLM_CREDIT_SNAPSHOT_<PROVIDER>_URL`, `..._BALANCE_JSON_PATH`, `..._HEADERS_JSON`)
    - `${ENV_NAME}` placeholder 치환 지원
    - dot-path JSON 추출(`a.b.0.c`) 지원
    - 실패 시 soft-fail 유지(매매/챗봇 흐름 비중단)
  - `src/bot/main.py` scheduler에 `llm_credit_snapshot_job`을 추가했다.
    - `LLM_CREDIT_SNAPSHOT_ENABLED=true`일 때만 주기 실행
    - startup 시 1회 즉시 실행
  - 운영 스크립트 보강:
    - `scripts/ops/llm_credit_snapshot_collect.sh` 추가(one-shot 수집 + 최근 snapshot 조회)
    - `scripts/ops/llm_usage_cost_report.sh`에 snapshot freshness 섹션 추가
    - `scripts/ops/llm_usage_smoke_and_compare.sh`에서 snapshot 1회 실행 결과 출력
- 정량 증빙:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| `tests/utils/test_llm_usage.py` 통과 건수 | 6 | 10 | +4 | +66.7 |
| credit snapshot 수집 실행 경로(스케줄러/one-shot) | 0 | 2 | +2 | N/A |
| `llm_usage_cost_report.sh` 내 snapshot 상태 섹션 수 | 0 | 1 | +1 | N/A |

- 남은 운영 검증:
  - OCI `.env`에 provider API endpoint/path/header를 넣어 실제 snapshot row 생성 확인 필요
  - 생성 확인 명령: `docker exec -u postgres coinpilot-db psql -d coinpilot -c "SELECT created_at, provider, balance_usd, source FROM llm_credit_snapshots ORDER BY created_at DESC LIMIT 20;"`

---

## 15. Phase 2.1 구현 반영 (2026-03-05)
- 문제 정의:
  - provider 공식 API에서 "잔여 크레딧(balance)" endpoint 의존성이 불명확해 운영 자동화가 막혔다.
  - 결과적으로 `llm_credit_snapshots` 기반 대조는 0건 상태에 머물렀고, 실측 검증이 지연됐다.
- 구현 요약:
  - `llm_provider_cost_snapshots` 테이블을 추가하고, provider 구간 비용(cost) 스냅샷을 저장하도록 전환했다.
    - 스키마: `migrations/v3_3_3_llm_provider_cost_snapshots.sql`, `deploy/db/init.sql`, `src/common/models.py`
  - `src/common/llm_usage.py`에 비용 수집 경로를 추가했다.
    - `LLM_COST_SNAPSHOT_*` env 기반 설정
    - URL 템플릿 placeholder 지원: `${START_UNIX}`, `${END_UNIX}`, `${START_ISO}`, `${END_ISO}`
    - `collect_llm_cost_snapshots_once()` one-shot 수집
  - `src/bot/main.py` 스케줄러를 `llm_cost_snapshot_job`으로 전환했다.
  - 운영 스크립트를 비용 스냅샷 기준으로 보정했다.
    - `scripts/ops/llm_usage_cost_report.sh`: `provider_cost_usd` 대조
    - `scripts/ops/llm_usage_smoke_and_compare.sh`: `LLM_COST_SNAPSHOT_ENABLED` 및 cost snapshot one-shot
    - `scripts/ops/llm_credit_snapshot_collect.sh`: 이름은 유지, 내부 동작은 cost snapshot 수집으로 전환
- 정량 증빙:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| provider 외부 대조 저장 대상 테이블 수 | 1 (`llm_credit_snapshots`) | 2 (`+ llm_provider_cost_snapshots`) | +1 | +100.0 |
| 비용 스냅샷 env 설정 키 수 | 0 | 10 (`LLM_COST_SNAPSHOT_*`) | +10 | N/A |
| `tests/utils/test_llm_usage.py` 통과 건수 | 10 | 12 | +2 | +20.0 |

- 운영 적용 후 확인 명령:
  - 마이그레이션: `docker exec -i -u postgres coinpilot-db psql -d coinpilot < /opt/coin-pilot/migrations/v3_3_3_llm_provider_cost_snapshots.sql`
  - 수집 확인: `scripts/ops/llm_credit_snapshot_collect.sh`
  - 행 확인: `docker exec -u postgres coinpilot-db psql -d coinpilot -c "SELECT created_at, provider, window_start, window_end, cost_usd FROM llm_provider_cost_snapshots ORDER BY created_at DESC LIMIT 20;"`

- README 동기화 검증:
  - `rg -n "LLM_COST_SNAPSHOT|provider_cost_usd|llm_provider_cost_snapshots" README.md`

---

## 16. Phase 2.1 OCI 운영 검증 (2026-03-05)
- 실행 요약:
  - `git pull --ff-only origin f21`: 최신 상태 확인(`Already up to date`)
  - 마이그레이션 멱등 재실행:
    - `v3_3_2_llm_usage_observability.sql`
    - `v3_3_3_llm_provider_cost_snapshots.sql`
  - bot 재빌드/재기동 후 env 투영 확인:
    - `LLM_USAGE_ENABLED=true`
    - `CHAT_PREMIUM_REVIEW_TIMEOUT_SEC=20`
    - `LLM_COST_SNAPSHOT_ENABLED=false`
    - `LLM_COST_SNAPSHOT_INTERVAL_MIN=60`
    - `LLM_COST_SNAPSHOT_LOOKBACK_HOURS=1`
- 운영 스모크 결과:
  - `scripts/ops/llm_usage_smoke_and_compare.sh 1`: `PASS`
  - route coverage: 6개
    - `ai_decision_analyst`, `ai_decision_guardian`, `chat_sql_agent`, `chat_rag_generation`, `chat_premium_review`, `embedding_query`
  - `scripts/ops/llm_usage_cost_report.sh 24` 집계 정상 출력
  - `scripts/ops/llm_credit_snapshot_collect.sh` 실행 시 cost snapshot summary:
    - `enabled=false`, `configured_providers=0`, `success_count=0`, `failure_count=0`
  - `llm_provider_cost_snapshots` 행 수:
    - `0 rows` (비활성 모드 기준 정상)

- 정량 증빙:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| smoke 스크립트 완료 여부(성공=1, 실패=0) | 0 | 1 | +1 | +100.0 |
| 1h route coverage(개수) | 0 | 6 | +6 | N/A |
| `llm_provider_cost_snapshots` 누적 건수(비활성 모드) | 0 | 0 | 0 | 0.0 |
| `LLM_COST_SNAPSHOT_ENABLED` 유효값 반영 여부(미설정→기본 false) | 0 | 1 | +1 | +100.0 |

- 해석:
  - 현재 모드는 "현상 유지(비활성)"로 정상 운영 중이며, 내부 원장(`llm_usage_events`) 기반 비용 관측은 안정적으로 동작한다.
  - provider 외부 비용 대조는 향후 `LLM_COST_SNAPSHOT_ENABLED=true` 전환 시점에 활성화한다.

---

## 17. Phase 3 운영 관측 업데이트 (2026-03-08)
- 관측 요약:
  - `/opt/coin-pilot` 기준에서 `scripts/ops/llm_usage_cost_report.sh 24` 실행은 정상 동작했고, 최근 24시간 모델/route별 토큰/비용 리포트가 출력됐다.
  - 내부 원장 기준으로는 `anthropic`과 `openai` 모두 비용 분리가 가능하다.
  - 하지만 `llm_provider_cost_snapshots`는 여전히 `0 rows`이며 freshness 섹션도 비어 있어 외부 비용 대조(reconciliation)는 아직 불가하다.
  - 따라서 `21-04`는 "운영 리포트 동작 확인 완료"까지는 도달했지만, 현재 문서 기준으로는 `in_progress` 유지가 맞다.
- 경로 주의:
  - 실행 위치가 `/opt/coin-pilot/deploy/cloud/oci`면 `scripts/ops/...` 상대경로가 맞지 않는다.
  - 권장 실행:
    - `cd /opt/coin-pilot && scripts/ops/llm_usage_cost_report.sh 24`
    - 또는 `/opt/coin-pilot/scripts/ops/llm_usage_cost_report.sh 24`

- 정량 관측(최근 24h):

| feature | route | provider | model | total_calls | success_calls | error_calls | total_tokens | cost_usd |
|---|---|---|---|---:|---:|---:|---:|---:|
| `ai_decision` | `ai_decision_analyst` | `anthropic` | `claude-haiku-4-5-20251001` | 13 | 12 | 1 | 54,343 | 0.066380 |
| `ai_decision` | `ai_decision_guardian` | `anthropic` | `claude-haiku-4-5-20251001` | 9 | 9 | 0 | 39,964 | 0.052317 |
| `ai_decision` | `ai_decision_analyst` | `openai` | `gpt-4o-mini` | 5 | 5 | 0 | 13,732 | 0.002353 |
| `ai_decision` | `ai_decision_guardian` | `openai` | `gpt-4o-mini` | 2 | 2 | 0 | 5,554 | 0.000919 |
| `daily_report` | `daily_report_summary` | `openai` | `gpt-4o-mini` | 1 | 1 | 0 | 328 | 0.000106 |

- reconciliation 관측:

| provider | ledger_cost_usd | provider_cost_usd | delta_usd |
|---|---:|---:|---:|
| `anthropic` | 0.118697 | 0.000000 | 0.118697 |
| `openai` | 0.003379 | 0.000000 | 0.003379 |

- snapshot 상태:

| 지표 | 값 |
|---|---:|
| `llm_provider_cost_snapshots` 총 행 수 | 0 |
| provider별 snapshot count | 0 providers |
| freshness 결과 행 수 | 0 |

- 정량 개선 증빙(추가):
  - 측정 기간/표본:
    - 최근 24시간, route 5개
  - 측정 기준:
    - route/provider/model 비용 리포트 출력 여부 + provider snapshot 존재 여부
  - 데이터 출처:
    - `scripts/ops/llm_usage_cost_report.sh 24`
    - `llm_provider_cost_snapshots` SQL
  - 재현 명령:
    - `cd /opt/coin-pilot && scripts/ops/llm_usage_cost_report.sh 24`
    - `docker exec -u postgres coinpilot-db psql -d coinpilot -c "SELECT provider, count(*) AS snapshot_count FROM llm_provider_cost_snapshots GROUP BY provider ORDER BY provider;"`
    - `docker exec -u postgres coinpilot-db psql -d coinpilot -c "SELECT provider, max(created_at) AS latest_snapshot_at FROM llm_provider_cost_snapshots GROUP BY provider ORDER BY provider;"`

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 24h cost report 집계 행 수 | 0 | 5 | +5 | 측정 불가(분모 0) |
| 24h 비용 관측 provider 수 | 0 | 2 | +2 | 측정 불가(분모 0) |
| provider cost snapshot 행 수 | 0 | 0 | 0 | 0.0 |

- 해석:
  - 내부 usage ledger 기반 토큰/비용 관측은 운영 가능 상태다.
  - 그러나 `provider_cost_usd`가 전부 0이고 snapshot 행이 없어서, 현재는 "route별 비용 추이 리포트는 가능, 외부 비용 대조는 미완료" 상태다.
  - 따라서 `21-04`는 `done`이 아니라 **"상태 명확화 완료, `in_progress` 유지"** 로 보는 것이 맞다.
- 다음 판정 조건:
  1) `LLM_COST_SNAPSHOT_ENABLED=true` 상태에서 최소 1개 provider snapshot row 생성
  2) freshness 결과에 provider별 최근 시각이 표시
  3) `ledger_cost_usd` vs `provider_cost_usd` 대조가 의미 있는 수준으로 출력
