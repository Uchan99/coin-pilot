# 20. OCI 유료 전환 대비 보안/과금 가드레일 강화 구현 결과

작성일: 2026-02-23  
작성자: Codex (GPT-5)  
관련 계획서: `docs/work-plans/20_oci_paid_tier_security_and_cost_guardrails_plan.md`  
상태: Implemented (Phase 1~2 코드/문서 하드닝)  
관련 트러블슈팅: 없음

---

## 1. 개요
- 구현 범위 요약:
  - 운영용 compose 보안 기본값 하드닝(fail-fast, 시크릿 강제)
  - 대시보드 접근 비밀번호 가드 추가
  - n8n webhook secret 검증 노드 전 워크플로우 반영
  - 보안 사전점검 자동화 스크립트 + runbook 반영
- 이번 구현이 해결한 핵심 문제:
  - "유료 전환 시 설정 실수/무단 접근으로 비용이 커질 수 있는 경로"를 코드/설정 단계에서 선차단

---

## 2. 구현 내용

### 2.1 운영 Compose 보안 하드닝
- 파일:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/cloud/oci/.env.example`
- 변경:
  - `DB_PASSWORD`, `UPBIT_*`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `N8N_WEBHOOK_SECRET`, `GRAFANA_ADMIN_*`, `DASHBOARD_ACCESS_PASSWORD`, `N8N_BASIC_AUTH_*`를 필수값으로 강제(`:?` fail-fast)
  - `N8N_BLOCK_ENV_ACCESS_IN_NODE`를 `true`로 변경
  - n8n basic auth 활성화(`N8N_BASIC_AUTH_ACTIVE=true`)
- 효과:
  - 약한 기본값/누락된 시크릿으로 서비스가 뜨는 사고를 사전 차단
  - n8n 노드에서 환경변수 임의 접근 가능성 축소

### 2.2 대시보드 접근 제어 추가
- 파일:
  - `src/dashboard/components/auth_guard.py`
  - `src/dashboard/app.py`
  - `src/dashboard/pages/1_overview.py`
  - `src/dashboard/pages/2_market.py`
  - `src/dashboard/pages/3_risk.py`
  - `src/dashboard/pages/4_history.py`
  - `src/dashboard/pages/5_system.py`
  - `src/dashboard/pages/06_chatbot.py`
  - `src/dashboard/pages/07_exit_analysis.py`
- 변경:
  - `DASHBOARD_ACCESS_PASSWORD` 기반 비밀번호 가드 추가
  - 모든 dashboard 엔트리 포인트에서 `enforce_dashboard_access()` 호출
- 효과:
  - 외부 노출 시 비인증 접근/LLM 무단 호출 리스크 감소

### 2.3 n8n webhook secret 검증 표준화
- 파일:
  - `config/n8n_workflows/trade_notification.json`
  - `config/n8n_workflows/risk_alert.json`
  - `config/n8n_workflows/daily_report.json`
  - `config/n8n_workflows/ai_decision.json`
  - `config/n8n_workflows/weekly-exit-report-workflow.json`
- 변경:
  - 모든 webhook 플로우에 `Validate Webhook Secret` IF 노드 추가
  - secret 불일치 시 Discord 전송 노드로 진행되지 않도록 연결 변경
  - 주간 리포트 workflow의 Discord URL을 env 기반(`$env.DISCORD_WEBHOOK_URL`)으로 통일
- 효과:
  - webhook 위조 요청이 알림 전송까지 이어지는 경로 차단

### 2.4 보안 사전점검 자동화
- 파일:
  - `scripts/security/preflight_security_check.sh`
  - `docs/runbooks/18_data_migration_runbook.md`
  - `docs/runbooks/18_oci_a1_flex_a_to_z_guide.md`
- 변경:
  - 배포 전 필수 보안 점검 스크립트 신설
    - `.env` 권한(600) 확인
    - 필수 env/placeholder 확인
    - compose 하드닝 옵션 확인
    - n8n workflow secret 검증 노드 존재 확인
  - runbook에 점검 절차 및 외부 포트 정책(`22/80/443`) 반영
- 효과:
  - 운영 전 체크리스트가 "수동 기억"에서 "반복 가능한 자동 점검"으로 전환

### 2.5 문서 추적성 반영
- 파일:
  - `docs/work-plans/20_oci_paid_tier_security_and_cost_guardrails_plan.md`
  - `docs/PROJECT_CHARTER.md`
- 변경:
  - 20번 계획 상태를 In Progress로 갱신
  - Charter 참고문서/변경이력에 20번 스트림 반영
- 효과:
  - plan/result/charter 간 추적성 확보

---

## 3. 변경 파일 목록
### 3.1 수정
1) `deploy/cloud/oci/docker-compose.prod.yml`  
2) `deploy/cloud/oci/.env.example`  
3) `config/n8n_workflows/trade_notification.json`  
4) `config/n8n_workflows/risk_alert.json`  
5) `config/n8n_workflows/daily_report.json`  
6) `config/n8n_workflows/ai_decision.json`  
7) `config/n8n_workflows/weekly-exit-report-workflow.json`  
8) `src/dashboard/app.py`  
9) `src/dashboard/pages/1_overview.py`  
10) `src/dashboard/pages/2_market.py`  
11) `src/dashboard/pages/3_risk.py`  
12) `src/dashboard/pages/4_history.py`  
13) `src/dashboard/pages/5_system.py`  
14) `src/dashboard/pages/06_chatbot.py`  
15) `src/dashboard/pages/07_exit_analysis.py`  
16) `docs/runbooks/18_data_migration_runbook.md`  
17) `docs/runbooks/18_oci_a1_flex_a_to_z_guide.md`  
18) `docs/work-plans/20_oci_paid_tier_security_and_cost_guardrails_plan.md`  
19) `docs/PROJECT_CHARTER.md`

### 3.2 신규
1) `src/dashboard/components/auth_guard.py`  
2) `scripts/security/preflight_security_check.sh`

---

## 4. DB/스키마 변경
- 없음

---

## 5. 검증 결과

### 5.1 코드/정적 검증
- 실행 명령:
  - `bash -n scripts/security/preflight_security_check.sh scripts/cloud/oci_retry_launch_a1_flex.sh scripts/cloud/run_oci_retry_from_env.sh`
  - `python3 -m py_compile src/dashboard/components/auth_guard.py src/dashboard/app.py src/dashboard/pages/1_overview.py src/dashboard/pages/2_market.py src/dashboard/pages/3_risk.py src/dashboard/pages/4_history.py src/dashboard/pages/5_system.py src/dashboard/pages/06_chatbot.py src/dashboard/pages/07_exit_analysis.py`
  - `for f in config/n8n_workflows/*.json; do jq empty "$f"; done`
  - `docker compose -f deploy/cloud/oci/docker-compose.prod.yml --env-file deploy/cloud/oci/.env.example config`
  - `./scripts/security/preflight_security_check.sh <temp_env_file>`
- 결과:
  - 쉘 문법 통과
  - 파이썬 문법 통과
  - n8n workflow JSON 유효성 통과
  - compose config 렌더링 통과
  - preflight 보안 점검 스크립트 실행 통과(임시 안전 env 파일 기준)

### 5.2 테스트 검증
- 실행 명령:
  - 없음 (이번 작업은 보안 설정/문서/워크플로우 구조 하드닝 중심)
- 결과:
  - 단위/통합 테스트 미실행
  - OCI 실서버에서 실제 webhook 헤더 검증 동작 확인이 추가 필요

### 5.3 런타임 확인(수동 필요)
- 대시보드 접근 시 비밀번호 프롬프트가 뜨는지
- 잘못된 `X-Webhook-Secret`로 n8n 호출 시 Discord 전송이 차단되는지
- `preflight_security_check.sh` 결과가 PASSED인지

---

## 6. 설계/아키텍처 결정 리뷰
- 최종 선택:
  - "단일 VM + Compose 유지" 상태에서 방어선(설정/인증/워크플로우 검증/사전점검) 우선 강화
- 대안:
  1) 즉시 OKE 전환
  2) Reverse Proxy 외부 인증만 먼저 적용
  3) 현재 구조에서 보안/비용 가드레일 선반영(채택)
- 채택 이유:
  - 18번 이관 흐름과 충돌이 적고, 즉시 위험 감소 효과가 큼
  - 운영 복잡도 급증 없이 실수성 사고를 크게 줄일 수 있음
- 트레이드오프:
  - 앱 레벨 비밀번호 가드는 OIDC 수준의 중앙 인증보다는 단순함
  - n8n secret 검증은 워크플로우 import/버전 관리 절차가 필요

---

## 7. 계획 대비 리뷰
- 계획과 일치:
  - Phase 1(시크릿/기본값/포트 정책)과 Phase 2 일부(대시보드 접근 제어, webhook 검증)를 코드로 반영
- 계획 대비 미완료:
  - OCI 콘솔 측 Budget/Quota 실제 적용(콘솔 작업)
  - Prometheus 경보 룰 고도화 및 월간 리포트 자동화

---

## 8. 다음 단계
1. OCI 콘솔에서 Budget + Quota를 실제 적용하고 증적 스크린샷/설정값을 결과 문서 Phase 2로 추가
2. n8n 실서버에서 webhook secret 불일치 테스트(차단 확인) 수행
3. 대시보드 외부 공개 전에 reverse proxy 인증(OIDC/Access) 적용 여부 최종 결정

---

## 9. References
- `docs/work-plans/20_oci_paid_tier_security_and_cost_guardrails_plan.md`
- `docs/security/docs1.md`
- `deploy/cloud/oci/docker-compose.prod.yml`
- `scripts/security/preflight_security_check.sh`
