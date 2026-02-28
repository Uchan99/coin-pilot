# 25. 남은 작업 마스터 체크리스트 도입 및 AGENTS 워크플로우 업데이트 계획

**작성일**: 2026-03-01  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`, `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`, `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md`, `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`, `docs/work-plans/24_discord_mobile_chatbot_query_plan.md`  
**승인 정보**: 사용자 / 2026-03-01 / "단일 파일이 좋을 것 같아. 진행해줘"

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 우선순위 작업(21-05, 24, 21-03, 21-04, 22, 23)이 문서로 분산되어 있어 진행 현황을 한 화면에서 추적하기 어려움.
  - 계획 문서/결과 문서가 업데이트되어도 "남은 작업" 집계 문서가 자동 동기화되지 않음.
- 왜 즉시 대응이 필요했는지:
  - 구현 순서가 명확한 현재 시점에 단일 체크리스트를 도입하면 누락/중복 작업을 줄이고, 작업 인수인계 품질을 높일 수 있음.

## 1. 문제 요약
- 증상:
  - 우선순위/상태/완료조건/검증명령이 문서별로 흩어져 있어 주기적인 수동 확인 필요.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 진행 관리 효율 저하
  - 리스크: main 계획 업데이트 시 체크리스트 누락 가능
  - 비용: 문서 추적 시간 증가
- 재현 조건:
  - main 계획 문서가 추가/상태 변경될 때마다 수동 반영 필요

## 2. 원인 분석
- 가설:
  - 문서 체계는 존재하나 "마스터 체크리스트 갱신 규칙"이 명시되지 않음.
- 조사 과정:
  - `AGENTS.md` 확인: Plan/Result/Troubleshooting 규칙은 있으나 체크리스트 동기화 규칙 없음.
  - `docs/` 확인: `docs/checklists/` 디렉터리 부재.
- Root cause:
  - 운영 문서 집계 레이어(remaining work checklist)와 업데이트 의무 규정이 부재.

## 3. 대응 전략
- 단기 핫픽스:
  - `docs/checklists/remaining_work_master_checklist.md` 신규 생성.
- 근본 해결:
  - `AGENTS.md`에 "main 계획 생성/완료 시 체크리스트 동기화" 의무를 추가.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 체크리스트 항목에 `업데이트 트리거` 및 `최종 수정일` 필드 포함.

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - 문서 기반 단일 체크리스트(`docs/checklists/remaining_work_master_checklist.md`) + AGENTS 규칙 강제

- 고려 대안:
  1) 체크리스트 없이 기존 plan/result만 유지
  2) 문서 체크리스트 + AGENTS 규칙 추가 (채택)
  3) 스크립트/DB 기반 자동 트래커 구현

- 대안 비교:
  1) 기존 유지:
    - 장점: 변경 최소
    - 단점: 추적 누락 지속
  2) 문서 체크리스트(채택):
    - 장점: 즉시 적용 가능, 현재 워크플로우와 충돌 없음
    - 단점: 수동 갱신 필요
  3) 자동 트래커:
    - 장점: 자동화 강함
    - 단점: 구현 비용/유지비 증가, 현재 단계 과투자

## 5. 구현/수정 내용 (예정)
- 변경 파일:
  1) `docs/checklists/remaining_work_master_checklist.md` (신규)
  2) `AGENTS.md` (체크리스트 동기화 규칙 추가)
  3) `docs/work-result/25_remaining_work_master_checklist_and_agents_workflow_update_result.md` (신규)
  4) 필요 시 `docs/PROJECT_CHARTER.md` (운영 규칙 변경 시 changelog 반영)

- 체크리스트 구성(예정):
  1) 우선순위 번호
  2) plan 번호/제목/링크
  3) 상태(`todo/in_progress/blocked/done`)
  4) 시작 조건/완료 조건
  5) 검증 명령
  6) 관련 result/troubleshooting 링크
  7) 업데이트 트리거(main 계획 생성/구현 완료/상태 변경)

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) 남은 작업 6개(21-05, 24, 21-03, 21-04, 22, 23)가 체크리스트에 반영됨
  2) AGENTS에 체크리스트 동기화 규칙이 명시됨
- 회귀 테스트:
  - 기존 AGENTS 문서의 Plan→Approval→Implement→Result 규칙이 유지됨
- 운영 체크:
  - 이후 main 계획 상태 변경 시 체크리스트 갱신 규칙을 따라 1회 수동 업데이트 수행

## 7. 롤백
- 코드 롤백:
  - 체크리스트 문서/AGENTS 변경 revert
- 데이터/스키마 롤백:
  - 없음

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - AGENTS 운영 규칙 성격의 변경이므로 Charter Changelog 반영 여부는 구현 시점에 최종 판단

## 9. 후속 조치
1) `24` 구현 착수 시 체크리스트 상태를 `in_progress`로 변경
2) 각 main 계획의 result 작성 완료 시 체크리스트 상태를 `done`으로 갱신
3) 월 1회 체크리스트 구조/필드 유효성 점검

## 10. 계획 변경 이력
- 2026-03-01: 사용자 승인에 따라 체크리스트 운영 방식을 \"폴더 분할\" 대신 \"단일 마스터 파일\"로 확정.
