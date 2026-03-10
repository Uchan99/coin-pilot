# 28-03. AI Decision RAG Canary Env Passthrough Fix 계획

**작성일**: 2026-03-11  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/28_ai_decision_strategy_case_rag_plan.md`, `docs/work-plans/28-02_ai_decision_rag_live_canary_limited_rollout_plan.md`  
**관련 장애 문서**: `docs/troubleshooting/28-03_ai_decision_rag_canary_env_passthrough_gap.md`

---

## 0. 트리거(Why started)
- OCI에서 `deploy/cloud/oci/.env`에는 `AI_DECISION_RAG_CANARY_ENABLED=true`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS=30`이 존재했지만, `docker exec coinpilot-bot env` 출력에는 해당 변수가 주입되지 않았다.
- 같은 시점의 운영 관측에서도 `agent_decisions.model_used`는 `openai:gpt-4o-mini (canary)`만 보였고, `scripts/ops/ai_decision_canary_report.sh 24`의 `analyst usage breakdown (rag status)`는 `openai / disabled`만 출력됐다.

## 1. 문제 요약
- 증상:
  - `28-02` 코드 반영 후에도 live canary에서 `canary-rag`/`canary-rag-fallback` 표본이 전혀 생성되지 않는다.
- 영향 범위:
  - 기능: canary RAG 실험이 실제로 켜지지 않음
  - 리스크: `28` Phase 2 운영 검증이 진행되지 못함
  - 비용/데이터: replay 비용만 증가하고, live canary 증빙은 생성되지 않음
- 재현 조건:
  - OCI `.env`에 RAG canary 관련 값을 넣고 bot를 재빌드해도, 컨테이너 런타임 env에 변수가 보이지 않는다.

## 2. 원인 분석
- 1차 가설:
  - `.env` 값은 존재하지만 `docker-compose.prod.yml`의 `bot.environment`에 passthrough가 누락됐을 가능성이 높다.
- 현재 확인 근거:
  - `grep -n 'AI_DECISION_RAG_CANARY_ENABLED|AI_DECISION_RAG_CASE_LOOKBACK_DAYS' deploy/cloud/oci/docker-compose.prod.yml` 결과 bot 환경 변수 목록에 해당 키가 없다.
  - `docker exec coinpilot-bot env | grep ...` 결과 `AI_CANARY_*`만 보이고 `AI_DECISION_RAG_*`는 누락됐다.
- Root cause:
  - OCI compose 파일이 `.env`의 `AI_DECISION_RAG_CANARY_ENABLED`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS`를 bot 컨테이너에 전달하지 않는다.

## 3. 아키텍처 선택
- 선택안:
  - `docker-compose.prod.yml`의 `bot.environment`에 누락된 두 env를 명시적으로 추가하고, OCI 재배포 후 런타임 주입 여부를 확인한다.
- 선택 이유:
  - 코드 경로 자체는 이미 구현돼 있고, 현재 문제는 런타임 wiring에 한정된다.
- 검토한 대안:
  1. runner에서 env 미주입 시 기본값으로 강제 활성화
     - 장점: compose 수정 없이 동작 가능
     - 단점: 안전 기본값과 운영 제어 원칙을 깨뜨린다.
  2. `.env.example`만 수정
     - 장점: 문서 정리
     - 단점: 실제 OCI 런타임 문제를 해결하지 못한다.
  3. n8n/cron 등 외부 래퍼에서 환경 주입
     - 장점: 특정 실행에 한정 가능
     - 단점: bot 메인 프로세스와 일관되지 않다.
- 트레이드오프:
  - compose 수정은 배포가 필요하지만, 원인 위치가 가장 명확하고 운영 제어도 유지된다.

## 4. 대응 전략
- 단기 조치:
  1. `deploy/cloud/oci/docker-compose.prod.yml`에 `AI_DECISION_RAG_CANARY_ENABLED`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS` passthrough 추가
  2. 결과/트러블슈팅/체크리스트에 OCI 관측 근거 반영
- 근본 해결:
  - 이후 canary 기능 추가 시 `.env.example`와 `docker-compose.prod.yml`의 env passthrough를 함께 검증하는 절차를 result에 고정한다.

## 5. 구현/수정 내용
- 변경 파일(예정):
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `docs/work-result/28-02_ai_decision_rag_live_canary_limited_rollout_result.md`
  - `docs/work-result/28_ai_decision_strategy_case_rag_result.md`
  - `docs/checklists/remaining_work_master_checklist.md`
  - `docs/troubleshooting/28-03_ai_decision_rag_canary_env_passthrough_gap.md`
- 구현 범위:
  - compose env passthrough 추가
  - OCI 검증 절차/근거 문서화
- 의도적으로 제외:
  - RAG prompt/logic 자체 변경
  - Guardian/primary 경로 변경

## 6. 검증 기준
- 런타임 env 확인:
  - `docker exec coinpilot-bot env | grep -E 'AI_DECISION_RAG_CANARY_ENABLED|AI_DECISION_RAG_CASE_LOOKBACK_DAYS'`
- live canary 관측:
  - `agent_decisions.model_used`에 `canary-rag` 또는 `canary-rag-fallback` 등장
  - `scripts/ops/ai_decision_canary_report.sh 24`의 `rag status`에 `enabled` 또는 `fallback` 등장
- 정량 기준:
  - post-restart 표본 기준 `rag_status=enabled|fallback` 호출이 최소 1건 이상 확인돼야 함

## 7. 롤백
- compose env passthrough 삭제 후 bot 재배포
- 운영에서 실험 중단 시 `.env`만 `AI_DECISION_RAG_CANARY_ENABLED=false`로 되돌려도 충분

## 8. 문서 반영
- result/troubleshooting/checklist 동기화
- Charter 변경:
  - 없음. 운영 정책 자체가 아니라 env wiring 결함 수정이다.

## 9. 리스크 / 가정 / 미확정
- 리스크:
  - env passthrough 수정 후에도 표본이 없으면 단순히 canary 트래픽이 아직 적은 상황일 수 있다.
- 가정:
  - `.env` 값 자체는 이미 정확히 입력돼 있다.
- 미확정:
  - live canary 표본 확보 속도

## 10. 변경 이력
- 2026-03-11: plan 생성. OCI 관측 결과 `.env`에는 값이 있지만 bot 컨테이너 env에 `AI_DECISION_RAG_*`가 누락된 문제를 compose passthrough gap으로 정의했다.
