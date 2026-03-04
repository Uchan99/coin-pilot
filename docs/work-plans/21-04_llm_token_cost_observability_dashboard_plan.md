# 21-04. LLM 토큰/비용 관측 대시보드 구축 계획

**작성일**: 2026-02-27  
**작성자**: Codex  
**상태**: In Progress  
**관련 계획 문서**: `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-02_llm_model_haiku_vs_gpt4omini_comparison_plan.md`  
**관련 결과 문서**: `docs/work-result/21-02_llm_model_haiku_vs_gpt4omini_comparison_result.md`, `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md`  
**승인 정보**: 사용자 승인 / 2026-03-04 / "12-04 계획 변경 커밋 푸시 완료했고, 이제 다음 구현 진행해주면 돼"

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 모델 비교(haiku vs gpt-4o-mini)는 문서 산식으로 가능하지만, 실측 토큰/비용은 자동 집계가 없음.
  - 카나리 실험(21-03) 성공 판정을 위해 모델별 실제 비용 관측이 필요함.
  - 사용자 피드백: 잔여 크레딧만 시간 단위로 조회하면 AI Decision 외 다른 기능(챗봇/리포트/임베딩) 비용이 섞여 원인 분리가 불가능함.
- 왜 즉시 대응이 필요했는지:
  - 실거래 전환 전 비용/품질 의사결정을 “추정치”에서 “실측치”로 바꿔야 함.

## 1. 문제 요약
- 증상:
  - 현재는 `agent_decisions.model_used`만 있고, 호출별 token in/out 및 추정 비용 데이터가 구조적으로 누락됨.
  - 계정 잔여 크레딧 감소량만으로는 어떤 경로가 비용을 소모했는지 분리 불가함.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 모델 운영 최적화 판단 지연
  - 리스크: 비용 급증 원인 미확인, AI Decision 비용 오판 가능성
  - 데이터: provider/model별 usage 시계열 부재
  - 비용: 월간 비용 추정 오차 확대
- 재현 조건:
  - 모델 카나리 또는 전환 의사결정 시 “AI Decision 전용 비용” 요청

## 2. 원인 분석
- 가설:
  - LLM 응답 메타데이터(usage)를 표준 저장하는 공통 계층이 없음.
- 조사 과정:
  - AI Decision 기록은 있으나 token/cost 필드가 없음을 확인.
  - 운영 대시보드는 트레이딩 지표 중심으로 비용 관측 패널이 없음.
  - 잔여 크레딧 조회 중심 설계는 route별 책임 분리에 부적합함을 확인.
- Root cause:
  - “호출 단위 usage 수집(원장) → DB 저장 → route/model 집계 → 시각화(Grafana)” 파이프라인 부재.

## 3. 대응 전략
- 단기 핫픽스:
  - 없음(관측 파이프라인 구축 필요)
- 근본 해결:
  - 1차 기준: LLM 호출 메타데이터를 이벤트 단위로 저장(event ledger)
  - 2차 기준: 계정 잔여 크레딧 스냅샷을 보조 수집하여 ledger 합계와 대조(reconciliation)
  - 일/시간 단위 집계를 통해 Grafana로 노출
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - usage 누락 시에도 기능은 계속 동작(soft-fail), 비용은 `unknown`으로 분리 집계
  - 가격표 버전(적용 날짜) 필드 보관
  - route 분류 불가 이벤트는 `route=unknown`으로 별도 집계

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **호출 단위 DB 원장(event ledger) + 계정 크레딧 스냅샷 대조 + Grafana 패널** 방식

- 고려 대안:
  1) 잔여 크레딧만 주기 조회(계정 단위)
  2) Prometheus counter만 누적(무상태)
  3) DB 이벤트 로그 + 크레딧 스냅샷 대조(채택)
  4) 벤더 과금 API에서 역수집

- 대안 비교:
  1) 잔여 크레딧만 조회:
    - 장점: 구현 단순
    - 단점: AI Decision/챗봇/리포트/임베딩 비용 분리가 불가능해 원인 분석 불가
  2) Prometheus-only:
    - 장점: 구현 빠름
    - 단점: 호출 단위 추적/사후 분석/재집계가 어려움
  3) DB 이벤트 로그 + 스냅샷 대조(채택):
    - 장점: 모델/경로별 정확한 비용 분리 + 계정 단위 이상징후(외부 호출/누락) 탐지 가능
    - 단점: 스키마 추가, 가격표/대조 로직 관리 필요
  4) 벤더 API 역수집:
    - 장점: 과금 명세에 근접
    - 단점: 실시간성/세분화 한계, 벤더 종속성 높음

## 5. 구현/수정 내용 (예정)
- 변경 파일(예상):
  1) `src/common/models.py` (usage 이벤트 + 크레딧 스냅샷 모델 추가)
  2) `migrations/` (신규 테이블/인덱스 추가)
  3) `src/common/llm_usage.py` (공통 usage 기록 유틸 신규)
  4) `src/agents/runner.py` (AI Decision usage 캡처/저장)
  5) `src/agents/router.py` (챗봇 usage 캡처)
  6) `src/agents/daily_reporter.py` (리포트 경로 usage 캡처)
  7) 임베딩 호출 경로 모듈(존재 시) usage 캡처
  8) `monitoring/grafana-provisioning/dashboards/` (비용 대시보드 JSON 추가)
  9) `scripts/ops/` (수동 reconciliation 리포트 스크립트 추가)
  10) `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md` (신규)

- 데이터 스키마(초안):
  - `llm_usage_events`
    - `created_at`, `route`, `feature`, `provider`, `model`
    - `input_tokens`, `output_tokens`, `total_tokens`
    - `estimated_cost_usd`, `price_version`
    - `request_id`(중복 방지), `status`(success/error), `error_type`(nullable)
  - `llm_credit_snapshots`
    - `created_at`, `provider`, `balance_usd`, `balance_unit`, `source`
    - `note`(nullable)

- route/feature 분류(초안):
  1) `ai_decision_analyst`
  2) `ai_decision_guardian`
  3) `chatbot`
  4) `daily_report`
  5) `embedding`
  6) `unknown` (분류 누락/예외)

- 집계 지표(초안):
  1) 모델별/route별 시간당 호출수
  2) 모델별/route별 시간당 input/output token
  3) 모델별/route별 일간 추정비용(USD)
  4) route별 평균 비용/호출, 오류율
  5) `ledger_sum` vs `credit_delta` 차이(대조 오차율)

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) AI Decision/챗봇/리포트/임베딩 호출 후 route별 usage 이벤트가 DB에 기록됨
  2) Grafana에서 모델/route 비용 시계열이 표시됨
  3) `ledger_sum`과 `credit_delta`가 허용 오차 내(예: ±10%)로 수렴
- 회귀 테스트:
  - usage 저장 실패 시 매매 판단 흐름은 중단되지 않아야 함
  - DB write 실패 시 경고 로그만 남기고 기능 지속
- 운영 체크:
  - 24h 샘플에서 수동 SQL 계산값과 대시보드 비용 값이 허용 오차 내 일치
  - AI Decision 전용 비용과 전체 비용이 분리 표기되는지 확인

## 7. 롤백
- 코드 롤백:
  - usage 기록 코드/대시보드 revert
- 데이터/스키마 롤백:
  - usage 테이블은 보존(읽기 미사용 상태로 비활성) 또는 별도 다운 마이그레이션 적용
- 운영 롤백:
  - usage 수집 플래그 비활성화(`LLM_USAGE_ENABLED=false`, 도입 시)

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 구현 결과서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 KPI(비용 지표)를 공식 지표로 채택할 경우 Charter changelog 반영

## 9. 후속 조치
1) 21-03 카나리와 결합한 모델 자동 승급/강등 정책 검토  
2) 월간 비용 리포트 자동 전송(n8n)  
3) 비용 이상치 감지 알람(rule) 추가

## 10. 계획 변경 이력
- 2026-03-04: 사용자 피드백 반영. “잔여 크레딧 중심”이 아닌 “호출 단위 원장 + 계정 크레딧 대조” 구조로 설계를 구체화하고, AI Decision 외 챗봇/리포트/임베딩 route 분리 관측 범위를 명시.
- 2026-03-04: 사용자 승인 후 구현 착수. `llm_usage_events/llm_credit_snapshots` 스키마, 공통 usage 캡처 유틸, route별 계측(AI Decision/Chatbot/Daily Report/RAG embedding 추정), 운영 집계 스크립트 범위를 Phase 1로 확정.
- 2026-03-04: 운영 확인 절차 자동화 요구 반영. 경로별 강제 호출(chat/rag/sql/premium-review + ai_decision analyst/guardian)과 usage/canary 리포트 연속 출력을 수행하는 smoke 스크립트를 Phase 1 범위에 추가.
- 2026-03-04: OCI 실행 중 smoke 스크립트 초기 구동 실패(`python -c` 따옴표 충돌, `SyntaxError`) 이슈를 반영해, 계측 플래그 출력 구문을 f-string에서 안전한 문자열 결합 형태로 보정하는 hotfix를 Phase 1 범위에 추가.
- 2026-03-04: OCI 운영 반영에서 `CHAT_PREMIUM_REVIEW_TIMEOUT_SEC` env projection 누락을 확인해 compose 보정 항목을 계획 가드레일로 추가. 관련 트러블슈팅 문서 `docs/troubleshooting/21-06_ai_canary_env_injection_and_observability_gap.md` 연결.
- 2026-03-04: Phase 1 운영 검증은 통과했으나 `llm_credit_snapshots` 자동 수집 부재로 reconciliation 정밀 검증은 Phase 2로 이월.
