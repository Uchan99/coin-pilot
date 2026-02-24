# 18-09. Grafana Trades/Volatility 메트릭 표시 보정 구현 결과

작성일: 2026-02-23
작성자: Codex (GPT-5)
관련 계획서: `docs/work-plans/18-09_grafana_trades_and_volatility_metrics_fix_plan.md`
상태: Verified
완료 범위: Phase 1
선반영/추가 구현: 있음(쿼리 안정화 보완)
관련 트러블슈팅: `docs/troubleshooting/18-03_grafana_no_data_with_prometheus_ok.md`

---

## 1. 개요
- 구현 범위 요약:
  - Trades 패널을 process-local counter 의존에서 DB-derived gauge 기반으로 전환.
  - Volatility 계산 결과를 Prometheus gauge에 실제 반영.
  - bot startup 시 변동성 워밍업 1회 실행 추가.
- 목표(요약):
  - Grafana에서 운영 해석 가능한 값(실제 최근 2일 체결/실제 변동성)을 표시.
- 이번 구현이 해결한 문제(한 줄):
  - 재시작/연결 누락으로 0에 고정되던 모니터링 값을 운영 데이터와 정렬했다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 Trades 메트릭 경로 보정
- 파일/모듈:
  - `src/utils/metrics.py`
  - `src/bot/main.py`
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-trades.json`
- 변경 내용:
  - `coinpilot_trade_count_2d` Gauge 신규 추가
  - bot loop에서 DB(`trading_history`) 기준 최근 2일 FILLED 건수 집계 후 gauge set
  - Trades 패널 쿼리를 `max(coinpilot_trade_count_2d) or vector(0)`로 변경
- 효과/의미:
  - bot 재시작 이후에도 최근 2일 체결 수가 안정적으로 표시됨

### 2.2 Volatility 메트릭 연결 복구
- 파일/모듈:
  - `src/analytics/volatility_model.py`
  - `src/bot/main.py`
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-overview.json`
- 변경 내용:
  - `update_volatility_state()`에서 `metrics.volatility_index.set(float(volatility))` 실행
  - bot startup에서 `retrain_volatility_job()` 1회 즉시 실행 추가
  - Overview volatility 쿼리를 `max(last_over_time(coinpilot_volatility_index[5m])) or vector(0)`로 보정
- 효과/의미:
  - 변동성 패널이 0 고정에서 해제되고, 최근 계산값이 즉시 노출됨

### 2.3 운영 반영
- 파일/모듈:
  - compose runtime
- 변경 내용:
  - `bot` 재빌드/재기동
  - `grafana` 재시작
- 효과/의미:
  - 수정 사항 즉시 반영

---

## 3. 변경 파일 목록
### 3.1 수정
1) `src/utils/metrics.py`
2) `src/bot/main.py`
3) `src/analytics/volatility_model.py`
4) `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-trades.json`
5) `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-overview.json`
6) `docs/troubleshooting/18-03_grafana_no_data_with_prometheus_ok.md`
7) `docs/work-plans/18-09_grafana_trades_and_volatility_metrics_fix_plan.md`

### 3.2 신규
1) `docs/work-result/18-09_grafana_trades_and_volatility_metrics_fix_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 코드/대시보드 쿼리 원복만 필요

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `jq . deploy/monitoring/grafana-provisioning/dashboards/coinpilot-trades.json >/dev/null`
  - `jq . deploy/monitoring/grafana-provisioning/dashboards/coinpilot-overview.json >/dev/null`
  - `python3 -m py_compile src/utils/metrics.py src/analytics/volatility_model.py src/bot/main.py`
- 결과:
  - 모두 통과

### 5.2 테스트/런타임 검증
- 실행 명령:
  - `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml up -d --build bot`
  - `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml restart grafana`
  - bot logs에서 변동성 워밍업 실행 확인
  - bot `/metrics`에서 `coinpilot_trade_count_2d`, `coinpilot_volatility_index` 확인
- 결과:
  - `coinpilot_trade_count_2d 4.0`
  - `coinpilot_volatility_index 0.0936...`
  - DB 최근 2일 FILLED count = 4와 일치

### 5.3 운영 확인
- Prometheus query 검증:
  - `max(coinpilot_trade_count_2d) or vector(0)` => `4`
  - `max(last_over_time(coinpilot_volatility_index[5m])) or vector(0)` => `0.0936...`

---

## 6. 배포/운영 확인 체크리스트(필수)
1) Grafana `CoinPilot Trades` 패널에서 `Total Trade Count`가 0이 아닌지 확인
2) Grafana `CoinPilot Overview`의 `Volatility Index`가 0 고정 해제됐는지 확인
3) 시간 범위를 `Last 2 days`로 놓고 값이 유지되는지 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 기간 집계(최근 2일 체결)는 DB 재계산 Gauge로 분리
  - 변동성은 계산 저장(Redis) + 관측(Prometheus) 동시 반영
- 고려했던 대안:
  1) 기존 counter 쿼리를 `increase`만으로 유지
  2) counter를 강제로 DB 값으로 보정(inc 루프)
  3) Grafana 패널만 수동 보정(코드 미수정)
- 대안 대비 실제 이점(근거/관측 포함):
  1) DB 기준 집계로 재시작 영향 제거
  2) metric wiring 복구로 volatility 실제값 노출
  3) 운영 화면 값과 DB 실측값 불일치 해소
- 트레이드오프(단점)와 보완/완화:
  1) loop마다 DB count 쿼리 1회 추가 -> 쿼리 단순화/인덱스 기반 조건 사용
  2) startup GARCH 1회 실행 비용 발생 -> 1회 워밍업으로 제한

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `src/analytics/volatility_model.py`: Redis/Prometheus 동시 반영 필요성, 실패 분리 처리
  2) `src/bot/main.py`: startup 변동성 워밍업 목적/실패 모드 설명
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 불변조건(invariants)
  - 실패 케이스 분리

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - Trades/Volatility 표시 이슈 동시 해결
- 변경/추가된 부분(왜 바뀌었는지):
  - Trades는 counter query 보정 대신 DB-derived gauge 방식으로 보강(재시작 안정성 강화)
- 계획에서 비효율적/오류였던 점(있다면):
  - 단순 PromQL 보정보다 metric source 보강이 더 효과적이었음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - Grafana 핵심 패널 값이 DB/실제 계산값과 일치하도록 보정 완료
- 후속 작업:
  1) 필요 시 `coinpilot_trade_count_7d` 등 기간별 gauge 확장
  2) Grafana 대시보드별 metric source(DB-derived vs process-local) 문서화

---

## 12. References
- `docs/work-plans/18-09_grafana_trades_and_volatility_metrics_fix_plan.md`
- `docs/troubleshooting/18-03_grafana_no_data_with_prometheus_ok.md`
- `src/utils/metrics.py`
- `src/bot/main.py`
- `src/analytics/volatility_model.py`
- `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-trades.json`
- `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-overview.json`
