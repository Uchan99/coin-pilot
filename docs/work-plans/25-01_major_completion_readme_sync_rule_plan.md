# 25-01. Major 완료 시 README 동기화 규칙 고정 및 README 업데이트 계획

**작성일**: 2026-03-02  
**작성자**: Codex  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/25_remaining_work_master_checklist_and_agents_workflow_update_plan.md`  
**관련 결과 문서**: `docs/work-result/25-01_major_completion_readme_sync_rule_result.md`  
**승인 정보**: 사용자 / 2026-03-03 / "진행해줘. 그리고, 이런 프로젝트 내용과 관련없는 계획사항은 99-로 고정하는거 어떨까?"  

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 대규모 구현(Major) 완료 후 README가 실제 운영 상태보다 뒤처질 수 있음.
- 왜 즉시 대응이 필요했는지:
  - 신규 참여자/운영자가 README를 첫 진입점으로 사용하므로 문서 드리프트를 줄여야 함.

## 1. 문제 요약
- 증상:
  - Major 반영 후 정책/구성/우선순위가 README에 즉시 반영되지 않을 수 있음.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 개발 기능 자체 영향 없음
  - 리스크: 운영 절차 오해, 온보딩 혼선
  - 데이터: 없음
  - 비용: 문서 불일치로 인한 확인/소통 비용 증가
- 재현 조건:
  - 대규모 기능 변경 직후 README 동기화 커밋이 누락될 때

## 2. 원인 분석
- 가설:
  1) README 동기화가 권장 사항이지 강제 규칙이 아님
  2) Plan/Result/Checklist 중심 프로세스에는 반영되지만 README gate가 약함
- 조사 과정:
  1) `AGENTS.md`, `docs/PROJECT_CHARTER.md` 문서 워크플로우 규칙 확인
  2) 기존 README 구조와 현재 체크리스트 상태 정합성 확인
- Root cause:
  - Major 완료 후 README 갱신 의무와 확인 절차가 명문화되지 않음

## 3. 대응 전략
- 단기 핫픽스:
  - `AGENTS.md`와 `docs/PROJECT_CHARTER.md`에 “Major 완료 시 README 동기화” 규칙 명시
- 근본 해결:
  - Major 작업 종료 정의에 README 동기화를 포함하고, Result 문서에서 검증 명령으로 확인
- 안전장치:
  - Result 문서에 README 동기화 확인 항목(`rg` 기반) 추가

## 4. 아키텍처/프로세스 대안 비교
- 대안 1: 현행 유지(개별 판단)
  - 장점: 절차 변경 없음
  - 단점: 드리프트 재발 가능성 높음
- 대안 2: 규칙 명문화 + 수동 검증(채택)
  - 장점: 현재 문서 기반 워크플로우와 일관성, 적용 비용 낮음
  - 단점: 수동 검증 필요
- 대안 3: CI에서 README 갱신 자동 강제
  - 장점: 누락 가능성 최소화
  - 단점: Major 판별 자동화 난이도 높고 오탐 가능

## 5. 구현/수정 내용
- 변경 파일(예정):
  1) `AGENTS.md`
  2) `docs/PROJECT_CHARTER.md` (운영 규칙 + changelog)
  3) `README.md` (현재 상태/백로그/문서 운영 규칙 최신화)
  4) `docs/work-result/25-01_major_completion_readme_sync_rule_result.md` (신규)
- DB 변경(있다면):
  - 없음
- 주의점:
  - README는 Charter를 대체하지 않도록 “Source of Truth 우선순위” 문구 유지

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) AGENTS/Charter에 Major 완료 시 README 동기화 규칙 존재
  2) README 내용이 현재 체크리스트 우선순위/운영 상태와 정합
- 회귀 테스트:
  - 문서 작업이라 코드 테스트는 없음
- 운영 체크:
  - `rg -n "Major|README|checklist" AGENTS.md docs/PROJECT_CHARTER.md README.md` 결과 확인

## 7. 롤백
- 코드 롤백:
  - 문서 커밋 revert
- 데이터/스키마 롤백:
  - 없음

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 승인 후 구현 및 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 필요(운영 규칙 변경 사항이므로 changelog 기록)

## 9. 후속 조치
1. 이후 Major 완료 시 Result 문서에 README 반영 여부를 기본 체크 항목으로 고정
2. 필요하면 차후 `docs/work-plans/25-02_...`로 CI 보조 검증(문서 링크/섹션 존재) 자동화 검토

## 10. 계획 변경 이력
- 2026-03-03: 사용자 승인 반영(`Approved`) 후 구현 착수.
- 2026-03-03: AGENTS/Charter에 Major 완료 시 README 동기화 규칙과 `99-` 번호 정책을 반영하고, README 최신화 및 결과 문서 작성까지 완료(`Verified`).
