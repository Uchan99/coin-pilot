# 21-05. OCI 인프라 리소스 모니터링 전환(Grafana 중심) 구현 결과

작성일: 2026-02-28
작성자: Codex
관련 계획서: docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md
상태: Done
완료 범위: Phase 1 + Phase 2 + Phase 3 + Phase 4-3 + 운영 재검증(2026-03-06)
선반영/추가 구현: 있음(운영 핫픽스 포함)
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
  - `coinpilot-container-map` 추가(docker ps 결과를 node-exporter textfile metric으로 변환)
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
  - `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=topk(10, container_memory_working_set_bytes{job=\"cadvisor\"})'`
  - `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=container_scrape_error{job=\"cadvisor\"}'`
- 결과:
  - `scripts/ops/check_24h_monitoring.sh t0`: FAIL 0 / WARN 0
  - `scripts/ops/check_24h_monitoring.sh t1h`: infra target(`node-exporter`, `cadvisor`) `UP(1)` 확인
  - `topk(...container_memory_working_set_bytes...)`에서 `/system.slice/docker-<id>.scope` 시계열 다수 확인
  - `container_scrape_error{job=\"cadvisor\"}` 값 `0` 확인

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
  - 컨테이너 패널 `No data` 이슈를 해결했고, 컨테이너 지표는 `서비스명 우선 + 12자리 ID fallback` 기준으로 표시되도록 보강됨
- 후속 작업(다음 plan 번호로 넘길 것):
  1) `24_discord_mobile_chatbot_query_plan` 구현 착수
  2) 21-03 카나리 실험 전, 21-05 인프라 알람 임계치 튜닝

---

## 11. (선택) Phase 2+ 선반영/추가 구현 결과
- 추가 변경 요약:
  - cAdvisor docker factory API 버전 불일치(1.41<1.44) 환경에서 Docker 라벨 기반 쿼리가 실패함을 확인.
  - 컨테이너 패널 쿼리를 `name` 기준에서 `id=~\"/system.slice/docker-.*\\.scope\"` 기준으로 전환해 즉시 시각화 복구.
  - 대시보드 범례를 긴 cgroup 경로 대신 `cid`(container id)로 표기하도록 보정.
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

## 12. Phase 3 추가 구현(컨테이너 서비스명 매핑 가독성 개선)
- 문제:
  - 컨테이너 패널 범례가 긴 해시(`cid`) 중심으로 표시되어 운영자가 `docker ps` 서비스명과 즉시 매칭하기 어려웠음.
- 변경:
  - 파일: `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - 대상 패널 3개(`Container CPU Usage by Container`, `Container Memory Working Set`, `Container Restart Changes (24h)`)
  - 쿼리 로직을 `display` 라벨 기준으로 전환:
    1) `id`에서 12자리 컨테이너 ID 추출(fallback)
    2) `container_label_com_docker_compose_service` 라벨이 있으면 `coinpilot-<service>`로 override
  - `legendFormat`을 `{{cid}}` → `{{display}}`로 변경

### 12.1 정량 증빙(정적 검증)
| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 서비스명 매핑 로직이 적용된 컨테이너 패널 수 | 0 | 3 | +3 | N/A |
| `legendFormat={{display}}` 적용 패널 수 | 0 | 3 | +3 | N/A |
| Fallback ID 길이(표시 기준) | 64자(해시 전체) | 12자(요약) | -52자 | -81.25 |

- 측정 근거 명령:
  - `rg -n '"title": "Container CPU Usage by Container"|"title": "Container Memory Working Set"|"title": "Container Restart Changes \\(24h\\)"|"legendFormat": "\\{\\{display\\}\\}"' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `rg -n 'container_label_com_docker_compose_service|docker-\\(\\[0-9a-f\\]\\{12\\}\\)' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`

### 12.2 운영 검증 방법(OCI)
1) `cd /opt/coin-pilot/deploy/cloud/oci && docker compose --env-file .env -f docker-compose.prod.yml up -d --force-recreate --no-deps grafana`
2) Grafana `CoinPilot Infra Overview`에서 컨테이너 3개 패널 범례가 `coinpilot-bot` 같은 서비스명으로 우선 표시되는지 확인
3) 서비스 라벨이 없는 시계열은 12자리 ID로 fallback되는지 확인
4) 서비스명이 계속 나오지 않으면 `cadvisor`를 `--docker_only=true --store_container_labels=true`로 재기동 후 아래 쿼리로 라벨 건수 재확인:
   - `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=count(container_memory_working_set_bytes{job="cadvisor",container_label_com_docker_compose_service!=""})'`

---

## 13. Phase 4 추가 구현(cAdvisor 라벨 비의존 서비스명 매핑)
- 문제:
  - OCI 환경에서 `container_label_com_docker_compose_service`가 계속 0건으로 관측되어, cAdvisor 라벨 기반 서비스명 표기가 구조적으로 불안정했다.
- 아키텍처 선택 이유:
  - cAdvisor 라벨 유무와 무관하게 `docker ps`는 항상 id/name을 제공하므로, 이를 Prometheus 메트릭으로 변환하면 환경 편차를 제거할 수 있다.
  - 기존 Prometheus/node-exporter/Grafana 스택을 재사용해 운영 복잡도를 최소화한다.
- 고려한 대안:
  1) cAdvisor 라벨 복구만 계속 시도(`docker_only`/권한 튜닝 반복)
  2) Grafana 운영 가이드로만 ID↔서비스명을 수동 해석
  3) `container-map` 사이드카로 id/name 매핑 메트릭을 별도 생성(채택)
- 대안 비교:
  - (1) 장점: 구성 추가 없음 / 단점: 환경 의존성 높아 재발 가능성 큼
  - (2) 장점: 구현 비용 0 / 단점: 운영자 수동 대응 비용이 지속 발생
  - (3) 장점: 자동 매핑 + fallback 유지 / 단점: 사이드카 1개 추가 운영 필요
- 변경:
  1) `node-exporter`에 textfile collector 경로(`--collector.textfile.directory=/host/root/var/lib/node_exporter/textfile_collector`) 추가
  2) `coinpilot-container-map` 사이드카 추가
  3) `deploy/cloud/oci/monitoring/scripts/generate_container_display_map.sh` 추가
  4) Grafana 컨테이너 3개 패널을 `coinpilot-container-map` 메트릭 기반으로 전환(`coinpilot_container_cpu_percent`, `coinpilot_container_memory_working_set_bytes`, `coinpilot_container_restart_count`)
  5) `scripts/ops/check_24h_monitoring.sh`에 `coinpilot_container_display_info` 존재 점검 추가

### 13.1 정량 증빙(구현 기준)
| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| container-map 노출 메트릭 수(`display/cpu/memory/restart/running`) | 0 | 5 | +5 | N/A |
| 서비스명 조인을 적용한 패널 수 | 0 | 3 | +3 | N/A |
| 운영 점검 자동화 항목(서비스명 매핑 점검) | 0 | 1 | +1 | N/A |

- 측정 근거 명령:
  - `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=count(coinpilot_container_display_info{job="node-exporter"})'`
  - `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=count(coinpilot_container_cpu_percent{job="node-exporter"})'`
  - `rg -n 'coinpilot_container_cpu_percent|coinpilot_container_memory_working_set_bytes|coinpilot_container_restart_count|legendFormat\": \"\\{\\{display\\}\\}\"' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `rg -n 'check_prometheus_container_display_map|container-map' scripts/ops/check_24h_monitoring.sh`

### 13.2 운영 검증 방법(OCI)
1) `cd /opt/coin-pilot/deploy/cloud/oci && docker compose --env-file .env -f docker-compose.prod.yml up -d --force-recreate --no-deps node-exporter container-map cadvisor prometheus grafana`
2) `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=count(coinpilot_container_display_info{job="node-exporter"})'` 결과가 1 이상인지 확인
3) Grafana 컨테이너 패널 범례가 `coinpilot-*` 서비스명으로 표시되는지 확인

### 13.3 운영 핫픽스(최근 5m No data)
- 증상:
  - 운영 검증에서 `topk(20, count by (id) (container_memory_working_set_bytes{job="cadvisor"}))` 결과가 `id="/"` 1건만 반환되어 최근 구간(Last 5m/15m) 패널이 `No data`로 재발.
- 조치:
  - 컨테이너 3개 패널의 데이터 소스를 cAdvisor에서 `coinpilot-container-map` 메트릭(`coinpilot_container_cpu_percent`, `coinpilot_container_memory_working_set_bytes`, `coinpilot_container_restart_count`)으로 전환.
  - `container-map` 스크립트에 CPU/메모리/재시작 수집 로직을 추가해, cAdvisor 시계열 공백과 무관하게 최근 구간 패널이 유지되도록 보강.

### 13.4 최종 운영 검증(2026-03-05)
- 실행 명령:
  1) `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=count(coinpilot_container_display_info)'`
  2) `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=count(coinpilot_container_cpu_percent)'`
  3) `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=count(coinpilot_container_memory_working_set_bytes)'`
  4) `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=count(coinpilot_container_restart_count)'`
  5) `scripts/ops/check_24h_monitoring.sh t1h`
- 결과:
  - 4개 메트릭 count 모두 `12` 확인
  - `t1h` 점검 결과 `FAIL: 0`, `WARN: 1`(알림 라우팅 수동확인 안내) 확인
  - Grafana `CoinPilot Infra Overview` Last 5m에서 컨테이너 범례가 `coinpilot-*` 서비스명으로 표시됨

### 13.5 정량 증빙(최종)
| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| Last 5m 컨테이너 패널 `No data` 여부(0/1) | 1 | 0 | -1 | -100.0 |
| 서비스명 표기 가능한 컨테이너 시계열 수 | 0 | 12 | +12 | N/A |
| `check_24h_monitoring.sh t1h` FAIL 건수 | 1 이상(이슈 시) | 0 | 개선 | N/A |

### 13.6 현재 상태 및 잔여 작업
- 현재 상태:
  - 컨테이너 패널 가독성/즉시성 이슈는 해소된 상태이며, 운영 기준 검증(`t1h`)은 통과했다.
  - `coinpilot_container_*` 메트릭 계열은 Prometheus에서 count `12`로 안정 노출 중이다.
- 추가 핫픽스(2026-03-05):
  - 증상: `coinpilot_container_memory_working_set_bytes`가 전 컨테이너 `0`으로 기록됨.
  - 원인: `generate_container_display_map.sh`의 메모리 단위 파서가 실행 환경(busybox awk)에서 호환성 이슈를 일으켜 변환 실패.
  - 조치: `to_bytes()`를 POSIX/busybox 호환 파서로 교체하고, stats/inspect 조회를 prefix-safe 매칭으로 보강.

### 13.7 최종 마감 검증(2026-03-05, t24h)
- 실행 명령:
  - `scripts/ops/check_24h_monitoring.sh t24h`
- 결과:
  - `FAIL: 0`, `WARN: 0`
  - 백업 최신성 확인: Postgres/Redis/n8n 모두 24h 이내 생성 확인
  - 따라서 21-05 완료 조건(가독성 개선 + 24h 운영 점검 통과)을 충족해 상태를 `done`으로 마감

### 13.8 README 동기화 검증(필수)
- 동기화 반영:
  - `README.md`의 운영 상태 요약에서 인프라 관측 항목을 `container-map` 포함, `21-05 완료`로 갱신
  - `README.md`의 우선순위 백로그 항목에서 `21-05` 상태를 `done`으로 갱신
- 검증 명령:
  - `rg -n "21-05|container-map|인프라 관측" README.md`
- 판정:
  - Charter/Checklist/Result와 README 상태 정합성 확인 완료

### 13.9 운영 재검증(2026-03-06, 카나리 관측 24h 경과 후)
- 배경:
  - 29번 배포 이후 `coinpilot-core up=0`이 일시 관측되어 21-05 완료 근거를 재검증했다.
- 실행 명령:
  1) `scripts/ops/check_24h_monitoring.sh t0`
  2) `scripts/ops/check_24h_monitoring.sh t1h`
  3) `scripts/ops/check_24h_monitoring.sh t24h`
  4) Grafana Alerting 임시 룰(`Coinpilot test`) FIRING으로 Discord Contact point 수신 확인
- 결과:
  - `t0`: `FAIL: 0`, `WARN: 0`
  - `t1h`: `FAIL: 0`, `WARN: 1` (수동 안내 항목만 잔존)
  - `t24h`: `FAIL: 0`, `WARN: 0`
  - Discord 수신 확인 완료(Grafana v10.0.0, 알림 메시지 도착)

### 13.10 정량 증빙(재검증)
| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| `check_24h_monitoring.sh t1h` FAIL 건수 | 1 | 0 | -1 | -100.0 |
| `check_24h_monitoring.sh t24h` FAIL 건수 | 0 | 0 | 0 | 0.0 |
| Grafana Contact point Discord 수신 여부(0/1) | 0 | 1 | +1 | N/A |
| `coinpilot-core up` 상태 | 0(일시) | 1(정상) | +1 | N/A |

---

## 14. References
- `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`
- `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- `docs/PROJECT_CHARTER.md`
- `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md`
