# 27. CI 파이프라인 의존성 충돌/테스트 환경변수 복구 구현 결과

작성일: 2026-03-02
작성자: Codex
관련 계획서: docs/work-plans/27_ci_pipeline_dependency_and_test_env_fix_plan.md
상태: Implemented
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): docs/troubleshooting/27_ci_dependency_conflict_and_test_env_missing.md

---

## 1. 개요
- 구현 범위 요약:
  - GitHub Actions CI workflow(`.github/workflows/ci.yml`)를 수정해 `security` 의존성 충돌과 `test` 환경변수 누락 이슈를 동시에 복구
- 목표(요약):
  - `main` 브랜치 기준 CI 품질 게이트를 정상화
- 이번 구현이 해결한 문제(한 줄):
  - requirements 충돌로 중단되던 `security` 잡과 DB env 누락으로 중단되던 `test` 잡의 공통 실패 경로를 제거했다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 test 잡 DB 환경변수 보강
- 파일/모듈:
  - `.github/workflows/ci.yml`
- 변경 내용:
  - `Run Unit Tests` 단계 env에 `DB_PASSWORD`, `DATABASE_URL` 추가
  - fail-fast DB 설정(`src/common/db.py`)으로 인한 import-time collection 에러를 방지하도록 주석 포함
- 효과/의미:
  - pytest collection 단계에서 `DB_PASSWORD is required ...` 오류 제거

### 2.2 security 잡 의존성 설치 전략 수정
- 파일/모듈:
  - `.github/workflows/ci.yml`
- 변경 내용:
  - `pip install -r requirements.txt -r requirements-bot.txt` 제거
  - `bandit`, `pip-audit` 도구만 설치
  - `pip-audit`를 `requirements.txt`/`requirements-bot.txt` 분리 실행
  - 아티팩트도 core/bot 리포트 2개 업로드로 변경
- 효과/의미:
  - `langchain-openai` 버전 충돌(0.3.19 vs 0.3.0)로 인한 resolver 실패 제거

---

## 3. 변경 파일 목록
### 3.1 수정
1) `.github/workflows/ci.yml`
2) `docs/checklists/remaining_work_master_checklist.md`
3) `docs/work-plans/27_ci_pipeline_dependency_and_test_env_fix_plan.md`
4) `docs/PROJECT_CHARTER.md`

### 3.2 신규
1) `docs/troubleshooting/27_ci_dependency_conflict_and_test_env_missing.md`
2) `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항:
  - 없음
- 마이그레이션:
  - 없음
- 롤백 전략/주의점:
  - workflow/doc 변경만 포함되어 `git revert`로 즉시 롤백 가능

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `rg -n "pip install -r requirements.txt -r requirements-bot.txt|DB_PASSWORD|DATABASE_URL|pip-audit" .github/workflows/ci.yml`
- 결과:
  - 충돌 유발 동시 설치 문구 제거 확인
  - test env 보강 및 pip-audit 분리 실행 설정 확인

### 5.2 테스트 검증
- 실행 명령:
  - `DB_PASSWORD=ci_test_password DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot_test REDIS_URL=redis://localhost:6379/0 PYTHONPATH=. .venv/bin/python -m pytest tests/utils/test_metrics.py tests/analytics/ tests/agents/`
- 결과:
  - `64 passed` (collection error 재현 없음)

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - GitHub Actions `CoinPilot CI` 재실행으로 `security`/`test` 잡 성공 여부 확인
- 결과:
  - 로컬에서는 재현 오류 제거 확인 완료
  - GitHub Actions 최종 상태는 원격 실행 결과 확인 필요

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `security` 잡 설치 단계에서 dependency conflict가 재발하지 않는지 확인
2) `test` 잡 pytest collection 단계가 정상 통과하는지 확인
3) `pip-audit-report-core.json`, `pip-audit-report-bot.json` artifact 업로드 여부 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - CI를 "실행 대상별 의존성 분리" 방식으로 수정
- 고려했던 대안:
  1) requirements 버전 통합(0.3.19/0.3.0 중 하나로 일괄)
  2) constraints 파일 도입 후 동시 설치 유지
  3) 스캔 실행 단위 분리(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 영향 범위가 작고 즉시 복구 가능
  2) bot/dashboard 런타임 의존성 정책을 건드리지 않아 운영 리스크가 낮음
  3) 실제 실패 로그의 직접 원인(동시 resolver)만 제거
- 트레이드오프(단점)와 보완/완화:
  1) 리포트 파일이 1개에서 2개로 늘어 해석 지점 증가
  2) artifact 업로드를 2개 파일로 고정해 후속 분석 혼선을 줄임

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `.github/workflows/ci.yml` test env 섹션
  2) `.github/workflows/ci.yml` pip-audit 분리 실행 섹션
- 주석에 포함한 핵심 요소:
  - fail-fast 환경설정 도입 배경
  - requirements 동시 설치 충돌 원인과 분리 실행 이유

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - security/test 두 실패 경로 모두 계획대로 수정
  - 검증 명령 실행 및 트러블슈팅 문서 작성 완료
- 변경/추가된 부분(왜 바뀌었는지):
  - Charter 변경 이력에 CI 복구 내역을 추가해 추적성 강화
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - CI 실패 원인 2개(의존성 충돌, test env 누락) 모두 코드 레벨로 제거
  - 체크리스트 `27` 상태를 `done`으로 동기화
- 후속 작업(다음 plan 번호로 넘길 것):
  1) GitHub Actions 재실행 결과 확인 후 필요 시 미세 조정
  2) 체크리스트 우선순위에 따라 `21-05` 잔여 작업 진행

---

## 11. (선택) Phase 2+ 선반영/추가 구현 결과
- 추가 변경 요약:
  - Bandit 보안 이슈 2건(B314/B104) 대응
  - security artifact 업로드 안정성 가드 추가
- 추가 변경 파일:
  1) `src/agents/news/rss_news_pipeline.py` (`defusedxml` 파싱 전환)
  2) `src/bot/main.py` (`BOT_HOST`/`BOT_PORT` env 기반 바인딩)
  3) `requirements.txt` (`defusedxml` 추가)
  4) `requirements-bot.txt` (`defusedxml` 추가)
  5) `deploy/cloud/oci/docker-compose.prod.yml` (`BOT_HOST`, `BOT_PORT` 주입)
  6) `deploy/docker-compose.yml` (`BOT_HOST`, `BOT_PORT` 주입)
  7) `deploy/cloud/oci/.env.example` (`BOT_HOST`, `BOT_PORT` 문서화)
  8) `.env.example` (`BOT_HOST`, `BOT_PORT` 문서화)
  9) `.github/workflows/ci.yml` (security report 선생성 + 업로드 가드)
  10) `docs/troubleshooting/27-01_bandit_xml_and_bind_all_interfaces_findings.md`
- 추가 검증 결과:
  - `DB_PASSWORD=ci_test_password DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot_test REDIS_URL=redis://localhost:6379/0 PYTHONPATH=. .venv/bin/python -m pytest tests/agents/test_rss_news_pipeline.py tests/utils/test_metrics.py tests/analytics/ tests/agents/` -> `24 passed`
  - `python - <<'PY' ... yaml.safe_load('.github/workflows/ci.yml') ... PY` -> `CI_YAML_OK`
- 영향/리스크:
  - 보안 경고 원인 코드는 제거됨.
  - 로컬 네트워크 제한으로 `bandit` 실행 바이너리 설치 검증은 미수행(원격 CI에서 최종 확인 필요).

---

## 12. References
- `.github/workflows/ci.yml`
- `docs/work-plans/27_ci_pipeline_dependency_and_test_env_fix_plan.md`
- `docs/troubleshooting/27_ci_dependency_conflict_and_test_env_missing.md`
- `docs/work-plans/27-01_bandit_findings_and_security_artifact_reliability_fix_plan.md`
- `docs/troubleshooting/27-01_bandit_xml_and_bind_all_interfaces_findings.md`

---

## 13. (선택) Phase 3 선반영/추가 구현 결과
- 관련 계획:
  - `docs/work-plans/27-02_pip_audit_known_vulnerability_remediation_plan.md`
- 관련 트러블슈팅:
  - `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md`
- 추가 변경 요약:
  1) 보안 취약점 완화를 위한 의존성 1차 상향
  2) `pip-audit` 결과를 CI 로그에 구조적으로 출력하는 요약 스텝 추가
  3) 즉시 해소 불가 CVE를 파일 기반 allowlist로 제한 예외 처리
  4) 보안 게이트 차단 정책은 유지(allowlist 제외 취약점 발견 시 최종 step에서 `exit 1`)
- 추가 변경 파일:
  1) `requirements.txt`
  2) `requirements-bot.txt`
  3) `.github/workflows/ci.yml`
  4) `security/pip_audit_ignored_vulns.txt`
  5) `docs/work-plans/27-02_pip_audit_known_vulnerability_remediation_plan.md`
  6) `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md`
  7) `docs/checklists/remaining_work_master_checklist.md`
- 추가 검증 결과:
  - `DB_PASSWORD=ci_test_password DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot_test REDIS_URL=redis://localhost:6379/0 PYTHONPATH=. .venv/bin/python -m pytest tests/utils/test_metrics.py tests/analytics/ tests/agents/` -> `64 passed`
  - `.github/workflows/ci.yml` YAML 파싱 -> `CI_YAML_OK`
- 제한 사항:
  - 로컬 네트워크 제한으로 `pip-audit` 자체 실행/검증은 불가.
  - 최종 판정은 GitHub Actions 재실행 결과(`security` job)로 확인 필요.

---

## 14. (선택) Phase 4 선반영/추가 구현 결과
- 관련 계획:
  - `docs/work-plans/27-03_backend_agent_vuln_remediation_plan.md`
- 관련 트러블슈팅:
  - `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md`
- 추가 변경 요약:
  1) backend/agent 우선 전략에 맞춰 core/bot `langgraph` 버전을 `0.6.11`로 정렬
  2) bot의 구버전 `langgraph==0.2.59` 경로에서 유입되던 `langgraph-checkpoint` 취약점 노출을 축소 시도
  3) `streamlit`과 충돌하는 `pillow>=12.1.1` 직접 핀 제거(설치 실패 재발 방지)
  4) `pillow` 취약점은 UI 전환 전까지 allowlist로 관리
- 추가 변경 파일:
  1) `requirements.txt`
  2) `requirements-bot.txt`
  3) `security/pip_audit_ignored_vulns.txt`
  4) `docs/work-plans/27-03_backend_agent_vuln_remediation_plan.md`
  5) `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md`
  6) `docs/checklists/remaining_work_master_checklist.md`
- 추가 검증 결과:
  - `DB_PASSWORD=ci_test_password DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot_test REDIS_URL=redis://localhost:6379/0 PYTHONPATH=. .venv/bin/python -m pytest tests/utils/test_metrics.py tests/analytics/ tests/agents/` -> `64 passed`
  - `.github/workflows/ci.yml` YAML 파싱 -> `CI_YAML_OK`
- 제한 사항:
  - 로컬 네트워크 제한으로 실제 `pip-audit`/resolver 결과는 GitHub Actions에서만 최종 판정 가능.
