# 31-02. OCI 원격 운영 접근 표준화 결과

작성일: 2026-03-12
작성자: Codex
관련 계획서: `docs/work-plans/31-02_oci_remote_ops_access_standardization_plan.md`
상태: Done
완료 범위: Wrapper 2종 + env example + runbook 동기화
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - WSL -> OCI 원격 명령 실행 wrapper 추가
  - WSL -> OCI 브라우저 접근용 SSH 터널 wrapper 추가
  - OCI access env example 추가
  - runbook/README/Charter 동기화
- 목표(요약):
  - 로컬 Docker 유무와 무관하게, 운영 접근은 OCI를 source of truth로 쓰는 표준 경로를 만든다.
- 이번 구현이 해결한 문제(한 줄):
  - WSL에서 운영 스크립트를 실행하려 할 때 `docker` 부재로 막히던 문제를 OCI SSH wrapper 기반 접근으로 우회 가능하게 했다.
- 해결한 문제의 구체 정의(필수: 증상/영향/재현 조건):
  - 증상:
    - WSL에는 `docker`가 없고, 기존 ops 스크립트는 OCI host의 Docker/DB를 전제로 한다.
    - `21-03`, `28`, `21-10` 관측을 하려 해도 매번 SSH 접속/경로/포트 포워딩을 수동으로 맞춰야 했다.
  - 영향:
    - monitoring-only 작업의 최신 상태 확인이 환경 차이 때문에 지연된다.
    - 사용자가 "지금 WSL에서 실행하는지, OCI에서 실행하는지"를 계속 의식해야 한다.
  - 재현 조건:
    - WSL에서 `scripts/ops/ai_decision_canary_report.sh 24` 같은 OCI 운영 명령을 그대로 실행하려고 할 때
- 기존 방식/상태(Before) 기준선 요약(필수):
  - WSL -> OCI 원격 명령 wrapper: 없음
  - WSL -> OCI 터널 wrapper: 없음
  - 공통 OCI access env example: 없음
  - runbook 내 wrapper 기반 표준 접근 절차: 없음

---

## 2. 구현 내용(핵심 위주)
### 2.1 `oci_remote_exec.sh` 추가
- 파일/모듈:
  - `scripts/ops/oci_remote_exec.sh`
- 변경 내용:
  - `deploy/cloud/oci/ops/oci_access.env`에서 SSH 대상/키/포트/원격 repo root를 읽는다.
  - 기본 작업 디렉토리를 `/opt/coin-pilot`로 고정해 기존 결과 문서와 동일한 경로 관례를 사용한다.
  - argv 모드와 `--raw` 모드를 둘 다 지원해 ops script와 SQL/compose 명령을 모두 프록시할 수 있게 했다.
- 효과/의미:
  - WSL에 Docker가 없어도, 운영 명령은 OCI에서 같은 경로/같은 스크립트로 실행할 수 있다.

### 2.2 `oci_tunnel.sh` 추가
- 파일/모듈:
  - `scripts/ops/oci_tunnel.sh`
- 변경 내용:
  - `dashboard`, `n8n`, `grafana`, `prometheus`, `all` 5개 프로파일을 지원한다.
  - SSH 터널 포트 매핑을 스크립트로 고정해 수동 `ssh -L` 명령 반복을 줄였다.
- 효과/의미:
  - 브라우저 접근도 CLI 접근과 동일한 env/config 기준으로 통일됐다.

### 2.3 `oci_access.env.example` 추가
- 파일/모듈:
  - `deploy/cloud/oci/ops/oci_access.env.example`
- 변경 내용:
  - SSH target/host/user/key/port, 원격 repo root, 로컬/원격 터널 포트 기본값을 예시로 제공한다.
- 효과/의미:
  - 개인 환경의 비밀 값은 커밋하지 않으면서도, 표준 변수 이름과 준비 순서를 고정할 수 있다.

### 2.4 runbook / README / Charter 동기화
- 파일/모듈:
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  - `README.md`
  - `docs/PROJECT_CHARTER.md`
- 변경 내용:
  - runbook에 wrapper 준비 순서와 사용 예시를 추가했다.
  - README에 OCI 원격 접근 표준 완료 상태를 반영했다.
  - Charter에 "운영 source of truth는 OCI"라는 접근 정책을 명시하고 changelog를 추가했다.
- 효과/의미:
  - 문서와 스크립트가 같은 운영 기준을 가리키게 됐다.

---

## 3. 변경 파일 목록
### 3.1 수정
1) `docs/work-plans/31-02_oci_remote_ops_access_standardization_plan.md`
2) `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
3) `README.md`
4) `docs/PROJECT_CHARTER.md`
5) `docs/checklists/remaining_work_master_checklist.md`

### 3.2 신규
1) `scripts/ops/oci_remote_exec.sh`
2) `scripts/ops/oci_tunnel.sh`
3) `deploy/cloud/oci/ops/oci_access.env.example`
4) `docs/work-result/31-02_oci_remote_ops_access_standardization_result.md`

---

## 4. DB/스키마 변경
- 변경 사항:
  - 없음
- 마이그레이션:
  - 없음
- 롤백 전략/주의점:
  - wrapper/runbook 변경 revert 시 원복 가능

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `bash -n scripts/ops/oci_remote_exec.sh`
  - `bash -n scripts/ops/oci_tunnel.sh`
  - `scripts/ops/oci_remote_exec.sh --help`
  - `scripts/ops/oci_tunnel.sh --help`
  - `rg -n "oci_remote_exec|oci_tunnel|oci_access.env.example" docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md README.md docs/PROJECT_CHARTER.md`
- 결과:
  - 두 wrapper의 bash syntax와 help 출력이 정상이다.
  - runbook/README/Charter에서 신규 wrapper와 env example 참조를 확인했다.

### 5.2 테스트 검증
- 실행 명령:
  - `scripts/ops/oci_remote_exec.sh --env-file /tmp/does-not-exist pwd || true`
  - `scripts/ops/oci_tunnel.sh --env-file /tmp/does-not-exist all || true`
- 결과:
  - env 파일이 없을 때 준비 순서를 안내하며 명확히 실패하도록 확인했다.

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - 실제 OCI SSH 연결은 수행하지 않았다.
- 결과:
  - 이 세션에서는 실제 SSH 키/호스트를 사용하지 않았고 네트워크 실행도 하지 않았다.
  - 따라서 런타임 검증은 사용자 환경에서 `oci_access.env`를 채운 뒤 수행해야 한다.

### 5.4 정량 개선 증빙(필수)
- 측정 기간/표본:
  - 2026-03-12
  - wrapper 2개, env example 1개, runbook/README/Charter 동기화 3개 문서
- 측정 기준(성공/실패 정의):
  - 성공:
    1) WSL에서 OCI 명령 실행용 wrapper가 존재할 것
    2) 브라우저 터널 wrapper가 존재할 것
    3) env example과 runbook 예시가 함께 제공될 것
  - 실패:
    1) SSH 대상/키/포트 준비 순서가 문서화되지 않음
    2) wrapper가 syntax/help 수준에서도 깨짐
- 데이터 출처(SQL/로그/대시보드/스크립트):
  - `scripts/ops/oci_remote_exec.sh`
  - `scripts/ops/oci_tunnel.sh`
  - `deploy/cloud/oci/ops/oci_access.env.example`
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- 재현 명령:
  - `bash -n scripts/ops/oci_remote_exec.sh`
  - `bash -n scripts/ops/oci_tunnel.sh`
  - `scripts/ops/oci_remote_exec.sh --help`
  - `scripts/ops/oci_tunnel.sh --help`
  - `rg -n "oci_remote_exec|oci_tunnel|oci_access.env.example" scripts/ops deploy/cloud/oci/ops docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md README.md docs/PROJECT_CHARTER.md`
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| WSL -> OCI 원격 명령 wrapper 수 | 0 | 1 | +1 | 측정 불가(분모 0) |
| WSL -> OCI 터널 wrapper 수 | 0 | 1 | +1 | 측정 불가(분모 0) |
| OCI access env example 수 | 0 | 1 | +1 | 측정 불가(분모 0) |
| wrapper 기반 runbook 표준 접근 섹션 수 | 0 | 2 | +2 | 측정 불가(분모 0) |
| wrapper 기준으로 바로 실행 가능한 대표 운영 경로 수(`21-03`, `28`, `21-10`) | 0 | 3 | +3 | 측정 불가(분모 0) |

- 정량 측정 불가 시(예외):
  - 불가 사유:
    - 실제 SSH/OCI 연결 검증은 세션 내 네트워크/비밀키 제약으로 수행하지 않았다.
  - 대체 지표:
    - bash syntax, help 출력, 문서 참조, 실패 메시지 경로 검증
  - 추후 측정 계획/기한:
    - 사용자 환경에서 `deploy/cloud/oci/ops/oci_access.env` 작성 후 `oci_remote_exec.sh scripts/ops/ai_decision_canary_report.sh 24`와 `oci_tunnel.sh all` 1회 실측

---

## 6. 배포/운영 확인 체크리스트(필수)
1. `deploy/cloud/oci/ops/oci_access.env`를 example에서 복사해 실제 SSH 값으로 채울 것
2. WSL에서 운영 명령은 가능하면 `scripts/ops/oci_remote_exec.sh`를 통해 OCI에서 실행할 것
3. 브라우저 접근은 가능하면 `scripts/ops/oci_tunnel.sh all` 또는 프로파일 조합을 사용할 것

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - SSH 기반 원격 명령 wrapper + SSH 터널 wrapper + env example + runbook 정렬
- 고려했던 대안:
  1) runbook 설명만 보강한다.
  2) WSL Docker integration을 필수 운영 전제로 둔다.
  3) OCI를 source of truth 실행 환경으로 고정하고 wrapper를 제공한다. (채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 운영 데이터가 실제로 존재하는 OCI 환경에서 명령을 실행하게 만들어 결과 해석이 일관된다.
  2) WSL에 Docker가 없어도 모니터링/SQL/compose 명령 접근 경로를 마련할 수 있다.
  3) CLI 접근과 브라우저 접근이 같은 env 기준을 공유한다.
- 트레이드오프(단점)와 보완/완화:
  1) SSH 키/호스트 준비가 필요하다.
  2) 이를 완화하기 위해 repo에는 example만 두고, missing env 시 준비 순서를 에러 메시지로 안내한다.

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `scripts/ops/oci_remote_exec.sh`의 원격 source of truth/경로 고정 의도
  2) `scripts/ops/oci_tunnel.sh`의 프로파일화 이유와 CLI/UI 접근 통일 의도
- 주석에 포함한 핵심 요소:
  - 의도/왜(why): 로컬 Docker 의존 제거, OCI 우선 실행
  - 불변조건(invariants): 기본 원격 repo root는 `/opt/coin-pilot`
  - 엣지케이스/실패 케이스: env 파일 누락, ssh 명령 누락, 대상 정보 미설정
  - 대안 대비 판단 근거: 문서-only 보강보다 wrapper 추가가 재사용성에서 유리함

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - `oci_remote_exec.sh`, `oci_tunnel.sh`, `oci_access.env.example`, runbook/result 동기화를 모두 수행했다.
- 변경/추가된 부분(왜 바뀌었는지):
  - Charter/README까지 같이 갱신했다. 접근 정책은 운영 규칙 성격이 강해 문서 2차 소스에도 반영하는 편이 안전하다.
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - WSL에서 OCI를 표준 실행 환경으로 쓰기 위한 wrapper와 문서 기준이 준비됐다.
  - 실제 SSH 런타임 검증만 남아 있다.
- 후속 작업(다음 plan 번호로 넘길 것):
  1) `21-03`, `28`, `21-10` 확인 시 wrapper 기반 명령으로 실제 OCI 관측 수행
  2) 필요 시 배포/재기동 계열 원격 wrapper를 별도 하위 작업으로 확장

---

## 11. README 동기화 여부
- 운영 접근 정책 변경 성격이 있어 `README.md`를 같은 변경 세트에서 동기화했다.
- 검증 명령:
  - `rg -n "OCI 원격 접근 표준|oci_remote_exec|oci_tunnel|oci_access.env.example" README.md`

---

## 12. References
- `docs/work-plans/31-02_oci_remote_ops_access_standardization_plan.md`
- `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- `scripts/ops/oci_remote_exec.sh`
- `scripts/ops/oci_tunnel.sh`
- `deploy/cloud/oci/ops/oci_access.env.example`
- `README.md`
- `docs/PROJECT_CHARTER.md`
