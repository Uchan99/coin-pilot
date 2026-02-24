# 18-07. Grafana No data 쿼리 안정화 구현 결과

작성일: 2026-02-23
작성자: Codex (GPT-5)
관련 계획서: `docs/work-plans/18-07_grafana_no_data_query_stabilization_plan.md`
상태: Verified
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - Overview 대시보드 3개 패널 쿼리를 fallback/rolling-window 방식으로 교체.
- 목표(요약):
  - `No data` 표시를 줄이고 항상 관측 가능한 값(최소 0) 제공.
- 이번 구현이 해결한 문제(한 줄):
  - Prometheus 데이터가 있어도 Grafana가 `No data`로 보이던 현상을 완화했다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 Overview 패널 쿼리 안정화
- 파일/모듈:
  - `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-overview.json`
- 변경 내용:
  - `coinpilot_active_positions` -> `max(coinpilot_active_positions) or vector(0)`
  - `coinpilot_api_latency_seconds_sum / coinpilot_api_latency_seconds_count` -> `(rate(coinpilot_api_latency_seconds_sum[5m]) / rate(coinpilot_api_latency_seconds_count[5m])) or vector(0)`
  - `coinpilot_volatility_index` -> `last_over_time(coinpilot_volatility_index[5m]) or vector(0)`
- 효과/의미:
  - 빈 벡터 구간에서도 패널이 0 또는 최근값으로 표시되어 운영 가시성이 개선.

### 2.2 런타임 반영
- 파일/모듈:
  - Grafana 컨테이너
- 변경 내용:
  - `grafana` 서비스 재시작으로 provisioning 파일 재로드
- 효과/의미:
  - 수정 내용 즉시 반영

---

## 3. 변경 파일 목록
### 3.1 수정
1) `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-overview.json`

### 3.2 신규
1) `docs/work-plans/18-07_grafana_no_data_query_stabilization_plan.md`
2) `docs/work-result/18-07_grafana_no_data_query_stabilization_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `jq . deploy/monitoring/grafana-provisioning/dashboards/coinpilot-overview.json >/dev/null`
- 결과:
  - JSON 유효성 통과

### 5.2 테스트 검증
- 실행 명령:
  - N/A (대시보드 쿼리 변경)
- 결과:
  - N/A

### 5.3 런타임/운영 반영 확인(선택)
- 실행 명령:
  - `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml restart grafana`
  - `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml ps grafana`
- 결과:
  - grafana 서비스 `Up`

---

## 6. 배포/운영 확인 체크리스트(필수)
1) Grafana `CoinPilot Overview` 새로고침
2) `Active Positions`, `API Latency (Avg)`, `Volatility Index` 패널 값 확인
3) 시간 범위 `Last 6 hours`로 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - PromQL 레벨에서 fallback/rolling-window를 적용해 시각화 안정성 확보
- 고려했던 대안:
  1) Grafana 패널 옵션만 변경(Null value 정책)
  2) 애플리케이션에서 별도 더미 메트릭 주입
  3) 현재 쿼리 유지
- 대안 대비 실제 이점(근거/관측 포함):
  1) Prometheus 원천 쿼리 자체가 안정화되어 패널 종속성 감소
  2) 코드 영향 범위가 대시보드 JSON 1개로 제한
  3) 운영 반영이 빠름
- 트레이드오프(단점)와 보완/완화:
  1) 0 fallback이 진짜 결측과 0을 구분하지 못할 수 있음 -> 필요 시 별도 health 패널 추가
  2) API Latency는 5분 rate 기준이라 저빈도 구간에서 0으로 보일 수 있음 -> 윈도우 조정 가능

---

## 8. 한국어 주석 반영 결과(필수)
- 코드 로직 변경이 아닌 대시보드 쿼리 변경이라 주석 추가 없음

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 3개 패널 쿼리 변경, JSON 검증, 런타임 반영 완료
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - Overview 핵심 패널의 `No data` 발생 가능성을 낮추는 안정화 반영 완료
- 후속 작업:
  1) 필요 시 `No data` vs `0` 구분용 별도 health 패널 추가

---

## 12. References
- `docs/work-plans/18-07_grafana_no_data_query_stabilization_plan.md`
- `deploy/monitoring/grafana-provisioning/dashboards/coinpilot-overview.json`
