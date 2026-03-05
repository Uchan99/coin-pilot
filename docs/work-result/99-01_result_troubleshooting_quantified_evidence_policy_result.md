# 99-01. Result/Troubleshooting 문제 정의·정량 개선 증빙 의무화 정책 반영 결과

작성일: 2026-03-04
작성자: Codex
관련 계획서: `docs/work-plans/99-01_result_troubleshooting_quantified_evidence_policy_plan.md`
상태: Verified
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - 문서 품질 게이트를 AGENTS/Charter/README/템플릿/체크리스트에 동시 반영
- 목표(요약):
  - 결과/트러블슈팅 문서에 "문제 정의 + before/after 수치 + 측정 근거"를 의무화
- 이번 구현이 해결한 문제(한 줄):
  - 문서마다 문제 정의와 개선 수치 증빙 수준이 달라 재현 가능한 품질 기준이 없던 문제를 해결했다.
- 해결한 문제의 구체 정의(필수: 증상/영향/재현 조건):
  - 증상: Result/Troubleshooting 템플릿에 정량 증빙 필수 섹션이 없어 작성자 재량으로 누락 가능
  - 영향: 회고/검증 시 개선 효과를 수치로 비교하기 어려움
  - 재현 조건: 템플릿 기반 작성 시 before/after 표가 필수 아님
- 기존 방식/상태(Before) 기준선 요약(필수):
  - AGENTS/Charter에 정량 증빙 "권고 해석 가능" 상태
  - 템플릿 내 정량 비교 표 섹션 0개

---

## 2. 구현 내용(핵심 위주)
### 2.1 운영 규칙 강제화
- 파일/모듈:
  - `AGENTS.md`
  - `docs/PROJECT_CHARTER.md`
  - `README.md`
- 변경 내용:
  - Result/Troubleshooting 필수 항목으로 문제 정의, before/after, 변화량, 측정 기준, 증빙 명령 명시
  - 정량 불가 시 예외 기재 규칙(사유/대체 지표/추후 계획) 추가
  - Charter 변경 이력에 정책 반영 로그 추가
- 효과/의미:
  - 문서 리뷰 시 "수치 없는 완료"를 기준 위반으로 명확히 판정 가능

### 2.2 템플릿 강제 항목 추가
- 파일/모듈:
  - `docs/templates/work-result.template.md`
  - `docs/templates/troubleshooting.template.md`
- 변경 내용:
  - `정량 개선 증빙(필수)` 섹션 추가
  - `Before/After 비교표`, 측정 기간/표본, 측정 기준, 데이터 출처, 재현 명령, 예외 처리 항목 추가
- 효과/의미:
  - 신규 문서 작성 단계에서 정량 증빙 누락 가능성을 구조적으로 차단

### 2.3 추적 문서 동기화
- 파일/모듈:
  - `docs/checklists/remaining_work_master_checklist.md`
  - `docs/work-plans/99-01_result_troubleshooting_quantified_evidence_policy_plan.md`
- 변경 내용:
  - 99-01 상태를 `done`으로 마감
  - 승인/구현/완료 이력을 체크리스트와 계획서에 반영
- 효과/의미:
  - 문서 정책 변경 작업도 일반 기능 구현과 동일한 추적성을 확보

---

## 3. 변경 파일 목록
### 3.1 수정
1) `AGENTS.md`
2) `docs/PROJECT_CHARTER.md`
3) `docs/templates/work-result.template.md`
4) `docs/templates/troubleshooting.template.md`
5) `docs/checklists/remaining_work_master_checklist.md`
6) `docs/work-plans/99-01_result_troubleshooting_quantified_evidence_policy_plan.md`
7) `README.md`

### 3.2 신규
1) `docs/work-result/99-01_result_troubleshooting_quantified_evidence_policy_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 문서 커밋 revert

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `rg -n "정량 개선 증빙|Before/After 비교표|측정 기간/표본|측정 불가 사유" docs/templates/work-result.template.md docs/templates/troubleshooting.template.md AGENTS.md docs/PROJECT_CHARTER.md README.md`
  - `git diff --numstat -- AGENTS.md docs/PROJECT_CHARTER.md docs/templates/work-result.template.md docs/templates/troubleshooting.template.md README.md docs/checklists/remaining_work_master_checklist.md docs/work-plans/99-01_result_troubleshooting_quantified_evidence_policy_plan.md`
- 결과:
  - 필수 키워드가 모든 대상 문서에서 확인됨
  - 변경 라인 통계 확인(문서 정책 반영 범위 추적 가능)

### 5.2 테스트 검증
- 실행 명령:
  - 없음(문서 정책 변경 작업)
- 결과:
  - 해당 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - 해당 없음(비코드 문서 정책)
- 결과:
  - 해당 없음

### 5.4 정량 개선 증빙(필수)
- 측정 기간/표본:
  - 2026-03-04, 정책 대상 문서 5개(AGENTS/Charter/README/Result 템플릿/Troubleshooting 템플릿)
- 측정 기준(성공/실패 정의):
  - 성공: 각 대상 문서에 정량 증빙 필수 항목이 명시되고, 템플릿에 비교표가 존재
- 데이터 출처(SQL/로그/대시보드/스크립트):
  - `rg`, `git diff`
- 재현 명령:
  - `rg -c "정량 개선 증빙\\(필수\\)" docs/templates/work-result.template.md docs/templates/troubleshooting.template.md`
  - `rg -c "before/after|정량|측정" AGENTS.md docs/PROJECT_CHARTER.md README.md`
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 템플릿 내 정량 증빙 필수 섹션 수 | 0 | 2 | +2 | N/A |
| 운영 규칙 문서(AGENTS/Charter/README) 내 정량 증빙 규칙 명시 수 | 0 | 3 | +3 | N/A |
| 체크리스트 상태 | `todo` | `done` | +1 단계 | N/A |

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `99-01` 계획서 승인/완료 상태 반영 확인  
2) 체크리스트 `99-01` 항목 `done` + 결과 문서 링크 연결 확인  
3) README 동기화 확인(규칙 추가)
   - 검증 명령: `rg -n "정량 증빙|before/after" README.md`

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 규칙(AGENTS/Charter) + 템플릿 + 체크리스트 + README를 동시에 갱신하는 다중 게이트 방식
- 고려했던 대안:
  1) AGENTS/Charter만 수정
  2) 템플릿만 수정
  3) CI 문서 린터를 즉시 도입
- 대안 대비 실제 이점(근거/관측 포함):
  1) 규칙+템플릿 동시 반영으로 정책 선언과 작성 실무를 즉시 일치시킴
  2) 체크리스트 상태 전환으로 완료 기준을 추적 가능하게 만듦
  3) README 동기화로 운영 진입점에서도 동일 기준을 확인 가능
- 트레이드오프(단점)와 보완/완화:
  1) 문서 작성 항목 증가
  2) 보완: 템플릿 표준화로 작성 부담을 구조화

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) 해당 없음(코드 로직 변경 없음)
  2) 문서 정책만 변경
- 주석에 포함한 핵심 요소:
  - 해당 없음

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - AGENTS/Charter/템플릿/체크리스트/README 반영 목표를 모두 수행
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - Result/Troubleshooting 정량 증빙 의무화 정책이 문서 체계에 반영 완료됨
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 필요 시 `99-02`로 문서 린터 자동 검증 도입 검토
  2) 다음 2~3개 신규 Result/Troubleshooting 문서에서 정책 준수 샘플 검증

---

## 11. References
- `docs/work-plans/99-01_result_troubleshooting_quantified_evidence_policy_plan.md`
- `AGENTS.md`
- `docs/PROJECT_CHARTER.md`
- `docs/templates/work-result.template.md`
- `docs/templates/troubleshooting.template.md`
- `docs/checklists/remaining_work_master_checklist.md`
