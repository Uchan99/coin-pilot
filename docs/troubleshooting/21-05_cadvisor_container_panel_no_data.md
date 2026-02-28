# 21-05. cAdvisor 컨테이너 패널 No data 트러블슈팅 / 핫픽스

작성일: 2026-02-28
상태: Fixed
우선순위: P1
관련 문서:
- Plan: docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md
- Result: docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md
- Charter update 필요: NO

---

## 1. 트리거(왜 시작했나)
- 모니터링/로그/사용자 리포트로 관측된 내용:
  - `CoinPilot Infra Overview`에서 `Container CPU Usage`, `Container Memory Working Set`, `Container Restart Changes(24h)`가 `No data`로 표시됨.
  - 동시에 Prometheus target(`node-exporter`, `cadvisor`)은 `UP`.
  - `topk(10, container_memory_working_set_bytes{job="cadvisor"})` 결과가 `id="/"` 1개만 반환됨.
- 긴급도/영향:
  - 인프라 관측 기능 중 컨테이너 레이어가 비어 운영 판단 정확도가 저하됨.

---

## 2. 증상/영향
- 증상:
  - 호스트 패널은 표시되지만 컨테이너 패널만 `No data`.
- 영향(리스크/데이터/비용/운영):
  - 컨테이너별 CPU/메모리/재시작 추이를 즉시 파악하기 어려움.
- 발생 조건/재현 조건:
  - cAdvisor가 Docker 컨테이너 메트릭을 인식하지 못하고 루트 cgroup(`id="/"`)만 노출하는 환경.

---

## 3. 재현/관측 정보
- 재현 절차:
  1) Grafana `CoinPilot Infra Overview` 접속
  2) Scrape Target은 UP인데 컨테이너 3개 패널이 No data인지 확인
  3) Prometheus에서 `topk(10, container_memory_working_set_bytes{job="cadvisor"})` 실행 시 `id="/"`만 보이는지 확인
- 핵심 로그/에러 메시지:
  - 별도 에러 로그 없음
- 관련 지표/대시보드(있다면):
  - `up{job="cadvisor"} == 1` 상태

---

## 4. 원인 분석
- 가설 목록:
  1) Prometheus scrape 실패
  2) cAdvisor 권한/마운트 부족으로 컨테이너 메트릭 미수집
  3) Grafana PromQL 라벨 필터 불일치
- 조사 과정(무엇을 확인했는지):
  - `up{job="cadvisor"}` 확인 결과 정상
  - `/api/v1/targets`에서 cadvisor target health `up`
  - `topk(10, container_memory_working_set_bytes{job="cadvisor"})` 결과가 루트 cgroup 1개(`id="/"`)뿐임을 확인
  - 초기 쿼리(`name=~"coinpilot-.*"`)가 선행 `/` 환경에 취약함을 확인
- Root cause(결론):
  - 1차 원인: 대시보드 라벨 매칭 불일치(`name` 선행 `/` 미고려)
  - 2차 원인: cAdvisor 실행 권한/마운트 부족으로 컨테이너별 시계열이 노출되지 않고 루트 cgroup만 수집됨

---

## 5. 해결 전략
- 단기 핫픽스:
  - 컨테이너 패널 쿼리 정규식을 `name=~"/?coinpilot-.*"`로 확장
- 근본 해결:
  - `cadvisor` 서비스 권한/마운트 보강(`privileged`, `/var/run/docker.sock`, `/sys/fs/cgroup`, `/dev/kmsg`)으로 컨테이너별 시계열 수집 복원
- 안전장치(feature flag, rate limit, timeout/cooldown, circuit breaker 등):
  - `job="cadvisor"`를 명시해 오염 시계열 유입 최소화

---

## 6. 수정 내용
- 변경 요약:
  - 컨테이너 3개 패널 쿼리의 `name` 라벨 정규식 보정
  - cAdvisor 권한/마운트 보강 및 `docker_only=false` 전환
- 변경 파일:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md` (변경 이력 추가)
  - `docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md` (Phase 2 기록)
  - `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md` (본 문서)
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  - cadvisor 설정/쿼리를 이전 상태로 복원

---

## 7. 검증
- 실행 명령/절차:
  - `python3 -m json.tool deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json >/dev/null`
  - `docker compose --env-file .env -f deploy/cloud/oci/docker-compose.prod.yml up -d --force-recreate --no-deps cadvisor prometheus grafana`
  - `curl -sS -G http://127.0.0.1:9090/api/v1/query --data-urlencode 'query=topk(10, container_memory_working_set_bytes{job="cadvisor"})'`
  - Grafana 패널 시계열 확인
- 결과:
  - JSON 문법 검증 통과
  - 운영 반영 후 `topk(...container_memory_working_set_bytes...)`가 루트 cgroup 외 컨테이너 시계열을 반환해야 정상

- 운영 확인 체크:
  1) Grafana 컨테이너 패널 3개가 `No data`에서 시계열로 전환되는지 확인
  2) `scripts/ops/check_24h_monitoring.sh t1h` PASS 유지 확인

---

## 8. 재발 방지
- 가드레일(테스트/알림/검증 스크립트/권한/필터/타임아웃 등):
  - 신규 대시보드 패널은 배포 직후 실제 라벨 샘플 1회 교차 검증
- 문서 반영:
  - plan/result 업데이트 여부: YES
  - troubleshooting 링크 추가 여부: YES
  - PROJECT_CHARTER.md 변경(있다면): 21-05 후속 핫픽스 항목 changelog 반영

---

## 9. References
- `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`
- `docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md`
- `deploy/cloud/oci/docker-compose.prod.yml`
- `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`

## 10. 배운점
- 동일 metric이라도 환경(cgroup/런타임)에 따라 라벨/시계열 유무가 달라질 수 있어, 대시보드 쿼리와 수집기 권한을 함께 검증해야 한다.
- 트러블슈팅 문서에는 "증상-가설-검증-결론" 인과를 남겨야 재발 시 복구 시간이 줄어든다.
- 포트폴리오 관점에서는 "관측성 구축"보다 "관측성 누락을 탐지하고 원인별로 분리 해결한 과정"이 실무 역량을 더 잘 보여준다.
