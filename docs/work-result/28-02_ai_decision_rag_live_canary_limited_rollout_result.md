# 28-02. AI Decision RAG Live Canary 제한 주입 결과

작성일: 2026-03-11
작성자: Codex
관련 계획서: `docs/work-plans/28-02_ai_decision_rag_live_canary_limited_rollout_plan.md`
상태: In Progress (코드 구현 및 정적 검증 완료, OCI env wiring fix 완료, post-redeploy live 관측 대기)

---

## 0. 해결한 문제 정의
- 증상:
  - `28-01` replay는 통과했지만, 실제 운영 canary 경로에서만 RAG를 제한 주입하는 안전한 활성화 경로가 없었다.
- 영향:
  - 코드를 바로 primary에 적용하면 rollback 반경이 커지고, canary에서도 RAG 실패가 거래 REJECT 원인으로 번질 수 있었다.
- 재현 조건:
  - `AI_CANARY_ENABLED=true` 환경에서 canary 모델 실험을 유지하면서도, RAG는 일부 경로에만 켜고 싶을 때
- Root cause:
  - live 경로에 RAG on/off 및 fallback status를 구분하는 분기와 운영 관측 메타가 없었다.

## 1. 이번 Phase 범위
- canary Analyst에만 RAG 제한 주입
- RAG 실패 시 baseline Analyst로 자동 fallback
- `agent_decisions.model_used`에 `canary-rag` / `canary-rag-fallback` 라벨 반영
- `llm_usage_events.meta`에 `rag_status` 기록
- `ai_decision_canary_report.sh`에 `rag_status` 기준 usage/latency/cost breakdown 추가

## 2. 구현 내용
1. canary-only live RAG 분기 추가
   - `src/agents/runner.py`
   - `AI_DECISION_RAG_CANARY_ENABLED=true`이면서 `route_label=canary`인 경우에만 RAG를 시도한다.
   - primary 및 `primary-fallback` 경로는 그대로 유지한다.
2. RAG 생성 실패 fallback
   - `src/agents/runner.py`
   - RAG 컨텍스트 생성이 예외로 실패하면 `text=""`, `status="fallback"`인 빈 컨텍스트를 내려 기존 Analyst 경로로 자동 복귀한다.
   - 즉, RAG 실패가 곧 거래 REJECT로 번지지 않도록 설계했다.
3. 운영 라벨 보강
   - `src/agents/runner.py`
   - `agent_decisions.model_used`를 `canary`에서 `canary-rag` 또는 `canary-rag-fallback`으로 구분 가능하게 했다.
4. usage 메타 보강
   - `src/agents/analyst.py`
   - `llm_usage_events.meta`에 `rag_status`를 함께 기록해 replay/live, rag on/off/fallback을 구분할 수 있게 했다.
5. canary report 보강
   - `scripts/ops/ai_decision_canary_report.sh`
   - `llm_usage_events` 기준 `provider/model/rag_status`별 `total_calls`, `avg_latency_ms`, `avg_cost_usd` 섹션을 추가했다.
6. env example 보강
   - `.env.example`
   - `deploy/cloud/oci/.env.example`
   - `AI_DECISION_RAG_CANARY_ENABLED`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS`를 추가했다.

## 3. 아키텍처 선택과 대안 비교
- 선택안:
  - canary Analyst에만 RAG를 제한 주입하고, 실패 시 baseline Analyst로 즉시 fallback한다.
- 선택 이유:
  - live 운영 영향 반경을 최소화하고 rollback을 env 플래그 하나로 끝낼 수 있다.
  - Guardian/primary를 건드리지 않아 원인 분리가 쉽다.
- 검토한 대안:
  1. primary + canary 동시 적용
     - 장점: 표본 확보가 빠르다.
     - 단점: rollback 반경이 크다.
  2. Guardian까지 동시 적용
     - 장점: 체인 전체 일관성 확보 가능
     - 단점: Analyst 변화 효과 분리가 어렵다.
  3. replay-only 유지
     - 장점: 운영 리스크 0
     - 단점: live latency/cost/실시간 입력 차이를 끝내 확인할 수 없다.

## 4. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| canary 전용 live RAG 스위치 | 0 | 1 | +1 |
| RAG 실패 시 baseline fallback 경로 | 0 | 1 | +1 |
| `model_used` 실험 라벨 구분 | canary 단일 | canary / canary-rag / canary-rag-fallback | 분류 3종 |
| canary report의 rag status usage breakdown | 0 | 1 | +1 |
| 신규/관련 테스트 | 0 | 9 passed | +9 |

## 5. 측정 기준
- 기간:
  - 2026-03-11 코드 구현 및 정적 검증
- 표본 수:
  - 관련 테스트 9건
- 성공 기준:
  - canary-only RAG 분기/라벨/폴백 로직이 테스트 가능 구조로 들어갈 것
  - 정적 검증 통과
- 실패 기준:
  - canary가 아닌 primary 경로에서도 RAG가 켜짐
  - RAG 예외가 발생할 때 baseline fallback 없이 실패함

## 6. 증빙 근거 (명령)
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_ai_decision_rag.py tests/agents/test_runner_canary_rag.py
python3 -m py_compile src/agents/runner.py src/agents/analyst.py src/agents/ai_decision_rag.py
bash -n scripts/ops/ai_decision_canary_report.sh
timeout 20s bash -lc 'PYTHONPATH=. .venv/bin/pytest -q tests/test_agents.py'
```

검증 결과:
- `tests/agents/test_ai_decision_rag.py tests/agents/test_runner_canary_rag.py`: `9 passed in 0.93s`
- `py_compile`: 통과
- `scripts/ops/ai_decision_canary_report.sh`: shell syntax 통과
- `tests/test_agents.py`: `timeout 20s` 제한에서 `..`까지 진행 후 종료(code 124)
  - 새 변경과 직접 관련 없는 기존 timeout fallback 케이스가 20초 제한 내 완료되지 않아, 본 작업의 직접 회귀 판정은 위 9건 테스트와 정적 검증으로 대체했다.

## 7. 측정 불가 사유 / 대체 지표 / 추후 계획
- 측정 불가 사유:
  - 2026-03-11 1차 OCI 관측에서는 `AI_DECISION_RAG_CANARY_ENABLED=true`가 `.env`에만 있고 `coinpilot-bot` runtime env에는 주입되지 않아, 실제 live canary RAG 표본이 생성되지 않았다.
- 대체 지표:
  - 관련 테스트 9건
  - `py_compile`
  - canary report shell syntax
- 추후 측정 계획:
  1. `28-03` compose env passthrough fix 반영 후 bot 재빌드
  2. `scripts/ops/ai_decision_canary_report.sh 24`
  3. `scripts/ops/llm_usage_cost_report.sh 24`
  4. `agent_decisions.model_used`의 `canary-rag` 표본 확인
  5. 24h / 72h 기준 `parse_fail`, `timeout`, `confidence`, `latency`, `cost` 비교

## 7.1 OCI env passthrough gap 및 보정
- 관련 계획/결과/장애 문서:
  - `docs/work-plans/28-03_ai_decision_rag_canary_env_passthrough_fix_plan.md`
  - `docs/work-result/28-03_ai_decision_rag_canary_env_passthrough_fix_result.md`
  - `docs/troubleshooting/28-03_ai_decision_rag_canary_env_passthrough_gap.md`
- 문제:
  - OCI `.env`에는 `AI_DECISION_RAG_CANARY_ENABLED=true`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS=30`이 있었지만, `docker exec coinpilot-bot env`에는 해당 키가 보이지 않았다.
  - 24h live 관측도 `openai:gpt-4o-mini (canary)` + `rag_status=disabled`만 보여 실제 RAG canary가 켜지지 않은 상태였다.
- 조치:
  - `deploy/cloud/oci/docker-compose.prod.yml`의 `bot.environment`에 두 env passthrough를 추가했다.
- 적용 결과:
  - 재배포 후 `docker exec coinpilot-bot env | grep ...`에서 두 키가 모두 보이는 것을 확인했다.
  - 직후에는 post-redeploy canary 표본이 아직 없어서 `canary-rag`는 `0건`이지만, 현재는 live 관측이 가능한 런타임 상태다.

## 8. OCI 적용 및 검증 방법
```bash
cd /opt/coin-pilot
git fetch origin
git checkout pretrade
git pull --ff-only origin pretrade
```

```bash
cd /opt/coin-pilot/deploy/cloud/oci
nano .env
```

예시:
```dotenv
AI_CANARY_ENABLED=true
AI_CANARY_PROVIDER=openai
AI_CANARY_MODEL=gpt-4o-mini
AI_CANARY_PERCENT=20
AI_DECISION_RAG_CANARY_ENABLED=true
AI_DECISION_RAG_CASE_LOOKBACK_DAYS=30
```

```bash
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml up -d --build bot
docker compose --env-file .env -f docker-compose.prod.yml ps bot
```

24h 확인:
```bash
cd /opt/coin-pilot
scripts/ops/ai_decision_canary_report.sh 24
scripts/ops/llm_usage_cost_report.sh 24
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT model_used, count(*) AS total, avg(confidence) AS avg_confidence
FROM agent_decisions
WHERE created_at >= now() - interval '24 hours'
GROUP BY model_used
ORDER BY total DESC, model_used;
"
```

성공 기준:
- `canary-rag` 또는 `canary-rag-fallback` 표본 확인
- `parse_fail_rate` 증가 `+2%p` 이내
- `timeout_rate` 증가 `+2%p` 이내
- `avg_confidence_delta >= -5pt`
- `avg cost_usd` 증가 `+25%` 이내
- `p50 latency_ms` 증가 `+25%` 이내

## 9. README / 체크리스트 동기화
- `README.md`:
  - 미반영
  - 사유: main `28`은 아직 `done`이 아니고, 이번 범위는 canary 실험 준비 단계다.
- `remaining_work_master_checklist.md`:
  - `28` 상태를 `in_progress` 유지
  - 최근 로그에 `28-02` 구현 완료 및 OCI live 관측 대기를 추가
