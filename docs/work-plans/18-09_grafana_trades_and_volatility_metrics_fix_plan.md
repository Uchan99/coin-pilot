# 18-09. Grafana Trades/Volatility 메트릭 표시 보정 작업 계획

**작성일**: 2026-02-23  
**작성자**: Codex (GPT-5)  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  
**관련 트러블슈팅 문서**: `docs/troubleshooting/18-03_grafana_no_data_with_prometheus_ok.md`

---

## 0. 트리거(Why started)
- Grafana `CoinPilot Trades`에서 최근 2일 카운트가 0으로 보임.
- Grafana `Volatility Index`가 지속적으로 0으로 고정됨.

## 1. 문제 요약
- 증상:
  - Trades 패널 0 고정(실제 DB 체결 내역과 불일치)
  - Volatility 패널 0 고정
- 영향 범위(기능/리스크/데이터/비용):
  - 트레이딩 기능 자체 영향 없음
  - 운영 모니터링 해석 오류 가능성 증가
- 재현 조건:
  - bot 재시작 이후 counter 기반 패널 확인 시
  - 변동성 재학습 후에도 Prometheus gauge 미갱신 시

## 2. 원인 분석
- 가설:
  1) Trades 패널이 누적 counter 현재값만 읽어 재시작 후 0으로 보임
  2) 변동성 계산은 수행돼도 Prometheus gauge set이 누락됨
- 조사 과정:
  - DB `trading_history` 최근 2일 FILLED 건수 확인
  - bot `/metrics` 노출값 확인
  - `src/analytics/volatility_model.py` 메트릭 업데이트 경로 점검
- Root cause:
  - Trades 쿼리식 부적절(`coinpilot_trade_count_total` 단순 조회)
  - `metrics.volatility_index.set(volatility)` 코드가 주석 처리되어 연결 누락

## 3. 대응 전략
- 단기 핫픽스:
  - Trades 패널을 DB 기준 `coinpilot_trade_count_2d` Gauge 기반으로 변경
  - Volatility 모델에서 Prometheus gauge를 실제 갱신
- 근본 해결:
  - 기간 집계는 Counter 직접 해석 대신 DB 재계산 Gauge 병행
  - 계산 결과 저장(Redis) + 관측(Prometheus) 동시 갱신 표준화
- 안전장치:
  - startup 직후 1회 변동성 warm-up 학습 스케줄 추가로 0 고정 완화

## 4. 구현/수정 내용
- 변경 파일:
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-trades.json`
  - `src/utils/metrics.py`
  - `src/analytics/volatility_model.py`
  - `src/bot/main.py`
- DB 변경(있다면):
  - 없음
- 주의점:
  - GARCH 학습은 비용이 있으므로 warm-up은 1회(date trigger)만 실행

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - Last 2 days 범위에서 Trades 카운트가 DB 방향성과 일치
  - Volatility Index 패널에 0이 아닌 값 반영(데이터 충분 시)
- 회귀 테스트:
  - JSON/YAML 문법 및 Python compile 확인
- 운영 체크:
  - bot/grafana 재기동 후 대시보드 갱신 확인

## 6. 롤백
- 코드 롤백:
  - 각 파일 expr/metric update/warm-up job 원복
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 결과서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 원칙 변경 없음(구현 보정), 업데이트 불필요

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) Grafana 대시보드 metric 타입별 PromQL 가이드 문서화
  2) 메트릭 wiring 상태를 preflight 체크 항목으로 검토

## 9. Plan Change Log
- 2026-02-23:
  - Trades 패널 전략을 `increase(counter[$__range])`에서 `DB-derived gauge(coinpilot_trade_count_2d)`로 조정.
  - 이유: 프로세스 재시작/Counter 초기화 영향 없이 실제 체결 이력을 안정적으로 반영하기 위함.
