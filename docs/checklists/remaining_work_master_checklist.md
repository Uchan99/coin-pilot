# Remaining Work Master Checklist

작성일: 2026-03-01  
최종 수정일: 2026-03-01  
목적: 우선순위 기준 남은 main 작업의 단일 추적 문서  
관련 계획: `docs/work-plans/25_remaining_work_master_checklist_and_agents_workflow_update_plan.md`

---

## 1) 운영 규칙
1. 이 문서는 "남은 작업"의 단일 소스다.
2. main 계획 문서가 생성/상태 변경/구현 완료되면 이 문서를 같은 커밋에서 갱신한다.
3. 상태 값은 `todo | in_progress | blocked | done`만 사용한다.
4. 항목이 `done`이 되려면 result 문서 링크와 검증 근거가 있어야 한다.

---

## 2) 우선순위 백로그 (Main)

| Priority | ID | 작업 | 상태 | 시작 조건 | 완료 조건 | 검증 명령/확인 | Plan | Result/TS |
|---|---|---|---|---|---|---|---|---|
| 1 | 21-05 | OCI 인프라 리소스 모니터링 | in_progress | exporter/Prometheus/Grafana 반영 완료 | 컨테이너 패널 표기 가독성 개선(서비스명 매핑 or 운영 해석 가이드 고정) 및 24h 관찰 완료 | `scripts/ops/check_24h_monitoring.sh t0 && scripts/ops/check_24h_monitoring.sh t1h` | `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md` | `docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md`, `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md` |
| 2 | 24 | 디스코드 모바일 조회 챗봇 | todo | 21-05 기본 모니터링 안정화 | `/수익률` 등 핵심 명령이 모바일 Discord에서 응답 | (예정) `curl` webhook 스모크 + Discord 응답 확인 | `docs/work-plans/24_discord_mobile_chatbot_query_plan.md` | (생성 예정) |
| 3 | 21-03 | AI Decision 카나리 실험 | todo | 24 최소 기능 반영 후 | 카나리 기간 동안 승인율/거절율/오류율/비용 비교 리포트 확보 | (예정) 카나리 기간 로그/DB 집계 쿼리 | `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md` | (생성 예정) |
| 4 | 21-04 | LLM 토큰/비용 관측 대시보드 | todo | 21-03 실험 데이터 구조 확정 | 모델별 토큰/비용 추이가 Grafana 또는 리포트로 확인 가능 | (예정) 메트릭/집계 테이블 확인 | `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md` | (생성 예정) |
| 5 | 22 | 기존 대시보드 가독성/실시간성 개선 | todo | 24/21-03 관측 요구사항 반영 | 탭별 stale 데이터 제거 + 핵심 카드/패널 가독성 개선 | (예정) UI 체크리스트 + 데이터 갱신 검증 | `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md` | (생성 예정) |
| 6 | 23 | Next.js 점진 이관 | todo | 22에서 확정된 정보구조/운영요건 확보 | 최소 핵심 화면의 병행 운영(기존 대비 기능 동등) | (예정) 기능 동등성 체크리스트 | `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md` | (생성 예정) |

---

## 3) 최근 업데이트 로그
- 2026-03-01: 단일 마스터 체크리스트 파일 생성(우선순위 1~6 초기 반영).
- 2026-03-01: 21-05 상태를 `in_progress`로 설정(기능은 동작, 컨테이너 패널 운영 가독성/안정화 후 마감 예정).

---

## 4) 다음 갱신 트리거
1. 새 main 계획 생성 시: 백로그 행 추가
2. 구현 시작 시: `todo -> in_progress`
3. 구현 완료 + 결과 문서 작성 시: `in_progress -> done`
4. 장애/차단 발생 시: `blocked` 전환 + troubleshooting 링크 추가
