# 99-01. Result/Troubleshooting 문제 정의·정량 개선 증빙 의무화 정책 반영 계획

**작성일**: 2026-03-04  
**작성자**: Codex  
**상태**: Verified  
**관련 계획 문서**: 없음  
**관련 결과 문서**: `docs/work-result/99-01_result_troubleshooting_quantified_evidence_policy_result.md`  
**승인 정보**: 사용자 / 2026-03-04 / "반영해줘."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - Result/Troubleshooting 문서가 "무엇을 고쳤는지"와 "얼마나 좋아졌는지"를 정량으로 일관되게 남기지 못하는 경우가 있음.
- 왜 즉시 대응이 필요했는지:
  - 의사결정/회고/재발방지의 근거 품질이 문서 작성자 개인 역량에 의존하고, 비교 가능한 개선 증빙이 누락될 수 있음.

## 1. 문제 요약
- 증상:
  - 문제 정의가 추상적으로 적히거나, 개선 효과가 정성 설명에 머무는 문서가 발생 가능.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 직접 기능 영향 없음
  - 리스크: 재발 시 원인/해결 재현 속도 저하, 품질 회고 난이도 상승
  - 데이터: 운영/개선 근거 데이터의 추적성 저하
  - 비용: 장애 대응 및 변경 검토 시간 증가
- 재현 조건:
  - 템플릿/규칙에 정량 증빙 필수 항목이 강제되지 않을 때

## 2. 원인 분석
- 가설:
  1) AGENTS/Charter에 "정량 개선 증빙"이 권장 수준으로만 해석될 수 있다.
  2) work-result/troubleshooting 템플릿에 before/after/측정방법/데이터 소스가 필수 필드로 고정되어 있지 않다.
  3) 체크리스트 완료 기준에 증빙 항목 검증이 명시되지 않았다.
- 조사 과정:
  - `AGENTS.md`, `docs/PROJECT_CHARTER.md`, `docs/templates/work-result.template.md`, `docs/templates/troubleshooting.template.md` 검토
- Root cause:
  - 문서 품질 기준이 "명시적 정량 증빙 필수"까지 규격화되지 않음

## 3. 대응 전략
- 단기 핫픽스:
  - AGENTS/Charter에 필수 작성 규칙(문제 정의 + before/after 수치 + 측정 명령/데이터 소스)을 명문화
- 근본 해결:
  - Result/Troubleshooting 템플릿에 정량 검증 섹션을 필수 블록으로 추가
  - 체크리스트 완료 조건에 "정량 증빙 링크/근거"를 반영
- 안전장치:
  - Result에서 "수치 부재 시 완료 불가(Partial/Blocked 처리)" 규칙 명시

## 4. 아키텍처/프로세스 대안 비교
- 대안 1: 기존 규칙 유지(작성자 재량)
  - 장점: 즉시 적용 부담 없음
  - 단점: 문서 품질 편차 지속, 검증 가능성 약함
- 대안 2: 규칙+템플릿 동시 강화(채택)
  - 장점: 작성 단계에서 누락 방지, 팀 공통 품질선 확보
  - 단점: 문서 작성 시간이 소폭 증가
- 대안 3: CI 문서 린터로 강제
  - 장점: 누락 자동 탐지
  - 단점: 규칙 예외 처리 복잡도, 초기 구축 비용

## 5. 구현/수정 내용
- 변경 파일(예정):
  1) `AGENTS.md`
  2) `docs/PROJECT_CHARTER.md` (운영 규칙 + 변경 이력)
  3) `docs/templates/work-result.template.md`
  4) `docs/templates/troubleshooting.template.md`
  5) `docs/checklists/remaining_work_master_checklist.md` (완료 조건 표현 보강)
  6) `docs/work-result/99-01_result_troubleshooting_quantified_evidence_policy_result.md` (신규)
- DB 변경(있다면):
  - 없음
- 주의점:
  - 정량 증빙은 "측정 가능 지표" 기준으로 강제하고, 측정 불가 사안은 예외 사유를 명시하도록 규정

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) AGENTS/Charter에 "문제 정의 + 정량 before/after + 측정 근거" 필수 규칙이 명시됨
  2) Result/Troubleshooting 템플릿에 해당 항목이 필수 섹션으로 존재
  3) 체크리스트 완료 조건 문구에 정량 증빙 기준이 반영됨
- 회귀 테스트:
  - 문서 변경 작업으로 코드 테스트 없음
- 운영 체크:
  - `rg -n "before|after|정량|수치|증빙|측정|문제" AGENTS.md docs/PROJECT_CHARTER.md docs/templates/work-result.template.md docs/templates/troubleshooting.template.md docs/checklists/remaining_work_master_checklist.md`

## 7. 롤백
- 코드 롤백:
  - 문서 커밋 revert
- 데이터/스키마 롤백:
  - 없음

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 승인 후 본 계획 구현 및 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 필요(운영 문서 작성 정책 변경)

## 9. 후속 조치
1. 필요 시 99-02로 문서 린터/체크 스크립트 도입 검토
2. 신규 결과/트러블슈팅 문서 2~3건 샘플에 정책 적용 점검

## 10. 계획 변경 이력
- 2026-03-04: 신규 계획 작성, 승인 대기(`Approval Pending`).
- 2026-03-04: 사용자 승인 후 구현 착수(`Approved`).
- 2026-03-04: AGENTS/PROJECT_CHARTER/템플릿/README/체크리스트 반영 및 결과 문서 작성 완료(`Verified`).
