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
- 긴급도/영향:
  - 인프라 관측 기능 중 컨테이너 레이어가 비어 운영 판단 정확도가 저하됨.

---

## 2. 증상/영향
- 증상:
  - 호스트 패널은 표시되지만 컨테이너 패널만 `No data`.
- 영향(리스크/데이터/비용/운영):
  - 컨테이너별 CPU/메모리/재시작 추이를 즉시 파악하기 어려움.
- 발생 조건/재현 조건:
  - cAdvisor metric `name` 라벨 값이 `/coinpilot-bot`처럼 선행 `/`를 포함하는 환경.

---

## 3. 재현/관측 정보
- 재현 절차:
  1) Grafana `CoinPilot Infra Overview` 접속
  2) Scrape Target은 UP인데 컨테이너 3개 패널이 No data인지 확인
- 핵심 로그/에러 메시지:
  - 별도 에러 로그 없음
- 관련 지표/대시보드(있다면):
  - `up{job="cadvisor"} == 1` 상태

---

## 4. 원인 분석
- 가설 목록:
  1) Prometheus scrape 실패
  2) cAdvisor 컨테이너 이상
  3) Grafana PromQL 라벨 필터 불일치
- 조사 과정(무엇을 확인했는지):
  - `up{job="cadvisor"}` 확인 결과 정상
  - `/api/v1/targets`에서 cadvisor target health `up`
  - 대시보드 쿼리 확인 결과 `name=~"coinpilot-.*"`로 고정
- Root cause(결론):
  - 환경별로 cAdvisor `name` 라벨이 `/coinpilot-...` 형태여서 정규식이 매칭되지 않음.

---

## 5. 해결 전략
- 단기 핫픽스:
  - 컨테이너 패널 쿼리 정규식을 `name=~"/?coinpilot-.*"`로 확장
- 근본 해결:
  - 대시보드 쿼리를 단일 라벨 형태에 고정하지 않고 호환 가능한 패턴으로 유지
- 안전장치(feature flag, rate limit, timeout/cooldown, circuit breaker 등):
  - `image!=""` 조건을 함께 적용해 cgroup 루트/잡음 시계열 제외

---

## 6. 수정 내용
- 변경 요약:
  - 컨테이너 3개 패널 쿼리의 `name` 라벨 정규식 보정
- 변경 파일:
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md` (변경 이력 추가)
  - `docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md` (Phase 2 기록)
  - `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md` (본 문서)
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  - 쿼리 정규식을 기존 값(`coinpilot-.*`)으로 복원

---

## 7. 검증
- 실행 명령/절차:
  - `python3 -m json.tool deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json >/dev/null`
  - OCI 반영 후 Grafana 패널 시계열 확인
- 결과:
  - JSON 문법 검증 통과
  - 운영 반영 전(로컬) 기준 문법 검증만 완료

- 운영 확인 체크:
  1) Grafana 컨테이너 패널 3개가 `No data`에서 시계열로 전환되는지 확인
  2) `scripts/ops/check_24h_monitoring.sh t1h` PASS 유지 확인

---

## 8. 재발 방지
- 가드레일(테스트/알림/검증 스크립트/권한/필터/타임아웃 등):
  - 신규 대시보드 패널은 배포 직후 실제 라벨 샘플로 1회 교차 검증
- 문서 반영:
  - plan/result 업데이트 여부: YES
  - troubleshooting 링크 추가 여부: YES
  - PROJECT_CHARTER.md 변경(있다면): 없음

---

## 9. References
- `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`
- `docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md`
- `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`

## 10. 배운점
- 동일 metric이라도 환경(cgroup/런타임)에 따라 라벨 모양이 달라질 수 있어, 초기 대시보드 설계는 라벨 호환성을 고려해야 한다.
- 트러블슈팅 문서에는 "증상-가설-검증-결론"의 인과를 남기는 것이 재발 방지에 가장 효과적이다.
- 포트폴리오 관점에서는 "관측성 구축" 자체보다 "관측성 오탐/누락을 빠르게 복구한 과정"이 실무 역량을 더 잘 보여준다.
