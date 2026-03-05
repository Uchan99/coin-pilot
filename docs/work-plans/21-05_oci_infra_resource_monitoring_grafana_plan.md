# 21-05. OCI 인프라 리소스 모니터링 전환(Grafana 중심) 계획

**작성일**: 2026-02-27  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/18-14_oci_24h_monitoring_script_automation_plan.md`, `docs/work-plans/20_oci_paid_tier_security_and_cost_guardrails_plan.md`  
**승인 정보**: 사용자 / 2026-02-28 / "21-05 계획부터 확정해서 진행하자"
**관련 트러블슈팅**: `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md`

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - OCI 콘솔(oci_computeagent namespace)에서 CPU/Memory/Disk/Network가 `No data` 상태.
  - 콘솔 메시지에 `Operating system might not be supported`가 표시됨(Ubuntu Minimal 이미지).
  - 현재 Grafana 대시보드는 트레이딩 지표 중심이라 인프라 상태(호스트/컨테이너 자원) 관측성이 부족함.
- 왜 즉시 대응이 필요했는지:
  - 실거래 전환 전, 리소스 병목/장애 징후를 조기에 탐지할 인프라 관측 체계가 필수.

## 1. 문제 요약
- 증상:
  - OCI Native Metrics 미수집(`No data`)으로 콘솔 기반 상태 판단 불가.
  - Grafana에서 CPU/RAM/Disk/Network/컨테이너 자원 추이를 통합 관측하기 어려움.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 장애 원인 분석 지연
  - 리스크: OOM/디스크 포화/컨테이너 재시작 반복 미탐지
  - 비용: 과도한 리소스 사용 시 사후 인지
- 재현 조건:
  - OCI Compute Agent 지표가 미활성 또는 OS 호환성 제한인 상태

## 2. 원인 분석
- 가설:
  - OCI Compute Agent 기반 지표가 현재 인스턴스 이미지/에이전트 상태와 맞지 않아 수집되지 않음.
- 조사 과정:
  - 콘솔 `No data` 확인
  - 로컬 SSH 명령(`uptime`, `free -h`, `docker stats`)은 정상 응답
- Root cause:
  - 콘솔 네이티브 메트릭 경로 의존만으로는 운영 관측성 보장이 어려움.

## 3. 대응 전략
- 단기 핫픽스:
  - 기존 24h 점검 스크립트(`check_24h_monitoring.sh`)에 인프라 요약 명령 사용을 지속.
- 근본 해결:
  - Prometheus + Grafana에 호스트/컨테이너 exporter를 추가해 운영 관측을 표준화.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 리소스 임계치 알람 규칙(CPU/Memory/Disk/Container Restart) 추가.

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **Prometheus 경로 확장 + Grafana 대시보드 분리** (인프라 관측 전용 대시보드 신설)

- 고려 대안:
  1) OCI 콘솔 메트릭만 사용
  2) Prometheus exporter(node-exporter, cadvisor) 추가 (채택)
  3) 상용 APM(외부 SaaS) 도입

- 대안 비교:
  1) OCI 콘솔만:
    - 장점: 추가 구성 최소
    - 단점: 현재 `No data` 상태로 신뢰 불가
  2) exporter 추가(채택):
    - 장점: 현재 스택과 자연스럽게 통합, Grafana에서 단일 관측 가능
    - 단점: Compose/대시보드/알람 구성 작업 필요
  3) 상용 APM:
    - 장점: 기능 풍부
    - 단점: 비용/복잡도 증가, 현재 단계 과투자

## 5. 구현/수정 내용 (예정)
- 변경 파일:
  1) `deploy/cloud/oci/docker-compose.prod.yml`
  2) `deploy/cloud/oci/monitoring/prometheus.yml`
  3) `deploy/cloud/oci/monitoring/grafana/provisioning/dashboards/provider.yaml` (필요 시)
  4) `deploy/monitoring/grafana-provisioning/dashboards/` 하위 대시보드 JSON (신규)
  5) `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
  6) `scripts/ops/check_24h_monitoring.sh`
  7) `docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md` (신규)

- 추가 서비스(예정):
  - `node-exporter` (호스트 CPU/Memory/Disk/Network)
  - `cadvisor` (컨테이너 CPU/Memory/FS/Restart 추이)

- 메트릭/패널 범위:
  1) 호스트: CPU%, Load, Memory%, Disk Usage%, Disk IO, Network RX/TX
  2) 컨테이너: CPU%, Memory%, Restart count, Network/Block I/O
  3) 앱 연계: bot up, API latency, decision count(기존 대시보드 연계)

## 6. 알람 규칙 설계(초안)
1) HostCPUHigh: 5분 평균 CPU > 85% for 10m  
2) HostMemoryHigh: Memory 사용률 > 90% for 10m  
3) HostDiskHigh: `/` 사용률 > 80% for 15m  
4) ContainerRestartBurst: 특정 컨테이너 restart 급증  
5) BotDown: 기존 `up{job="coinpilot-core"} == 0` 유지

## 7. 검증 기준
- 재현 케이스에서 해결 확인:
  1) Grafana 인프라 대시보드에서 호스트/컨테이너 시계열이 실제로 표시됨
  2) `No data` 경고 없이 24시간 이상 연속 수집
- 회귀 테스트:
  - 기존 bot/dashboard/prometheus/grafana 서비스 기동 영향 없음
- 운영 체크:
  - `scripts/ops/check_24h_monitoring.sh` 결과와 Grafana 수치가 크게 불일치하지 않는지 샘플 비교

## 8. 롤백
- 코드 롤백:
  - exporter 서비스/스크랩 타겟/대시보드 revert
- 운영 롤백:
  - exporter 컨테이너만 제거 후 기존 스택 유지
- 데이터/스키마 롤백:
  - 없음

## 9. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 정책/관측 기준 변경 시 Changelog 반영

## 10. 후속 조치
1) OCI 콘솔 메트릭 경로(Compute Agent) 복구 가능 여부는 별도 트랙으로 점검  
2) 인프라 대시보드와 앱 대시보드를 분리 운영(Ops/Trading)  
3) 실거래 전환 전 7일간 알람 오탐률 튜닝

## 11. 계획 변경 이력
- 2026-02-28: 1차 적용 후 Grafana 컨테이너 패널이 `No data`로 표시되는 이슈를 확인. cAdvisor `name` 라벨이 `/coinpilot-...` 형식인 환경을 반영해 대시보드 쿼리 정규식(`/?coinpilot-.*`) 보정 항목을 계획 범위에 추가.
- 2026-02-28: 추가 진단에서 cAdvisor가 루트 cgroup(`id="/"`)만 수집하는 현상을 확인. `cadvisor` 서비스 권한/마운트(`privileged`, `docker.sock`, `cgroup`, `kmsg`) 보강 및 `docker_only=false` 전환을 계획 범위에 추가.
- 2026-02-28: cAdvisor docker factory API 버전 불일치(1.41<1.44)로 Docker 라벨(`name`) 기반 필터가 불안정함을 확인. 컨테이너 패널 쿼리를 `id=/system.slice/docker-...scope` 기준으로 전환하는 보정 단계를 계획 범위에 추가.
- 2026-03-05: 컨테이너 패널 가독성 보강 범위를 추가. 범례를 `서비스명 우선 + ID fallback`(12자리) 방식으로 전환해 운영자가 `docker ps` 결과와 즉시 대응 가능하도록 한다.
- 2026-03-05: cAdvisor 시계열에 `container_label_*`이 비어 있는 환경을 확인해, 운영 설정을 `--docker_only=true --store_container_labels=true`로 전환해 서비스명 라벨 수집을 우선 복구하도록 계획 범위를 확장.
- 2026-03-05: 라벨 수집 경로가 계속 비어 있는 환경을 기준으로, `container-map`(docker ps→node-exporter textfile metric) 사이드카를 도입해 Grafana에서 서비스명 조인을 안정적으로 복구하는 단계(Phase 4)를 추가.
- 2026-03-05: `docker_only=true` 이후 cAdvisor `id`가 `/docker/<id>` 형식으로 바뀌는 케이스를 확인해, 대시보드 정규식을 `docker-`/`docker/` 동시 지원으로 보강하는 핫픽스를 범위에 추가.
- 2026-03-05: 최근 구간(Last 5m/15m) `No data` 재발 케이스를 확인해, `container-map` 조인 유지 조건에서 cAdvisor를 `docker_only=false`로 재조정하여 cgroup 기반 시계열 복구를 우선하도록 변경.
- 2026-03-05: cAdvisor 시계열이 `id="/"` 단일로 고착되는 환경을 확인해, 컨테이너 CPU/Memory/Restart 패널의 데이터 소스를 `coinpilot-container-map` 메트릭으로 전환하는 우회 전략(Phase 4-3)을 추가.
- 2026-03-05: OCI 운영 검증에서 `coinpilot_container_{display_info,cpu_percent,memory_working_set_bytes,restart_count}` count가 모두 `12`, `check_24h_monitoring.sh t1h`가 `FAIL:0/WARN:1`로 확인됨. 21-05는 `t24h` 연속성 확인 전까지 `in_progress` 유지.
- 2026-03-05: `coinpilot_container_memory_working_set_bytes`가 전 컨테이너 `0`으로 노출되는 회귀를 확인. `generate_container_display_map.sh`의 메모리 단위 변환을 busybox awk 호환 파서로 교체하고 stats/inspect 조회 매칭을 prefix-safe 방식으로 보강하는 핫픽스를 범위에 추가.
- 2026-03-05: `check_24h_monitoring.sh t24h` 결과 `FAIL:0/WARN:0` 확인. 21-05 main 작업을 완료(`done`)로 마감하고 README/체크리스트/결과 문서를 동기화.
