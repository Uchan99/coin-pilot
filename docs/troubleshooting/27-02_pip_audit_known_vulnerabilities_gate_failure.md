# 27-02. pip-audit known vulnerabilities로 security job 실패

작성일: 2026-03-02
상태: Investigating
우선순위: P1
관련 문서:
- Plan: `docs/work-plans/27-02_pip_audit_known_vulnerability_remediation_plan.md`
- Result: `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md` (Phase 3 예정)
- Charter update 필요: TBD

---

## 1. 트리거(왜 시작했나)
- 관측 내용:
  - GitHub Actions security 단계에서 `pip-audit`가 `Found 11 known vulnerabilities in 7 packages`로 종료.
- 영향:
  - CI 보안 게이트가 차단되어 main 기준 자동 검증 흐름 중단.

## 2. 증상/영향
- 증상:
  - `pip-audit -r requirements.txt` 단계 exit code 1.
- 영향:
  - 배포 전 검증 실패, 수동 확인 비용 증가.

## 3. 1차 원인 가설
1. 직접 pin된 패키지 버전 중 CVE 포함 버전 존재
2. transitive dependency 취약점 포함
3. runtime 비필수 패키지가 감사 대상에 포함

## 3.1 취약점 매핑 (Phase A 산출)
| CVE | 패키지(관측 버전) | 주 영향 영역 | 코드/서비스 매핑 | 즉시 조치 방향 |
|---|---|---|---|---|
| CVE-2024-7774 | `langchain==0.3.x` | 에이전트 체인 유틸 | `src/agents/rag_agent.py`, `src/agents/daily_reporter.py`, `src/analytics/exit_performance.py` | 현재 fix version 미제공으로 allowlist 유지, 후속 메이저 전환 때 재평가 |
| CVE-2026-26013 | `langchain-core==0.3.81` | 프롬프트/메시지 코어 | `src/agents/analyst.py`, `src/agents/guardian.py`, `src/agents/router.py`, `src/agents/state.py` | `langchain-core 1.x` 전환 필요(27-03 Phase C) |
| CVE-2025-64439 | `langgraph-checkpoint==2.1.2` | 그래프 체크포인트 | 주로 bot requirements의 `langgraph==0.2.59` 경로에서 유입 | bot `langgraph`를 core와 정렬(`0.6.11`)해 제거 시도 |
| CVE-2026-27794 | `langgraph-checkpoint==3.0.1` | 그래프 체크포인트 | core/bot 공통 `langgraph` 경로에서 유입 | `langgraph` 1.x/`checkpoint` 4.x 전환 필요(27-03 Phase B/C) |
| CVE-2025-62727 | `starlette==0.47.3` | FastAPI 하위 HTTP 레이어 | `src/bot/main.py`, `src/mobile/query_api.py`의 API 경로 전반 | `fastapi`-`starlette` 호환 조합 재검증 필요, 현재 allowlist |
| CVE-2026-25990 | `pillow==11.3.0` | 대시보드 이미지 처리 | `streamlit` transitive dependency | `streamlit` 상향 전까지 allowlist 유지 |

## 4. 대응 방향(초안)
1. audit 리포트에서 package/CVE/fix_version 매핑
2. 최소 상향 버전으로 requirements 정리
3. pytest/런타임 smoke/audit 재검증
4. 해소 불가 CVE만 제한적 allowlist 적용(사유 기록 + 정기 재검토)

## 5. 진행 상태
- 현재:
  - 사용자 승인 완료
  - 1차 대응 반영 완료
    - `requirements.txt`/`requirements-bot.txt` 보안 상향(예: `fastapi`, `httpx`, `redis`, `uvicorn`, `streamlit`, `plotly`, `langchain-openai`)
    - security workflow에 pip-audit 상세 요약/게이트 스텝 추가(패키지/버전/CVE ID 로그 출력)
    - 즉시 해소 불가 CVE는 `security/pip_audit_ignored_vulns.txt`로 관리
  - 27-03 착수 반영:
    - backend/agent 우선 처리 정책으로 `langgraph`를 core/bot 모두 `0.6.11`로 정렬
    - `pillow>=12.1.1` 직접 핀 제거(설치 충돌 방지), `CVE-2026-25990`는 allowlist 유지
    - CI security에서 pip-audit 개별 step annotation 에러 노이즈를 제거하기 위해, step 내부에서는 exitcode 파일만 기록하고 최종 요약 step에서만 게이트 판정하도록 조정
  - 27-03 Phase C 1차 반영:
    - `langchain` 직접 의존 제거(`requirements.txt`, `requirements-bot.txt`)
    - `src/agents/daily_reporter.py`, `src/analytics/exit_performance.py`의 prompt import를 `langchain_core`로 전환
    - `src/agents/rag_agent.py`에서 `langchain.chains` 의존 제거(수동 체인 + retriever fallback)
    - `tests/agents/test_rag_agent.py` 신규 추가 후 회귀 테스트 `67 passed`
- 다음:
  - GitHub Actions 재실행 후 실제 취약 패키지 목록 확인
  - Phase D로 allowlist 축소 가능 항목(`CVE-2024-7774` 등) 재평가
  - 잔여 blocking 취약점이 있으면 2차 최소 상향 또는 구조 전환(메이저 업그레이드) 진행

## 6. References
- `.github/workflows/ci.yml`
- `requirements.txt`
- `requirements-bot.txt`
