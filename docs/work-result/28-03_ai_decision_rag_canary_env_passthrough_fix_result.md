# 28-03. AI Decision RAG Canary Env Passthrough Fix 결과

작성일: 2026-03-12
작성자: Codex
관련 계획서: `docs/work-plans/28-03_ai_decision_rag_canary_env_passthrough_fix_plan.md`
관련 장애 문서: `docs/troubleshooting/28-03_ai_decision_rag_canary_env_passthrough_gap.md`
상태: Done

---

## 0. 해결한 문제 정의
- 증상:
  - `deploy/cloud/oci/.env`에는 `AI_DECISION_RAG_CANARY_ENABLED=true`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS=30`이 있었지만, `coinpilot-bot` 컨테이너 런타임 env에는 두 변수가 주입되지 않았다.
  - live canary 관측에서 `agent_decisions.model_used`는 `openai:gpt-4o-mini (canary)`만 보였고, `canary-rag`/`canary-rag-fallback` 표본은 `0건`이었다.
  - `scripts/ops/ai_decision_canary_report.sh 24`의 analyst usage breakdown에서도 `rag_status=disabled`만 출력됐다.
- 영향:
  - `28-02`의 canary 전용 RAG 제한 주입 코드가 운영에서 실제로 켜지지 않았다.
  - replay 비용은 발생했지만, live canary 검증 표본은 생성되지 않았다.
- 재현 조건:
  - OCI `.env`에 RAG canary 값을 넣은 상태로 bot를 재빌드/재배포할 때
- Root cause:
  - `deploy/cloud/oci/docker-compose.prod.yml`의 `bot.environment`에 `AI_DECISION_RAG_CANARY_ENABLED`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS` passthrough가 누락돼 있었다.

## 1. 구현 내용
1. OCI compose env passthrough 추가
   - `deploy/cloud/oci/docker-compose.prod.yml`
   - `bot.environment`에 아래 두 키를 추가했다.
     - `AI_DECISION_RAG_CANARY_ENABLED`
     - `AI_DECISION_RAG_CASE_LOOKBACK_DAYS`
2. 문서 추적성 보강
   - `28-02`, main `28`, troubleshooting, checklist에 OCI 재배포 전/후 근거와 후속 검증 절차를 연결했다.

## 2. 아키텍처 선택과 대안 비교
- 선택안:
  - OCI compose의 `bot.environment`에 명시적으로 env passthrough를 추가한다.
- 선택 이유:
  - 현재 문제는 코드 로직이 아니라 런타임 wiring 결함이며, compose 수정이 가장 직접적인 원인 제거다.
- 검토한 대안:
  1. runner에서 env 누락 시 기본값으로 강제 활성화
     - 장점: compose 수정 없이 동작 가능
     - 단점: 안전 기본값을 깨고, 운영 제어 경계를 흐린다.
  2. `.env.example`만 수정
     - 장점: 문서 정리에는 도움이 됨
     - 단점: 실제 OCI 컨테이너 env 누락은 해결하지 못한다.
  3. n8n/cron 래퍼에서 별도 env 주입
     - 장점: 특정 실행 경로만 우회 가능
     - 단점: bot 메인 프로세스와 운영 경로가 분리돼 일관성이 깨진다.
- 트레이드오프:
  - compose 수정은 재배포가 필요하지만, bot 메인 프로세스와 실험 경로의 환경 제어를 일관되게 유지할 수 있다.

## 3. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| `.env` 내 RAG canary env 존재 여부 | 2 | 2 | 0 |
| `docker-compose.prod.yml` bot env passthrough | 0 | 2 | +2 |
| `coinpilot-bot` 런타임 env의 `AI_DECISION_RAG_*` 주입 수 | 0 | 2 | +2 |
| 최근 24h `canary-rag` 표본 | 0 | 0 | 0 |
| 최근 24h `rag_status=enabled|fallback` analyst 호출 | 0 | 0 | 0 |

## 4. 측정 기준
- 기간:
  - before: 2026-03-11 OCI live canary 24h 관측
  - after: 2026-03-12 compose 수정 및 OCI 재배포 직후
- 표본 수:
  - runtime env key 2개
  - live canary post-redeploy 표본은 아직 `0건`
- 성공 기준:
  - `docker exec coinpilot-bot env`에 두 env가 모두 보여야 한다.
  - 이후 새 canary 표본이 쌓일 때 `canary-rag` 또는 `canary-rag-fallback`이 생성될 수 있는 상태여야 한다.
- 실패 기준:
  - `.env` 값은 있어도 runtime env에 여전히 누락됨

## 5. 증빙 근거 (명령)
```bash
rg -n "AI_DECISION_RAG_CANARY_ENABLED|AI_DECISION_RAG_CASE_LOOKBACK_DAYS" deploy/cloud/oci/docker-compose.prod.yml
```

```bash
cd /opt/coin-pilot/deploy/cloud/oci
grep -n 'AI_DECISION_RAG_CANARY_ENABLED\|AI_DECISION_RAG_CASE_LOOKBACK_DAYS\|AI_CANARY_' .env
docker compose --env-file .env -f docker-compose.prod.yml up -d --build bot
docker exec coinpilot-bot env | grep -E 'AI_DECISION_RAG_CANARY_ENABLED|AI_DECISION_RAG_CASE_LOOKBACK_DAYS|AI_CANARY_'
```

```bash
cd /opt/coin-pilot
scripts/ops/ai_decision_canary_report.sh 24
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT model_used, count(*) AS total, avg(confidence) AS avg_confidence
FROM agent_decisions
WHERE created_at >= now() - interval '24 hours'
GROUP BY model_used
ORDER BY total DESC, model_used;
"
```

검증 결과:
- compose 파일 passthrough 키 2개 추가 확인
- OCI `.env`에는 기존과 동일하게 RAG canary env가 존재함
- 재배포 후 `docker exec coinpilot-bot env`에서 `AI_DECISION_RAG_CANARY_ENABLED=true`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS=30` 확인
- 직후 24h 관측에서는 아직 `canary-rag` 표본 `0건`이며, 이는 post-redeploy canary 표본 미도착 상태로 해석

## 6. 측정 불가 사유 / 대체 지표 / 추후 계획
- 측정 불가 사유:
  - 재배포 직후라 post-redeploy canary 표본이 아직 쌓이지 않았다.
- 대체 지표:
  - runtime env 주입 여부
  - `canary-rag`가 생성될 수 있는 런타임 상태 복구 여부
- 추후 측정 계획:
  1. `docker inspect -f '{{.State.StartedAt}}' coinpilot-bot`로 post-redeploy 시작 시각 확인
  2. 해당 시각 이후 `agent_decisions.model_used`에 `canary-rag`/`canary-rag-fallback` 등장 여부 확인
  3. `scripts/ops/ai_decision_canary_report.sh 24`에서 `rag_status=enabled|fallback` usage breakdown 재확인

## 7. OCI 적용 및 검증 방법
```bash
cd /opt/coin-pilot
git fetch origin
git checkout pretrade
git pull --ff-only origin pretrade
```

```bash
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml up -d --build bot
docker compose --env-file .env -f docker-compose.prod.yml ps bot
docker exec coinpilot-bot env | grep -E 'AI_DECISION_RAG_CANARY_ENABLED|AI_DECISION_RAG_CASE_LOOKBACK_DAYS|AI_CANARY_'
```

```bash
docker inspect -f '{{.State.StartedAt}}' coinpilot-bot
```

## 8. README / 체크리스트 동기화
- `README.md`:
  - 미반영
  - 사유: main `28`은 아직 `done`이 아니고, 이번 변경은 OCI env wiring fix 하위 작업이다.
- `remaining_work_master_checklist.md`:
  - `28` 상태를 `in_progress` 유지
  - 최근 로그에 `28-03` 구현 완료 및 post-redeploy live canary 표본 대기 상태를 추가했다.
