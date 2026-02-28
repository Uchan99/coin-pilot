# 21-05. OCI 인프라 리소스 모니터링 전환(Grafana 중심) 구현 결과

작성일: 2026-02-28
작성자: Codex
관련 계획서: docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md
상태: Implemented
완료 범위: Phase 1
선반영/추가 구현: 있음(Phase 2 일부)
관련 트러블슈팅(있다면): docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md

---

## 1. 개요
- 구현 범위 요약:
  - Compose에 `node-exporter`, `cadvisor`를 추가
  - Prometheus scrape target을 인프라 exporter까지 확장
  - Grafana 프로비저닝 대시보드에 인프라 전용 대시보드 추가
  - 24시간 점검 스크립트(`t0`, `t1h`)에 인프라 타겟 검증 추가
  - 운영 Runbook/Charter 문서 동기화
- 목표(요약):
  - OCI 콘솔 메트릭 `No data` 상황에서도 CoinPilot 운영 인프라(CPU/RAM/Disk/Container)를 Grafana에서 일관되게 관측
- 이번 구현이 해결한 문제(한 줄):
  - 앱 메트릭 중심 관측에서 벗어나 호스트/컨테이너 리소스까지 운영 관측 범위를 확장함.

---

## 2. 구현 내용(핵심 위주)
### 2.1 Compose exporter 서비스 추가
- 파일/모듈:
  - `deploy/cloud/oci/docker-compose.prod.yml`
- 변경 내용:
  - `coinpilot-node-exporter` 추가
  - `coinpilot-cadvisor` 추가
  - `prometheus`가 exporter 서비스에 의존하도록 `depends_on` 확장
- 효과/의미:
  - 호스트/컨테이너 자원 지표를 Prometheus가 직접 수집 가능

### 2.2 Prometheus scrape job 확장
- 파일/모듈:
  - `deploy/cloud/oci/monitoring/prometheus.yml`
- 변경 내용:
  - `node-exporter` job 추가 (`node-exporter:9100`)
  - `cadvisor` job 추가 (`cadvisor:8080`)
  - 운영자가 빠르게 이해할 수 있도록 한국어 설명 주석 추가
- 효과/의미:
  - 기존 `coinpilot-core` + `prometheus` 외 인프라 지표가 연속 수집됨

### 2.3 Grafana 인프라 대시보드 신설
- 파일/모듈:
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
- 변경 내용:
  - 신규 대시보드 `CoinPilot Infra Overview`(UID: `coinpilot-infra-01`) 추가
  - 패널: Host CPU/Memory/Disk/Network, Container CPU/Memory/Restart changes, Scrape target status
- 효과/의미:
  - 운영자가 앱 성능/거래 지표와 별개로 인프라 병목을 빠르게 진단 가능

### 2.4 24h 운영 점검 자동화 확장
- 파일/모듈:
  - `scripts/ops/check_24h_monitoring.sh`
- 변경 내용:
  - 점검 서비스 목록에 `node-exporter`, `cadvisor` 추가
  - `t1h` 단계에서 `up{job="node-exporter"}`, `up{job="cadvisor"}`를 각각 검사하는 함수 추가
  - 비교 오탐 방지 의도/실패 영향에 대한 한국어 주석 추가
- 효과/의미:
  - 기존 앱 중심 health check를 인프라 관측 체인까지 포함하도록 강화

### 2.5 운영 문서 정합화
- 파일/모듈:
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  - `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`
  - `docs/PROJECT_CHARTER.md`
- 변경 내용:
  - Runbook에 exporter/인프라 대시보드/검증 명령 추가
  - Plan 상태를 `Approved`로 전환, 승인 정보 기입
  - Charter 문서 참고/변경 이력에 21-05 반영
- 효과/의미:
  - 문서 기반 운영과 실제 구성의 불일치 제거

---

## 3. 변경 파일 목록
### 3.1 수정
1) `deploy/cloud/oci/docker-compose.prod.yml`
2) `deploy/cloud/oci/monitoring/prometheus.yml`
3) `scripts/ops/check_24h_monitoring.sh`
4) `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
5) `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`
6) `docs/PROJECT_CHARTER.md`

### 3.2 신규
1) `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
2) `docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항:
  - 없음
- 마이그레이션:
  - 없음
- 롤백 전략/주의점:
  - exporter 서비스 및 scrape job 제거 시 DB 영향 없음

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `python -m json.tool deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json >/dev/null`
  - `bash -n scripts/ops/check_24h_monitoring.sh`
- 결과:
  - JSON/Shell syntax 검증 통과

### 5.2 테스트 검증
- 실행 명령:
  - (해당 없음: 인프라 설정/문서 작업)
- 결과:
  - 단위 테스트 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(OCI에서 실행):
  - `cd /opt/coin-pilot/deploy/cloud/oci`
  - `docker compose --env-file .env -f docker-compose.prod.yml up -d`
  - `docker compose --env-file .env -f docker-compose.prod.yml ps`
  - `curl -sS "http://127.0.0.1:9090/api/v1/query?query=up%7Bjob%3D%22node-exporter%22%7D"`
  - `curl -sS "http://127.0.0.1:9090/api/v1/query?query=up%7Bjob%3D%22cadvisor%22%7D"`
  - `cd /opt/coin-pilot && scripts/ops/check_24h_monitoring.sh t1h`
- 결과:
  - 본 작업 환경에서는 Docker runtime 미사용(WSL sandbox 제약)으로 미실행
  - 상기 명령을 OCI에서 실행해 `UP(1)` 확인 필요

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `coinpilot-node-exporter`, `coinpilot-cadvisor` 컨테이너가 `Up`인지 확인
2) Prometheus target `node-exporter`, `cadvisor`가 모두 `UP`인지 확인
3) Grafana `CoinPilot Infra Overview` 대시보드 패널이 `No data` 없이 표시되는지 확인
4) `scripts/ops/check_24h_monitoring.sh t0/t1h`가 PASS인지 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 기존 Prometheus/Grafana 스택을 유지한 채 exporter를 추가하는 방식으로 인프라 관측 경로를 확장
- 고려했던 대안:
  1) OCI 콘솔 메트릭만 사용
  2) Prometheus exporter(node-exporter/cadvisor) 추가
  3) 외부 SaaS/APM 도입
- 대안 대비 실제 이점(근거/관측 포함):
  1) 현재 운영 스택과 동일 도구 체계 유지(학습/운영 오버헤드 최소)
  2) 앱/인프라 지표를 Grafana에서 한 화면에서 연계 관측 가능
  3) 24h 점검 스크립트와 결합해 운영 점검 자동화 경로가 유지됨
- 트레이드오프(단점)와 보완/완화:
  1) exporter 컨테이너 2개 추가로 관리 대상 증가
  2) cAdvisor 지표/레이블 변동 가능성 존재 → 대시보드/점검 스크립트는 단순하고 보수적인 쿼리로 구성

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `deploy/cloud/oci/monitoring/prometheus.yml`: 각 scrape job 목적 설명
  2) `scripts/ops/check_24h_monitoring.sh`: exporter 타겟 분리 조회 이유 및 오탐 방지 의도
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 실패 시 운영 영향(관측 공백)
  - 오탐 방지 전략

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - Compose exporter 추가
  - Prometheus scrape 확장
  - Grafana 인프라 대시보드 신설
  - Runbook/Charter 문서 반영
- 변경/추가된 부분(왜 바뀌었는지):
  - `scripts/ops/check_24h_monitoring.sh`를 함께 확장하여 운영 점검 자동화와 인프라 관측을 직접 연결
- 계획에서 비효율적/오류였던 점(있다면):
  - 계획서의 대시보드 경로가 `monitoring/...`로 표기되어 있어 실제 경로(`deploy/monitoring/...`)로 정정 필요했음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - exporter 추가 및 t0/t1h 점검 경로는 OCI에서 동작 확인됨
  - 컨테이너 패널 `No data` 보정(Phase 2 핫픽스)을 코드 반영했으며 운영 반영 확인만 남음
- 후속 작업(다음 plan 번호로 넘길 것):
  1) `24_discord_mobile_chatbot_query_plan` 구현 착수
  2) 21-03 카나리 실험 전, 21-05 인프라 알람 임계치 튜닝

---

## 11. (선택) Phase 2+ 선반영/추가 구현 결과
- 추가 변경 요약:
  - cAdvisor docker factory API 버전 불일치(1.41<1.44) 환경에서 Docker 라벨 기반 쿼리가 실패함을 확인.
  - 컨테이너 패널 쿼리를 `name` 기준에서 `id=~\"/system.slice/docker-.*\\.scope\"` 기준으로 전환해 즉시 시각화 복구.
  - `id=\"/\"` 루트 cgroup만 수집되는 현상을 완화하기 위해 cadvisor 권한/마운트를 보강하고 `docker_only=false`로 전환함.
- 추가 변경 파일:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`
  - `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md`
- 추가 검증 결과:
  - JSON 문법 검증 통과(`python3 -m json.tool ...`)
  - 운영 반영 후 `topk(10, container_memory_working_set_bytes{job=\"cadvisor\"})`에서 루트 cgroup 외 컨테이너 시계열 확인 필요
- 영향/리스크:
  - 기존 쿼리 대비 라벨 호환성 개선으로 `No data` 가능성 감소
  - 다만 cAdvisor 라벨 스키마가 크게 달라지는 환경에서는 추가 튜닝이 필요할 수 있음

---

## 12. References
- `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`
- `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- `docs/PROJECT_CHARTER.md`
- `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md`
