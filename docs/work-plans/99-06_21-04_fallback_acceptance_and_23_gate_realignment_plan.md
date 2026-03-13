# 99-06. 21-04 Fallback Acceptance 및 23 게이트 재정렬 계획

**작성일**: 2026-03-13  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`, `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`  
**관련 결과 문서**: `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md`, `docs/work-result/22_dashboard_readability_and_live_data_reliability_result.md`
**승인 정보**: 사용자 승인 / 2026-03-14 / "그렇게 진행해줘."

---

## 0. 트리거(Why started)
- 운영/문서에서 무엇이 관측됐는지:
  - `21-04`는 내부 usage observability는 완료됐지만, provider reconciliation은 개인 계정 capability 제약으로 더 진행할 수 없는 상태다.
  - 그런데 checklist/README에서는 `21-04=blocked`가 유지되어, `23`의 선행 게이트를 계속 막는 효과를 내고 있다.
  - 반면 `23` 계획 본문은 이미 `21-04 관측성 안정화(현상 유지 모드 포함)`를 허용 기준으로 적고 있다.
- 왜 지금 정리해야 하는지:
  - 현재 상태를 그대로 두면 `21-04`가 “구현 미완료”인지 “외부 capability 제약으로 fallback 운영 확정”인지 해석이 엇갈린다.
  - `23`의 실제 blocker가 `21-03`인지, `21-04`인지도 문서상 혼선이 생긴다.

## 1. 문제 요약
- 증상:
  - `21-04` result는 fallback 운영 기준을 이미 정의했는데, backlog 상태는 여전히 `blocked`다.
  - `23` plan은 `21-04 현상 유지 모드 포함`을 허용하면서도 checklist/README에서는 `21-04 blocked`에 계속 묶여 있다.
- 영향:
  - 남은 작업 우선순위 해석이 왜곡된다.
  - `23` 착수 조건이 실제보다 더 엄격하게 읽힌다.

## 2. 목표 / 비목표
### 2.1 목표
1. `21-04`를 "fallback accepted / done"으로 정리할 수 있는지 문서 기준을 확정한다.
2. `23`의 선행 게이트에서 `21-04`는 "provider reconciliation 완료"가 아니라 "내부 observability 안정화 + fallback 운영 기준 확정"으로 재정렬한다.
3. checklist/README/관련 result 문서 간 상태 표현을 일관되게 맞춘다.

### 2.2 비목표
1. provider cost snapshot capability 자체를 해결하지 않는다.
2. `23` 구현을 바로 시작하지 않는다.
3. `21-03` monitoring-only 상태를 이번 작업에서 종료하지 않는다.

## 3. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **문서 게이트 재정의 + fallback accepted 상태 정리**

- 고려 대안:
  1) `21-04 blocked` 유지 + `23`도 계속 blocked 유지
  2) `21-04`를 done으로 정리하되 `23` plan/checklist는 수정하지 않음
  3) `21-04 fallback accepted done` + `23` 게이트 문구 재정렬 (채택 예정)

- 대안 비교:
  1) 유지:
    - 장점: 상태 변경이 단순
    - 단점: 외부 capability 제약이 product backlog를 영구 차단하는 구조가 됨
  2) 21-04만 done:
    - 장점: backlog 한 항목 정리 가능
    - 단점: `23` 게이트 문구가 남아 문서 드리프트 지속
  3) 채택안:
    - 장점: 실제 운영 의미와 backlog 게이트를 일치시킴
    - 단점: 관련 문서를 여러 곳 동시에 수정해야 함

## 4. 수정 범위 (예정)
1. `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md`
   - 상태를 `fallback accepted` 기준으로 재정의
   - provider reconciliation은 후속 capability 의존 항목으로 명확히 분리
2. `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`
   - `21-04` 선행 게이트를 "관측성 안정화(현상 유지 모드 포함)" 기준으로 더 명시적으로 정리
3. `docs/checklists/remaining_work_master_checklist.md`
   - `21-04` 상태와 `23` blocker 설명을 동기화
4. `README.md`
   - backlog 상태와 운영 요약을 동기화

## 5. 검증 기준
1. `21-04` 상태 표현이 plan/result/checklist/README에서 서로 모순되지 않아야 한다.
2. `23`의 남은 blocker가 문서상 명확해야 한다.
3. `21-04` 외부 capability 제약과 `23` product gate가 분리 표현돼야 한다.

## 6. 후속 판단 포인트
1. `21-04` 정리 후 `23`의 실질 blocker는 `21-03`인지 재판정
2. 실거래 전환 스트림(`21`, `21-09`)과 `23`의 선후 관계가 추가로 정리돼야 하는지 검토

## 7. 계획 변경 이력
- 2026-03-13: 사용자 요청에 따라 `21-04 blocked` 상태와 `23 blocked` 게이트가 과도하게 연결된 문서 드리프트를 정리하기 위한 메타 계획을 신규 생성했다.
- 2026-03-14: 사용자 요청에 따라 포트폴리오 문서용 `99-05`와 충돌을 피하기 위해 본 계획 번호를 `99-06`으로 재배정하고, 승인 상태를 `Approved`로 전환했다.
