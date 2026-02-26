# 18-14. OCI 24시간 모니터링 스크립트 자동화 결과

작성일: 2026-02-26  
작성자: Codex (GPT-5)  
관련 계획서: `docs/work-plans/18-14_oci_24h_monitoring_script_automation_plan.md`  
상태: Verified  
완료 범위: Phase 1~2  
선반영/추가 구현: 있음(Phase 2: `--output` 옵션)  
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - OCI 24시간 운영 점검을 phase 단위로 자동 실행하는 스크립트 추가
  - 마스터 runbook에 자동 실행 명령 및 사용법 연결
  - Charter 참조/변경 이력 업데이트
- 목표(요약):
  - T+0m/1h/6h/12h/24h 점검을 반복 가능한 방식으로 표준화
- 이번 구현이 해결한 문제(한 줄):
  - 문서 중심 수동 점검을 실행 가능한 PASS/FAIL 점검으로 전환

---

## 2. 구현 내용(핵심 위주)
### 2.1 24시간 점검 스크립트 신규 작성
- 파일/모듈: `scripts/ops/check_24h_monitoring.sh`
- 변경 내용:
  - 실행 모드: `all`, `t0`, `t1h`, `t6h`, `t12h`, `t24h`
  - 점검 항목:
    - compose 서비스 상태
    - bot 치명 오류 키워드
    - Prometheus `up{job="coinpilot-core"}`
    - Entry/AI/Risk 흐름 로그
    - RSS/daily 배치 실패 키워드
    - Postgres/Redis/n8n 백업 최신성
  - 결과 출력:
    - `[PASS]`, `[WARN]`, `[FAIL]` 및 최종 요약 카운트
- 효과/의미:
  - 운영자가 시간대별 점검을 동일 기준으로 반복 가능

### 2.2 운영 문서(runbook) 자동화 경로 반영
- 파일/모듈: `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- 변경 내용:
  - 11.3에 자동 실행 명령(`scripts/ops/check_24h_monitoring.sh all`) 추가
  - 빠른 명령 모음에 스크립트 사용법 추가
- 효과/의미:
  - 문서-실행 간 간극 축소

### 2.3 Charter 추적성 업데이트
- 파일/모듈: `docs/PROJECT_CHARTER.md`
- 변경 내용:
  - 18-14 plan/result 링크 추가
  - changelog에 자동화 스크립트 반영 이력 추가
- 효과/의미:
  - Source of Truth 기준으로 운영 자동화 반영 내역 추적 가능

---

## 3. 변경 파일 목록
### 3.1 수정
1) `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`  
2) `docs/PROJECT_CHARTER.md`  

### 3.2 신규
1) `docs/work-plans/18-14_oci_24h_monitoring_script_automation_plan.md`  
2) `docs/work-result/18-14_oci_24h_monitoring_script_automation_result.md`  
3) `scripts/ops/check_24h_monitoring.sh`  

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 문서/스크립트 변경 revert

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `bash -n scripts/ops/check_24h_monitoring.sh`
  - `scripts/ops/check_24h_monitoring.sh --help`
  - `scripts/ops/check_24h_monitoring.sh t0 --output /tmp/coinpilot-monitoring-check.log || true`
  - `rg -n "check_24h_monitoring.sh|18-14_oci_24h_monitoring_script_automation" docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md docs/PROJECT_CHARTER.md`
- 결과:
  - bash 문법 검증 통과
  - help 출력 정상
  - `--output` 인자 파싱 및 로그 파일 생성 동작 확인
  - runbook/charter 참조 링크 반영 확인

### 5.2 테스트 검증
- 실행 명령:
  - 없음(운영 스크립트/문서 작업)
- 결과:
  - 해당 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - OCI에서 `scripts/ops/check_24h_monitoring.sh t0` 또는 `all` 실행
- 결과:
  - 환경 의존(OCI 서비스 상태)에 따라 PASS/WARN/FAIL 출력

---

## 6. 배포/운영 확인 체크리스트(필수)
1) OCI에서 실행 권한 확인  
`chmod +x /opt/coin-pilot/scripts/ops/check_24h_monitoring.sh`

2) 전체 점검 실행  
`/opt/coin-pilot/scripts/ops/check_24h_monitoring.sh all`

3) phase별 재실행  
`/opt/coin-pilot/scripts/ops/check_24h_monitoring.sh t24h`

4) 결과 파일 저장 실행  
`/opt/coin-pilot/scripts/ops/check_24h_monitoring.sh all --output /var/log/coinpilot/monitoring-24h.log`

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - Bash 단일 스크립트 + phase 인자 기반 점검 자동화
- 고려했던 대안:
  1) Python CLI 점검 도구
  2) alias/문서 명령 모음 유지
  3) Bash 자동 점검 스크립트(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) OCI 기본 환경에서 추가 의존성 없이 즉시 실행 가능
  2) 운영자가 phase별 점검을 반복 호출 가능
  3) PASS/WARN/FAIL 요약으로 운영 판단 속도 개선
- 트레이드오프(단점)와 보완/완화:
  1) Grafana/Discord 일부 항목은 완전 자동 판정이 어려움 -> WARN + 수동 확인 안내 병행
  2) 로그 키워드 기반 점검은 오탐 가능성 존재 -> 치명 키워드 위주로 범위 제한

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `set -e` 미사용 이유(전체 점검 지속성) 설명
  2) 백업 최신성(age hour) 판정 의도 설명
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 점검 불변조건(phase별 동일 검사)
  - 실패 모드(치명 로그/백업 누락)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - phase 기반 자동 점검 스크립트 구현
  - runbook/charter 추적성 반영
- 변경/추가된 부분(왜 바뀌었는지):
  - 사용자 추가 요청으로 `--output <file>` 옵션을 같은 계획의 Phase 2 확장으로 반영
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 24시간 점검 절차가 문서+자동화 스크립트+로그 저장 옵션까지 준비됨
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 21번 실거래 전환 시 실주문/정산 phase를 스크립트에 추가
  2) JSON 출력 등 구조화된 결과 포맷(`--json`) 확장 검토

---

## 11. (선택) Phase 2+ 선반영/추가 구현 결과
- 추가 변경 요약:
  - 사용자 추가 요청에 따라 `--output <file>` 옵션 도입
  - 파일 출력은 `tee -a`를 사용해 콘솔과 파일 동시 기록
- 추가 변경 파일:
  - `scripts/ops/check_24h_monitoring.sh`
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  - `docs/work-plans/18-14_oci_24h_monitoring_script_automation_plan.md`
  - `docs/work-result/18-14_oci_24h_monitoring_script_automation_result.md`
- 추가 검증 결과:
  - `--help`에 옵션 노출 확인
  - `t0 --output /tmp/...` 호출 시 로그 파일 생성 확인
- 영향/리스크:
  - 파일 경로 권한이 없으면 스크립트가 시작 단계에서 실패할 수 있음
  - 운영 환경에서는 `/var/log/coinpilot` 같은 쓰기 가능한 경로 사용 권장

---

## 12. References
- `docs/work-plans/18-14_oci_24h_monitoring_script_automation_plan.md`
- `scripts/ops/check_24h_monitoring.sh`
- `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- `docs/PROJECT_CHARTER.md`
