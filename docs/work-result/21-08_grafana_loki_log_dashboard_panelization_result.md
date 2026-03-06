# 21-08. Grafana Loki 로그 패널화 구현 결과

작성일: 2026-03-06
작성자: Codex
관련 계획서: docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md
상태: Partial
완료 범위: Phase A + Phase B (패널 JSON 반영/Runbook 정합화), Phase C(OCI 런타임 검증) 대기
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - `coinpilot-infra` 대시보드에 Loki 로그 패널 5종 추가
  - runbook의 로그 정상 기준을 `service` 라벨 중심에서 `filename` ingest 쿼리 기준으로 정렬
  - 체크리스트에 21-08 착수 상태 반영
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
  - 대시보드 버전 `5 -> 6` 증가

### 2.2 Runbook 정합화
- 파일:
  - `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
- 변경 내용:
  - 로그 정상 기준을 `Loki service 라벨` 중심에서 `filename` ingest 쿼리 기준으로 변경
  - 패널 5종의 목적/해석 기준 추가
  - `Loki/Pipeline quick check` 명령을 ingest 쿼리 기준으로 갱신

### 2.3 작업 추적 동기화
- 파일:
  - `docs/checklists/remaining_work_master_checklist.md`
  - `docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md`
- 변경 내용:
  - 21-08 상태를 `in_progress`로 전환
  - 계획서 승인 정보 반영(`Approved`)

---

## 3. 변경 파일 목록
1) `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
2) `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
3) `docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md`
4) `docs/checklists/remaining_work_master_checklist.md`
5) `docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md`

---

## 4. DB/스키마 변경
- 없음

---

## 5. 검증 결과
### 5.1 정적 검증
- 실행 명령:
  - `jq empty deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `jq '.version, (.panels | length), ([.panels[] | select(.datasource.uid=="loki")] | length)' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
  - `rg -n 'Loki Ingest Volume|Top Log Files by Volume|Promtail Pipeline Errors|Promtail Timestamp Too Old|Promtail API Mismatch' deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
- 결과:
  - JSON 파싱 정상(`OK_JSON`)
  - 대시보드 버전: `6`
  - 전체 패널 수: `13`
  - Loki 패널 수: `5`
  - 패널 타이틀 5종 모두 존재 확인

### 5.2 런타임/운영 검증
- 상태:
  - 로컬 환경에서 Grafana/OCI 런타임 검증은 미수행
- OCI 검증 명령(사용자 실행):
  - `cd /opt/coin-pilot/deploy/cloud/oci`
  - `docker compose --env-file .env -f docker-compose.prod.yml up -d grafana loki promtail-targets promtail`
  - `scripts/ops/check_24h_monitoring.sh t1h`
  - `curl -sS -G http://127.0.0.1:3100/loki/api/v1/query --data-urlencode 'query=sum(count_over_time({filename=~"/targets/logs/coinpilot-.*\\.log"}[5m]))'`
  - Grafana `CoinPilot Infra Overview`에서 5개 패널 값/갱신 여부 확인

### 5.3 정량 증빙
- 측정 기간/표본:
  - 코드 반영 시점 1회(정적 구조 검증)
- 성공/실패 기준:
  - 성공: Loki 패널 5종이 JSON에 존재 + JSON 유효성 통과
  - 실패: JSON 파싱 오류 또는 패널 누락
- 출처:
  - `jq`, `rg` 명령 출력
- Before/After:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| `coinpilot-infra` 총 패널 수 | 8 | 13 | +5 | +62.5 |
| Loki datasource 패널 수 | 0 | 5 | +5 | N/A |
| 대시보드 버전 | 5 | 6 | +1 | +20.0 |
| Runbook 로그 정상 기준(`service` 중심 -> `filename` ingest 기준) | 미정렬 | 정렬 완료 | +1 정책 반영 | N/A |

- 정량 측정 불가 항목:
  - 항목: 패널 런타임 값 갱신/알림 반응성
  - 사유: OCI/Grafana 실환경 실행이 이 턴에서 불가
  - 대체 지표: 정적 패널 구성 수치(패널 수/쿼리 존재/JSON 유효성)
  - 추후 측정 계획: OCI에서 `t1h` + ingest 쿼리 + Grafana 패널 캡처로 Phase C 마감

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
  - 패널/문서 반영은 완료됐고, 21-08은 OCI 런타임 검증 전 단계(`in_progress`)다.
- 다음 단계:
  1) OCI에서 패널 값 갱신 및 쿼리 결과 검증
  2) 결과 문서에 런타임 정량치(패널 스냅샷/쿼리 값/경고 빈도) 추가 후 `done` 전환

---

## 8. References
- Plan: `docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md`
- Dashboard: `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
- Runbook: `docs/runbooks/18_wsl_oci_local_cloud_operations_master_runbook.md`
