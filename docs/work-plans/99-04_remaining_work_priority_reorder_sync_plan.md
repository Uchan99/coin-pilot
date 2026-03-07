# 99-04. Remaining Work 우선순위 재정렬 동기화 계획

**작성일**: 2026-03-08  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/29_regime_transition_strategy_evaluation_and_hotfix_plan.md`, `docs/work-plans/29-01_bull_regime_rule_funnel_observability_and_review_automation_plan.md`, `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md`, `docs/work-plans/31_oci_ops_monitoring_cron_automation_and_gap_hardening_plan.md`  
**승인 정보**: 미승인 / - / 사용자 승인 대기

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - `29`를 `done`으로 마감한 뒤에도 `docs/checklists/remaining_work_master_checklist.md`의 `Priority` 숫자와 `README.md`의 우선순위 목록이 현재 실행 의도와 완전히 일치하지 않는다.
  - 완료 항목(`21-05`, `21-07`, `21-08`)이 README backlog 상단에 남아 있고, 사용자가 확정한 2주 로드맵(`29 -> 21-03 -> 21-04 -> 29-01 -> 30 -> 31 -> 28 -> 22 -> 23`)이 체크리스트 숫자 열에 직접 반영되어 있지 않다.
- 왜 즉시 대응이 필요했는지:
  - 다음 작업 선택 기준 문서가 남은 작업의 단일 소스인 만큼, 숫자 우선순위와 실제 실행 순서가 어긋나면 후속 턴에서 혼선이 생길 수 있다.

## 1. 문제 요약
- 증상:
  - 체크리스트의 `Priority` 열이 최신 실행 순서를 직접 반영하지 못한다.
  - README의 "현재 우선순위 백로그"가 완료 항목과 진행 항목을 섞어 보여준다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 코드 영향 없음
  - 리스크: 잘못된 다음 작업 선택, 문서/실행 순서 불일치
  - 데이터: 없음
  - 비용: 운영 판단/문서 확인 시간 증가
- 재현 조건:
  - 체크리스트 숫자 열이나 README 우선순위 목록만 보고 다음 작업을 고를 때

## 2. 원인 분석
- 가설:
  1) 체크리스트는 완료/진행 이력을 축적하면서 우선순위 숫자를 즉시 재배열하지 않았다.
  2) README backlog는 최근 완료 항목 제거보다 운영 요약 보존에 초점을 맞춰 갱신됐다.
- 조사 과정:
  - `docs/checklists/remaining_work_master_checklist.md`
  - `README.md`
  - `29`, `29-01`, `30`, `31`, `28`, `22`, `23` 계획 문서
- Root cause:
  - 상태 갱신은 수행됐지만, "남은 작업만 기준으로 숫자 우선순위 재정렬" 규칙이 별도로 실행되지 않았다.

## 3. 대응 전략
- 단기 핫픽스:
  - 체크리스트 `Priority` 숫자 열을 현재 남은 작업 기준으로 재배열한다.
  - README 우선순위 백로그를 남은 작업 중심으로 재작성한다.
- 근본 해결:
  - 완료 항목은 운영 상태 요약에 남기고, backlog는 "미완료 main 작업만" 나열하는 규칙으로 정리한다.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 상태 값(`todo|in_progress|blocked|done`)과 Plan/Result 링크는 바꾸지 않는다.
  - 정의/정책/범위 변경 없이 정렬/표현만 수정한다.

## 4. 구현/수정 내용
- 변경 파일:
  1) `docs/checklists/remaining_work_master_checklist.md`
  2) `README.md`
  3) `docs/work-result/99-04_remaining_work_priority_reorder_sync_result.md`
- DB 변경(있다면):
  - 없음
- 주의점:
  - `Priority` 숫자는 "현재 남은 작업 우선순위"만 반영하고, 완료 항목의 historical order와 혼동하지 않도록 업데이트 로그는 유지한다.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  1) 체크리스트 `Priority` 1번이 `21-03` 또는 사용자가 확정한 가장 우선 작업으로 표시된다.
  2) `29-01`, `30`, `31`, `28`, `22`, `23`의 상대 순서가 사용자 확정 순서와 일치한다.
  3) README backlog가 완료 항목을 제외한 현재 남은 작업만 표시한다.
- 회귀 테스트:
  - 문서 작업으로 코드/서비스 영향 없음
- 운영 체크:
  - `rg -n "21-03|21-04|29-01|30|31|28|22|23" docs/checklists/remaining_work_master_checklist.md README.md`

## 6. 롤백
- 코드 롤백:
  - 문서 커밋 revert
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 승인 후 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 불필요 예상(정의/정책 변경이 아니라 우선순위 표현 정렬)

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) main 상태 변경 시 backlog 숫자 재정렬 여부를 함께 점검
  2) README backlog는 완료 항목 제거, 운영 상태 요약은 완료 항목 유지 원칙을 유지
