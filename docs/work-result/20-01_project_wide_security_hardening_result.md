# 20-01. 전역 보안 하드닝(Compose/DB/CI) 구현 결과

작성일: 2026-02-23
작성자: Codex (GPT-5)
관련 계획서: `docs/work-plans/20-01_project_wide_security_hardening_plan.md`
상태: Verified
완료 범위: Phase 1~2
선반영/추가 구현: 있음(20번 상위 계획의 하위 실행 항목)
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - Compose 이미지/포트/필수 env 하드닝
  - 앱 컨테이너 non-root 실행 전환
  - DB 연결 코드의 약한 기본값 제거(fail-fast)
  - CI 보안 스캔(Bandit + pip-audit 차단 게이트 + 리포트) 추가
  - preflight 스크립트에 mutable tag 검사 추가
  - OCI VM 런타임 보안 검증 체크리스트(runbook) 추가
- 목표(요약):
  - 유료 전환 전 "기본값/오구성 기반 보안 리스크"를 코드 레벨에서 선차단
- 이번 구현이 해결한 문제(한 줄):
  - 레거시/운영 경로에 남아 있던 공개 포트, 약한 폴백, 루트 실행, 무스캔 상태를 동시에 정리했다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 Compose 하드닝
- 파일/모듈:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/docker-compose.yml`
- 변경 내용:
  - 외부 이미지 mutable tag 제거: `timescale/timescaledb:2.18.0-pg15`, `redis:7.2.12-alpine3.21`, `n8nio/n8n:1.123.17`
  - 필수 env를 `:?` fail-fast로 강제
  - 레거시 compose 포트를 `127.0.0.1` 바인딩으로 제한
  - 앱 서비스에 `no-new-privileges` + `cap_drop: [ALL]` 적용
- 효과/의미:
  - 공개면과 오구성 리스크를 줄이고, 재현 가능한 배포 기준을 강화했다.

### 2.2 컨테이너 권한 하드닝
- 파일/모듈:
  - `deploy/docker/bot.Dockerfile`
  - `deploy/docker/collector.Dockerfile`
  - `deploy/docker/dashboard.Dockerfile`
- 변경 내용:
  - 전용 `app` 사용자 생성 후 `USER app`으로 실행
  - `COPY --chown=app:app`로 런타임 권한 정합성 확보
- 효과/의미:
  - 컨테이너 탈출/권한 상승 시 피해 범위를 축소했다.

### 2.3 DB 연결 fail-fast
- 파일/모듈:
  - `src/common/db.py`
  - `src/dashboard/utils/db_connector.py`
- 변경 내용:
  - `DB_PASSWORD` 기본값 `postgres` 폴백 제거
  - `DATABASE_URL` 미설정 시 `DB_PASSWORD` 필수 강제
- 효과/의미:
  - 약한 기본값으로 서비스가 기동되는 보안 사고를 차단했다.

### 2.4 보안 자동 점검/CI 강화
- 파일/모듈:
  - `scripts/security/preflight_security_check.sh`
  - `.github/workflows/ci.yml`
- 변경 내용:
  - preflight에 mutable tag/부동 alpine/no tag 검사 추가
  - CI에 `security` job 추가
    - Bandit: high severity/high confidence 게이트
    - pip-audit: 취약점 발견 시 job fail(차단) + JSON 리포트 아티팩트 업로드
- 효과/의미:
  - PR 단계와 배포 전 단계에서 보안 검증 자동화가 동작하게 됐다.

### 2.5 OCI VM 런타임 검증 체크리스트 추가
- 파일/모듈:
  - `docs/runbooks/20-01_oci_runtime_security_verification_checklist.md`
- 변경 내용:
  - preflight/compose config/배포/상태/포트/non-root/스모크체크를 한 번에 점검하는 운영 체크리스트 추가
- 효과/의미:
  - 로컬 정적 검증을 넘어, 실제 VM 반영 후 운영 안전성을 반복 점검할 수 있게 됐다.

---

## 3. 변경 파일 목록
### 3.1 수정
1) `deploy/cloud/oci/docker-compose.prod.yml`
2) `deploy/docker-compose.yml`
3) `deploy/docker/bot.Dockerfile`
4) `deploy/docker/collector.Dockerfile`
5) `deploy/docker/dashboard.Dockerfile`
6) `src/common/db.py`
7) `src/dashboard/utils/db_connector.py`
8) `.github/workflows/ci.yml`
9) `docs/work-plans/20-01_project_wide_security_hardening_plan.md`
10) `docs/work-result/20-01_project_wide_security_hardening_result.md`

### 3.2 신규
1) `docs/work-plans/20-01_project_wide_security_hardening_plan.md`
2) `docs/work-result/20-01_project_wide_security_hardening_result.md`
3) `docs/runbooks/20-01_oci_runtime_security_verification_checklist.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 코드/compose 설정만 되돌리면 됨

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `bash -n scripts/security/preflight_security_check.sh`
  - `python3 -m py_compile src/common/db.py src/dashboard/utils/db_connector.py`
  - `./scripts/security/preflight_security_check.sh`
  - `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml config >/tmp/compose.prod.resolved.yml`
  - `DB_PASSWORD=dummy UPBIT_ACCESS_KEY=dummy UPBIT_SECRET_KEY=dummy ANTHROPIC_API_KEY=dummy docker compose -f deploy/docker-compose.yml config >/tmp/compose.legacy.resolved.yml`
- 결과:
  - shell/python 문법 검증 통과
  - preflight 결과 `PASSED`
  - 운영/레거시 compose config 렌더링 통과
  - CI workflow 수정은 코드 반영 완료(원격 GitHub Actions에서 실행 시 차단 동작 확인 필요)

### 5.2 테스트 검증
- 실행 명령:
  - 미실행 (이번 변경은 인프라/보안 설정 중심)
- 결과:
  - 단위/통합 테스트는 별도 CI 실행 필요

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - OCI VM에서 `docker compose --env-file .env -f docker-compose.prod.yml up -d --build`
  - `docker compose -f docker-compose.prod.yml ps`
  - `docs/runbooks/20-01_oci_runtime_security_verification_checklist.md` 절차로 추가 점검
- 결과:
  - 로컬 환경에서는 compose config 레벨까지 확인 완료
  - 실제 VM 런타임 기동/헬스체크는 운영 반영 시 추가 확인 필요

---

## 6. 배포/운영 확인 체크리스트(필수)
1) 운영 `.env`에 필수값 누락이 없는지 (`preflight_security_check.sh` 결과 `PASSED`)
2) `docker compose -f deploy/cloud/oci/docker-compose.prod.yml config`가 에러 없이 렌더링되는지
3) 배포 후 `docker compose ps`에서 `db/redis/bot/dashboard/n8n/grafana/prometheus` 상태 확인
4) `docs/runbooks/20-01_oci_runtime_security_verification_checklist.md`의 포트/non-root 점검 통과

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - Compose 기반 운영은 유지하고, 권한/시크릿/검증 자동화를 전역 하드닝
- 고려했던 대안:
  1) 즉시 OKE 전환
  2) 운영 compose만 부분 수정
  3) 전역 하드닝 + CI 보안 스캔 추가(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 운영/레거시 경로 모두 동일한 보안 원칙 적용
  2) preflight + CI로 사전 차단 레이어 확보
  3) 18번 마이그레이션 흐름을 깨지 않고 적용 가능
- 트레이드오프(단점)와 보완/완화:
  1) CI 시간 증가
  2) fail-fast로 초기 설정 진입장벽 증가(문서/런북으로 보완)

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `src/common/db.py`의 fail-fast 설계 의도
  2) `src/dashboard/utils/db_connector.py`의 보안 폴백 제거 의도
- 주석에 포함한 핵심 요소:
  - 의도/왜(why): 약한 기본값 제거
  - 실패 케이스: 필수 env 누락 시 즉시 중단

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - Compose/컨테이너/DB/CI/preflight 하드닝 전 항목 반영
- 변경/추가된 부분(왜 바뀌었는지):
  - 레거시 compose에도 필수 env 강제와 loopback 바인딩을 추가 적용
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 20-01 보안 하드닝은 코드/설정 기준으로 완료됐고 정적 검증도 통과했다.
- 후속 작업(다음 plan 번호로 넘길 것):
  1) OCI VM에서 신규 runbook 기준 실제 런타임 점검 수행/증적 기록
  2) pip-audit 결과 기반 취약 의존성 정리(필요 시 20-02 계획 분리)

---

## 11. References
- `docs/work-plans/20-01_project_wide_security_hardening_plan.md`
- `docs/work-plans/20_oci_paid_tier_security_and_cost_guardrails_plan.md`
- `docs/security/docs1.md`
- `docs/PROJECT_CHARTER.md`
- `docs/runbooks/20-01_oci_runtime_security_verification_checklist.md`
