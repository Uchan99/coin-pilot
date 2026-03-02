# Remaining Work Master Checklist

작성일: 2026-03-01  
최종 수정일: 2026-03-02  
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
| 1 | 27 | CI 파이프라인 의존성 충돌/테스트 환경변수 복구 | in_progress | main merge 후 CI 실패 재현 로그 확보 | `security`/`test` 잡 모두 성공(의존성 충돌 제거 + DB env 누락 제거 + pip-audit known vulnerability 해소) | `DB_PASSWORD=... DATABASE_URL=... .venv/bin/python -m pytest tests/utils/test_metrics.py tests/analytics/ tests/agents/` 통과 + `pip-audit -r requirements.txt`/`pip-audit -r requirements-bot.txt` 통과 + GitHub Actions 재확인 | `docs/work-plans/27_ci_pipeline_dependency_and_test_env_fix_plan.md`, `docs/work-plans/27-01_bandit_findings_and_security_artifact_reliability_fix_plan.md`, `docs/work-plans/27-02_pip_audit_known_vulnerability_remediation_plan.md`, `docs/work-plans/27-03_backend_agent_vuln_remediation_plan.md` | `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md`, `docs/troubleshooting/27_ci_dependency_conflict_and_test_env_missing.md`, `docs/troubleshooting/27-01_bandit_xml_and_bind_all_interfaces_findings.md`, `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md` |
| 2 | 21-05 | OCI 인프라 리소스 모니터링 | in_progress | exporter/Prometheus/Grafana 반영 완료 | 컨테이너 패널 표기 가독성 개선(서비스명 매핑 or 운영 해석 가이드 고정) 및 24h 관찰 완료 | `scripts/ops/check_24h_monitoring.sh t0 && scripts/ops/check_24h_monitoring.sh t1h` | `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md` | `docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md`, `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md` |
| 3 | 24 | 디스코드 모바일 조회 챗봇 | done | 21-05 기본 모니터링 안정화 | `/positions`, `/pnl`, `/status`, `/risk`, `/ask` 정상 응답 + role/channel 제한 정책 검증 완료 | `docker compose --profile discord-bot ... up -d --build bot discord-bot` + Discord slash command 수동 확인(허용/차단 케이스 포함) | `docs/work-plans/24_discord_mobile_chatbot_query_plan.md` | `docs/work-result/24_discord_mobile_chatbot_query_result.md`, `docs/troubleshooting/24_mobile_visibility_gap_discord_query_need.md`, `docs/troubleshooting/24-01_discord_role_nonetype_guard_fix.md`, `docs/troubleshooting/24-02_mobile_api_500_missing_psycopg2.md` |
| 4 | 21-03 | AI Decision 카나리 실험 | todo | 24 최소 기능 반영 후 | 카나리 기간 동안 승인율/거절율/오류율/비용 비교 리포트 확보 | (예정) 카나리 기간 로그/DB 집계 쿼리 | `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md` | (생성 예정) |
| 5 | 21-04 | LLM 토큰/비용 관측 대시보드 | todo | 21-03 실험 데이터 구조 확정 | 모델별 토큰/비용 추이가 Grafana 또는 리포트로 확인 가능 | (예정) 메트릭/집계 테이블 확인 | `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md` | (생성 예정) |
| 6 | 22 | 기존 대시보드 가독성/실시간성 개선 | todo | 24/21-03 관측 요구사항 반영 | 탭별 stale 데이터 제거 + 핵심 카드/패널 가독성 개선 | (예정) UI 체크리스트 + 데이터 갱신 검증 | `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md` | (생성 예정) |
| 7 | 23 | Next.js 점진 이관 | todo | 22에서 확정된 정보구조/운영요건 확보 | 최소 핵심 화면의 병행 운영(기존 대비 기능 동등) | (예정) 기능 동등성 체크리스트 | `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md` | (생성 예정) |
| 8 | 26 | README 최신 운영 상태 반영 개편 | done | 문서 드리프트 확인 | README 기준 실행/운영 안내가 Charter/현재 배포 구조와 정합 | `rg -n \"PROJECT_CHARTER|check_24h_monitoring|discord-bot\" README.md` + README 링크 경로 존재 점검 | `docs/work-plans/26_readme_current_state_refresh_plan.md` | `docs/work-result/26_readme_current_state_refresh_result.md` |

---

## 3) 최근 업데이트 로그
- 2026-03-01: 단일 마스터 체크리스트 파일 생성(우선순위 1~6 초기 반영).
- 2026-03-01: 21-05 상태를 `in_progress`로 설정(기능은 동작, 컨테이너 패널 운영 가독성/안정화 후 마감 예정).
- 2026-03-01: 24 상태를 `in_progress`로 전환(사용자 승인 후 구현 착수).
- 2026-03-01: 24 구현 코드/결과 문서 작성 완료, 운영 Discord 수동 검증 단계로 유지(`in_progress`).
- 2026-03-02: 24-01 운영 핫픽스(`NoneType role.id`) 트러블슈팅 링크 추가.
- 2026-03-02: 24-02 운영 핫픽스(`/api/mobile/positions` 500, psycopg2 누락) 트러블슈팅 링크 추가.
- 2026-03-02: 24 상태를 `done`으로 전환(Discord 명령 정상 응답 + role/channel 허용/차단 정책 검증 완료).
- 2026-03-02: 26 신규 main 계획 등록(README 최신 운영 상태 반영 개편, `todo`).
- 2026-03-02: 26 구현 완료 및 결과 문서 연결(`done`).
- 2026-03-02: 27 신규 main 계획 등록(CI 파이프라인 복구, `todo`).
- 2026-03-02: 27 구현 완료 및 결과/트러블슈팅 문서 연결(`done`).
- 2026-03-02: 27 후속 이슈(Bandit B314/B104 + security artifact 경고)로 상태를 `in_progress`로 재전환, 27-01 하위 계획 연결.
- 2026-03-02: 27-01 후속 핫픽스 반영(B314/B104 제거 + security artifact 가드) 후 `27`을 `done`으로 재전환.
- 2026-03-02: 27 후속 이슈(pip-audit known vulnerabilities fail)로 상태를 `in_progress`로 재전환, 27-02 하위 계획/트러블슈팅 연결.
- 2026-03-02: 27-02 1차 조치 반영(주요 의존성 상향 + pip-audit 상세 요약 게이트 추가), GitHub Actions 재검증 대기.
- 2026-03-02: 27-02 2차 조치 반영(상향 불가 CVE allowlist 파일 도입 + ignored/blocking 분리 출력), GitHub Actions security 재검증 대기.
- 2026-03-02: 27-03 하위 계획 추가(백엔드/에이전트 취약점 우선 해소, `f27` 브랜치 + WSL 실험, 승인 대기).
- 2026-03-02: 27-03 승인 후 착수, Phase A 매핑 및 Phase B 1차(`langgraph` core/bot 정렬, `pillow` 직접 핀 제거) 반영.
- 2026-03-02: 27-03 보강 반영, CI security에서 `pip-audit` 개별 step annotation 에러를 제거하고 최종 요약 step 단일 게이트로 판정하도록 조정.
- 2026-03-02: 27-03 Phase C 1차 반영(`langchain` 직접 의존 제거, `rag_agent` 수동 체인 전환, `test_rag_agent.py` 추가) 및 로컬 회귀 테스트 `67 passed` 확인.

---

## 4) 다음 갱신 트리거
1. 새 main 계획 생성 시: 백로그 행 추가
2. 구현 시작 시: `todo -> in_progress`
3. 구현 완료 + 결과 문서 작성 시: `in_progress -> done`
4. 장애/차단 발생 시: `blocked` 전환 + troubleshooting 링크 추가
