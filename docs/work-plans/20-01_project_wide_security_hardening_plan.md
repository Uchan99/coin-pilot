# 20-01. 전역 보안 하드닝(Compose/DB/CI) 작업 계획

**작성일**: 2026-02-23  
**작성자**: Codex (GPT-5)  
**상태**: Verified (2026-02-23, scope extended)  
**관련 계획 문서**: `docs/work-plans/20_oci_paid_tier_security_and_cost_guardrails_plan.md`  
**관련 결과 문서**: `docs/work-result/20-01_project_wide_security_hardening_result.md`  
**관련 보안 기준**: `docs/security/docs1.md`  

---

## 0. 트리거(Why started)
- 운영 보안 점검 요청에 따라 프로젝트 전체를 재검토했고, 남아 있는 고위험 설정(레거시 compose 공개 포트, 루트 실행 컨테이너, DB 약한 폴백, CI 보안 스캔 부재)을 확인했다.
- 20번 상위 계획(유료 전환 대비 보안/과금 가드레일)의 하위 실행 항목으로, 코드/설정 레벨에서 즉시 차단 가능한 리스크를 먼저 고정해야 한다.

## 1. 문제 요약
- 증상:
  - 레거시 `deploy/docker-compose.yml`에 `0.0.0.0` 포트 바인딩과 약한 기본 비밀번호 폴백(`postgres`)이 남아 있다.
  - 운영 compose 일부 이미지가 mutable tag(`latest`, `alpine`)를 사용한다.
  - 앱 컨테이너가 root 사용자로 실행된다.
  - DB 연결 코드에 약한 비밀번호 폴백이 남아 있다.
  - CI에 SAST/SCA 자동 스캔 단계가 없다.
- 영향 범위(기능/리스크/데이터/비용):
  - 무단 접근 시 DB/Redis/대시보드 노출 가능성 증가
  - 설정 누락 시 취약 기본값으로 기동될 가능성
  - 취약 의존성/코드 패턴을 PR 단계에서 조기 검출하지 못함
- 재현 조건:
  - `.env` 누락 상태 또는 기존 레거시 compose 사용 시 재현 가능

## 2. 원인 분석
- 가설:
  - 클라우드 이관(18번) 중 운영 compose는 하드닝됐지만, 레거시 경로와 코드 폴백이 완전 정리되지 않았다.
- 조사 과정:
  - `deploy/docker-compose.yml`, `deploy/cloud/oci/docker-compose.prod.yml`, Dockerfiles, DB 커넥터, CI 워크플로우를 점검했다.
- Root cause:
  - 보안 강화가 운영 경로 중심으로 우선 반영되면서, 레거시/공통 모듈의 일관 하드닝 및 CI 보안 게이트가 후순위로 남았다.

## 3. 대응 전략
- 단기 핫픽스:
  - 레거시 compose의 공개 포트를 loopback으로 제한하고, DB 비밀번호 폴백 제거.
  - Dockerfiles를 non-root 기본으로 전환.
  - DB 접속 코드에서 약한 기본 비밀번호 폴백 제거(누락 시 fail-fast).
  - CI에 Bandit(SAST), pip-audit(SCA) 단계 추가.
- 근본 해결:
  - 운영/개발 경로 모두에서 "기본값 안전"이 아니라 "누락 시 실패" 원칙을 적용한다.
  - 보안 검증 스크립트에 mutable tag 탐지 규칙을 추가해 재발을 방지한다.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - `preflight_security_check.sh`에 mutable tag 검사 추가.
  - CI 보안 스캔을 PR 자동 실행으로 고정.

## 4. 아키텍처 선택 및 대안 비교
- 최종 선택:
  - 기존 Compose 기반 운영을 유지하면서, 설정/컨테이너 권한/CI 스캔을 전역 하드닝한다.
- 고려한 대안:
  1. OKE 전환으로 정책 제어를 클러스터 레벨에서 해결
  2. 운영 compose만 수정하고 레거시/dev 경로는 현상 유지
  3. 전역 하드닝 + CI 보안 게이트 추가 (채택)
- 채택 이유:
  - 즉시 적용 가능하고, 현재 운영/개발 동시 리스크를 가장 빠르게 줄일 수 있다.
  - 18번 마이그레이션 흐름을 깨지 않으면서도 20번 목표(보안/과금 가드레일)와 정합성이 높다.
- 트레이드오프:
  - CI 보안 스캔으로 파이프라인 시간이 늘어난다.
  - non-root 전환 시 파일 권한 이슈가 발생할 수 있어 검증이 필요하다.

## 5. 구현/수정 내용
- 변경 파일(예정):
  - `deploy/docker-compose.yml`
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/docker/bot.Dockerfile`
  - `deploy/docker/collector.Dockerfile`
  - `deploy/docker/dashboard.Dockerfile`
  - `src/common/db.py`
  - `src/dashboard/utils/db_connector.py`
  - `.github/workflows/ci.yml`
  - `scripts/security/preflight_security_check.sh`
- DB 변경(있다면):
  - 없음(코드 레벨 연결 구성만 변경)
- 주의점:
  - 기존 `.env`가 없는 환경에서는 의도적으로 fail-fast될 수 있다.
  - Dockerfile non-root 전환 후 compose 기동 검증이 필요하다.

## 6. 검증 기준
- 재현 케이스에서 해결 확인:
  - 레거시 compose에서 공개 포트가 `127.0.0.1`로 제한되는지 확인
  - DB_PASSWORD 누락 시 앱이 즉시 명확한 에러로 중단되는지 확인
- 회귀 테스트:
  - Python 문법 검증(`py_compile`)
  - 보안 preflight 스크립트 실행
  - CI YAML 문법 및 job 구조 점검
- 운영 체크:
  - 운영 compose에서 mutable tag 검출 규칙이 동작하는지 확인
  - non-root 설정이 Dockerfile 레벨에서 반영됐는지 확인

## 7. 롤백
- 코드 롤백:
  - 각 파일별 git revert 또는 이전 커밋 복원
- 데이터/스키마 롤백:
  - 없음

## 8. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 생성 후 결과 문서(`20-01`) 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 필요(20번 하위 보안 하드닝 실행 이력 추가)

## 9. 후속 조치
- 운영 VM에서 실제 compose 기동 기준 보안 스캔(Bandit/pip-audit) 리포트 보관
- 이미지 digest pinning 정책을 릴리스 체크리스트에 강제 항목으로 추가
- OCI VM 런타임 보안 점검 체크리스트(runbook) 정례 운영
- CI 보안 게이트를 `advisory`에서 `blocking`으로 단계 상향

## 10. 변경 이력
- 2026-02-23: 계획서 작성 (초안)
- 2026-02-23: 계획 범위 전 항목 구현 완료 후 상태를 `Verified`로 갱신
- 2026-02-23: 추가 범위 반영
  - OCI VM 런타임 보안 검증 체크리스트 문서화
  - CI `pip-audit` 게이트를 fail(차단) 모드로 상향
