# 21-06. AI 카나리 env 주입 누락 및 관측 공백 트러블슈팅 / 핫픽스

작성일: 2026-03-04
상태: Verified
우선순위: P1
관련 문서:
- Plan: `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`
- Result: `docs/work-result/21-03_ai_decision_model_canary_experiment_result.md`, `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md`
- Charter update 필요: NO

---

## 1. 트리거(왜 시작했나)
- 모니터링/로그/사용자 리포트로 관측된 내용:
  - OCI `bot` 컨테이너 내부에서 `AI_CANARY_*`, `AI_DECISION_PRIMARY_*`, `LLM_PROVIDER`가 비어 있음.
  - `scripts/ops/llm_usage_smoke_and_compare.sh` 실행 시 시작 단계 `SyntaxError`로 중단.
  - 카나리 리포트에서 OpenAI canary 모델이 집계되지 않음.
- 긴급도/영향:
  - 카나리 실험(21-03) 해석 불가.
  - LLM usage 관측(21-04) 운영 검증 절차 중단.

---

## 2. 증상/영향
- 증상:
  - `docker compose ... exec -T bot sh -lc 'echo AI_CANARY_PERCENT=$AI_CANARY_PERCENT'` 결과가 빈 문자열.
  - smoke 스크립트 시작부에서 `python -c` 문자열 파싱 실패.
  - `agent_decisions` 신규 행이 없어 canary 분포 판정 불가.
- 영향(리스크/데이터/비용/운영):
  - 리스크: 카나리 비율/모델 전환 검증 실패.
  - 데이터: `model_used` 비교 표본 부족.
  - 운영: 수동 점검 명령 반복, 해석 시간 증가.
- 발생 조건/재현 조건:
  - `deploy/cloud/oci/docker-compose.prod.yml`에 필요한 env projection 누락된 상태에서 재기동.
  - smoke 스크립트 시작부 Python one-liner에 이중 따옴표 충돌 존재.
- 기존 상태(Before) 기준선:
  - canary 핵심 env 7개 기준, 컨테이너 내부 유효 값 0/7.
  - smoke 스크립트 성공률 0/1.

---

## 3. 재현/관측 정보
- 재현 절차:
  1) `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'echo AI_CANARY_PERCENT=$AI_CANARY_PERCENT'`
  2) `scripts/ops/llm_usage_smoke_and_compare.sh 1`
  3) `scripts/ops/ai_decision_canary_report.sh 24`
- 입력/데이터:
  - OCI `.env`에 `AI_CANARY_*` 및 `OPENAI_API_KEY` 설정 상태.
- 핵심 로그/에러 메시지:
  - `SyntaxError: invalid syntax. Perhaps you forgot a comma?`
  - `LLM_PROVIDER=` / `AI_CANARY_PERCENT=` (빈 값)
- 관련 지표/대시보드(있다면):
  - `scripts/ops/ai_decision_canary_report.sh 24`
  - `scripts/ops/llm_usage_cost_report.sh 1`

---

## 4. 원인 분석
- 가설 목록:
  1) OCI `.env` 자체가 잘못됨
  2) compose 파일의 `bot.environment`에 변수 projection 누락
  3) smoke 스크립트 문자열 quoting 버그
- 조사 과정(무엇을 확인했는지):
  - OCI `.env`에서 변수 키/값 존재 확인.
  - `bot` 컨테이너 내부 env 출력으로 projection 누락 확인.
  - `deploy/cloud/oci/docker-compose.prod.yml`에 누락 변수 추가 후 재기동하여 반영 확인.
  - smoke 스크립트 Python one-liner를 따옴표 충돌 없는 형태로 수정 후 재실행.
- Root cause(결론):
  - 원인 1: compose env projection 누락으로 컨테이너가 카나리/타임아웃 설정을 읽지 못함.
  - 원인 2: smoke 스크립트 시작부 quoting 버그로 운영 검증 스크립트가 즉시 중단됨.
  - 참고: canary 모델 미집계의 직접 원인은 코드 오류가 아니라 관측 구간 신규 `agent_decisions` 표본 부족.

---

## 5. 해결 전략
- 단기 핫픽스:
  - compose env projection 추가 후 `bot` 강제 recreate.
  - smoke 스크립트 quoting 수정.
- 근본 해결:
  - 운영 체크리스트에 "컨테이너 내부 env 투영 확인" 단계 고정.
  - canary 판정 전 최소 표본 기준(모델별 N) 충족 확인.
- 안전장치(feature flag, rate limit, timeout/cooldown, circuit breaker 등):
  - `AI_CANARY_ENABLED` kill switch 유지.
  - `AI_CANARY_PERCENT` 상한 20 유지.
  - `CHAT_PREMIUM_REVIEW_TIMEOUT_SEC` 명시 projection 추가.

---

## 6. 수정 내용
- 변경 요약:
  - OCI compose `bot.environment`에 누락 env 반영.
  - smoke 스크립트 시작부 Python quoting 핫픽스 반영.
  - 운영/결과 문서에 관측 공백 원인과 후속 수집 조건 명시.
- 변경 파일:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `scripts/ops/llm_usage_smoke_and_compare.sh`
  - `docs/work-result/21-03_ai_decision_model_canary_experiment_result.md`
  - `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md`
  - `docs/checklists/remaining_work_master_checklist.md`
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  - compose/env 변경 revert 후 `docker compose ... up -d --force-recreate --no-deps bot`

---

## 7. 검증
- 실행 명령/절차:
  - `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'echo AI_CANARY_PERCENT=$AI_CANARY_PERCENT; echo CHAT_PREMIUM_REVIEW_TIMEOUT_SEC=$CHAT_PREMIUM_REVIEW_TIMEOUT_SEC'`
  - `scripts/ops/llm_usage_smoke_and_compare.sh 1`
  - `scripts/ops/ai_decision_canary_report.sh 24`
- 결과:
  - 통과(핵심 env projection 정상, smoke 완료, usage route 집계 출력 확인).
  - 단, canary 분포는 신규 의사결정 표본 부족으로 계속 관찰 필요.

- 운영 확인 체크:
  1) 모델별 최소 표본 충족 전에는 카나리 승격/판정 보류.
  2) `llm_provider_cost_snapshots` 수집 전까지 reconciliation은 참고치로만 사용.

### 7.1 정량 개선 증빙(필수)
- 측정 기간/표본:
  - 2026-03-04 OCI 운영 검증 세션, 수동 점검 1회.
- 측정 기준(성공/실패 정의):
  - 성공: 핵심 env 값이 컨테이너 내부에 투영되고 smoke 스크립트가 끝까지 완료됨.
- 데이터 출처(SQL/로그/대시보드/스크립트):
  - `docker compose exec -T bot ... echo`
  - `scripts/ops/llm_usage_smoke_and_compare.sh`
  - `scripts/ops/ai_decision_canary_report.sh`
- 재현 명령:
  - `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'echo LLM_PROVIDER=$LLM_PROVIDER; echo AI_CANARY_PERCENT=$AI_CANARY_PERCENT; echo CHAT_PREMIUM_REVIEW_TIMEOUT_SEC=$CHAT_PREMIUM_REVIEW_TIMEOUT_SEC'`
  - `scripts/ops/llm_usage_smoke_and_compare.sh 1`

- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| bot 내부 canary 핵심 env 유효 개수(7개 기준) | 0 | 7 | +7 | +100.0 |
| bot 내부 `CHAT_PREMIUM_REVIEW_TIMEOUT_SEC` 유효 여부 | 0 | 1 | +1 | +100.0 |
| smoke 스크립트 완료 여부(성공=1, 실패=0) | 0 | 1 | +1 | +100.0 |
| post-restart `agent_decisions` 신규 건수 | 0 | 0 | 0 | 0.0 |

- 정량 측정 불가 시(예외):
  - 불가 사유: post-restart 구간에서 신규 AI decision 신호 자체가 아직 부족.
  - 대체 지표: `decision_lag`, 최근 6h/24h 총 건수 모니터링.
  - 추후 측정 계획/기한: 최소 24~48h 관찰 후 모델별 N>=20 확보 시 재판정.

---

## 8. 재발 방지
- 가드레일(테스트/알림/검증 스크립트/권한/필터/타임아웃 등):
  - 배포 직후 필수 점검 명령 고정:
    - env projection 확인
    - usage smoke 1회 실행
    - canary report 확인
  - OCI 환경에서 `rg` 미설치 가정하고 `grep -E` 대체 명령을 runbook에 유지.
- 문서 반영:
  - plan/result 업데이트 여부: YES
  - troubleshooting 링크 추가 여부: YES
  - PROJECT_CHARTER.md 변경(있다면): 없음

---

## 9. References
- `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`
- `docs/work-result/21-03_ai_decision_model_canary_experiment_result.md`
- `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`
- `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md`
- `scripts/ops/ai_decision_canary_report.sh`
- `scripts/ops/llm_usage_smoke_and_compare.sh`

## 10. 배운점
- 트러블 슈팅 경험을 통해 깨달은 점이나 배운점:
  - `.env` 값 존재와 컨테이너 env 주입은 별개 검증이 필요하다.
  - 운영 스크립트는 one-liner quoting 오류가 실제 운영 가시성을 즉시 끊을 수 있다.
- 포트폴리오용으로 트러블 슈팅을 작성할때, 어떤 점을 강조해야하는지, 활용하면 좋을 내용:
  - "재현 조건-원인-정량 Before/After-가드레일" 4단 구조를 명시하면 재현성과 설계 역량을 동시에 보여줄 수 있다.
- 트러블 슈팅을 통해 어떤 능력이 향상되었는지:
  - 배포 후 검증 자동화 관점(환경 주입/계측/리포트)을 빠르게 체계화하는 능력이 향상되었다.
