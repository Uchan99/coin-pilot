# 27. CI 파이프라인 의존성 충돌/테스트 환경변수 복구 계획

**작성일**: 2026-03-02  
**작성자**: Codex  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/25_remaining_work_master_checklist_and_agents_workflow_update_plan.md`  
**관련 결과 문서**: `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md`
**관련 트러블슈팅 문서**: `docs/troubleshooting/27_ci_dependency_conflict_and_test_env_missing.md`
**승인 정보**: 사용자 / 2026-03-02 / "그렇게 진행해줘."

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - `main` 병합 후 GitHub Actions `CoinPilot CI` 실패.
  - `security` 잡: `requirements.txt` + `requirements-bot.txt` 동시 설치 시 `langchain-openai` 버전 충돌(0.3.19 vs 0.3.0).
  - `test` 잡: 테스트 수집 단계에서 `DB_PASSWORD is required when DATABASE_URL is not set` 예외 6건 발생.
- 왜 즉시 대응이 필요했는지:
  - 기본 브랜치 CI가 깨진 상태로 유지되면 후속 PR 품질 게이트가 무력화됨.

## 1. 문제 요약
- 증상:
  1) 보안 파이프라인 의존성 해석 실패(`ResolutionImpossible`)
  2) 테스트 수집 단계 import 실패(DB env 미설정)
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: CI 중단, 배포 자동화 차단
  - 리스크: 회귀 검출 실패 가능성 증가
  - 데이터: 없음
  - 비용: 반복 재시도/수동 점검 비용 증가
- 재현 조건:
  - GitHub Actions `ci.yml` 기준 동일 재현 가능

## 2. 원인 분석
- 가설:
  - `security`는 상호 독립 requirements를 단일 env에 동시에 설치해 충돌.
  - `test`는 fail-fast DB 설정 도입 이후 최소 DB env 주입이 누락됨.
- 조사 과정:
  - `.github/workflows/ci.yml` 확인
  - `requirements.txt`, `requirements-bot.txt` 버전 핀 비교
  - `src/common/db.py`의 fail-fast 로직 확인
- Root cause:
  1) 보안 잡 설계가 다중 requirements 충돌 케이스를 고려하지 않음
  2) 테스트 잡 환경변수에 `DATABASE_URL`/`DB_PASSWORD`가 없음

## 3. 대응 전략
- 단기 핫픽스:
  1) `security` 잡에서 충돌 유발 설치(`pip install -r requirements.txt -r requirements-bot.txt`) 제거
  2) `bandit`, `pip-audit`만 설치하고 audit은 requirements 파일 단위로 실행
  3) `test` 잡 환경에 `DATABASE_URL`, `DB_PASSWORD` 주입
- 근본 해결:
  - CI가 "실행 대상별 격리 환경" 원칙을 따르도록 workflow를 명시적으로 분리
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - workflow 변경 후 동일 명령으로 로컬/CI 재검증
  - 실패 시 즉시 롤백 가능한 최소 변경 유지

## 4. 구현/수정 내용
- 변경 파일(예정):
  - `.github/workflows/ci.yml`
  - (필요 시) `tests/conftest.py` 테스트 기본 env 보강
  - `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md`
- DB 변경(있다면):
  - 없음
- 주의점:
  - bot 런타임 의존성(`requirements-bot.txt`) 자체 버전 정책은 이번 작업에서 섣불리 통합하지 않음

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - `security` 잡에서 dependency conflict 미발생
  - `test` 잡이 collection 단계 통과
- 회귀 테스트:
  - 기존 테스트 명령 성공
- 운영 체크:
  - GitHub Actions `CoinPilot CI` 전체 green

## 6. 롤백
- 코드 롤백:
  - `ci.yml` 단일 파일 revert로 즉시 복구 가능
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 승인 후 구현, 구현 완료 후 result 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 규칙 변경 없음(불필요 예상)

## 8. 아키텍처/설계 대안 비교
- 대안 1: requirements 버전 전면 통일
  - 장점: 장기적으로 단순함
  - 단점: 런타임 영향 범위 큼(지금은 핫픽스 범위를 초과)
- 대안 2: security 잡에서 requirements 동시 설치 유지 + constraints 파일 추가
  - 장점: 환경 통합
  - 단점: 관리 복잡도 증가, 즉시 안정화에 불리
- 대안 3: 실행 대상별 CI 환경 분리(채택)
  - 장점: 최소 변경으로 실패 지점 직접 제거
  - 단점: 파일별 감사 실행 결과를 합쳐 해석해야 함

## 9. 후속 조치
1. CI 복구 후 `21-03`, `21-04` 진행 전 파이프라인 안정성 1~2회 확인
2. 필요 시 장기 과제로 requirements 정책 통합 계획 별도 수립

---

## Plan 변경 이력
- 2026-03-02: 초안 작성, 사용자 승인 대기(`Approval Pending`).
- 2026-03-02: 사용자 승인 반영(`Approved`), 구현 착수.
- 2026-03-02: CI workflow 수정 및 로컬 pytest 검증 완료(`Verified`).
