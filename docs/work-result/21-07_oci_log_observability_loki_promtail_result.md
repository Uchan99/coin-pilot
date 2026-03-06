# 21-07. OCI 로그 관측 체계 강화(Loki/Promtail/Grafana) 구현 결과

작성일: 2026-03-06
작성자: Codex
관련 계획서: docs/work-plans/21-07_oci_log_observability_loki_promtail_plan.md
상태: Partial
완료 범위: Phase A + Phase B (구성/문서/점검 스크립트)
선반영/추가 구현: 있음(운영 점검 자동화 연동)
관련 트러블슈팅(있다면): docs/troubleshooting/21-07_promtail_docker_api_version_mismatch.md

---

## 1. 개요
- 구현 범위 요약:
  - OCI Compose에 `loki`, `promtail` 서비스 추가
  - Grafana datasource provisioning에 Loki 추가
  - `check_24h_monitoring.sh t1h`에 로그 파이프라인 점검 로직 추가
  - 운영 runbook/체크리스트/charter 동기화
- 목표(요약):
  - 메트릭 중심 관측(21-05)에서 로그 축을 추가해 RCA 속도를 높인다.
- 이번 구현이 해결한 문제(한 줄):
  - 장애 시 수동 `docker logs` 의존도를 줄이고, Loki 기반 중앙 로그 조회 경로를 표준화했다.
- 해결한 문제의 구체 정의(증상/영향/재현 조건):
  - 증상: 이슈 시 서비스별 로그를 개별 조회해야 하므로 원인 분석 시작 시간이 지연됨
  - 영향: `coinpilot-core up=0` 같은 단기 장애의 분석 리드타임 증가
  - 재현 조건: 배포 직후/일시 네트워크 오류/LLM 오류 급증 구간
- 기존 방식/상태(Before) 기준선 요약:
  - Compose 모니터링 스택에 로그 백엔드가 없었고, 24h 점검 스크립트도 로그 수집 파이프라인 상태를 검증하지 못함

---

## 2. 구현 내용(핵심 위주)
### 2.1 Loki/Promtail 서비스 추가
- 파일/모듈:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/cloud/oci/monitoring/loki/config.yml`
  - `deploy/cloud/oci/monitoring/promtail/config.yml`
- 변경 내용:
  - Loki 저장소(`coinpilot_loki_data`)와 Promtail 수집 에이전트를 Compose 서비스로 추가
  - Promtail을 Docker SD 기반(`docker.sock`)으로 구성해 `coinpilot-*` 컨테이너 로그를 라벨링(`service`, `container`, `cid`)해 수집
  - Docker Engine API 최소 버전 불일치 대응을 위해 `PROMTAIL_DOCKER_API_VERSION` 환경변수(기본 `1.44`)를 추가
  - Loki 보존기간 기본값 14일(336h) 설정
- 효과/의미:
  - 운영 로그 조회 경로가 컨테이너 단일 명령에서 중앙 검색형으로 전환됨

### 2.2 Grafana datasource 연동
- 파일/모듈:
  - `deploy/monitoring/grafana-provisioning/datasources.yaml`
- 변경 내용:
  - `uid=loki` datasource 추가(`http://loki:3100`)
- 효과/의미:
  - Grafana Explore에서 `Prometheus + Loki`를 같은 UI에서 교차 조회 가능

### 2.3 24h 운영 점검 자동화 확장
- 파일/모듈:
  - `scripts/ops/check_24h_monitoring.sh`
- 변경 내용:
  - 서비스 점검 대상에 `loki`, `promtail` 추가
  - `t1h` 단계에 아래 검증 추가
    - Loki readiness (`/ready`)
    - Loki `service` 라벨 조회(coinpilot-* 유입 여부)
    - Promtail 전송 오류 키워드 점검
- 효과/의미:
  - 로그 파이프라인 상태를 운영 점검 루틴에서 자동 확인 가능

### 2.4 문서 동기화
- 파일/모듈:
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  - `docs/checklists/remaining_work_master_checklist.md`
  - `docs/work-plans/21-07_oci_log_observability_loki_promtail_plan.md`
  - `docs/PROJECT_CHARTER.md`
- 변경 내용:
  - Runbook에 Loki/Promtail 운영 점검 절차 추가
  - 체크리스트 21-07 상태를 `in_progress`로 전환
  - Plan 상태를 `Approved`로 전환하고 승인 정보 반영
  - Charter changelog에 21-07 착수 반영
- 효과/의미:
  - 구현/운영/정책 문서가 같은 기준으로 맞춰짐

---

## 3. 변경 파일 목록
### 3.1 수정
1) `deploy/cloud/oci/docker-compose.prod.yml`
2) `deploy/monitoring/grafana-provisioning/datasources.yaml`
3) `scripts/ops/check_24h_monitoring.sh`
4) `.env.example`
5) `deploy/cloud/oci/.env.example`
6) `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
7) `docs/work-plans/21-07_oci_log_observability_loki_promtail_plan.md`
8) `docs/checklists/remaining_work_master_checklist.md`
9) `docs/PROJECT_CHARTER.md`

### 3.2 신규
1) `deploy/cloud/oci/monitoring/loki/config.yml`
2) `deploy/cloud/oci/monitoring/promtail/config.yml`
3) `docs/work-result/21-07_oci_log_observability_loki_promtail_result.md`
4) `docs/troubleshooting/21-07_promtail_docker_api_version_mismatch.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점:
  - Loki/Promtail 서비스와 관련 설정만 제거하면 된다(DB 영향 없음)

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `bash -n scripts/ops/check_24h_monitoring.sh`
  - `rg -n "loki|promtail|LOKI_URL|check_loki_log_pipeline" deploy/cloud/oci/docker-compose.prod.yml scripts/ops/check_24h_monitoring.sh deploy/monitoring/grafana-provisioning/datasources.yaml`
- 결과:
  - shell 문법 검증 통과
  - Loki/Promtail 구성 요소가 Compose/스크립트/datasource에 반영된 것을 정적 확인
  - `docker compose config` 기반 검증은 로컬 WSL에 Docker 미설치로 수행 불가(OCI에서 검증 필요)

### 5.2 테스트 검증
- 실행 명령:
  - (해당 없음: 인프라 구성/운영 문서 변경)
- 결과:
  - 단위 테스트 대상 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(OCI에서 실행):
  - `cd /opt/coin-pilot/deploy/cloud/oci`
  - `docker compose --env-file .env -f docker-compose.prod.yml up -d --build loki promtail grafana`
  - `docker compose --env-file .env -f docker-compose.prod.yml ps loki promtail grafana`
  - `curl -sS http://127.0.0.1:3100/ready`
  - `curl -sS -G http://127.0.0.1:3100/loki/api/v1/label/service/values`
  - `cd /opt/coin-pilot && scripts/ops/check_24h_monitoring.sh t1h`
- 결과:
  - 1차 실행(배포 직후): `FAIL:2`, `WARN:3`
    - `coinpilot-core up=0`(재기동 직후)
    - `Loki /ready` 미응답(워밍업 구간)
  - 2차 실행(45초 워밍업 후): `FAIL:0`, `WARN:3`
    - `coinpilot-core up=1`, `Loki ready` 회복
    - WARN 잔존: `Loki service 라벨 미검출` + `promtail 오류 키워드`
  - 추가 로그에서 Root cause 확정:
    - `promtail`: `client version 1.42 is too old. Minimum supported API version is 1.44`

### 5.4 정량 개선 증빙(필수)
- 측정 기간/표본:
  - 2026-03-06 배포 직후~워밍업 재검증 2회 + promtail/loki/bot 로그 15분
- 측정 기준(성공/실패 정의):
  - 성공: `t1h FAIL=0` + Loki ready + promtail 수집 오류 없음
  - 실패: `t1h FAIL>0` 또는 promtail API 불일치 오류 감지
- 데이터 출처(SQL/로그/대시보드/스크립트):
  - `scripts/ops/check_24h_monitoring.sh t1h` 출력 + `docker compose logs --since=15m promtail`
- 재현 명령:
  - `scripts/ops/check_24h_monitoring.sh t1h`
  - `docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs --since=15m promtail`
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| Compose 로그 관측 서비스 수(`loki`,`promtail`) | 0 | 2 | +2 | N/A |
| Grafana 로그 datasource 수(`Loki`) | 0 | 1 | +1 | N/A |
| `t1h` 로그 파이프라인 자동 검증 항목 수 | 0 | 3 | +3 | N/A |
| `t1h` FAIL 건수(배포 직후→워밍업 후) | 2 | 0 | -2 | -100.0 |
| `t1h` WARN 건수(배포 직후→워밍업 후) | 3 | 3 | 0 | 0.0 |
| promtail API mismatch 오류(15분 로그) | 11 | N/A(핫픽스 배포 전) | N/A | N/A |

- 정량 측정 불가 시(예외):
  - 불가 사유: promtail API 버전 핫픽스 코드 반영 후 OCI 재배포 전이라 오류 감소치 확정 불가
  - 대체 지표: 오류 패턴과 발생 빈도(15초 주기 반복)로 원인-영향을 우선 증빙
  - 추후 측정 계획/기한: `PROMTAIL_DOCKER_API_VERSION=1.44` 재배포 직후 15분 로그에서 mismatch 오류 0건 확인

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `coinpilot-loki`, `coinpilot-promtail` 컨테이너 `Up` 확인
2) `curl http://127.0.0.1:3100/ready` 결과 `ready` 확인
3) `loki/api/v1/label/service/values`에 `coinpilot-*` 라벨 유입 확인
4) `scripts/ops/check_24h_monitoring.sh t1h`에서 Loki/Promtail 관련 FAIL=0 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 기존 Prometheus/Grafana 스택에 Loki/Promtail을 추가해 메트릭+로그 관측을 단일 UI로 통합
- 고려했던 대안:
  1) `docker compose logs` 수동 조회 유지
  2) Loki/Promtail 자체 구축 (채택)
  3) 외부 SaaS 로그 플랫폼
- 대안 대비 실제 이점(근거/관측 포함):
  1) 현재 Compose/Grafana 운영 구조를 유지해 도입 비용 최소화
  2) 서비스 라벨 기반 검색으로 장애 시점 RCA 시작 시간을 줄일 수 있음
  3) `check_24h_monitoring.sh`에 통합되어 운영 루틴 일관성 확보
- 트레이드오프(단점)와 보완/완화:
  1) 디스크 사용량 증가 가능성 -> 14일 보존 + 주기 점검
  2) 라벨 증가에 따른 저장량 변동 -> `coinpilot-*` 필터와 빈 라벨 drop 적용

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `deploy/cloud/oci/monitoring/promtail/config.yml`: 수집 대상 필터와 drop 정책 의도
  2) `scripts/ops/check_24h_monitoring.sh`: Loki readiness/라벨 점검 목적과 경고 기준
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 엣지케이스(초기 구간 라벨 미검출 가능)
  - 실패 케이스(전송 오류 키워드 감지 시 경고)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - Compose 서비스 추가, Grafana datasource 연동, 운영 점검 절차 연동
- 변경/추가된 부분(왜 바뀌었는지):
  - `check_24h_monitoring.sh`에 Loki 파이프라인 점검을 먼저 넣어, 운영자 수동 확인 의존을 줄임
- 계획에서 비효율적/오류였던 점(있다면):
  - Plan 단계에서 검증 기준은 있었으나 스크립트 자동화 포인트가 명시적으로 부족해 착수 시 보강

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 21-07은 코드/문서 기준으로 착수 및 Phase A/B 반영 완료(`in_progress`)
- 후속 작업(다음 plan 번호로 넘길 것):
  1) Promtail API mismatch 핫픽스 배포 후 `t1h` WARN 축소 수치 갱신
  2) 로그 기반 Discord 알림 규칙 정의(Phase C)

---

## 11. (선택) Phase 2+ 선반영/추가 구현 결과
- 해당 없음

---

## 12. References
- Plan: `docs/work-plans/21-07_oci_log_observability_loki_promtail_plan.md`
- Runbook: `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- Checklist: `docs/checklists/remaining_work_master_checklist.md`
- Troubleshooting: `docs/troubleshooting/21-07_promtail_docker_api_version_mismatch.md`
