# 27. CI dependency conflict + test env missing 트러블슈팅 / 핫픽스

작성일: 2026-03-02
상태: Fixed
우선순위: P1
관련 문서:
- Plan: `docs/work-plans/27_ci_pipeline_dependency_and_test_env_fix_plan.md`
- Result: `docs/work-result/27_ci_pipeline_dependency_and_test_env_fix_result.md`
- Charter update 필요: YES

---

## 1. 트리거(왜 시작했나)
- 모니터링/로그/사용자 리포트로 관측된 내용:
  - `main` 병합 직후 GitHub Actions `CoinPilot CI` 실패
  - `security`: requirements 동시 설치 단계에서 dependency resolver 충돌
  - `test`: pytest collection 단계에서 `DB_PASSWORD is required when DATABASE_URL is not set`
- 긴급도/영향:
  - 기본 브랜치 CI 실패로 품질 게이트가 중단되어 우선 복구 필요

---

## 2. 증상/영향
- 증상:
  1) `ERROR: ResolutionImpossible` (`langchain-openai==0.3.19` vs `0.3.0`)
  2) agents 테스트 6건 collection error
- 영향(리스크/데이터/비용/운영):
  - 리스크: 회귀 검증 실패
  - 비용: 수동 검증 반복 비용 증가
- 발생 조건/재현 조건:
  - `.github/workflows/ci.yml`의 기존 설정으로 재현 가능

---

## 3. 재현/관측 정보
- 재현 절차:
  1) security 잡의 `pip install -r requirements.txt -r requirements-bot.txt`
  2) test 잡의 `python -m pytest tests/utils/test_metrics.py tests/analytics/ tests/agents/`
- 핵심 로그/에러 메시지:
  - `ERROR: Cannot install langchain-openai==0.3.0 and langchain-openai==0.3.19`
  - `RuntimeError: DB_PASSWORD is required when DATABASE_URL is not set`

---

## 4. 원인 분석
- 가설 목록:
  1) 실행 대상이 다른 requirements를 단일 env에 합쳐 설치한 것이 원인
  2) fail-fast DB 설정 도입 이후 CI test env 누락
  3) test 코드 회귀
- 조사 과정(무엇을 확인했는지):
  - `.github/workflows/ci.yml` 확인
  - `requirements.txt`/`requirements-bot.txt` 버전 핀 비교
  - `src/common/db.py` import 시점 fail-fast 확인
- Root cause(결론):
  1) 보안 스캔 단계 설치 전략 문제(의존성 충돌)
  2) test 잡 환경변수 누락(DB 설정)

---

## 5. 해결 전략
- 단기 핫픽스:
  - security 잡에서 패키지 동시 설치 제거
  - pip-audit를 requirements 파일 단위로 분리 실행
  - test 잡에 `DB_PASSWORD`/`DATABASE_URL` 주입
- 근본 해결:
  - CI를 실행 대상별 격리 원칙으로 운영
- 안전장치(feature flag, rate limit, timeout/cooldown, circuit breaker 등):
  - workflow 내부 주석으로 의도/실패 모드 기록
  - 로컬에서 동일 pytest 명령 재실행으로 즉시 회귀 확인

---

## 6. 수정 내용
- 변경 요약:
  - `.github/workflows/ci.yml` 수정
- 변경 파일:
  - `.github/workflows/ci.yml`
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  - `git revert <커밋>`으로 workflow 변경만 롤백 가능

---

## 7. 검증
- 실행 명령/절차:
  - `DB_PASSWORD=ci_test_password DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot_test REDIS_URL=redis://localhost:6379/0 PYTHONPATH=. .venv/bin/python -m pytest tests/utils/test_metrics.py tests/analytics/ tests/agents/`
- 결과:
  - 64 passed, collection error 재현되지 않음

- 운영 확인 체크:
  1) GitHub Actions `CoinPilot CI` 재실행 시 `security` 설치 단계 충돌 미발생
  2) `test` job collection 단계 정상 통과

---

## 8. 재발 방지
- 가드레일(테스트/알림/검증 스크립트/권한/필터/타임아웃 등):
  - 보안 스캔은 실행 대상별 requirements 분리 감사 유지
  - fail-fast 환경변수 도입 시 CI env 동시 갱신 규칙 유지
- 문서 반영:
  - plan/result 업데이트 여부: YES
  - troubleshooting 링크 추가 여부: YES
  - PROJECT_CHARTER.md 변경(있다면): CI 복구 변경 이력 추가

---

## 9. References
- `.github/workflows/ci.yml`
- `requirements.txt`
- `requirements-bot.txt`
- `src/common/db.py`

## 10. 배운점
- 트러블 슈팅 경험을 통해 깨달은 점이나 배운점:
  - CI 단계는 "실행 대상 분리" 원칙이 중요하다. 한 환경에 모든 의존성을 합치면 불필요한 충돌이 발생한다.
- 포트폴리오용으로 트러블 슈팅을 작성할 때 강조할 점:
  - 증상-원인-수정-검증을 명령 단위로 남겨 재현 가능성을 보여주는 것이 핵심이다.
- 트러블 슈팅을 통해 어떤 능력이 향상되었는지:
  - 파이프라인 실패를 로그 기반으로 빠르게 분해하고, 최소 변경으로 복구하는 능력.
