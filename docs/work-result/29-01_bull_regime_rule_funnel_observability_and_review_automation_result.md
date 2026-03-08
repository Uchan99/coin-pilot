# 29-01. BULL 레짐 Rule Funnel 관측성 강화 + 주기 점검 자동화 결과

**작성일**: 2026-03-08  
**작성자**: Codex  
**상태**: In Progress (Phase 1 로컬 구현/검증 완료)  
**관련 계획서**: `docs/work-plans/29-01_bull_regime_rule_funnel_observability_and_review_automation_plan.md`

---

## 0. 해결한 문제 정의
- 증상:
  - 운영에서 "BULL 레짐인데 AI decision이 적다"는 관측이 있었지만, 기존 DB에는 `agent_decisions`만 있어 Rule pass 이후 어느 단계에서 병목이 생기는지 분해할 수 없었다.
- 영향:
  - BULL 진입 부족의 원인을 Rule/Risk/AI 중 어디서 찾을지 불명확했고, 29번 전략 판단 이후 후속 핫픽스/튜닝 근거가 약했다.
- 재현 조건:
  - 레짐 노출은 BULL 우세인데 실제 AI decision 건수는 SIDEWAYS 중심으로 보이는 구간
- Root cause:
  - 레짐별 Rule funnel 이벤트 스키마, 런타임 계측 훅, 주간 리포트 통합 경로가 부재했다.

## 1. 이번 Phase 범위
- 신규 퍼널 이벤트 스키마 추가:
  - `rule_funnel_events`
- 런타임 계측 추가:
  - `rule_pass`
  - `risk_reject`
  - `ai_prefilter_reject`
  - `ai_guardrail_block`
  - `ai_confirm`
  - `ai_reject`
- 운영 리포트 추가:
  - `scripts/ops/rule_funnel_regime_report.sh <hours>`
- 기존 Weekly Exit Report 증분 확장:
  - payload에 `rule_funnel`, `rule_funnel_suggestions` 추가
- 자동 수정:
  - 미구현, 금지 정책 유지

## 2. 구현 내용
1. DB/모델
   - `src/common/models.py`에 `RuleFunnelEvent` 추가
   - `migrations/v3_3_4_rule_funnel_events.sql` 추가
   - `deploy/db/init.sql`에 baseline 생성 SQL 반영
2. 런타임 계측
   - `src/bot/main.py`:
     - Entry signal 시 `rule_pass`
     - 주문 금액 0 또는 리스크 검증 실패 시 `risk_reject`
     - AI prefilter 차단 시 `ai_prefilter_reject`
     - AI guardrail 차단 시 `ai_guardrail_block`
   - `src/agents/runner.py`:
     - 최종 AI decision 시 `ai_confirm` / `ai_reject`
3. 공용 계층
   - `src/common/rule_funnel.py`:
     - reason 문자열을 집계 가능한 `reason_code`로 정규화
     - 관측 실패가 주문 흐름을 멈추지 않도록 soft-fail 처리
   - `src/analytics/rule_funnel.py`:
     - 기간별 레짐/단계 집계
     - BULL 기준 자동 제안 생성(자동 수정 아님)
4. 운영 리포트
   - `scripts/ops/rule_funnel_regime_report.sh`
   - `src/analytics/exit_performance.py`에서 주간 payload에 funnel 요약/제안 증분 통합
5. 운영 문서
   - `docs/runbooks/18_data_migration_runbook.md`에 신규 migration 적용 순서 반영

## 3. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| 레짐별 퍼널 DB stage 수 | 0 | 6 | +6 |
| 주간 리포트 내 퍼널 필드 수 | 0 | 2 (`rule_funnel`, `rule_funnel_suggestions`) | +2 |
| 신규 운영 리포트 스크립트 수 | 0 | 1 | +1 |
| 신규/확장 로컬 검증 테스트 | 0 | 6 passed | +6 |

## 4. 측정 기준
- 기간:
  - 로컬 구현 검증 시점 2026-03-08 단일 실행
- 표본 수:
  - 테스트 6건
    - `tests/analytics/test_rule_funnel.py`
    - `tests/analytics/test_exit_performance_phase3.py`
    - `tests/analytics/test_exit_performance_phase4.py`
- 성공 기준:
  - 신규 모듈 문법 오류 없음
  - 퍼널 제안/주간 payload 테스트 통과
  - 운영 스크립트 쉘 구문 오류 없음
- 실패 기준:
  - 기존 AI decision 흐름 import/compile 실패
  - 주간 payload 확장으로 테스트 회귀 발생

## 5. 증빙 근거 (명령)
```bash
python3 -m py_compile src/common/models.py src/common/rule_funnel.py src/analytics/rule_funnel.py src/analytics/exit_performance.py src/agents/runner.py src/bot/main.py
PYTHONPATH=. .venv/bin/pytest -q tests/analytics/test_rule_funnel.py tests/analytics/test_exit_performance_phase3.py tests/analytics/test_exit_performance_phase4.py
bash -n scripts/ops/rule_funnel_regime_report.sh
```

추가 확인:
```bash
timeout 20s env PYTHONPATH=. .venv/bin/pytest -q tests/test_agents.py -vv -s
```
- 결과:
  - `test_agent_runner_confirm_scenario`, `test_agent_runner_low_confidence_rejection` 통과 확인
  - `test_agent_runner_timeout_fallback`은 기존 40초 timeout 대기 특성 때문에 20초 제한에서 중단

## 6. 측정 불가 사유 / 대체 지표 / 추후 계획
- 측정 불가 사유:
  - OCI 운영 DB에는 아직 `v3_3_4_rule_funnel_events.sql`을 적용하지 않았으므로 실제 레짐별 이벤트 누적 수치는 아직 없다.
- 대체 지표:
  - 로컬 코드/테스트/스크립트 검증으로 스키마/계측 경로/리포트 확장 성공 여부를 우선 확인했다.
- 추후 측정 계획:
  1. OCI에 migration 적용
  2. `scripts/ops/rule_funnel_regime_report.sh 72` 실행
  3. 최근 72시간 BULL/SIDEWAYS 레짐별 `rule_pass -> ai_confirm` 전환율 비교
  4. 주간 webhook payload에 funnel 섹션이 포함되는지 실제 운영 로그로 확인

## 7. 리스크 / 가정 / 미확정 사항
- 리스크:
  - 퍼널 이벤트가 현재는 "이벤트 로그"이므로, 장시간 운영 전에는 write volume 증가량을 실제 OCI에서 확인해야 한다.
- 가정:
  - n8n/Discord weekly webhook은 payload의 신규 필드를 무시하지 않고 그대로 전달 가능하다고 가정했다.
- 미확정:
  - `31` 작업에서 cron/systemd 보조 점검을 어떤 경로로 얹을지는 아직 미확정이다.

## 8. README / 체크리스트 동기화
- `README.md`:
  - 미반영
  - 사유: `29-01`은 아직 `done`이 아니고 Phase 1 구현만 완료되어 README 동기화 조건(major completed)에 해당하지 않음
- `remaining_work_master_checklist.md`:
  - `29-01` 상태를 `in_progress`로 반영
  - 본 결과 문서 링크를 추가할 예정
