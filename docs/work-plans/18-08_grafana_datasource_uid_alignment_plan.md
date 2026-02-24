# 18-08. Grafana Datasource UID 정렬 작업 계획

**작성일**: 2026-02-23  
**작성자**: Codex (GPT-5)  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/18-07_grafana_no_data_query_stabilization_plan.md`

---

## 0. 트리거(Why started)
- Prometheus에는 metric 값이 존재하나 Grafana Overview 패널은 계속 `No data`.

## 1. 문제 요약
- 증상:
  - Explore/Prometheus 값 확인 가능, Dashboard 패널은 No data 지속.
- 영향 범위(기능/리스크/데이터/비용):
  - 모니터링 가시성 저하.
- 재현 조건:
  - 대시보드에서 `uid: prometheus` datasource 참조 시.

## 2. 원인 분석
- 가설:
  1) 대시보드의 datasource uid(`prometheus`)와 실제 datasource uid 불일치
- 조사 과정:
  - dashboard JSON uid 참조 확인
  - datasource provisioning 파일 확인(고정 uid 미설정)
- Root cause:
  - datasource uid 고정값 미설정으로 환경별 uid 드리프트 가능

## 3. 대응 전략
- 단기 핫픽스:
  - datasource provisioning에 `uid: prometheus`를 명시하여 dashboard 참조와 정렬
- 근본 해결:
  - Grafana provisioned datasource에 UID 고정 정책 적용
- 안전장치:
  - restart 후 대시보드 재로딩 확인

## 4. 구현/수정 내용
- 변경 파일:
  - `deploy/monitoring/grafana-provisioning/datasources.yaml`
- DB 변경(있다면):
  - 없음
- 주의점:
  - Grafana 볼륨 상태에 따라 기존 계정/설정은 유지됨

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - Overview 3개 패널 `No data` 해소
- 회귀 테스트:
  - YAML 문법 확인
- 운영 체크:
  - grafana 재시작 후 새로고침

## 6. 롤백
- 코드 롤백:
  - uid 라인 제거
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서/결과서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 정의 변경 없음

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) Grafana provisioning 검증 체크리스트에 UID 항목 추가
