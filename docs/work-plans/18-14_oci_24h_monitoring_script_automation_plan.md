# 18-14. OCI 24시간 모니터링 스크립트 자동화 계획

**작성일**: 2026-02-26  
**작성자**: Codex (GPT-5)  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/18-13_oci_24h_monitoring_checklist_plan.md`  
**승인 정보**: 사용자 채팅 승인(2026-02-26, "좋아 해줘")

---

## 0. 트리거(Why started)
- 사용자 요청으로 24시간 점검 절차를 수동 명령 모음이 아닌 실행 가능한 스크립트로 자동화할 필요가 생김.
- 운영자가 시간대별 점검을 빠르게 재실행하고 PASS/FAIL을 일관되게 판단할 수 있어야 함.

## 1. 문제 요약
- 증상:
  - 체크리스트는 있으나 명령을 매번 수동 입력해야 함
  - 같은 점검이라도 운영자마다 판단 기준이 달라질 수 있음
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 장애 탐지 지연 가능성
  - 리스크: 핵심 에러(traceback/critical) 누락 가능
  - 데이터: 백업 생성 여부 확인 누락 가능
  - 비용: 장애 대응 시간 증가
- 재현 조건:
  - 재배포 직후 T+0m/1h/6h/12h/24h 점검을 수동으로 반복할 때

## 2. 원인 분석
- 가설:
  - 운영 체크리스트가 "문서 중심"으로만 존재해 실행 자동화가 부족함
- 조사 과정:
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md` 11.3 확인
  - 현재 명령셋은 제공되지만 단계별 자동 판정 기능은 없음
- Root cause:
  - 점검 로직(명령 + 판정 기준 + 출력)이 스크립트로 캡슐화되지 않음

## 3. 대응 전략
- 단기 핫픽스:
  - `scripts/ops/check_24h_monitoring.sh` 신규 작성
- 근본 해결:
  - 시간대별 phase 인자(`t0`, `t1h`, `t6h`, `t12h`, `t24h`, `all`)로 표준 점검 자동화
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 치명 키워드 기반 로그 검사(critical/traceback/undefined*)
  - 백업 파일 최신성 검사(24h 구간)

## 4. 구현/수정 내용
- 변경 파일:
  - `scripts/ops/check_24h_monitoring.sh` (신규)
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  - `docs/PROJECT_CHARTER.md`
  - `docs/work-result/18-14_oci_24h_monitoring_script_automation_result.md` (신규)
- DB 변경(있다면):
  - 없음
- 주의점:
  - OCI에서 실행하는 것을 기본 가정
  - Grafana/Discord 라우팅 최종 확인은 수동 확인 단계 병행

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - 각 phase 실행 시 PASS/FAIL 요약이 출력되는지 확인
- 회귀 테스트:
  - runbook의 수동 체크리스트와 스크립트 phase가 일치하는지 확인
- 운영 체크:
  - `all` 모드 실행 시 24시간 점검 항목이 누락 없이 호출되는지 확인

## 6. 롤백
- 코드 롤백:
  - 스크립트 파일 및 runbook 참조 revert
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 18-14 plan/result 생성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 필요(문서 참조 및 changelog 추가)

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) 실거래 전환(21번) 단계에서 실주문/정산 점검 phase 확장
  2) 결과를 로그 파일로 남기는 `--output` 옵션 추가 검토(2026-02-26 구현 완료)

## 9. 아키텍처 선택/대안/트레이드오프
- 최종 선택:
  - 단일 Bash 스크립트 + phase 인자 기반 점검
- 대안:
  1) Python CLI 점검 도구
  2) 단순 명령 alias 모음
  3) Bash phase 스크립트(채택)
- 채택 이유:
  - 1은 배포 의존성/실행환경 관리 비용 증가
  - 2는 판정 로직(PASS/FAIL) 구현이 약함
  - 3은 OCI 운영 환경에서 즉시 실행 가능하고 의존성이 최소

## 10. 계획 변경 이력
- 2026-02-26 (초기): phase 기반 자동 점검 스크립트(`all/t0/t1h/t6h/t12h/t24h`) 범위로 승인
- 2026-02-26 (확장): 사용자 추가 요청("붙여줘")에 따라 `--output <file>` 로그 저장 옵션을 동일 계획 범위의 Phase 2로 확장
