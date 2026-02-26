# 21-04. LLM 토큰/비용 관측 대시보드 구축 계획

**작성일**: 2026-02-27  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-02_llm_model_haiku_vs_gpt4omini_comparison_plan.md`  
**관련 결과 문서**: `docs/work-result/21-02_llm_model_haiku_vs_gpt4omini_comparison_result.md`  
**승인 정보**: 승인자 / 승인 시각 / 승인 코멘트

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 모델 비교(haiku vs gpt-4o-mini)는 문서 산식으로 가능하지만, 실측 토큰/비용은 자동 집계가 없음.
  - 카나리 실험(21-03) 성공 판정을 위해 모델별 실제 비용 관측이 필요함.
- 왜 즉시 대응이 필요했는지:
  - 실거래 전환 전 비용/품질 의사결정을 “추정치”에서 “실측치”로 바꿔야 함.

## 1. 문제 요약
- 증상:
  - 현재는 `agent_decisions.model_used`만 있고, 호출별 token in/out 및 추정 비용 데이터가 구조적으로 누락됨.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 모델 운영 최적화 판단 지연
  - 리스크: 비용 급증/비효율 모델 유지 가능성
  - 데이터: provider/model별 usage 시계열 부재
  - 비용: 월간 비용 추정 오차 확대
- 재현 조건:
  - 모델 카나리 또는 전환 의사결정 시 실측 데이터 요청

## 2. 원인 분석
- 가설:
  - LLM 응답 메타데이터(usage)를 표준 저장하는 공통 계층이 없음.
- 조사 과정:
  - AI Decision 기록은 있으나 token/cost 필드가 없음을 확인.
  - 운영 대시보드는 트레이딩 지표 중심으로 비용 관측 패널이 없음.
- Root cause:
  - “수집(usage) → 저장(DB) → 집계 → 시각화(Grafana)” 파이프라인 부재.

## 3. 대응 전략
- 단기 핫픽스:
  - 없음(관측 파이프라인 구축 필요)
- 근본 해결:
  - LLM 호출 메타데이터를 이벤트 단위로 저장하고, 일/시간 단위 집계를 통해 Grafana로 노출
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - usage 누락 시에도 기능은 계속 동작(soft-fail), 비용은 `unknown`으로 분리 집계
  - 가격표 버전(적용 날짜) 필드 보관

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **DB 이벤트 로그 + 집계 뷰 + Grafana 패널** 방식

- 고려 대안:
  1) Prometheus counter만 누적(무상태)
  2) DB 이벤트 로그 중심(채택)
  3) 벤더 과금 API에서 역수집

- 대안 비교:
  1) Prometheus-only:
    - 장점: 구현 빠름
    - 단점: 호출 단위 추적/사후 분석/재집계가 어려움
  2) DB 이벤트 로그(채택):
    - 장점: 모델별/경로별 정확한 사후 분석 가능, 재집계 가능
    - 단점: 스키마 추가와 집계 쿼리 관리 필요
  3) 벤더 API 역수집:
    - 장점: 과금 명세에 근접
    - 단점: 실시간성/세분화 한계, 벤더 종속성 높음

## 5. 구현/수정 내용 (예정)
- 변경 파일(예상):
  1) `src/common/models.py` (usage 이벤트 모델 추가)
  2) `migrations/` (LLM usage 이벤트 테이블 추가)
  3) `src/agents/runner.py` (AI Decision usage 캡처/저장)
  4) `src/agents/router.py` (챗봇 경로 usage 캡처 여부 검토)
  5) `monitoring/grafana-provisioning/dashboards/` (비용 대시보드 JSON 추가)
  6) `deploy/cloud/oci/monitoring/prometheus.yml` (필요 시 exporter/metric 추가)
  7) `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md` (신규)

- 데이터 스키마(초안):
  - `llm_usage_events`
    - `created_at`, `route`(analyst/guardian/chatbot), `provider`, `model`
    - `input_tokens`, `output_tokens`, `total_tokens`
    - `estimated_cost_usd`, `price_version`
    - `request_id`(중복 방지)

- 집계 지표(초안):
  1) 모델별 시간당 호출수
  2) 모델별 시간당 input/output token
  3) 모델별 일간 추정비용(USD)
  4) route별 평균 비용/호출

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) AI Decision 발생 후 usage 이벤트가 DB에 기록됨
  2) Grafana에서 모델별 비용 시계열이 표시됨
- 회귀 테스트:
  - usage 저장 실패 시 매매 판단 흐름은 중단되지 않아야 함
  - DB write 실패 시 경고 로그만 남기고 기능 지속
- 운영 체크:
  - 24h 샘플에서 수동 계산값과 대시보드 비용 값이 허용 오차 내 일치

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
