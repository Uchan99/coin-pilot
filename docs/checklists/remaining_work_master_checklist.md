# Remaining Work Master Checklist

작성일: 2026-03-01  
최종 수정일: 2026-03-10  
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
| 1 | 21-03 | AI Decision 카나리 실험 | in_progress | 24 최소 기능 반영 후 | 카나리 기간 동안 승인율/거절율/오류율/비용 비교 리포트 확보 | `scripts/ops/ai_decision_canary_report.sh 24` + `agent_decisions.model_used` 모델 혼재 확인 | `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md` | `docs/work-result/21-03_ai_decision_model_canary_experiment_result.md`, `docs/troubleshooting/21-06_ai_canary_env_injection_and_observability_gap.md` |
| 2 | 21-04 | LLM 토큰/비용 관측 대시보드 | blocked | 21-03 실험 데이터 구조 확정 | 개인 계정 fallback 기준으로 내부 usage observability 운영 가능 상태 유지 + org/admin 계정 capability 확보 후 provider reconciliation 재개 | `scripts/ops/llm_usage_cost_report.sh 24` + `scripts/ops/llm_credit_snapshot_collect.sh` + `SELECT route, provider, model, count(*) FROM llm_usage_events GROUP BY 1,2,3;` + `SELECT provider, count(*) FROM llm_provider_cost_snapshots GROUP BY 1;` | `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md` | `docs/work-result/21-04_llm_token_cost_observability_dashboard_result.md`, `docs/troubleshooting/21-06_ai_canary_env_injection_and_observability_gap.md` |
| 3 | 29-01 | BULL 레짐 Rule Funnel 관측성 강화 + 주기 점검 자동화 | in_progress | 29 baseline 지표 고정 | 레짐별 Rule/Risk/AI 퍼널 지표 상시 조회 + 7일(주 1회) 자동 리포트 + 기존 Weekly Exit Report 증분 확장 + 자동 수정 금지(승인형 제안만) 운영 기준 확정 | (예정) `scripts/ops/rule_funnel_regime_report.sh 72` + 주간 리포트 로그 누적 확인 + 퍼널 SQL 검증 | `docs/work-plans/29-01_bull_regime_rule_funnel_observability_and_review_automation_plan.md` | `docs/work-result/29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md` |
| 4 | 30 | 전략 피드백 자동화(Spec-First, 승인형 배포) | in_progress | 29 결과(기준선) 확보 + 21-03/21-04 관측 데이터 사용 가능 | 관측->원인분해->제안->검증->승인 배포 루프 spec 확정 + 자동 분석/게이트 PoC 결과 문서화 | `bash scripts/ops/strategy_feedback_report.sh 7 14 30` + `bash scripts/ops/strategy_feedback_gate.sh 7 14 30` + KPI SQL 검증 + `scripts/ops/rule_funnel_regime_report.sh 72` | `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md` | `docs/work-result/30_strategy_feedback_automation_spec_first_result.md`, `docs/troubleshooting/30_strategy_feedback_ops_script_runtime_compatibility.md` |
| 5 | 31 | OCI 운영 모니터링 스크립트 크론 자동화 + 관측 갭 보강 | done | 21-08 완료 + 사용자 승인 | 모니터링 스크립트 주기 실행(cron) 표준화 + 실행가드(flock/timeout) + 로그 보관 + LLM/AI 관측 갭 점검 자동화 | `bash -n scripts/ops/check_24h_monitoring.sh` + `bash -n scripts/ops/run_scheduled_monitoring.sh` + `crontab/cron.d 등록 확인` + `24h 누적 로그 점검` | `docs/work-plans/31_oci_ops_monitoring_cron_automation_and_gap_hardening_plan.md` | `docs/work-result/31_oci_ops_monitoring_cron_automation_and_gap_hardening_result.md`, `docs/troubleshooting/31_scheduled_monitoring_runtime_path_and_loki_readiness_false_fail.md` |
| 6 | 28 | AI Decision 전략문서/과거사례 기반 RAG 보강 | todo | 21-03/21-04 관측 데이터와 승인 확보 | 전략 문서 + 과거 사례 우선 RAG 실험 설계 승인 및 canary 검증 계획 확정 | (예정) `scripts/ops/ai_decision_canary_report.sh 24` + RAG on/off 비교 리포트 | `docs/work-plans/28_ai_decision_strategy_case_rag_plan.md` | (생성 예정) |
| 7 | 22 | 대시보드 가독성/실시간성 표준화(Spec-First) | todo | 24/21-03 관측 요구사항 반영 | 프론트 무관 운영 UI/freshness/stale 표준 확정 + 23 수용 기준 체크리스트 완성 | (예정) 22 spec 문서 + acceptance checklist 검토 | `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md` | (생성 예정) |
| 8 | 23 | Next.js 점진 이관 | blocked | 21-03 카나리 관측 마감 + 21-04 관측성 안정화 + 28 실험 설계 승인 + 22 spec 확정 + 29 전략 평가 결론 확정 | 핵심 화면 병행 운영(기능 동등) + 안정화 후 FE 레포 분리 게이트 정의/충족 | (예정) 기능 동등성 체크리스트 + 분리 게이트 점검 | `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`, `docs/work-plans/23-01_frontend_backend_repository_split_timing_plan.md` | (생성 예정) |
| - | 29 | 레짐 전환 구간 전략 평가 + 조건부 핫픽스 | done | 사용자 승인 + 운영 데이터 감사 가능 상태 | 백테스트 시나리오 비교 + 핫픽스 적용/보류 결론 확정 + 결과 문서 작성 | `PYTHONPATH=. python scripts/backtest_v3.py` + `PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 120 --output /tmp/regime_scenarios_120d.csv` + `PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 240 --output /tmp/regime_scenarios_240d.csv` + `docker exec -u postgres coinpilot-db psql -d coinpilot -c "SELECT symbol, MIN(timestamp), MAX(timestamp), COUNT(*) ... FROM market_data ..."` | `docs/work-plans/29_regime_transition_strategy_evaluation_and_hotfix_plan.md` | `docs/work-result/29_regime_transition_strategy_evaluation_and_hotfix_result.md` |
| - | 27 | CI 파이프라인 의존성 충돌/테스트 환경변수 복구 | done | main merge 후 CI 실패 재현 로그 확보 | `security`/`test` 잡 모두 성공 + backend/agent 계열 known vulnerability 해소 완료 + 잔여 `CVE-2026-25990(pillow)`는 프론트 전환 스트림(22/23)으로 이관 | `DB_PASSWORD=... DATABASE_URL=... .venv/bin/python -m pytest tests/utils/test_metrics.py tests/analytics/ tests/agents/` 통과 + GitHub Actions `test`/`security` 성공 + `security/pip_audit_ignored_vulns.txt`에 `CVE-2026-25990` 단일 잔여 확인 | `docs/work-plans/27_ci_pipeline_dependency_and_test_env_fix_plan.md`, `docs/work-plans/27-01_bandit_findings_and_security_artifact_reliability_fix_plan.md`, `docs/work-plans/27-02_pip_audit_known_vulnerability_remediation_plan.md`, `docs/work-plans/27-03_backend_agent_vuln_remediation_plan.md`, `docs/work-plans/27-04_langchain_langgraph_major_migration_plan.md` | `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md`, `docs/troubleshooting/27_ci_dependency_conflict_and_test_env_missing.md`, `docs/troubleshooting/27-01_bandit_xml_and_bind_all_interfaces_findings.md`, `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md` |
| - | 21-05 | OCI 인프라 리소스 모니터링 | done | exporter/Prometheus/Grafana 반영 완료 | 컨테이너 패널 표기 가독성 개선(서비스명 매핑) + 메모리 0 회귀 핫픽스 + `t24h` 관찰 완료 | `scripts/ops/check_24h_monitoring.sh t0 && scripts/ops/check_24h_monitoring.sh t1h && scripts/ops/check_24h_monitoring.sh t24h` | `docs/work-plans/21-05_oci_infra_resource_monitoring_grafana_plan.md` | `docs/work-result/21-05_oci_infra_resource_monitoring_grafana_result.md`, `docs/troubleshooting/21-05_cadvisor_container_panel_no_data.md` |
| - | 24 | 디스코드 모바일 조회 챗봇 | done | 21-05 기본 모니터링 안정화 | `/positions`, `/pnl`, `/status`, `/risk`, `/ask` 정상 응답 + role/channel 제한 정책 검증 완료 | `docker compose --profile discord-bot ... up -d --build bot discord-bot` + Discord slash command 수동 확인(허용/차단 케이스 포함) | `docs/work-plans/24_discord_mobile_chatbot_query_plan.md` | `docs/work-result/24_discord_mobile_chatbot_query_result.md`, `docs/troubleshooting/24_mobile_visibility_gap_discord_query_need.md`, `docs/troubleshooting/24-01_discord_role_nonetype_guard_fix.md`, `docs/troubleshooting/24-02_mobile_api_500_missing_psycopg2.md` |
| - | 21-07 | OCI 로그 관측 체계 강화(Loki/Promtail) | done | 21-05 완료 + 사용자 승인 | Loki/Promtail 수집 + Grafana 조회 + Discord 테스트 알림 기준 확정 + `t1h FAIL=0` + Loki ingest 양수 확인 | `docker compose --env-file .env -f docker-compose.prod.yml up -d --build loki promtail-targets promtail grafana` + `curl -sS http://127.0.0.1:3100/ready` + `scripts/ops/check_24h_monitoring.sh t1h` + `curl -sS -G http://127.0.0.1:3100/loki/api/v1/query --data-urlencode 'query=sum(count_over_time({filename=~\"/targets/logs/coinpilot-.*\\\\.log\"}[5m]))'` + Grafana Alerting 테스트 규칙 1회 발화 후 Discord 수신 확인 | `docs/work-plans/21-07_oci_log_observability_loki_promtail_plan.md` | `docs/work-result/21-07_oci_log_observability_loki_promtail_result.md`, `docs/troubleshooting/21-07_promtail_docker_api_version_mismatch.md` |
| - | 21-08 | Grafana Loki 로그 패널화 | done | 21-07 완료 + 사용자 승인 | `coinpilot-infra`에 Loki 핵심 패널(ingest/error/warn/top talker) 반영 + runbook 해석 기준 문서화 + OCI 검증 결과 문서화 | `scripts/ops/check_24h_monitoring.sh t1h` + `curl -sS -G http://127.0.0.1:3100/loki/api/v1/query --data-urlencode 'query=sum(count_over_time({filename=~\"/targets/logs/coinpilot-.*\\\\.log\"}[5m]))'` + Grafana 패널 수동 확인 | `docs/work-plans/21-08_grafana_loki_log_dashboard_panelization_plan.md` | `docs/work-result/21-08_grafana_loki_log_dashboard_panelization_result.md` |
| - | 26 | README 최신 운영 상태 반영 개편 | done | 문서 드리프트 확인 | README 기준 실행/운영 안내가 Charter/현재 배포 구조와 정합 | `rg -n \"PROJECT_CHARTER|check_24h_monitoring|discord-bot\" README.md` + README 링크 경로 존재 점검 | `docs/work-plans/26_readme_current_state_refresh_plan.md` | `docs/work-result/26_readme_current_state_refresh_result.md` |
| - | 99-01 | Result/Troubleshooting 정량 증빙 의무화 정책 반영 | done | 사용자 승인 완료 | AGENTS/Charter/템플릿에 문제 정의 + before/after 수치 + 측정 근거 필수 규칙 반영 완료 + 결과 문서 작성 완료 | `rg -n \"before|after|정량|증빙|측정|문제\" AGENTS.md docs/PROJECT_CHARTER.md docs/templates/work-result.template.md docs/templates/troubleshooting.template.md` | `docs/work-plans/99-01_result_troubleshooting_quantified_evidence_policy_plan.md` | `docs/work-result/99-01_result_troubleshooting_quantified_evidence_policy_result.md` |
| - | 99-02 | 트러블슈팅 문서 정량 증빙 백필(전수) | done | 사용자 일괄 정리 요청 승인 | `docs/troubleshooting/*.md` 전수에 정량 섹션/상태 문구 반영 완료 | `for f in docs/troubleshooting/*.md; do if ! rg -q \"정량\" \"$f\"; then echo \"$f\"; fi; done` 출력 없음 확인 | `docs/work-plans/99-02_troubleshooting_quantitative_backfill_all_docs_plan.md` | `docs/work-result/99-02_troubleshooting_quantitative_backfill_all_docs_result.md` |
| - | 99-03 | 트러블슈팅 표준 Before/After 비교표 전수 통일 | done | 사용자 표준표 전수 적용 요청 승인 | 트러블슈팅 32개 문서 모두 5열 표준표(`지표/Before/After/변화량(절대)/변화율`) 적용 | `for f in docs/troubleshooting/*.md; do if ! rg -q \"\\| 지표 \\| Before \\| After \\| 변화량\\(절대\\) \\| 변화율\\(%\\) \\|\" \"$f\"; then echo \"$f\"; fi; done` 출력 없음 확인 | `docs/work-plans/99-03_troubleshooting_standard_before_after_table_backfill_plan.md` | `docs/work-result/99-03_troubleshooting_standard_before_after_table_backfill_result.md` |
| - | 99-04 | Remaining Work 우선순위 재정렬 동기화 | done | 사용자 승인 + 현재 남은 작업 순서 확정 | 체크리스트 `Priority` 열과 README backlog가 최신 남은 작업 순서와 일치 | `rg -n "21-03|21-04|29-01|30|31|28|22|23" docs/checklists/remaining_work_master_checklist.md README.md` | `docs/work-plans/99-04_remaining_work_priority_reorder_sync_plan.md` | `docs/work-result/99-04_remaining_work_priority_reorder_sync_result.md` |

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
- 2026-03-02: 27-03 Phase D 1차 반영(미관측 stale allowlist `CVE-2024-7774` 제거), 잔여 4건은 메이저 호환성 검토 후 후속 축소 예정.
- 2026-03-02: 27-03 Phase D 2차 반영(`fastapi==0.129.0` 상향, `CVE-2025-62727` allowlist 제거), 로컬 회귀 테스트 `67 passed`, CI security 재검증 대기.
- 2026-03-02: 27-03 Phase D 3차 반영(`langgraph-checkpoint==4.0.0` 명시 핀, `CVE-2026-27794` allowlist 제거), 로컬 회귀 테스트 `67 passed`, CI security 재검증 대기.
- 2026-03-02: 27-03 Phase D 3차 롤백(CI resolver 충돌: `langgraph 0.6.11` vs `langgraph-checkpoint==4.0.0`), checkpoint 핀 제거 및 `CVE-2026-27794` allowlist 복구.
- 2026-03-02: 27-04 메이저 전환 계획 추가(`langchain-core`/`langgraph`/`langgraph-checkpoint` 동시 상향 트랙), 27의 다음 구현 경로를 단건 핀 방식에서 스택 전환 방식으로 명확화.
- 2026-03-02: 27-04 Phase M1/M2 1차 착수(1.x 후보 버전 상향 + LangGraph 호환 레이어 도입 + allowlist에서 `CVE-2026-26013`/`CVE-2026-27794` 제거), 로컬 회귀 테스트 `70 passed`, CI 재검증 대기.
- 2026-03-02: 27-04 Phase M1/M2 2차 보정(`pydantic-settings==2.10.1` 상향)으로 `langchain-community==0.4.1`와 resolver 충돌 해소 시도, CI 재검증 대기.
- 2026-03-02: 27-04 Phase M1/M2 3차 보정(`langchain-core==1.2.13` 상향)으로 `langchain-text-splitters==1.1.1`와 resolver 충돌 해소 시도, CI 재검증 대기.
- 2026-03-03: 27 최종 마감(`done`) 처리. `test`/`security` 통과를 확인했고, 잔여 `CVE-2026-25990(pillow)` 1건은 Streamlit 전이 의존성 이슈로 `22`/`23` 스트림에서 제거하도록 이관.
- 2026-03-04: 21-03 사용자 승인 후 구현 착수(`in_progress`). Analyst/Guardian 카나리 라우팅 및 모델별 집계 스크립트 반영 중.
- 2026-03-04: 21-03 Phase 1 구현 완료(라우팅/로깅/env 예시/집계 스크립트/테스트) 및 결과 문서 작성. 현재 상태는 운영 관찰 대기(`in_progress`)로 유지.
- 2026-03-04: 21-04 사용자 승인 후 구현 착수 및 Phase 1 반영(`in_progress`). usage ledger 스키마/공통 수집 유틸/route별 계측/운영 집계 스크립트/결과 문서를 추가.
- 2026-03-04: 21-04 운영 검증 자동화 보강. `scripts/ops/llm_usage_smoke_and_compare.sh`를 추가해 권장 확인 절차(경로 강제 호출 + usage/canary 비교 리포트)를 1회 실행으로 자동화.
- 2026-03-04: 21-04 운영 hotfix 반영. `llm_usage_smoke_and_compare.sh` 시작 단계의 `python -c` 따옴표 충돌(`SyntaxError`)을 수정해 smoke 절차가 정상 진행되도록 보정.
- 2026-03-04: 21-03/21-04 운영 관측 이슈를 `21-06` 트러블슈팅으로 분리 기록. compose env projection 누락/스크립트 quoting 오류를 수정하고, 결과 문서에 정량 Before/After를 추가.
- 2026-03-04: 21-03/21-04 문서 상태 동기화 완료. 21-03은 표본 부족으로 관찰 지속, 21-04는 Phase 1 구현 완료 + Phase 2(credit snapshot 자동수집) 대기로 `in_progress` 유지.
- 2026-03-04: 99-01 신규 메타 계획 등록(결과/트러블슈팅 문서의 문제 정의/정량 증빙 의무화, 현재 `Approval Pending`).
- 2026-03-04: 99-01 사용자 승인 후 정책 반영 착수(`in_progress`) 및 AGENTS/Charter/템플릿/README 동기화.
- 2026-03-04: 99-01 구현 및 결과 문서 작성 완료(`done`).
- 2026-03-04: 24/27/21-05 트러블슈팅 문서를 결과 문서와 대조해 정량 근거(명령 수/테스트 통과 수/취약점 건수/패널 복구 수치) 섹션을 보강.
- 2026-03-04: 99-02 전수 백필 수행. 정량 섹션 누락 트러블슈팅 문서 24개에 `정량 증빙 상태`를 일괄 추가해 누락 0건으로 정리.
- 2026-03-04: 99-02 정밀 보강 2차 반영. 백필 24개 문서 중 18개에 원문 수치 라인(%, 건수, passed/failed, 시간)을 자동 추출해 정량 증빙 밀도를 상향.
- 2026-03-05: 99-03 완료. 트러블슈팅 32개 문서 전부를 5열 표준표 형식으로 통일했고, 기존 4열 표(7개)와 표준표 누락(24개)을 모두 해소.
- 2026-03-05: 21-03에 임시 메모로 넣었던 RAG 방향 문구를 제거하고, 별도 main 계획 `28`(전략문서/과거사례 기반 RAG 보강)으로 분리 등록.
- 2026-03-05: 21-04 Phase 2 코드 반영. credit snapshot 자동수집(job/env 기반), one-shot 수집 스크립트, usage 리포트 freshness 구간을 추가했고 상태는 OCI 운영 검증 대기로 `in_progress` 유지.
- 2026-03-05: 21-04 Phase 2.1 코드 반영. balance endpoint 의존을 줄이기 위해 `LLM_COST_SNAPSHOT_*` + `llm_provider_cost_snapshots` 기반 provider 비용 스냅샷 수집으로 전환, 리포트 대조축을 `provider_cost_usd`로 보정.
- 2026-03-05: 21-04 Phase 2.1 OCI 운영 검증 완료. `smoke + compare` PASS, 1h route coverage 6개, `LLM_COST_SNAPSHOT_ENABLED=false`(현상 유지) 상태에서 `llm_provider_cost_snapshots` 0건 정상 확인.
- 2026-03-05: 다음 실행 포커스를 `21-05`(OCI 인프라 모니터링 가독성 마감 및 24h 관찰 증빙)으로 고정.
- 2026-03-05: 21-05 가독성 보강 1차 반영. `coinpilot-infra.json` 컨테이너 3개 패널을 `서비스명 우선 + 12자리 ID fallback` 범례로 전환해 운영 식별성을 개선했고, 상태는 24h 운영 관찰 대기(`in_progress`)로 유지.
- 2026-03-05: 21-05 가독성 보강 2차 반영. cAdvisor를 `--docker_only=true --store_container_labels=true`로 전환해 `container_label_com_docker_compose_service` 라벨 복구 경로를 적용.
- 2026-03-05: 21-05 가독성 보강 3차 반영. cAdvisor 라벨 의존을 제거하기 위해 `coinpilot-container-map`(docker ps→node-exporter textfile metric) 사이드카를 추가하고, Grafana 패널 쿼리를 `coinpilot_container_display_info` 조인 + ID fallback 구조로 전환.
- 2026-03-05: 21-05 가독성 보강 4차 핫픽스. `docker_only=true` 환경에서 cAdvisor `id`가 `/docker/<id>`로 바뀌는 케이스를 반영해 Grafana 컨테이너 패널 정규식을 `docker-`/`docker/` 겸용으로 수정.
- 2026-03-05: 21-05 가독성 보강 5차 핫픽스. 최근 구간 `No data` 재발을 완화하기 위해 `container-map` 조인 유지 조건에서 cAdvisor를 `docker_only=false`로 재조정.
- 2026-03-05: 21-05 가독성 보강 6차 핫픽스. cAdvisor `id="/"` 단일 시계열 고착 환경을 우회하기 위해 컨테이너 패널 데이터 소스를 `coinpilot-container-map`의 CPU/Memory/Restart 메트릭으로 전환.
- 2026-03-05: 21-05 운영 검증 기록 업데이트. `coinpilot_container_*` 4개 핵심 메트릭 count `12`, `check_24h_monitoring.sh t1h` 결과 `FAIL:0/WARN:1` 확인. 남은 마감 조건은 `t24h` 연속성 확인.
- 2026-03-05: 21-05 회귀 핫픽스. `coinpilot_container_memory_working_set_bytes` 전량 `0` 이슈를 확인해 `generate_container_display_map.sh` 메모리 변환 파서를 busybox awk 호환 형태로 보정.
- 2026-03-05: 21-05 최종 마감(`done`). `check_24h_monitoring.sh t24h` 결과 `FAIL:0/WARN:0`, 백업 3종 최신 생성 확인(Postgres/Redis/n8n), README 운영 상태를 `21-05 완료`로 동기화.
- 2026-03-05: 22 계획을 Spec-First로 재정의. Streamlit 직접 리팩터 선행 대신, 프론트 무관 운영 UI/freshness/stale 표준을 먼저 확정하는 방향으로 조정.
- 2026-03-05: 23 계획을 “모노레포 시작 → 안정화 후 FE 분리”로 보정하고, 하위 계획 `23-01_frontend_backend_repository_split_timing_plan.md`를 추가해 레포 분리 게이트를 명시.
- 2026-03-05: 사용자 요청에 따라 FE/BE 이관(23)을 선행 작업 완료 전 착수하지 않도록 상태를 `blocked`로 전환하고, 선행 게이트(21-03/21-04/28/22/29)를 완료 조건으로 고정.
- 2026-03-05: 독립 main 계획 `29` 추가(레짐 전환 구간 전략 평가 + 조건부 핫픽스). FE/BE 이관보다 전략 성능 검증을 우선하는 순서로 백로그를 조정.
- 2026-03-06: 사용자 승인(`f29 브랜치로 옮겨서 시작`) 반영으로 `29` 상태를 `in_progress`로 전환.
- 2026-03-06: 29 Phase 1 착수 결과 반영. 시나리오 비교 도구(`scripts/backtest_regime_transition_scenarios.py`) 추가 및 부분 결과 문서 연결.
- 2026-03-06: 29 Phase 2 1차(OCI 120일) 실행 반영. `transition_sensitive`가 baseline 대비 수익/승률/MDD 개선을 보였고, 표본 부족으로 추가 검증(180/240일) 후 핫픽스 확정 예정.
- 2026-03-06: 29 Phase 2 확장(OCI 180/240일) 실행 반영. 결과가 120일과 동일하여 데이터 윈도우 점검(SQL) 및 표본 확대 후 핫픽스 최종 결정을 진행.
- 2026-03-06: 29 Phase 3 반영. 장기 데이터 윈도우 확보를 위해 `scripts/backfill_for_regime.py`를 `--days/--symbols` 기반으로 확장하고, 기본 12,000분 동작 호환을 유지.
- 2026-03-06: 29 Phase 4 반영. DOGE/XRP 비중 축소 + BTC/ETH/SOL 비중 확대 요청을 반영해 `symbol_rebalanced`/`transition_sensitive_symbol_rebalanced` 시나리오를 추가.
- 2026-03-06: 29 Phase 5 반영. 심볼 비중 배율을 전략 공통 설정으로 승격하고(`config/strategy_v3.yaml` + `StrategyConfig`), 실거래(`src/bot/main.py`)와 백테스트(`scripts/backtest_v3.py`) 계산식을 동일 규칙으로 정렬.
- 2026-03-06: 독립 main 계획 `30` 추가(전략 피드백 자동화 Spec-First). 자동 분석/자동 제안/승인형 배포 원칙을 명시하고 체크리스트에 `todo`로 등록.
- 2026-03-06: 21-05 재검증 반영. `t0/t1h/t24h` 재실행과 Grafana Contact point->Discord 수신 확인을 완료했고, `done` 상태 근거를 결과 문서에 보강.
- 2026-03-06: 21-07 신규 계획 추가(OCI 로그 관측: Loki/Promtail/Grafana). 현재 상태 `todo`/`Approval Pending`.
- 2026-03-06: 21-07 사용자 승인 후 착수(`in_progress`). Loki/Promtail Compose 반영, Grafana Loki datasource, `check_24h_monitoring.sh t1h` 로그 수집 점검 로직을 추가.
- 2026-03-06: 21-07 운영 이슈 반영. promtail docker API mismatch(`1.42 < min 1.44`) 원인을 확인했고, `PROMTAIL_DOCKER_API_VERSION` 핫픽스와 점검 스크립트 FAIL 기준 강화 + 트러블슈팅 문서를 추가.
- 2026-03-06: 21-07 2차 핫픽스 반영. 1차 API 버전 핫픽스로 mismatch가 재현되어 `promtail-targets` 파일 타깃 생성 사이드카 + promtail 파일 수집 구조로 전환하고, 최종 OCI 재검증을 대기 상태로 유지.
- 2026-03-06: 21-07 2차 검증 결과 반영. `t1h`가 `FAIL:0/WARN:2`로 개선됐고 mismatch는 해소됐으나 `service` 라벨 미검출 WARN이 남아 3차 보강(`filename` 기반 라벨 추출) 적용 후 재검증 대기.
- 2026-03-06: 21-07 3차 검증 결과 반영. `timestamp too old`로 `FAIL:1`이 재발했고 symlink churn 로그를 확인해 4차 보강(타깃 증분 갱신 + positions 영속화 + too old 경고 분리) 적용 후 재검증 대기.
- 2026-03-06: 21-07 최종 마감(`done`). 4차 보강 재검증에서 `check_24h_monitoring.sh t1h` 결과 `FAIL:0/WARN:2`, Loki 쿼리 `sum(count_over_time({filename=~"/targets/logs/coinpilot-.*\\.log"}[5m]))=1362` 확인, Grafana 테스트 알림 Discord 수신 및 README 동기화 완료.
- 2026-03-06: 21-08 신규 계획 추가(Approval Pending). 21-07 후속으로 Grafana `coinpilot-infra`에 Loki 로그 KPI 패널(ingest/error/warn/top talker)을 표준화하는 작업을 분리 등록.
- 2026-03-06: 21-08 사용자 승인 후 착수(`in_progress`). `coinpilot-infra.json`에 Loki 패널 5종을 추가하고 runbook 정상 기준을 `filename` 기반 ingest 쿼리로 업데이트.
- 2026-03-07: 21-08 마감(`done`). OCI 검증에서 `check_24h_monitoring.sh t1h` 결과 `FAIL:0/WARN:1`, Loki ingest 쿼리 값 `187`을 확인했고 결과 문서/README를 동기화.
- 2026-03-07: 21-08 후속 보정 반영. 사용자 요청에 따라 Promtail 오류/경고 3개 패널에 `or vector(0)`를 적용해 정상 구간 `No data` 대신 `0`으로 표기하도록 조정.
- 2026-03-07: 21-08 후속 보정 2차 반영. 사용자 요청에 따라 `coinpilot-infra` 13개 패널 전체에 한국어 description(블록 의미/점검 포인트)을 추가해 대시보드 내부 해석 가이드를 제공.
- 2026-03-07: 21-08 후속 보정 3차 반영. 사용자 요청에 따라 절대 기준이 유효한 9개 패널에 주의/위험 threshold를 반영하고 description에도 동일 기준값을 명시해 운영 판단 기준을 정량화.
- 2026-03-07: 21-08 후속 보정 4차 반영. 사용자 요청에 따라 Grafana alert rule 7개를 provisioning YAML로 코드화하고 compose에 alerting 마운트를 추가해 재기동 자동 반영 경로를 확정.
- 2026-03-07: 21-08 후속 보정 5차 반영. 사용자 요청에 따라 Loki alert rule 3개에 `or vector(0)` + `noDataState=OK`를 적용하고, API mismatch 임계치를 `>=3, for 5m`로 완화해 Pending/No data 노이즈를 줄임.
- 2026-03-07: 31 신규 계획 추가(Approval Pending). `scripts/ops` 운영 스크립트의 cron 주기 자동화, 실행가드, 로그 보관, 추가 관측 갭(LLM snapshot freshness/AI inactivity) 보강 범위를 등록.
- 2026-03-07: 사용자 요청에 따라 `29-01` 하위 계획을 신규 등록(Approval Pending). BULL 레짐 Rule funnel 계측 공백을 메우고, 7일(주 1회) 주기 점검 자동화 및 자동 수정 금지(승인형 제안) 원칙을 명시.
- 2026-03-07: 사용자 요청에 따라 `29-01/30/31` 계획을 "주 1회(7일) 고정 + 기존 Weekly Exit Report 확장" 기준으로 동기화.
- 2026-03-07: 사용자 요청에 따라 30 계획에 운영 가드레일 6종과 자동 수정 범위(Tier-A YAML 자동 적용 / Tier-B 코드 변경 PR 제안)를 반영하고, 29-01/31에 연계 정책을 추가.
- 2026-03-08: 29 최종 마감(`done`). `market_data` 실가용 범위가 약 122~125일임을 확인했고, 120/240일 시나리오 모두 `transition_sensitive`가 손실/MDD 개선은 보였지만 `avg_profit_per_trade < 0`, `RR < 1.0`, `PF < 1.0`으로 수익성 게이트를 통과하지 못해 "추가 레짐 완화 핫픽스 보류" 결론을 결과 문서/README와 동기화.
- 2026-03-08: 99-04 메타 계획 추가(`todo`, Approval Pending). 29 마감 이후 현재 남은 작업 기준으로 체크리스트 `Priority` 열과 README backlog를 재정렬하는 작업을 별도 추적 항목으로 등록.
- 2026-03-08: 99-04 완료(`done`). 체크리스트 상단 우선순위를 `21-03 -> 21-04 -> 29-01 -> 30 -> 31 -> 28 -> 22 -> 23`으로 재배열하고, README backlog에서 완료 항목 4개를 제거해 남은 작업만 표시하도록 동기화.
- 2026-03-08: 21-03 24h 운영 관측 업데이트. `agent_decisions` 최근 24h 집계에서 primary 13건, canary 5건으로 모델 혼재는 확인됐지만, 계획 기준인 모델별 최소 표본 `N>=20`에 미달해 상태는 `in_progress` 유지. 실행 경로는 `cd /opt/coin-pilot && scripts/ops/ai_decision_canary_report.sh 24` 또는 절대경로 사용이 필요함을 결과 문서에 명시.
- 2026-03-08: 21-04 24h 운영 관측 업데이트. `scripts/ops/llm_usage_cost_report.sh 24`에서 route/provider/model 비용 리포트 5행과 provider 2개 비용 분리는 확인됐지만, `llm_provider_cost_snapshots`는 여전히 `0 rows`라 reconciliation/freshness가 비어 있음. 따라서 상태는 `in_progress` 유지하고, `cd /opt/coin-pilot && scripts/ops/llm_usage_cost_report.sh 24` 실행 경로를 결과 문서에 명시.
- 2026-03-08: 29-01 사용자 승인 후 착수(`in_progress`). `rule_funnel_events` 스키마, `scripts/ops/rule_funnel_regime_report.sh`, 주간 리포트 payload 확장(`rule_funnel`, `rule_funnel_suggestions`)까지 Phase 1 로컬 구현을 완료했고, 신규 분석 테스트 6건 통과를 결과 문서에 기록.
- 2026-03-08: 29-01 OCI 운영 검증 1차 완료. `coinpilot-bot` 재빌드 후 `rule_funnel_events` 적재 4건(`SIDEWAYS rule_pass=2`, `SIDEWAYS risk_reject=2`)을 확인해 운영 DB 계측 경로가 실제 동작함을 검증했다. 단, 아직 BULL/AI 단계 표본은 없어 최종 병목 해석은 보류.
- 2026-03-08: 29-01 후속 보정. OCI에서 `단일 주문 한도 초과`가 `risk_other`로 뭉친 것을 확인해 `risk_reject` reason_code를 `max_per_order`/`max_total_exposure` 등으로 세분화했고, 관련 로컬 테스트 4건을 통과시켰다.
- 2026-03-09: 29-01 72h 운영 메모 추가. `SIDEWAYS rule_pass=12`, `SIDEWAYS risk_reject=12`, `BULL=0`, `AI stage=0`으로 확인돼 최종 병목 해석은 BULL 표본 확보 시점까지 보류하고, 재확인 SQL 3종을 결과 문서에 메모했다.
- 2026-03-09: 29-01 Weekly Exit Report 운영 확인. `weekly_exit_report_job` 수동 실행에서 bot 로그 기준 전송 성공, Discord 수신 성공까지 확인했다. 1차 description 직접 확장안은 n8n/Discord 400 오류가 있었으나, 기존 weekly-report 형식(`jsonBody = {{ { \"embeds\": [...] } }}`)을 유지한 채 `제안/Rule Funnel/Rule Funnel 제안`을 embed fields로 추가하는 2차 보정 후 Discord 실메시지에 세 필드가 정상 표시됨을 재확인했다.
- 2026-03-09: 21-03 72h 운영 관측 업데이트. canary env(`AI_CANARY_ENABLED=true`, `AI_CANARY_PERCENT=20`)와 실제 canary 표본 `6건`을 확인해 비활성/환경 누락 이슈는 해소됐음을 검증했다. 다만 계획 기준인 모델별 최소 표본 `N>=20`에는 여전히 미달하므로 `in_progress` 유지, 추가 구현보다 관측 지속이 우선이다.
- 2026-03-09: 29-01은 구현/운영 검증 범위가 사실상 마무리됐고 현재는 `BULL` 및 `AI stage` 표본 대기만 남았다. 상태는 `in_progress`를 유지하지만 신규 구현 포커스는 다음 우선순위 작업(`30`)으로 이동 가능하다.
- 2026-03-10: 사용자 요청에 따라 `30` 계획을 `f30` 브랜치에서 구체화했다. 최신 입력 조건(`21-03` 표본 부족, `21-04` snapshot 누락, `29-01` monitoring-only)을 반영해 데이터 계약, 최소 표본 게이트, `gate_result(recommend|hold|discard)`, Discord 주간 보고 필드, 자동 보류 조건을 문서화했다. 이후 사용자 피드백을 반영해 `SELL >= 12` 검토 게이트 + `SELL >= 20` 강한 승인 게이트로 이원화하고, 승인 판단 윈도우를 `14일 기본 / 30일 확장`으로 구체화했다. 상태는 승인 전이므로 `todo` 유지.
- 2026-03-10: 사용자 승인 후 `30`을 `in_progress`로 전환하고 1차 구현(전략 피드백 분석기, `strategy_feedback_report.sh`, `strategy_feedback_gate.sh`, 테스트 3건)을 반영했다. Discord/n8n 통합과 자동 적용기는 이번 Phase 범위에서 제외했다.
- 2026-03-10: 30 OCI 런타임 호환성 보정. 초기 `Permission denied`, 이후 `python: command not found`와 `ModuleNotFoundError: sqlalchemy`를 확인해 두 ops 스크립트를 host python 대신 `docker compose exec -T bot python` 패턴으로 전환하고, 관련 트러블슈팅 문서를 체크리스트에 연결했다.
- 2026-03-10: 30 OCI 1차 운영 실행 성공. `strategy_feedback_report.sh 7 14 30` / `gate.sh 7 14 30`에서 `gate_result=discard`, `approval_tier=reviewable`, `sell_samples=16`, `ai_decisions=544`, `bull_rule_pass=0`, `avg_realized_pnl_pct=-0.6369`, `profit_factor=0.5807`를 확인했다. 현재는 비용 snapshot 누락과 BULL 표본 부족, 실현 손익/PF 기준 미달로 변경 제안이 생성되지 않는 상태다.
- 2026-03-10: 실거래 전환 요구사항 분리 문서화. 기존 `21_live_trading_transition_1m_krw_plan.md`의 범위를 보완하기 위해 `21-09_upbit_live_trading_dashboard_history_reconciliation_plan.md`를 추가했고, Upbit 실거래 전환 시 Dashboard/History/Reconciliation이 함께 바뀌는 점과 현재 우선순위(`21-04 -> 31` 선행 권장)를 명시했다.
- 2026-03-10: `21-09` Stage A 구현 완료. 실거래 최소 데이터 계약으로 exchange 원장 테이블 4종(`exchange_account_snapshots`, `exchange_orders`, `exchange_fills`, `reconciliation_runs`)과 ORM/migration/init baseline을 추가했고, 테스트 3건을 통과했다.
- 2026-03-10: `21-04` Phase 2.2 보강. provider 비용 API가 배열 bucket/POST body/최소 단위(cents) 응답을 반환하는 경우를 지원하도록 cost snapshot 파서를 확장했고, env/compose 예시와 테스트를 함께 보강해 `tests/utils/test_llm_usage.py` 14건 통과를 확인했다.
- 2026-03-10: `21-04` env example 현실화 보정. 개인 계정 기준으로는 admin/org 비용 API를 바로 사용할 수 없다는 주석을 추가했고, `.env.example`/`deploy/cloud/oci/.env.example`의 cost snapshot 기본 주기를 24h로 조정했으며 Anthropic divisor 기본값을 100으로 수정했다.
- 2026-03-10: `21-04` 개인 계정 fallback 운영 기준을 결과 문서에 확정했다. 현재는 `LLM_USAGE_ENABLED=true`, `LLM_COST_SNAPSHOT_ENABLED=false` 기준으로 내부 usage ledger 관측만 운영하고, provider reconciliation은 org/admin 계정 capability 확보 전까지 보류한다.
- 2026-03-10: `21-04` 상태를 `blocked`로 전환. 사유는 구현 실패가 아니라 개인 계정 capability 제약으로 provider 비용 API reconciliation을 더 진행할 수 없기 때문이며, 현재는 내부 usage observability만 정상 운영하는 fallback 모드다.
- 2026-03-10: `31` 사용자 승인 후 착수(`in_progress`). `check_24h_monitoring.sh`에 `--automation-mode`를 추가해 수동 UI 확인 WARN 노이즈를 억제했고, `run_scheduled_monitoring.sh` 래퍼와 `deploy/cloud/oci/ops/coinpilot-monitoring.cron.example`를 추가해 cron 주기표/실행 가드/로그 표준의 첫 구현을 반영했다.
- 2026-03-10: `31` OCI 1차 검증 중 런타임 이슈를 확인했다. 비root `/tmp` 스모크에서 기본 lock 경로 권한 충돌이 발생했고, Loki `/ready` empty 응답으로 false FAIL이 발생해 트러블슈팅 문서를 추가하고 `LOCK_ROOT=${LOG_ROOT}/locks` 기본값 및 Loki readiness fallback(query API success) 보정을 반영했다.
- 2026-03-10: `31` OCI 2차 검증 완료. `/etc/cron.d/coinpilot-monitoring` + `cron active` 상태에서 root 기준 스모크를 재실행했고, `monitoring-t1h`는 `FAIL:0/WARN:0/exit_code=0`, `ai-canary-24h`/`llm-usage-24h`도 모두 `exit_code=0`으로 통과했다. 현재는 Phase A/B 검증 완료 상태이며, 남은 범위는 관측 갭 자동 판정(Phase C)이다.
- 2026-03-10: `31` Phase C 1차 구현 반영. `check_24h_monitoring.sh`에 `LLM snapshot freshness(24h)`, `AI decision inactivity(6h)`, `scheduled monitoring heartbeat(24h)` 자동 판정을 추가했고, 개인 계정 fallback(21-04 blocked)과 충돌하지 않도록 `LLM_COST_SNAPSHOT_ENABLED=false`일 때는 INFO 처리하도록 고정했다. OCI 재검증은 다음 실행에서 수행한다.
- 2026-03-10: `31` Phase C OCI 재검증 완료 및 마감(`done`). `t6h/t12h/t24h`와 `all --automation-mode` 실행에서 `FAIL:0/WARN:0`, `AI inactivity PASS(최근 6h 10건)`, `heartbeat 6개 PASS`, 개인 계정 fallback 기준 `LLM snapshot freshness INFO 처리`를 확인했다. README도 같은 변경 세트에서 동기화했다.

---

## 4) 다음 갱신 트리거
1. 새 main 계획 생성 시: 백로그 행 추가
2. 구현 시작 시: `todo -> in_progress`
3. 구현 완료 + 결과 문서 작성 시: `in_progress -> done`
4. 장애/차단 발생 시: `blocked` 전환 + troubleshooting 링크 추가
