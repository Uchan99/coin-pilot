# 27-03. 백엔드/에이전트 취약점 우선 해소 계획 (f27 WSL 실험)

**작성일**: 2026-03-02  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/27-02_pip_audit_known_vulnerability_remediation_plan.md`  
**관련 결과 문서**: `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md` (Phase 4 예정)  
**관련 트러블슈팅 문서**: `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md`  
**승인 정보**: 승인자 / 승인 시각 / 승인 코멘트

---

## 0. 트리거(Why started)
- `pip-audit` 보안 게이트는 allowlist를 통해 통과 중이나, 백엔드/에이전트 계열 취약점이 남아 있음.
- 사용자 합의: 운영 OCI에는 영향 없이 `f27` 브랜치 + WSL 실험으로 진행.

## 1. 문제 요약
- 현재 남은 취약점은 크게 2축:
  1) `langchain-core` 계열 (메이저 전환 필요)
  2) `langgraph-checkpoint` 계열 (메이저 전환 필요)
- `streamlit/pillow` 계열은 UI 전환(Next.js) 가능성을 고려해 이번 작업 우선순위에서 제외.

## 2. 범위/비범위
- 범위(In):
  - backend/agent 런타임에 직접 영향을 주는 `langchain*`, `langgraph*` 취약점 해소
  - CI security 게이트에서 해당 취약점 allowlist 제거
- 비범위(Out):
  - `streamlit`/`pillow` 해결
  - OCI 배포/운영 반영
  - `dev` 브랜치 변경

## 3. 실행 환경/브랜치 전략
- 브랜치: `f27` 전용
- 실험 환경: WSL 로컬
- 배포 정책: 이번 작업 중 OCI 반영 금지
- 병합 정책:
  1) `f27`에서 CI 통과 + 회귀 테스트 통과
  2) 사용자 검토 후 `dev`로 PR
  3) `dev` 검증 후에만 배포 검토

## 4. 아키텍처/설계 대안 비교
- 대안 1: allowlist 유지 (현상 유지)
  - 장점: 즉시 안정
  - 단점: 보안 부채 지속
- 대안 2: 전 의존성 일괄 메이저 업그레이드
  - 장점: 한 번에 정리
  - 단점: 장애 원인 분리 어려움, 롤백 리스크 큼
- 대안 3: 스트림 분할 단계적 업그레이드 (채택)
  - 장점: 실패 지점 명확, 단계별 롤백 가능, 검증 부담 분산
  - 단점: 작업 회차 증가

## 5. 단계별 구현 계획

### Phase A: 영향도 매핑 + 기준선 고정
- 목표:
  - CVE별 패키지/버전/코드 경로/서비스 영향도 표 작성
- 작업:
  1) `pip-audit` 로그 기준 취약 항목 정규화
  2) `src/agents/*`, `src/bot/*` import/사용 경로 매핑
  3) allowlist 중 backend/agent 대상만 우선 목록 확정
- 산출물:
  - 트러블슈팅 문서에 매핑 표 추가

### Phase B: LangGraph 계열 정리
- 목표:
  - `langgraph-checkpoint` 관련 취약점 제거
- 작업:
  1) `langgraph`/`langgraph-checkpoint` 호환 조합 업그레이드
  2) graph runner/state 연동부 회귀 수정
  3) 관련 테스트 보강

### Phase C: LangChain core 계열 정리
- 목표:
  - `langchain-core` 포함 관련 취약점 제거
- 작업:
  1) `langchain*` 패키지 조합 상향
  2) 메시지/체인 호출 인터페이스 변경 반영
  3) analyst/guardian/sql/rag 경로 회귀 수정

### Phase D: allowlist 축소/정리
- 목표:
  - backend/agent 대상 취약점 allowlist 0건
- 작업:
  1) `security/pip_audit_ignored_vulns.txt`에서 해당 CVE 제거
  2) CI gate 로그에서 ignored/blocking 재검증

## 6. 검증 기준
- 필수:
  1) `python -m pytest tests/utils/test_metrics.py tests/analytics/ tests/agents/` 통과
  2) CI `security`에서 backend/agent 대상 취약점이 allowlist 없이 통과
- 보조:
  - `docker compose ... up -d --build bot` (WSL 로컬 스모크)

## 7. 롤백 전략
- Phase 단위 커밋 분리
- 각 Phase 실패 시 해당 커밋만 revert
- allowlist는 마지막 단계에서만 제거하여 중간 실패 시 안정성 유지

## 8. 문서 반영 계획
- 구현 중:
  - `docs/troubleshooting/27-02_pip_audit_known_vulnerabilities_gate_failure.md` 진행 로그 업데이트
- 구현 후:
  - `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md` Phase 4 추가
  - `docs/checklists/remaining_work_master_checklist.md` 상태/링크 갱신
  - 필요 시 `docs/PROJECT_CHARTER.md` changelog 반영

## 9. 리스크/가정
- 리스크:
  - LangChain/LangGraph 메이저 변경으로 런타임 행위 차이 발생 가능
- 가정:
  - 현재 테스트셋이 핵심 회귀를 탐지할 수 있음

---

## Plan 변경 이력
- 2026-03-02: 초기 작성, 승인 대기(`Approval Pending`).
