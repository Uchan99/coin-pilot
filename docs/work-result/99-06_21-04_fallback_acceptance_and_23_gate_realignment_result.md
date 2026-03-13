# 99-06. 21-04 Fallback Acceptance 및 23 게이트 재정렬 결과

**작성일**: 2026-03-14  
**작성자**: Codex  
**관련 계획서**: `docs/work-plans/99-06_21-04_fallback_acceptance_and_23_gate_realignment_plan.md`  
**상태**: Done

---

## 0. 해결한 문제 정의
- 증상:
  - `21-04`는 내부 usage observability 구현과 fallback 운영 기준이 이미 정리됐는데도 `blocked`로 남아 있었다.
  - `23` 계획은 `21-04 관측성 안정화(현상 유지 모드 포함)`를 허용하면서도 checklist/README에서는 `21-04 blocked`가 그대로 반영돼, `23`이 계속 `21-04`에 막힌 것처럼 읽혔다.
- 영향:
  - `21-04`가 구현 미완인지 외부 capability 제약인지 구분이 흐려졌다.
  - `23`의 실질 blocker가 `21-03`인지 `21-04`인지 backlog 해석이 왜곡됐다.
- 재현 조건:
  - 체크리스트/README/23 계획서를 함께 읽을 때 `21-04 blocked`와 `21-04 현상 유지 모드 허용`이 동시에 보이는 상태
- Root cause:
  - `21-04`의 fallback accepted 운영 기준이 result에만 고정되고, checklist/README/23 게이트 문구가 후속 동기화되지 않았다.

## 1. 이번 변경 범위
- `21-04` 상태를 `blocked`에서 `done (fallback accepted)`로 재정의
- `23` 선행 게이트를 "provider reconciliation 완료"가 아니라 "내부 observability 안정화 + fallback 운영 기준 확정"으로 명시
- checklist/README/work-plan/work-result 상태 문구 동기화

## 2. Before / After 정량 증빙
| 항목 | Before | After | 변화량 |
|---|---:|---:|---:|
| `21-04` checklist 상태 | `blocked` | `done` | +1 상태 |
| `21-04` README backlog 상태 | `blocked` | `done` | +1 상태 |
| `23`의 `21-04` 게이트 해석 | reconciliation 완료처럼 읽힘 | fallback 운영 확정이면 충족 | 해석 명확화 |
| 문서 충돌 지점 수(`21-04 blocked` vs `현상 유지 모드 포함`) | 1세트 | 0세트 | -1 |

## 3. 측정 기준
- 기간:
  - 2026-03-14 문서 동기화 1회
- 표본 수:
  - 관련 문서 6종
    - `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`
    - `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md`
    - `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
    - `docs/checklists/remaining_work_master_checklist.md`
    - `README.md`
    - `docs/work-plans/99-06_21-04_fallback_acceptance_and_23_gate_realignment_plan.md`
- 성공 기준:
  1. `21-04` 상태가 문서상 일관되게 `fallback accepted done`으로 읽힐 것
  2. `23`이 `21-04`가 아니라 실질 잔여 게이트 중심으로 해석될 것
- 실패 기준:
  - plan/result/checklist/README 중 한 곳이라도 `21-04`를 구현 미완 `blocked`로 유지

## 4. 변경 내용
1. `21-04` 결과 문서에 최종 판정 섹션 추가
   - historical `blocked` 판단은 유지하되, 2026-03-14 기준으로 `fallback accepted done`으로 종료
2. `21-04` 계획 문서 상태 보정
   - 개인 계정 fallback accepted 상태를 완료 기준으로 반영
3. `23` 계획 문서 선행 게이트 보정
   - `21-04`는 "현상 유지 모드 포함"을 명시하고, provider reconciliation 미완은 `23` blocker가 아님을 분명히 함
4. checklist/README 동기화
   - `21-04=done`
   - `23=blocked`는 유지하되, 실질 blocker가 `21-03`임을 드러내는 방향으로 설명 정리

## 5. 측정 불가 사유 / 대체 지표 / 추후 계획
- 측정 불가 사유:
  - 이 작업은 코드/운영 동작 변경이 아니라 문서/상태 정의 정합화 작업이라, 런타임 성능 수치 변화는 직접 측정 대상이 아니다.
- 대체 지표:
  - 상태값 변화(`blocked -> done`)와 게이트 문구 충돌 해소 여부를 검증 지표로 사용했다.
- 추후 계획:
  1. `21-03` 표본이 닫히면 `23` blocked 해제 가능 여부를 재판정한다.
  2. 실거래 전환(`21`, `21-09`)이 메인 backlog에 올라와야 하는지도 별도 정리한다.

## 6. 증빙 명령
```bash
rg -n "21-04|fallback|done|blocked|23" \
  docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md \
  docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md \
  docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md \
  docs/checklists/remaining_work_master_checklist.md \
  README.md \
  docs/work-plans/99-06_21-04_fallback_acceptance_and_23_gate_realignment_plan.md
```

## 7. README / 체크리스트 동기화
- `README.md`:
  - `21-04` 운영 상태를 `done (fallback accepted)`로 동기화했다.
- `remaining_work_master_checklist.md`:
  - `21-04`를 `done`으로, `99-06`을 `done`으로 동기화했다.

## 8. 최종 상태 요약
- `21-04`:
  - 구현 완료 + fallback 운영 기준 확정 + provider reconciliation은 외부 capability 의존 항목으로 분리
  - 최종 상태 `done`
- `23`:
  - `21-04`는 더 이상 blocker가 아님
  - 현재 blocked 해석의 핵심은 `21-03` monitoring-only 미종료 쪽이다
