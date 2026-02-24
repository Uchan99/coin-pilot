# 18-07. Grafana No data 쿼리 안정화 작업 계획

**작성일**: 2026-02-23  
**작성자**: Codex (GPT-5)  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`

---

## 0. 트리거(Why started)
- Grafana Overview 패널(`Active Positions`, `API Latency (Avg)`, `Volatility Index`)에서 `No data`가 표시됨.
- Prometheus 실측값은 존재하여 시각화 계층 쿼리 안정화가 필요.

## 1. 문제 요약
- 증상:
  - 패널에 `No data` 간헐/상시 표시.
- 영향 범위(기능/리스크/데이터/비용):
  - 트레이딩 로직 영향 없음.
  - 모니터링 가시성 저하.
- 재현 조건:
  - 특정 시간 범위/표현식 평가 타이밍에서 시계열 벡터 공백 발생 시.

## 2. 원인 분석
- 가설:
  1) raw gauge/ratio 쿼리가 순간 벡터 공백을 허용해 패널이 No data로 렌더링.
- 조사 과정:
  - Prometheus API로 동일 metric 존재 확인.
  - 대시보드 쿼리식 확인.
- Root cause:
  - 패널 쿼리가 공백 구간 fallback(`or vector(0)`)과 window 기반 안전식이 부족.

## 3. 대응 전략
- 단기 핫픽스:
  - 3개 패널 쿼리를 fallback/rolling-window 기반 식으로 교체.
- 근본 해결:
  - 대시보드 핵심 패널 쿼리 표준(`or vector(0)`, `rate`, `last_over_time`) 적용.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 없음(시각화 계층 수정).

## 4. 구현/수정 내용
- 변경 파일:
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-overview.json`
- DB 변경(있다면):
  - 없음
- 주의점:
  - JSON 문법 유지, Grafana provisioning 경로와 동일 파일 수정.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - 3개 패널이 `No data` 대신 숫자/시계열을 표시.
- 회귀 테스트:
  - `jq` JSON 유효성 검사.
- 운영 체크:
  - Grafana 대시보드 새로고침 후 패널 값 확인.

## 6. 롤백
- 코드 롤백:
  - 3개 expr 원복.
- 데이터/스키마 롤백:
  - 없음.

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 결과서 작성.
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 정책 변경 없음, 업데이트 불필요.

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) Grafana 패널 쿼리 lint/check 스크립트 검토.
