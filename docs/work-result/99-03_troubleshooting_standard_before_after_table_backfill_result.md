# 99-03. 트러블슈팅 문서 표준 Before/After 비교표 전수 백필 결과

작성일: 2026-03-05
작성자: Codex
관련 계획서: `docs/work-plans/99-03_troubleshooting_standard_before_after_table_backfill_plan.md`
상태: Verified
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - `docs/troubleshooting/*.md` 전수에 표준 5열 비교표(`지표/Before/After/변화량/변화율`)를 통일 적용.
- 목표(요약):
  - 포트폴리오 활용 시 문서 간 정량 비교 형식을 일관화.
- 이번 구현이 해결한 문제(한 줄):
  - 문서마다 다른 정량 표 형식을 표준표 하나로 통일했다.
- 해결한 문제의 구체 정의(필수: 증상/영향/재현 조건):
  - 증상: 24개 문서는 정량 섹션만 있고 표가 없었고, 7개 문서는 4열 커스텀 표를 사용.
  - 영향: 문서 간 비교/검토 속도 저하.
  - 재현 조건: 표준 헤더 누락 스캔 시 31개 문서가 비표준.
- 기존 방식/상태(Before) 기준선 요약(필수):
  - 표준 5열 비교표가 있는 문서는 1개(`21-06`)뿐.

---

## 2. 구현 내용(핵심 위주)
### 2.1 표준표 누락 문서 자동 삽입
- 파일/모듈:
  - `docs/troubleshooting/*.md` (24개 백필 문서)
- 변경 내용:
  - `정량 증빙 상태` 섹션에 표준 5열 비교표 자동 삽입.
  - 문서별 수치 라인 자동 추출 건수를 `Before/After` 지표로 기록.
- 효과/의미:
  - 모든 백필 문서가 최소 1개 이상의 표준표를 보유.

### 2.2 기존 4열 표(비고/근거) 문서 표준화
- 파일/모듈:
  - `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md`
  - `docs/troubleshooting/24_mobile_visibility_gap_discord_query_need.md`
  - `docs/troubleshooting/24-01_discord_role_nonetype_guard_fix.md`
  - `docs/troubleshooting/24-02_mobile_api_500_missing_psycopg2.md`
  - `docs/troubleshooting/27-01_bandit_xml_and_bind_all_interfaces_findings.md`
  - `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md`
  - `docs/troubleshooting/27_ci_dependency_conflict_and_test_env_missing.md`
- 변경 내용:
  - 4열 표를 5열 표준표로 변환.
  - 상태형 지표(성공/실패, 발생/미발생)는 0/1로 매핑해 변화량 계산 가능하게 정규화.
- 효과/의미:
  - 포트폴리오에서 문서 간 비교 축이 통일됨.

---

## 3. 변경 파일 목록
### 3.1 수정
1) `docs/troubleshooting/*.md` 중 31개 문서
2) `docs/checklists/remaining_work_master_checklist.md`

### 3.2 신규
1) `docs/work-plans/99-03_troubleshooting_standard_before_after_table_backfill_plan.md`
2) `docs/work-result/99-03_troubleshooting_standard_before_after_table_backfill_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항:
  - 없음
- 마이그레이션:
  - 없음
- 롤백 전략/주의점:
  - 문서 커밋 revert.

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `for f in docs/troubleshooting/*.md; do if ! rg -q "\\| 지표 \\| Before \\| After \\| 변화량\\(절대\\) \\| 변화율\\(%\\) \\|" "$f"; then echo "$f"; fi; done | sort`
- 결과:
  - 출력 없음(32개 문서 모두 표준표 보유).

### 5.2 테스트 검증
- 실행 명령:
  - 없음(문서 작업)
- 결과:
  - 해당 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - 체크리스트 업데이트 로그 확인.
- 결과:
  - 99-03 행/로그 반영.

### 5.4 정량 개선 증빙(필수)
- 측정 기간/표본:
  - 2026-03-05, `docs/troubleshooting/*.md` 32개 전수.
- 측정 기준(성공/실패 정의):
  - 성공: 모든 문서에 표준 5열 비교표 존재.
- 데이터 출처(SQL/로그/대시보드/스크립트):
  - 문서 전수 스캔 명령 출력.
- 재현 명령:
  - `for f in docs/troubleshooting/*.md; do if ! rg -q "\\| 지표 \\| Before \\| After \\| 변화량\\(절대\\) \\| 변화율\\(%\\) \\|" "$f"; then echo "$f"; fi; done | sort`
  - `python3 - <<'PY' ... standard/legacy table count ... PY`

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 표준 5열 비교표 적용 문서 수(32개 기준) | 1 | 32 | +31 | +3100.0 |
| 4열 커스텀 표(`비고/근거`) 문서 수 | 7 | 0 | -7 | -100.0 |
| 표준표 누락 문서 수 | 31 | 0 | -31 | -100.0 |

- 정량 측정 불가 시(예외):
  - 없음

---

## 6. 배포/운영 확인 체크리스트(필수)
1) 전수 스캔 결과 표준표 누락 0건 확인
2) 체크리스트 99-03 행/로그 반영 확인
3) 계획/결과 문서 링크 유효성 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 자동 백필 + 예외 문서(기존 4열 표) 수동 표준화 혼합 방식.
- 고려했던 대안:
  1) 고가치 문서만 수동 정밀화
  2) 전수 자동 삽입만 수행
  3) 전수 자동 삽입 + 예외 수동 표준화(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 적용 속도와 표준 정합성을 동시에 확보.
  2) 수치 없는 문서에 임의 값 삽입 없이 형식 통일.
  3) 포트폴리오 제출 시 문서 간 비교 가능성 증가.
- 트레이드오프(단점)와 보완/완화:
  1) 자동 추출 기반 지표는 issue-specific 정확도가 낮을 수 있음.
  2) 후속으로 우선순위 문서부터 수동 정밀화 진행.

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) 문서 작업(코드 주석 대상 없음)
  2) 해당 없음
- 주석에 포함한 핵심 요소:
  - 해당 없음(문서 변경 전용 작업)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 표준표 누락 해소, 4열 표준화, 체크리스트 동기화까지 계획대로 완료.
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 트러블슈팅 문서 32개 전부 표준 5열 Before/After 비교표를 보유.
- 후속 작업(다음 plan 번호로 넘길 것):
  1) week 레거시 문서를 result/log 대조 기반 issue-specific 수치로 수동 정밀화.
  2) 문서 품질 점검 스크립트(표준표/정량 섹션 누락 검사) 자동화 검토.

---

## 12. References
- `docs/work-plans/99-03_troubleshooting_standard_before_after_table_backfill_plan.md`
- `docs/work-result/99-02_troubleshooting_quantitative_backfill_all_docs_result.md`
- `docs/checklists/remaining_work_master_checklist.md`
