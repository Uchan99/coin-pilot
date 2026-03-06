# 21-07. OCI 로그 관측 체계 강화(Loki/Promtail/Grafana) 계획

**작성일**: 2026-03-06  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md`, `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`  
**승인 정보**: 사용자 / 2026-03-06 / "진행하자."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 21-05로 메트릭 관측은 안정화됐지만, 에러 원인 추적은 여전히 컨테이너 로그 수동 조회(`docker compose logs`) 의존도가 높다.
  - `coinpilot-core up=0` 같은 일시 이슈가 발생했을 때, 이벤트 시점 전후 로그 상관분석이 즉시 되지 않는다.
- 왜 즉시 대응이 필요한지:
  - 카나리(21-03), 비용 관측(21-04), 전략 핫픽스(29)가 동시에 진행 중이라 로그 기반 RCA 속도가 운영 안정성에 직접 영향.

## 1. 문제 요약
- 증상:
  - 장애/경고 발생 시 컨테이너별 로그를 개별 명령으로 수집해야 해 대응 시간이 늘어남.
  - 로그 보존/검색/알림 연계 기준이 표준화되어 있지 않음.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 장애 원인 확인 지연
  - 리스크: 일시 장애 재발 시 탐지/복구 시간 증가
  - 데이터: 사고 시점 로그 증빙 누락 가능성
  - 비용: 수동 조사 시간 증가(운영 피로도)
- 재현 조건:
  - `up` 경고, 응답 지연, AI 호출 에러 급증 등 단기 이슈가 발생하는 구간

## 2. 원인 분석
- 가설:
  - 메트릭 체계(Prometheus)는 갖춰졌으나 로그 체계(Loki/Promtail)가 없어 관측 3축(metrics/logs/alerts) 중 logs 축이 공백.
- 조사 과정:
  - 21-05 운영 재검증에서 메트릭/알림은 확인됐으나, 원인 분석은 수동 로그 확인으로 수행.
- Root cause:
  - 중앙 로그 저장/검색/라벨링 체계가 미도입 상태.

## 3. 대응 전략
- 단기 핫픽스:
  - 표준 로그 점검 명령(서비스별 `docker compose logs --since`)을 runbook에 고정.
- 근본 해결:
  - Loki + Promtail + Grafana Explore 연동으로 중앙 로그 수집/검색/알림 기반을 구축.
- 안전장치:
  - 로그 보존기간 제한(예: 7~14일)과 라벨 최소화로 저장소 폭증/고카디널리티 방지.

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **Prometheus(메트릭) + Loki(로그) + Grafana(단일 조회/알림)**

- 고려 대안:
  1) 현행 유지(`docker logs` 수동 조회)
  2) Loki/Promtail 도입(채택 예정)
  3) 외부 SaaS 로그 플랫폼 도입

- 대안 비교:
  1) 현행 유지:
    - 장점: 구현 비용 0
    - 단점: RCA 속도/재현성 저하
  2) Loki/Promtail:
    - 장점: 현 스택과 자연 통합, 비용/운영 복잡도 균형
    - 단점: 스토리지/보존 정책 설계 필요
  3) SaaS:
    - 장점: 고급 기능 풍부
    - 단점: 비용 증가, 데이터 외부 의존

## 5. 구현/수정 내용 (예정)
### Phase A. 로그 수집 경로 설계
1. Compose에 `loki`, `promtail` 서비스 추가 설계
2. promtail scrape 대상(coinpilot-* 컨테이너) 라벨 규칙 정의
3. 보존기간/용량 제한 정책 정의

### Phase B. Grafana 연동
1. Loki datasource provisioning
2. Explore/대시보드에서 서비스별 로그 조회 템플릿 추가
3. 공통 로그 쿼리(에러/타임아웃/예외) 스니펫 문서화

### Phase C. 알림/운영 절차
1. 로그 기반 알림 후보 정의(에러 burst, panic, traceback)
2. Discord 라우팅 연계 테스트
3. runbook + 24h 점검 스크립트 연동 지점 정의

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  1) `coinpilot-bot` 최근 15분 오류 로그를 Grafana Explore에서 조회 가능
  2) 특정 에러 키워드 검색 시 컨테이너/시각 라벨이 일관되게 표시
- 회귀 테스트:
  - 기존 Prometheus/Grafana/앱 서비스 기동 영향 없음
- 운영 체크:
  - 로그 수집 지연(ingest lag) 허용 범위 내(예: 30초~1분)
  - 디스크 사용량 증가율 관측 기준 정의

## 7. 롤백
- 코드 롤백:
  - Loki/Promtail 서비스 및 provisioning 파일 제거
- 데이터/스키마 롤백:
  - DB 스키마 변경 없음
- 운영 롤백:
  - 로그 체계만 비활성화하고 기존 메트릭 체계 유지

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 구현 후 결과 문서 작성
- PROJECT_CHARTER.md 업데이트 필요 여부:
  - 로그 관측을 운영 표준으로 확정하는 시점에 changelog 반영

## 9. 후속 조치
1. Phase C(로그 기반 알림 규칙) 구현 브랜치 분리 및 단계별 적용
2. 21-05 인프라 대시보드와 로그 대시보드 링크 연결
3. 21-03/21-04 운영 리포트에 로그 근거 필드 추가 검토

## 10. 계획 변경 이력
- 2026-03-06: 21-05 완료 이후 후속 과제로 로그 관측 체계 강화를 분리 계획으로 생성(Approval Pending).
- 2026-03-06: 사용자 승인으로 상태를 `Approved`로 전환하고, Phase A/B(Compose+Loki datasource+운영 점검 스크립트) 구현에 착수.
