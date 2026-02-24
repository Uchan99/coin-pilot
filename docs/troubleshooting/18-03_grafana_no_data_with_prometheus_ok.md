# 18-03. Grafana No data (Prometheus 데이터 존재) 트러블슈팅

작성일: 2026-02-23
상태: Resolved
관련 Plan:
- `docs/work-plans/18-07_grafana_no_data_query_stabilization_plan.md`
- `docs/work-plans/18-08_grafana_datasource_uid_alignment_plan.md`
- `docs/work-plans/18-09_grafana_trades_and_volatility_metrics_fix_plan.md`
관련 Result:
- `docs/work-result/18-07_grafana_no_data_query_stabilization_result.md`
- `docs/work-result/18-08_grafana_datasource_uid_alignment_result.md`
- `docs/work-result/18-09_grafana_trades_and_volatility_metrics_fix_result.md`

---

## 증상
- Grafana `CoinPilot Overview`에서 `Active Positions`, `API Latency (Avg)`, `Volatility Index`가 `No data`.
- 그러나 Prometheus query API에서는 동일 메트릭 값이 정상 반환됨.

## 원인
1) 대시보드 쿼리가 순간 공백에 취약(벡터 빈값 발생 시 No data)
2) Grafana datasource UID 고정 미설정으로 dashboard UID 참조(`prometheus`)와 드리프트 가능
3) Trades 패널이 process-local Counter 현재값에 의존하여 재시작 후 0으로 보이는 구조
4) Volatility 계산값은 Redis에 저장되지만 Prometheus gauge 업데이트 연결 누락

## 조치
1) 대시보드 쿼리 안정화
- `max(coinpilot_active_positions) or vector(0)`
- `(rate(coinpilot_api_latency_seconds_sum[5m]) / rate(coinpilot_api_latency_seconds_count[5m])) or vector(0)`
- `last_over_time(coinpilot_volatility_index[5m]) or vector(0)`

2) Datasource UID 정렬
- `deploy/monitoring/grafana-provisioning/datasources.yaml`에 `uid: prometheus` 추가

3) Grafana 재시작
- `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml restart grafana`

4) Trades/Volatility 메트릭 보정
- `coinpilot_trade_count_2d` Gauge 추가(DB 기준 최근 2일 FILLED 건수)
- Trades 패널 쿼리를 `max(coinpilot_trade_count_2d) or vector(0)`로 변경
- Volatility 모델에서 `metrics.volatility_index.set(volatility)` 실행
- bot startup 시 변동성 워밍업 1회 실행(`retrain_volatility_job`)

## 검증
- Prometheus targets: `bot:8000` health `up`
- Prometheus query에서 세 메트릭 값 반환 확인
- Grafana 새로고침 후 패널 값 표시 확인(사용자 UI 확인 필요)

## 재발 방지
- Grafana provisioned datasource는 UID 고정
- 핵심 패널 쿼리는 `or vector(0)`/window 함수 기반으로 작성
