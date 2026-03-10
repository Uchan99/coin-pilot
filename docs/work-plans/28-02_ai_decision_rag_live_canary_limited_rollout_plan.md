# 28-02. AI Decision RAG Live Canary 제한 주입 계획

**작성일**: 2026-03-11  
**작성자**: Codex  
**상태**: In Progress  
**관련 계획 문서**: `docs/work-plans/28_ai_decision_strategy_case_rag_plan.md`, `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`  
**승인 정보**: 2026-03-11 사용자 승인 완료 (`28 Phase 2 진행`)

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - `28` Phase 1 offline replay 2차 측정에서 `samples=10`, `decision_changed_count=0`, `avg_confidence_delta=-2.8`, parse fail `0->0`을 확인했다.
- 왜 즉시 대응이 필요했는지:
  - prompt ordering/weighting 보정으로 과보수 drift는 해소됐고, 이제 실제 canary 경로에서 제한적으로 주입해 운영성/비용/지연을 확인할 수 있는 상태가 됐다.
  - 다만 live 주입은 운영 영향이 있으므로, Analyst canary에만 좁은 범위로 적용하고 즉시 롤백 가능한 구조를 먼저 문서로 고정해야 한다.

## 1. 문제 요약
- 증상:
  - offline replay는 통과했지만, 실제 운영 canary 경로에서 RAG 주입이 latency/cost/error에 어떤 영향을 주는지 아직 모른다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: canary Analyst decision 품질/일관성
  - 리스크: canary 경로에서의 REJECT 증가, latency 증가, cost 증가
  - 데이터: `agent_decisions`, `llm_usage_events` 관측 필요
  - 비용: RAG 주입으로 입력 토큰 증가 가능
- 재현 조건:
  - `AI_CANARY_ENABLED=true` 환경에서 canary 모델로 Analyst가 호출될 때

## 2. 원인 분석
- 가설:
  - replay 기준으로는 문제가 줄었지만, live에서는 입력 다양성/운영 타이밍/실시간 market context 차이로 다시 drift나 비용 급등이 발생할 수 있다.
- 조사 과정:
  - 28-01 replay 결과에서 cost는 `0.0054 -> 0.0069`, latency p50은 `6525.5ms -> 7590.0ms`, confidence delta는 `-2.8`이었다.
  - confidence/drift는 허용 범위에 들어왔지만, live 표본에서 동일 패턴이 유지되는지는 미확정이다.
- Root cause:
  - 아직 live canary 단계의 운영 실측이 없어, replay 결과만으로 최종 적용 여부를 결정할 수 없다.

## 3. 아키텍처 선택
- 선택안:
  - **canary Analyst에만 RAG를 제한 주입하고, primary/Guardian은 건드리지 않는다.**
- 선택 이유:
  - 운영 리스크와 원인 분리를 동시에 만족시키는 가장 작은 단계다.
  - Guardian까지 같이 바꾸면 효과를 분리하기 어렵고, primary까지 건드리면 rollback 반경이 커진다.
- 검토한 대안:
  1. primary+canary 동시 적용
     - 장점: 더 빨리 표본 확보
     - 단점: rollback 반경이 크고 운영 리스크가 높다.
  2. Guardian까지 동시 적용
     - 장점: agent chain 전체 일관성 확보 가능
     - 단점: Analyst 변화 효과를 분리하기 어렵다.
  3. replay만 더 반복하고 live는 미룸
     - 장점: 운영 리스크 0
     - 단점: 실시간 운영 특성(지연/비용/실시간 입력 차이)을 영원히 확인할 수 없다.
  4. live 전면 적용
     - 장점: 빠른 검증
     - 단점: 현재 프로젝트 운영 원칙과 정면 충돌한다.
- 트레이드오프:
  - 선택안은 표본 확보 속도는 느리지만, rollback과 원인 분리가 명확하다.

## 4. 대응 전략
- 단기 핫픽스:
  - 없음. 신규 기능은 canary에만 제한 적용
- 근본 해결:
  1. canary Analyst에만 `rag_context` 생성/주입
  2. `rag_enabled`, `rag_source_summary`, latency/cost를 기존 usage/decision 로그와 함께 남김
  3. 24~72h canary 관측으로 confirm/reject/error/cost를 비교
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - primary 경로 미변경
  - Guardian 미변경
  - RAG 생성 실패/timeout 시 기존 Analyst 경로로 폴백
  - env 플래그 하나로 즉시 비활성화 가능
  - canary 비율(`AI_CANARY_PERCENT`)은 현행 유지

## 5. 구현/수정 내용
- 변경 파일(예정):
  - `src/agents/runner.py`
  - `src/agents/analyst.py`
  - 필요 시 `src/agents/state.py`
  - 필요 시 `scripts/ops/ai_decision_canary_report.sh`
  - `docs/work-result/28_ai_decision_strategy_case_rag_result.md`
  - `docs/work-result/28-02_ai_decision_rag_live_canary_limited_rollout_result.md`
- 구현 범위:
  1. canary Analyst 경로에서만 `rag_context` 생성/주입
  2. replay와 같은 `rag_source_summary` 메타를 운영 decision에도 남김
  3. 비활성 env 플래그 추가(`AI_DECISION_RAG_CANARY_ENABLED` 가칭)
  4. 결과 문서에 OCI 관측 절차와 rollback 명령 명시
- 의도적으로 제외:
  - Guardian RAG
  - primary 경로 적용
  - 외부 일반 이론 문서/이미지

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  - canary 표본에서 parse fail/timeout 급증이 없어야 한다.
- 회귀 테스트:
  - 기존 RAG unit test
  - canary/off switch fallback 테스트(가능하면 추가)
- 운영 체크:
  - `scripts/ops/ai_decision_canary_report.sh 24`
  - `scripts/ops/llm_usage_cost_report.sh 24`
  - `agent_decisions`에서 canary + rag 사용 여부 확인
- 정량 기준:
  - 초기 관측 창: 24h, 72h
  - `parse_fail_rate` 증가 `+2%p` 이내
  - `timeout_rate` 증가 `+2%p` 이내
  - `avg_confidence_delta` baseline 대비 `-5pt` 초과 하락 금지
  - `avg cost_usd` 증가 `+25%` 이내
  - `p50 latency_ms` 증가 `+25%` 이내
  - live 표본 `N>=10` 전에는 `hold`

## 7. 롤백
- 코드 롤백:
  - canary RAG 주입 커밋 revert
- 운영 롤백:
  - `AI_DECISION_RAG_CANARY_ENABLED=false`
  - bot 재배포
- 데이터/스키마 롤백:
  - 없음

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 구현 시 본 plan과 별도 result 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 없음. 실험 단계이며 공식 운영 정책 변경이 아니다.

## 9. 리스크 / 가정 / 미확정
- 리스크:
  - canary 표본이 여전히 적어 해석이 늦어질 수 있다.
  - live 입력에서는 replay에 없던 reasoning drift가 재발할 수 있다.
  - cost 증가가 confidence 개선 대비 과도할 수 있다.
- 가정:
  - 현행 canary 라우팅은 정상 동작 중이다.
  - 개인 계정 fallback 환경에서도 `llm_usage_events` 기반 cost 비교는 가능하다.
- 미확정:
  - `rag_enabled` 메타를 어디에 남길지(`reasoning`/state/log meta) 최적 위치
  - canary report에 RAG 여부 기준 breakdown을 추가할지 여부

## 10. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1. canary report에 `rag_enabled` 축을 추가
  2. live canary 통과 시 Guardian 확장 여부 별도 하위 계획 분리
  3. `29-01` funnel과 연결해 `ai_confirm/ai_reject` 변화까지 함께 비교

## 11. 변경 이력
- 2026-03-11: plan 생성. Phase 1 replay 통과 후 canary Analyst 제한 주입 범위와 정량 게이트를 정의했다.
- 2026-03-11: 사용자 승인 후 `In Progress`로 전환. `runner` canary-only RAG 주입, RAG 실패 fallback, canary report의 `rag_status` 관측을 구현 범위로 고정했다.
