# 21-08. Grafana Loki 로그 패널화 구현 결과

작성일: 2026-03-06
작성자: Codex
관련 계획서: docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md
상태: Done
완료 범위: Phase A + Phase B + Phase C + Phase D + Phase E + Phase F + Phase G (패널 반영/Runbook 정합화/OCI 런타임 검증/No data -> 0 보정/패널 설명 추가/임계치 기준 반영/Alert Rule 프로비저닝 코드화)
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - `coinpilot-infra` 대시보드에 Loki 로그 패널 5종 추가
  - runbook의 로그 정상 기준을 `service` 라벨 중심에서 `filename` ingest 쿼리 기준으로 정렬
  - 체크리스트에 21-08 완료 상태 반영
  - Promtail 오류/경고 패널 3종에 `or vector(0)` 보정 적용(빈 구간 `No data` 대신 `0`)
  - 대시보드 패널 13개에 한국어 description 추가(블록 의미/점검 포인트 내장)
  - 절대 기준이 유효한 패널 9개에 주의/위험 임계치(threshold) 반영
  - Grafana alert rule 7개를 provisioning YAML로 코드화하고 compose 마운트로 자동 로드 경로를 고정
- 해결한 문제(한 줄):
  - 로그 관측이 Explore 수동 조회에 머물던 상태를 대시보드 패널 기반 상시 관측 구조로 확장했다.
- 해결한 문제의 구체 정의(증상/영향/재현 조건):
  - 증상: Loki 로그는 수집되지만 운영자가 한 화면에서 ingest/error/warn를 즉시 파악하기 어려움
  - 영향: 탐지/분석 시작 시간 지연
  - 재현 조건: 로그 상태 확인 시 Explore 전환이 필요한 운영 구간

---

## 2. 구현 내용
### 2.1 Grafana 패널 추가
- 파일:
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
- 추가 패널:
  1) `Loki Ingest Volume (5m)`
  2) `Top Log Files by Volume (5m)`
  3) `Promtail Pipeline Errors (5m)`
  4) `Promtail Timestamp Too Old (15m)`
  5) `Promtail API Mismatch (5m)`
- 기타:
  - 대시보드 버전 `5 -> 9` 증가(Phase D `6 -> 7`, Phase E `7 -> 8`, Phase F `8 -> 9`)

### 2.2 Runbook 정합화
- 파일:
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- 변경 내용:
  - 로그 정상 기준을 `Loki service 라벨` 중심에서 `filename` ingest 쿼리 기준으로 변경
  - 패널 5종의 목적/해석 기준 추가
  - 주의/위험 임계치(호스트/컨테이너/로그 오류) 수치 기준 추가
  - `Loki/Pipeline quick check` 명령을 ingest 쿼리 기준으로 갱신

### 2.3 작업 추적 동기화
- 파일:
  - `docs/checklists/remaining_work_master_checklist.md`
  - `docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md`
- 변경 내용:
  - 계획서 승인 정보 반영(`Approved`)
  - OCI 검증 완료 후 체크리스트 상태를 `done`으로 전환

### 2.4 후속 보정(Phase D: No data -> 0)
- 파일:
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
- 변경 내용:
  - `Promtail Pipeline Errors (5m)` 쿼리 끝에 `or vector(0)` 추가
  - `Promtail Timestamp Too Old (15m)` 쿼리 끝에 `or vector(0)` 추가
  - `Promtail API Mismatch (5m)` 쿼리 끝에 `or vector(0)` 추가
- 목적:
  - 정상 구간에서 오류/경고 패널이 `No data`로 보이는 해석 혼선을 줄이고, 명시적으로 `0`을 노출

### 2.5 후속 보정(Phase E: 패널 설명 추가)
- 파일:
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
- 변경 내용:
  - `coinpilot-infra`의 13개 패널 전체에 `description` 필드 추가
  - 각 설명에 패널 의미, 정상 기준(예: 오류 패널 정상=0), 점검 포인트를 한국어로 명시
- 목적:
  - 운영자가 대시보드 내부에서 블록 의미를 즉시 이해하고, 오해 없이 대응 기준을 확인할 수 있게 함

### 2.6 후속 보정(Phase F: 임계치 기준 반영)
- 파일:
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
- 변경 내용:
  - 호스트/컨테이너/로그 오류 패널 등 절대 기준이 유효한 9개 패널에 threshold 추가 또는 보정
  - description에 주의/위험 기준(예: CPU 70/85, 메모리 75/90, 오류 1/5 등)을 명시
- 목적:
  - 대시보드 해석을 정성 판단에서 정량 기준 기반 운영으로 전환

### 2.7 후속 보정(Phase G: Alert Rule 프로비저닝 코드화)
- 파일:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/cloud/oci/monitoring/grafana/provisioning/alerting/coinpilot-infra-rules.yaml`
- 변경 내용:
  - Grafana provisioning 경로에 alerting 마운트를 추가:
    - `./monitoring/grafana/provisioning/alerting:/etc/grafana/provisioning/alerting:ro`
  - 인프라/로그 핵심 경보 7개를 코드로 고정:
    - `Coinpilot Core Down`
    - `Host CPU High`
    - `Host Memory High`
    - `Root Disk High`
    - `Promtail Pipeline Errors Detected`
    - `Promtail Timestamp Too Old High`
    - `Promtail API Mismatch Detected`
- 목적:
  - UI 수동 생성 없이 재배포 시 동일 alert rule을 자동 반영하고 변경 이력을 Git에서 추적

---

## 3. 변경 파일 목록
1) `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
2) `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
3) `docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md`
4) `docs/checklists/remaining_work_master_checklist.md`
5) `docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md`
6) `deploy/cloud/oci/docker-compose.prod.yml`
7) `deploy/cloud/oci/monitoring/grafana/provisioning/alerting/coinpilot-infra-rules.yaml`

---

## 4. DB/스키마 변경
- 없음

---

## 5. 검증 결과
### 5.1 정적 검증
- 실행 명령:
  - `jq empty deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `jq '.version, (.panels | length), ([.panels[] | select(.datasource.uid=="loki")] | length)' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `jq -r '.panels[] | select(.id==11 or .id==12 or .id==13) | .targets[0].expr' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `jq '[.panels[] | select((.description // "") != "")] | length' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `jq '[.panels[] | select(((.fieldConfig.defaults.thresholds.steps // []) | length) >= 2)] | length' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `rg -n 'Loki Ingest Volume|Top Log Files by Volume|Promtail Pipeline Errors|Promtail Timestamp Too Old|Promtail API Mismatch' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `python3 -c 'import yaml; yaml.safe_load(open("deploy/cloud/oci/monitoring/grafana/provisioning/alerting/coinpilot-infra-rules.yaml")); print("YAML_OK")'`
  - `rg -n 'provisioning/alerting|coinpilot-infra-rules.yaml|uid:' deploy/cloud/oci/docker-compose.prod.yml deploy/cloud/oci/monitoring/grafana/provisioning/alerting/coinpilot-infra-rules.yaml`
- 결과:
  - JSON 파싱 정상(`OK_JSON`)
  - 대시보드 버전: `9`
  - 전체 패널 수: `13`
  - Loki 패널 수: `5`
  - 패널 타이틀 5종 모두 존재 확인
  - 오류/경고 패널 3종 쿼리 모두 `or vector(0)` 포함 확인
  - description 적용 패널 수: `13/13`
  - threshold 적용 패널 수: `9/13`
  - alerting YAML 파싱 정상(`YAML_OK`)
  - compose에 Grafana alerting provisioning 마운트 1개 존재 확인
  - provisioning alert rule UID 7개(`cp-*`) 존재 확인

### 5.2 런타임/운영 검증
- OCI 검증 명령(사용자 실행):
  - `cd /opt/coin-pilot/deploy/cloud/oci`
  - `docker compose --env-file .env -f docker-compose.prod.yml up -d grafana loki promtail-targets promtail`
  - `scripts/ops/check_24h_monitoring.sh t1h`
  - `curl -sS -G http://127.0.0.1:3100/loki/api/v1/query --data-urlencode 'query=sum(count_over_time({filename=~"/targets/logs/coinpilot-.*\\.log"}[5m]))'`
  - Grafana `CoinPilot Infra Overview`에서 5개 패널 값/갱신 여부 확인
- 결과(2026-03-07, 사용자 실행 로그):
  - `scripts/ops/check_24h_monitoring.sh t1h` => `FAIL:0`, `WARN:1`
  - Loki ingest query => `187` (`sum(count_over_time({filename=~"/targets/logs/coinpilot-.*\\.log"}[5m]))`)
  - 로그 수집 파이프라인 항목:
    - Loki readiness: PASS
    - filename 라벨 로그 스트림 확인: PASS
    - promtail 전송 오류 키워드: PASS
    - promtail-targets 타깃 생성 오류 키워드: PASS

### 5.3 정량 증빙
- 측정 기간/표본:
  - 정적 구조 검증 1회 + OCI 운영 검증 1회(2026-03-07)
- 성공/실패 기준:
  - 성공: Loki 패널 5종이 JSON에 존재 + JSON 유효성 통과 + alerting YAML 유효성 통과 + `t1h FAIL=0` + ingest 쿼리 양수
  - 실패: JSON 파싱 오류 또는 패널 누락
- 출처:
  - `jq`, `rg`, `python3(yaml)` 명령 출력 + 사용자 운영 로그(`check_24h_monitoring.sh t1h`, Loki query)
- Before/After:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| `coinpilot-infra` 총 패널 수 | 8 | 13 | +5 | +62.5 |
| Loki datasource 패널 수 | 0 | 5 | +5 | N/A |
| 대시보드 버전 | 5 | 9 | +4 | +80.0 |
| Runbook 로그 정상 기준(`service` 중심 -> `filename` ingest 기준) | 미정렬 | 정렬 완료 | +1 정책 반영 | N/A |
| 오류/경고 패널 zero-fill(`or vector(0)`) 미적용 쿼리 수 | 3 | 0 | -3 | -100.0 |
| 패널 description 적용 수 | 0 | 13 | +13 | N/A |
| threshold 적용 패널 수 | 4 | 9 | +5 | +125.0 |
| provisioning alert rule 파일 수 | 0 | 1 | +1 | N/A |
| provisioning alert rule UID 수 | 0 | 7 | +7 | N/A |
| Grafana alerting provisioning 마운트 수 | 0 | 1 | +1 | N/A |
| `check_24h_monitoring.sh t1h` FAIL | 0 | 0 | 0 | 0.0 |
| `check_24h_monitoring.sh t1h` WARN | 2 | 1 | -1 | -50.0 |
| Loki ingest query(5m) | N/A | 187 | N/A | N/A |

- 정량 측정 불가 항목:
  - 해당 없음(OCI 런타임 검증 완료)

---

## 6. 설계/아키텍처 결정 리뷰
- 최종 선택:
  - 기존 `coinpilot-infra` 대시보드에 Loki 패널을 통합
- 고려 대안:
  1) Explore 수동 조회 유지
  2) 로그 전용 대시보드 신규 생성
  3) 기존 인프라 대시보드 통합(채택)
- 채택 이유:
  - 운영자가 메트릭/로그를 단일 화면에서 상관 분석 가능
  - 기존 운영 동선 유지
- 트레이드오프:
  - 패널 수 증가로 가독성 저하 가능
  - 완화: 핵심 KPI 5개로 제한하고 질의는 `filename` 기준으로 단순화

---

## 7. 결론 및 다음 단계
- 현재 상태:
  - 21-08은 패널 반영 + runbook 정렬 + OCI 런타임 검증(`FAIL:0`, ingest 양수) + 패널 설명/임계치 내장 + alert rule 프로비저닝 코드화를 충족해 `done`으로 마감한다.
- 다음 단계:
  1) Grafana 재기동 후 `Alerting > Alert rules`에서 provisioned 7개 규칙 로드 여부 확인
  2) 24h 운영 중 `Promtail Timestamp Too Old (15m)` 패널 추세와 `Promtail Timestamp Too Old High` 경보 상관관계를 주 1회 점검

---

## 8. References
- Plan: `docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md`
- Dashboard: `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
- Runbook: `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- Compose: `deploy/cloud/oci/docker-compose.prod.yml`
- Alerting Provisioning: `deploy/cloud/oci/monitoring/grafana/provisioning/alerting/coinpilot-infra-rules.yaml`

## 9. README 동기화 검증
- 수행 이유:
  - 21-08 메인 계획 완료(`done`)로 README 동기화가 필요함
- 반영 내용:
  - 운영 상태 날짜를 2026-03-07로 갱신
  - Grafana 로그 패널화(21-08 완료) 문구와 백로그 상태(`21-08 done`)를 반영
  - 패널 description/threshold 후속 보정 내용(운영 기준 내장)을 추가
  - alert rule provisioning 코드화(7개 규칙 + compose 마운트) 내용을 추가
- 검증 명령:
  - `rg -n "2026-03-07|21-08|Grafana 로그 패널화" README.md`
