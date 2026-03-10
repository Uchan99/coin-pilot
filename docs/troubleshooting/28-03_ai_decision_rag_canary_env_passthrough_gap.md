# 28-03. AI Decision RAG Canary Env Passthrough Gap

**작성일**: 2026-03-11  
**작성자**: Codex  
**관련 계획 문서**: `docs/work-plans/28-03_ai_decision_rag_canary_env_passthrough_fix_plan.md`  
**관련 결과 문서**: `docs/work-result/28-02_ai_decision_rag_live_canary_limited_rollout_result.md`, `docs/work-result/28_ai_decision_strategy_case_rag_result.md`

---

## 1. 문제 정의
- 증상:
  - OCI `.env`에는 `AI_DECISION_RAG_CANARY_ENABLED=true`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS=30`이 존재했지만, `coinpilot-bot` 컨테이너 런타임 env에는 해당 값이 보이지 않았다.
  - `agent_decisions.model_used`는 `openai:gpt-4o-mini (canary)`만 누적됐고, `canary-rag`/`canary-rag-fallback` 표본은 0건이었다.
  - `scripts/ops/ai_decision_canary_report.sh 24`의 `analyst usage breakdown (rag status)`에서도 `openai / disabled`만 출력됐다.
- 영향:
  - `28-02` live canary 실험이 실제로는 비활성 상태로 운영됐다.
  - offline replay는 통과했지만 live canary 검증이 진행되지 못했다.
- 재현 조건:
  - `deploy/cloud/oci/.env`에 RAG canary env를 입력한 상태로 bot 재빌드/재배포

## 2. 재현/증빙 명령
```bash
cd /opt/coin-pilot/deploy/cloud/oci
grep -n 'AI_DECISION_RAG_CANARY_ENABLED\|AI_DECISION_RAG_CASE_LOOKBACK_DAYS\|AI_CANARY_' .env
docker exec coinpilot-bot env | grep -E 'AI_DECISION_RAG_CANARY_ENABLED|AI_DECISION_RAG_CASE_LOOKBACK_DAYS|AI_CANARY_'
```

```bash
cd /opt/coin-pilot
scripts/ops/ai_decision_canary_report.sh 24
```

## 3. before / after 정량 근거
- before(문제 상태):
  - `.env` 기준 `AI_DECISION_RAG_CANARY_ENABLED=true` 존재
  - 컨테이너 env 기준 `AI_DECISION_RAG_CANARY_ENABLED` 미주입
  - 최근 24h `canary-rag` 표본 `0건`
  - 최근 24h `rag_status=enabled|fallback` analyst 호출 `0건`
- after:
  - 계획 단계. 아직 수정 전
- 측정 기준:
  - 기간: 최근 24시간
  - 성공 기준: post-restart 이후 `canary-rag` 또는 `canary-rag-fallback` 1건 이상

## 4. 원인 분석
- `deploy/cloud/oci/docker-compose.prod.yml`의 `bot.environment`에는 `AI_CANARY_*`는 있으나 `AI_DECISION_RAG_CANARY_ENABLED`, `AI_DECISION_RAG_CASE_LOOKBACK_DAYS` passthrough가 없다.
- 따라서 `.env` 값은 존재해도 bot 컨테이너에 전달되지 않는다.

## 5. 대응 방향
- compose env passthrough를 추가하고 bot를 재배포한다.
- post-restart 표본만 대상으로 `agent_decisions.model_used`와 `llm_usage_events.meta.rag_status`를 재검증한다.

## 6. 재발 방지
- canary/live 기능 추가 시 `.env.example` 수정뿐 아니라 `docker-compose.prod.yml` passthrough 여부를 반드시 같이 검증한다.
- result 문서의 OCI 검증 절차에 `docker exec coinpilot-bot env | grep ...`를 표준 체크로 포함한다.
