# 31-02. OCI 원격 운영 접근 표준화 계획

**작성일**: 2026-03-12  
**작성자**: Codex  
**상태**: Approved  
**상위 계획 문서**: `docs/work-plans/31_oci_ops_monitoring_cron_automation_and_gap_hardening_plan.md`  
**관련 계획 문서**: `docs/work-plans/18-12_wsl_oci_local_cloud_operations_master_runbook_plan.md`, `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/28_ai_decision_strategy_case_rag_plan.md`  
**승인 정보**: 사용자 승인 / 2026-03-12 / "그렇게 진행해줘."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - `21-03`, `28`, `21-10`의 최신 상태를 확인하려고 했지만 현재 WSL 환경에는 `docker`가 없어 OCI 런타임/DB에 직접 접근할 수 없었다.
  - 기존 ops 스크립트(`scripts/ops/ai_decision_canary_report.sh`, `scripts/ops/llm_usage_cost_report.sh`, `scripts/ops/check_24h_monitoring.sh`)는 모두 OCI 호스트의 Docker Compose 또는 컨테이너를 전제로 한다.
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`에는 수동 SSH/터널 절차가 있으나, WSL에서 "같은 명령을 OCI에서 실행"하는 표준 wrapper는 없다.
- 왜 즉시 대응이 필요한지:
  - 운영 표본 확인이 필요한 작업들이 남아 있어도, 로컬 개발 환경 차이 때문에 관측 자체가 막히면 다음 우선순위 작업 판단이 지연된다.
  - 사용자 요청은 "모든 접근을 OCI로 진행 가능하게" 만드는 것이므로, 수동 runbook 수준이 아니라 재사용 가능한 접근 표준이 필요하다.

## 1. 문제 요약
- 증상:
  - WSL에서는 `docker`가 없어 운영 스크립트를 그대로 실행할 수 없다.
  - OCI에 SSH로 붙어 수동 실행은 가능하지만, 명령마다 접속/경로/환경파일을 다시 맞춰야 한다.
  - 브라우저 접근(대시보드/Grafana/n8n)도 SSH 터널 명령을 수동으로 관리해야 한다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: monitoring/ops 명령 실행 경로가 환경에 따라 깨짐
  - 리스크: 잘못된 환경(WSL vs OCI)에서 명령을 실행해 무의미한 결과를 보거나 시간을 낭비할 수 있음
  - 데이터: 최신 운영 표본 확인 지연
  - 비용: 반복 SSH/터널/경로 맞춤으로 운영 공수 증가
- 재현 조건:
  - WSL 로컬에서 OCI 운영 스크립트나 container/DB 기반 점검 명령을 실행하려고 할 때

## 2. 원인 분석
- 가설:
  1. 운영 표준은 OCI인데, 실행 도구는 여전히 "현재 셸이 Docker 가능한 환경"이라고 가정하고 있다.
  2. runbook는 설명 중심이고, 반복 실행 가능한 wrapper/script 계층이 비어 있다.
  3. 브라우저용 SSH 터널과 CLI용 원격 실행이 분리 문서로만 존재해 사용 경로가 일관되지 않다.
- 조사 과정:
  - `scripts/ops/*.sh`의 runtime 가정 확인
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`의 SSH/터널 절차 확인
  - `31`, `21-03`, `28` 결과 문서에 기록된 OCI 실행 예시 점검
- Root cause:
  - "WSL에서 OCI 운영 명령을 표준화된 방식으로 프록시하는 실행 계층"이 없다.

## 3. 대응 전략
- 단기 핫픽스:
  - WSL에서 OCI SSH 접속/원격 명령 실행/포트 터널링을 빠르게 재사용할 수 있는 wrapper를 추가한다.
- 근본 해결:
  - CLI 접근과 브라우저 접근을 모두 포함하는 **OCI access standard**를 스크립트 + runbook + env example 형태로 코드화한다.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 원격 실행 대상 사용자/호스트/키 경로를 명시적으로 제한
  - destructive 명령은 wrapper 기본값에서 허용하지 않고, 명시 인자로만 실행
  - SSH 연결 timeout / strict host key 정책 / 기본 작업 디렉토리(`/opt/coin-pilot`)를 고정

## 4. 구현/수정 내용
- 변경 파일(예정):
  1. `scripts/ops/oci_remote_exec.sh`
  2. `scripts/ops/oci_tunnel.sh`
  3. `deploy/cloud/oci/ops/oci_access.env.example`
  4. `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  5. `docs/work-result/31-02_oci_remote_ops_access_standardization_result.md`
- 구현 범위(예정):
  1. WSL -> OCI 원격 명령 실행 wrapper
     - 기본 원격 사용자/호스트/SSH key/env file/compose file/remote repo root 지원
  2. 운영 포트 터널 wrapper
     - dashboard/grafana/n8n/prometheus 공통 tunnel 프로파일 제공
  3. 자주 쓰는 monitoring 예시 정렬
     - `21-03`, `28`, `21-10` 확인 명령을 wrapper 기반 예시로 통일
  4. runbook 정리
     - "어느 터미널에서 무엇을 실행하는가"를 WSL 기준으로 한 번에 이해되게 재작성
- DB 변경(있다면):
  - 없음
- 주의점:
  - 실제 SSH 키/공인 IP/호스트명은 커밋하지 않는다.
  - 원격 명령 래퍼는 읽기/조회 중심으로 시작하고, 배포/재기동 계열은 후속 확장 대상으로 분리할 수 있다.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  1. WSL에서 `docker`가 없어도 OCI의 `scripts/ops/ai_decision_canary_report.sh 24`를 wrapper로 실행할 수 있을 것
  2. WSL에서 dashboard/grafana/n8n/prometheus 터널을 단일 스크립트로 열 수 있을 것
  3. `21-03`, `28`, `21-10` 확인 명령이 runbook와 wrapper 예시에서 동일한 패턴으로 문서화될 것
- 회귀 테스트:
  - 기존 OCI 호스트 내 직접 실행 경로(`/opt/coin-pilot`에서 직접 bash 실행)는 그대로 유지돼야 함
  - wrapper 미사용 시 기존 스크립트 동작이 바뀌지 않아야 함
- 운영 체크:
  - 잘못된 호스트/키/작업경로로 연결될 때 명확하게 실패 메시지를 출력해야 함
  - 브라우저 터널 포트 충돌 시 재현 가능한 오류 메시지를 남겨야 함

## 6. 롤백
- 코드 롤백:
  - 신규 wrapper/env example/runbook 변경 revert
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 승인 후 구현 시 `docs/work-result/31-02_oci_remote_ops_access_standardization_result.md` 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - OCI access standard를 운영 규칙으로 승격할 정도의 정책 변경이 있으면 changelog 반영

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1. 원격 배포/재기동까지 wrapper 범위를 넓힐지 별도 판단
  2. SSH config 기반 alias(`Host coinpilot-oci`)를 repo 밖 개인 환경 가이드로 분리할지 검토
  3. monitoring-only 작업 결과 문서에 OCI wrapper 예시 명령을 공통 패턴으로 backfill할지 검토

## 9. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **SSH 기반 OCI 원격 실행 wrapper + 포트 터널 wrapper + runbook 정렬**
- 고려 대안:
  1. 기존 runbook 설명만 보강하고 스크립트는 추가하지 않는다.
  2. WSL에 Docker Desktop/WSL integration을 강제한다.
  3. SSH wrapper로 OCI를 단일 source of truth 실행 환경으로 고정한다. (채택 예정)
- 대안 비교:
  1. 문서만 보강:
     - 장점: 구현량이 적다.
     - 단점: 반복 수작업과 실수 가능성이 그대로 남는다.
  2. WSL Docker 강제:
     - 장점: 로컬 재현성이 높아질 수 있다.
     - 단점: 실제 운영 데이터/컨테이너는 여전히 OCI에 있으므로 문제를 근본적으로 해결하지 못한다.
  3. SSH wrapper:
     - 장점: 운영 source of truth가 OCI라는 현재 구조와 일치한다.
     - 단점: SSH 키/호스트 관리가 필요하고 네트워크 의존성이 있다.

## 10. 변경 이력
- 2026-03-12: 사용자 요청("모든 접근은 다 OCI로 진행할 수 있도록")에 따라 신규 하위 계획 생성. 초기 상태는 `Approval Pending`.
- 2026-03-12: 사용자 승인 후 구현 범위를 `oci_remote_exec.sh`, `oci_tunnel.sh`, `oci_access.env.example`, runbook/result/README/Charter 동기화로 확정했다.
