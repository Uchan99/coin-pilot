# 21-08. Grafana Loki 로그 패널화 계획

**작성일**: 2026-03-06  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/21-07_oci_log_observability_loki_promtail_plan.md`, `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`  
**승인 정보**: 사용자 / 2026-03-06 / "구현 시작해줘."
**추가 승인 정보(후속)**: 사용자 / 2026-03-07 / "진행해줘."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 21-07에서 Loki/Promtail 수집 파이프라인은 안정화(`t1h FAIL:0`, Loki ingest 양수)됐지만, 로그 관측은 현재 Grafana Explore 중심의 수동 조회 비중이 높다.
  - 운영자가 `timestamp too old`, promtail 전송 오류, 서비스별 로그 유입량을 대시보드 패널에서 즉시 확인하기 어렵다.
- 왜 즉시 대응이 필요한지:
  - 메트릭(21-05)과 로그(21-07)를 같은 운영 대시보드 레벨로 맞춰야 장애 탐지/원인분석 시간이 단축된다.

## 1. 문제 요약
- 증상:
  - 로그 관측은 가능하지만, 운영 대시보드에서 핵심 로그 KPI가 패널화되어 있지 않아 조회 절차가 길다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 경고 발생 시 탐지 지연
  - 리스크: 이슈 재발 구간의 초기 대응 시간 증가
  - 데이터: 로그 유입 이상을 늦게 인지할 가능성
  - 비용: 수동 점검/조사 공수 증가
- 재현 조건:
  - Prometheus 패널은 정상이나, Loki 관련 상태 확인이 필요할 때 Explore를 별도 실행해야 하는 모든 운영 구간

## 2. 원인 분석
- 가설:
  1) Loki datasource 연결만 완료되고 운영 KPI 패널이 정의되지 않았다.
  2) `service` 라벨 안정성이 환경별로 달라 패널 기준 라벨(`filename` fallback)이 정리되지 않았다.
  3) 경고 성격 로그(`timestamp too old`)와 장애성 로그를 구분하는 시각화 기준이 부재하다.
- 조사 과정:
  - 21-07 결과 문서 기준으로 `t1h` PASS/WARN 기준과 Loki query 기준을 확인.
  - 운영 검증에서 ingest 수치(`1362`)는 확보됐으나 패널 기반 상시 관측 기준은 부재함을 확인.
- Root cause:
  - “수집 파이프라인 구축”까지 완료됐고, “운영 대시보드 표준 패널 정의”가 미완료인 상태.

## 3. 대응 전략
- 단기 핫픽스:
  - `coinpilot-infra` 대시보드에 Loki 핵심 패널 4~6개를 먼저 추가해 운영자가 한 화면에서 메트릭+로그를 함께 확인할 수 있게 한다.
- 근본 해결:
  - 로그 패널 표준 쿼리/임계치/운영 해석 가이드를 runbook + 점검 스크립트 기준과 정합화한다.
- 안전장치:
  - `service` 라벨 단독 의존 금지, `filename` 라벨 기반 fallback 쿼리를 기본 채택
  - 경고성 로그와 장애성 로그를 분리 시각화(경고가 FAIL처럼 보이지 않도록 구분)

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **기존 `coinpilot-infra` 대시보드에 Loki 패널을 병행 추가** (메트릭+로그 통합 운영 화면)

- 고려 대안:
  1) Grafana Explore 수동 조회 유지
  2) 별도 로그 전용 대시보드 신규 생성
  3) 기존 인프라 대시보드(`coinpilot-infra`)에 로그 패널 통합 (채택 예정)

- 대안 비교:
  1) 수동 조회 유지:
    - 장점: 구현 0
    - 단점: 운영 대응 속도 개선 없음
  2) 로그 전용 대시보드:
    - 장점: 로그 집중도 높음
    - 단점: 운영자가 화면을 추가 이동해야 하며 메트릭/로그 상관분석에 불리
  3) 기존 인프라 대시보드 통합:
    - 장점: 단일 화면 상관분석 가능, 기존 운영 습관 유지
    - 단점: 패널 수 증가로 가독성 저하 가능(레이아웃 최적화 필요)

## 5. 구현/수정 내용 (예정)
### Phase A. 패널 설계/추가
1. 대상 파일: `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-infra.json`
2. 추가 패널(초안):
  - Loki Ingest Volume(5m): `sum(count_over_time({filename=~"/targets/logs/coinpilot-.*\\.log"}[5m]))`
  - Promtail Error Burst(5m): `sum(count_over_time({filename="/targets/logs/coinpilot-promtail.log"} |= "level=error"[5m]))`
  - Timestamp Too Old Warning(15m): `sum(count_over_time({filename="/targets/logs/coinpilot-promtail.log"} |= "timestamp too old"[15m]))`
  - Service/File Top Talker(5m): `topk(5, sum by (filename) (count_over_time({filename=~"/targets/logs/coinpilot-.*\\.log"}[5m])))`
  - Recent Error Logs(로그 패널): `{"filename"="/targets/logs/coinpilot-promtail.log"} |= "error"`

### Phase B. 운영 기준 정합화
1. `scripts/ops/check_24h_monitoring.sh t1h`의 성공 기준과 패널 임계치 문구 정렬
2. runbook에 패널별 해석 기준 추가(정상/주의/장애)

### Phase C. 검증/문서화
1. OCI에서 패널 값 스크린샷/쿼리 결과 수집
2. 결과 문서(`docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md`) 작성

### Phase D. 시각화 보정(No data -> 0)
1. 대상 패널:
  - `Promtail Pipeline Errors (5m)`
  - `Promtail Timestamp Too Old (15m)`
  - `Promtail API Mismatch (5m)`
2. 구현:
  - 각 쿼리에 `or vector(0)`를 적용해 정상 구간 `No data` 대신 `0`이 표기되도록 보정

### Phase E. 패널 설명(Description) 추가
1. 대상:
  - `coinpilot-infra` 대시보드 전체 패널(13개)
2. 구현:
  - 각 패널에 한국어 운영 설명(의미/정상 기준/점검 포인트)을 `description`으로 추가
3. 의도:
  - 운영자가 패널 의미를 UI 내부에서 즉시 확인할 수 있게 해 해석 오차를 줄임

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) `coinpilot-infra`에서 Loki 패널 값이 0 이상으로 갱신되는지 확인
  2) Promtail 에러 발생 시 해당 패널이 동시에 반응하는지 확인
- 회귀 테스트:
  - 기존 Prometheus 인프라 패널(`CPU/Memory/Restart/UP`) 값 변경 없음
- 운영 체크:
  - `scripts/ops/check_24h_monitoring.sh t1h` 결과와 패널 상태가 모순되지 않아야 함

## 7. 롤백
- 코드 롤백:
  - `coinpilot-infra.json`에서 Loki 패널 블록 제거 후 Grafana 재로드
- 데이터/스키마 롤백:
  - 없음

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 승인 후 구현 시 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 정책/임계치 변경이 발생하면 changelog 반영
  - 단순 패널 추가만으로 정책 변경이 없으면 Charter 수정 생략

## 9. 후속 조치
1. 로그 패널 기반 Discord 알림 규칙(빈도/임계치) 정식화
2. 21-03/21-04 운영 리포트에 로그 패널 링크 추가 검토

## 10. 계획 변경 이력
- 2026-03-06: 21-07 완료 이후 후속 과제로 Grafana Loki 로그 패널화 계획 신규 생성(Approval Pending).
- 2026-03-06: 사용자 승인으로 상태를 `Approved`로 전환하고, `coinpilot-infra` Loki 패널 추가 구현에 착수.
- 2026-03-07: 사용자 요청("No data 대신 0 표기")에 따라 Phase D 후속 보정 범위를 추가. Promtail 오류/경고 3개 패널 쿼리에 `or vector(0)`를 적용해 빈 구간을 0으로 시각화하도록 조정.
- 2026-03-07: 사용자 요청("진행해줘") 승인에 따라 Phase E(패널 설명 추가)를 범위에 포함. `coinpilot-infra` 13개 패널에 한국어 description을 추가해 운영 해석 가이드를 UI 내부로 통합.
