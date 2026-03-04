# 99-02. 트러블슈팅 문서 정량 증빙 백필(전수) 구현 결과

작성일: 2026-03-04
작성자: Codex
관련 계획서: `docs/work-plans/99-02_troubleshooting_quantitative_backfill_all_docs_plan.md`
상태: Verified
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - `docs/troubleshooting/*.md` 전수 점검 후 정량 섹션 누락 문서에 `정량 증빙 상태` 섹션을 일괄 백필.
- 목표(요약):
  - 트러블슈팅 문서 형식을 최소한 동일 기준으로 맞춰 재사용성과 탐색성을 높임.
- 이번 구현이 해결한 문제(한 줄):
  - 레거시 트러블슈팅 문서의 정량 근거 누락 상태를 일괄 표준화했다.
- 해결한 문제의 구체 정의(필수: 증상/영향/재현 조건):
  - 증상: 문서마다 정량 근거 형식이 다르거나 누락.
  - 영향: 문제 해결 효과를 빠르게 비교하기 어려움.
  - 재현 조건: `docs/troubleshooting/*.md`에서 `정량` 키워드 누락 문서 스캔.
- 기존 방식/상태(Before) 기준선 요약(필수):
  - 일부 최신 문서만 정량표 보유, 다수 레거시는 미보유.

---

## 2. 구현 내용(핵심 위주)
### 2.1 누락 문서 전수 식별
- 파일/모듈:
  - `docs/troubleshooting/*.md`
- 변경 내용:
  - `정량` 키워드 기준 누락 문서를 식별.
- 효과/의미:
  - 정리 대상을 명확히 정의해 누락 없이 백필 수행.

### 2.2 일괄 백필 적용
- 파일/모듈:
  - 정량 섹션이 없던 트러블슈팅 문서 전수
- 변경 내용:
  - 문서 말미에 `정량 증빙 상태 (2026-03-04 백필)` 표준 섹션 추가.
  - 수치 근거가 없는 경우는 “기록 한계/추후 보강 기준”으로 명시.
- 효과/의미:
  - 임의 수치 작성 없이 문서 품질 기준을 맞춤.

---

## 3. 변경 파일 목록
### 3.1 수정
1) `docs/troubleshooting/11_scheduler_and_notification_issues.md`
2) `docs/troubleshooting/12_strategy_tuning_and_report_fix.md`
3) `docs/troubleshooting/13_strategy_regime_reliability_and_hotfixes.md`
4) `docs/troubleshooting/14_trade_count_split_hotfix.md`
5) `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`
6) `docs/troubleshooting/18-02_ai_model_404_and_notification_reliability.md`
7) `docs/troubleshooting/18-03_grafana_no_data_with_prometheus_ok.md`
8) `docs/troubleshooting/18-10_systemd_compose_pull_guard.md`
9) `docs/troubleshooting/18-11_n8n_volume_mismatch_and_backup.md`
10) `docs/troubleshooting/18-15_analyst_rule_boundary_false_rejects.md`
11) `docs/troubleshooting/18-16_t12h_failed_keyword_false_positive.md`
12) `docs/troubleshooting/18-17_trade_notification_quantity_blank.md`
13) `docs/troubleshooting/18-18_notification_style_and_decision_color.md`
14) `docs/troubleshooting/18_compose_bot_status_missing_after_migration.md`
15) `docs/troubleshooting/18_oci_a1_flex_capacity_and_throttle_retry.md`
16) `docs/troubleshooting/prometheus_grafana_monitoring_runbook.md`
17) `docs/troubleshooting/week1-ts.md`
18) `docs/troubleshooting/week2-ts.md`
19) `docs/troubleshooting/week3-ts.md`
20) `docs/troubleshooting/week4-ts.md`
21) `docs/troubleshooting/week5-ts.md`
22) `docs/troubleshooting/week6-ts.md`
23) `docs/troubleshooting/week7-ts.md`
24) `docs/troubleshooting/week8-ts.md`
25) `docs/checklists/remaining_work_master_checklist.md`

### 3.2 신규
1) `docs/work-plans/99-02_troubleshooting_quantitative_backfill_all_docs_plan.md`
2) `docs/work-result/99-02_troubleshooting_quantitative_backfill_all_docs_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항:
  - 없음
- 마이그레이션:
  - 없음
- 롤백 전략/주의점:
  - 문서 커밋 revert로 롤백 가능.

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `for f in docs/troubleshooting/*.md; do if ! rg -q "정량" "$f"; then echo "$f"; fi; done | sort`
- 결과:
  - 출력 없음(모든 대상 문서에 `정량` 키워드 존재).

### 5.2 테스트 검증
- 실행 명령:
  - 없음(문서 작업)
- 결과:
  - 해당 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - 체크리스트 업데이트 로그 확인.
- 결과:
  - `docs/checklists/remaining_work_master_checklist.md`에 본 백필 작업 로그 반영.

### 5.4 정량 개선 증빙(필수)
- 측정 기간/표본:
  - 2026-03-04, `docs/troubleshooting/*.md` 32개 전수.
- 측정 기준(성공/실패 정의):
  - 성공: 모든 문서가 정량 관련 섹션 또는 정량 상태 문구를 포함.
- 데이터 출처(SQL/로그/대시보드/스크립트):
  - 로컬 문서 스캔 명령.
- 재현 명령:
  - `for f in docs/troubleshooting/*.md; do if ! rg -q "정량" "$f"; then echo "$f"; fi; done | sort`

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| `정량` 키워드 미포함 문서 수 | 24 | 0 | -24 | -100.0 |
| `정량` 키워드 포함 문서 수(32개 기준) | 8 | 32 | +24 | +300.0 |
| 백필 24개 중 수치 라인 자동 추출 반영 문서 수 | 0 | 18 | +18 | N/A |

- 정량 측정 불가 시(예외):
  - 없음

---

## 6. 배포/운영 확인 체크리스트(필수)
1) 트러블슈팅 문서 전수 스캔 결과가 비어 있는지 확인
2) 체크리스트 최근 업데이트 로그 반영 확인
3) 신규 문서(`99-02` plan/result) 링크 유효성 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - “정량 백필 섹션 일괄 추가 + 수치 미보관 시 명시” 방식.
- 고려했던 대안:
  1) 수치가 있는 문서만 선별 보강
  2) 모든 문서를 결과 대조 후 완전 수치화
  3) 전수 백필 후 점진 정밀화(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 누락 문서 24개를 한 번에 정리해 형식 일관성 확보.
  2) 근거 없는 수치 생성 리스크를 회피.
  3) 후속 정밀화 우선순위를 명확히 설정 가능.
- 트레이드오프(단점)와 보완/완화:
  1) 일부 문서는 여전히 정밀 수치가 부족함.
  2) 이를 문서에 명시하고 후속 보강 기준을 넣어 보완.

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
  - 누락 식별 → 전수 백필 → 체크리스트 동기화를 계획대로 수행.
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 트러블슈팅 문서의 정량 섹션 누락은 전수 해소됨.
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 레거시 week 문서를 우선순위별로 result 대조해 구체 수치표 정밀화.
  2) 신규 트러블슈팅 작성 시 템플릿 준수 자동 점검 스크립트 검토.

---

## 11. (선택) Phase 2+ 선반영/추가 구현 결과
- 추가 변경 요약:
  - 1차 백필에서 넣은 일반 문구를 정밀 보강하기 위해, 백필 24개 문서에서 숫자 라인(%, 건수, passed/failed, 시간 단위 등)을 자동 추출해 `정량 증빙 상태` 섹션에 반영.
- 추가 검증 결과:
  - 백필 문서 24개 중 18개 문서에서 최소 1개 이상의 구체 수치 라인 자동 반영.
  - 나머지 문서는 수치 원문이 부족하거나 패턴 불명확해 “기록 한계/추후 보강” 기준을 유지.
- 영향/리스크:
  - 장점: 포트폴리오 관점에서 문서별 “수치 근거 발견 가능성”이 즉시 증가.
  - 리스크: 자동 추출 기반이므로 일부 라인은 추가 정제(수동 교정)가 필요.

---

## 12. References
- `docs/work-plans/99-02_troubleshooting_quantitative_backfill_all_docs_plan.md`
- `docs/checklists/remaining_work_master_checklist.md`
