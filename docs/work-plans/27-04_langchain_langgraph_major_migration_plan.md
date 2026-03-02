# 27-04. LangChain/LangGraph 메이저 전환 계획

**작성일**: 2026-03-02  
**작성자**: Codex  
**상태**: Investigating  
**관련 계획 문서**: `docs/work-plans/27-03_backend_agent_vuln_remediation_plan.md`  
**관련 결과 문서**: `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md` (Phase 10 예정)  
**관련 트러블슈팅 문서**: `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md`  
**승인 정보**: 사용자 / 2026-03-02 / "메이지 전환 계획 세우고 진행하자."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - `CVE-2026-26013(langchain-core)`, `CVE-2026-27794(langgraph-checkpoint)`가 allowlist에 잔존.
  - 단건 핀 시도(`langgraph-checkpoint==4.0.0`)는 CI에서 resolver 충돌로 실패.
- 왜 즉시 대응이 필요했는지:
  - 보안 부채를 줄이려면 단건 핀이 아닌 스택 단위 메이저 전환이 필요함이 확인됨.

## 1. 문제 요약
- 증상:
  - `langgraph==0.6.11`가 `langgraph-checkpoint<4.0.0` 제약을 강제해 최신 fix 버전과 충돌.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: CI security는 통과 가능하나 allowlist 의존 상태 유지.
  - 리스크: 주요 AI orchestration 스택에 known CVE 잔존.
  - 데이터: 직접 영향 없음.
  - 비용: 반복 시도/롤백으로 운영 비용 증가.
- 재현 조건:
  - `requirements*.txt`에 `langgraph-checkpoint==4.0.0` 추가 시 CI install 단계에서 `ResolutionImpossible`.

## 2. 원인 분석
- 가설:
  1) `langgraph` 메이저가 올라가야만 `checkpoint` 4.x를 수용할 수 있음.
  2) `langchain-core` fix(1.2.11)도 관련 패키지군 동반 상향이 필요함.
  3) 단일 패키지 핀으로는 구조적 의존성 제약을 해소할 수 없음.
- 조사 과정:
  1) CI 에러 로그에서 resolver constraint 확인.
  2) D3 시도/롤백 결과를 문서화해 반복 실패 방지.
  3) 현재 코드의 `langgraph` 사용 경로(`src/agents/runner.py`, `src/agents/router.py`, `src/agents/state.py`) 확인.
- Root cause:
  - 현재 스택 버전 조합이 보안 fix 요구 버전과 상호 비호환.

## 3. 대응 전략
- 단기 핫픽스:
  - 기존 안정 조합 유지 + allowlist 3건(`26013`, `27794`, `25990`) 관리.
- 근본 해결:
  - `langchain-core`, `langgraph`, `langgraph-checkpoint`를 메이저 전환 가능한 호환 조합으로 동시 상향.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - Phase 단위 커밋 분리.
  - 각 phase마다 `pytest` + CI(`test`, `security`) 확인.
  - 실패 시 즉시 이전 phase로 revert.

## 4. 아키텍처/설계 대안 비교
- 대안 1: allowlist 유지(현상 유지)
  - 장점: 즉시 안정.
  - 단점: 보안 부채 지속.
- 대안 2: 단건 핀/부분 업그레이드 반복
  - 장점: 변경량 작음.
  - 단점: resolver 충돌 반복, 성공 가능성 낮음.
- 대안 3: 스택 메이저 동시 전환(채택)
  - 장점: 구조적 충돌 근본 해소 가능, 장기 유지보수 유리.
  - 단점: 코드/테스트 영향 범위 큼.

## 5. 단계별 구현 계획
- Phase M0 (기준선 동결)
  1) 현재 안정 조합 태깅/기록.
  2) 롤백 커맨드/커밋 포인트 고정.
- Phase M1 (의존성 조합 탐색)
  1) `langchain-core 1.x`, `langgraph 1.x`, `langgraph-checkpoint 4.x` 후보 조합 선정.
  2) CI install 가능한 최소 조합 확정.
- Phase M2 (코드 호환 전환)
  1) `StateGraph`/message state API 차이 반영.
  2) router/runner/state 관련 비호환 수정.
  3) 한국어 주석으로 전환 의도/제약 명시.
- Phase M3 (테스트/보안 게이트 정리)
  1) 전체 대상 테스트 통과.
  2) `CVE-2026-26013`, `CVE-2026-27794` allowlist 제거.
  3) CI `security` green 확인.
- Phase M4 (문서/체크리스트 마감)
  1) result/troubleshooting/checklist 최종 동기화.
  2) 필요 시 Charter changelog 반영.

## 6. 구현/수정 대상(예정)
- 변경 파일:
  - `requirements.txt`
  - `requirements-bot.txt`
  - `src/agents/runner.py`
  - `src/agents/router.py`
  - `src/agents/state.py`
  - `tests/agents/*` (영향 테스트 보강)
  - `security/pip_audit_ignored_vulns.txt`
- DB 변경(있다면):
  - 없음(예정)
- 주의점:
  - `langgraph` 메이저 전환 시 graph compile/invoke 흐름이 달라질 수 있어 회귀 테스트를 우선 작성.

## 7. 검증 기준
- 재현 케이스에서 해결 확인:
  - CI install 단계에서 resolver 충돌 0건.
- 회귀 테스트:
  - `DB_PASSWORD=ci_test_password DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot_test PYTHONPATH=. .venv/bin/python -m pytest tests/utils/test_metrics.py tests/analytics/ tests/agents/`
- 운영 체크:
  - GitHub Actions `test`, `security` 모두 success.

## 8. 롤백
- 코드 롤백:
  - 메이저 전환 phase 커밋 단위 revert.
- 데이터/스키마 롤백:
  - 없음.

## 9. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획 기준으로 구현 후 `27` result에 Phase 10+로 기록.
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 정책 변경이 없으면 미반영.
  - CI 보안 게이트 정책 자체 변경 시 changelog 기록.

## 10. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) `langchain/langgraph` 계열 의존성 검증을 월 1회 점검 루틴으로 추가 검토.
  2) 메이저 업그레이드 전용 브랜치/실험 규칙을 운영 표준으로 정리.

---

## Plan 변경 이력
- 2026-03-02: 계획 초안 작성 및 사용자 승인(`Approved`).
- 2026-03-02: Phase M1/M2 1차 착수. 의존성 후보를 1.x 계열(`langchain-core==1.2.11`, `langgraph==1.0.8` 등)로 상향하고, LangGraph 엔트리/메시지 병합 경로에 호환 레이어(`src/agents/langgraph_compat.py`)를 도입.
- 2026-03-02: Phase M1/M2 2차 보정. CI resolver 충돌(`pydantic-settings==2.5.0` vs `langchain-community==0.4.1` 요구사항) 대응으로 core/bot `pydantic-settings==2.10.1` 상향.
