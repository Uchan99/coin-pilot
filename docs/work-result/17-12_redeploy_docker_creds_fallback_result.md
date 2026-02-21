# 17-12. Redeploy Docker Credential Helper Fallback 구현 결과

작성일: 2026-02-21
작성자: Codex
관련 계획서: `docs/work-plans/17-12_redeploy_docker_creds_fallback_plan.md`
상태: Implemented
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - `redeploy_latest_minikube.sh`에 Docker credential helper 자동 fallback 로직 추가.
- 목표(요약):
  - `credsStore=desktop.exe` 환경에서 발생하는 build 단계 credential 에러를 스크립트 자체에서 우회.
- 이번 구현이 해결한 문제(한 줄):
  - Docker Desktop helper 이슈로 재배포가 시작도 못 되는 문제를 스크립트 레벨에서 완화.

---

## 2. 구현 내용(핵심 위주)
### 2.1 Docker credential fallback 로직 추가
- 파일/모듈:
  - `scripts/redeploy_latest_minikube.sh`
- 변경 내용:
  - `configure_docker_creds_fallback()` 함수 추가.
  - 조건:
    - `DOCKER_CONFIG` 미지정
    - `~/.docker/config.json` 존재
    - `credsStore`가 `desktop` 또는 `desktop.exe`
  - 동작:
    - `/tmp/coinpilot-docker-config.*` 임시 디렉토리 생성
    - 최소 `config.json`(`{"auths":{}}`) 작성
    - `DOCKER_CONFIG`를 임시 경로로 export
- 효과/의미:
  - helper 호출 실패를 피하고 공용 이미지 pull 경로를 정상화.

### 2.2 안전장치 및 정리 로직
- 파일/모듈:
  - `scripts/redeploy_latest_minikube.sh`
- 변경 내용:
  - `cleanup_tmp_docker_config()` + `trap ... EXIT`로 임시 파일 자동 정리.
  - `COINPILOT_KEEP_DOCKER_CREDS=1` 설정 시 fallback 비활성화.
  - 사용자가 직접 `DOCKER_CONFIG`를 지정한 경우 기존 설정 존중.
- 효과/의미:
  - 기존 사용자 설정을 덮어쓰지 않으면서 fallback을 선택적으로 적용.

---

## 3. 변경 파일 목록
### 3.1 수정
1) `scripts/redeploy_latest_minikube.sh`

### 3.2 신규
1) `docs/work-plans/17-12_redeploy_docker_creds_fallback_plan.md`
2) `docs/work-result/17-12_redeploy_docker_creds_fallback_result.md`

### 3.3 삭제(없으면 생략)
- 없음

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 코드 롤백만 수행

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `bash -n scripts/redeploy_latest_minikube.sh`
- 결과:
  - 통과 (`OK` 확인).

### 5.2 테스트 검증
- 실행 명령:
  - 스크립트성 변경으로 별도 pytest 대상 없음.
- 결과:
  - 해당 없음.

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - 본 작업에서는 실배포 실행 미수행(빌드/롤아웃은 사용자 운영 타이밍에 수행).
- 결과:
  - 없음.

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `./scripts/redeploy_latest_minikube.sh` 재실행.
2) `kubectl rollout status deployment/bot -n coin-pilot-ns` 확인.
3) `kubectl rollout status deployment/dashboard -n coin-pilot-ns` 확인.

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 스크립트 내부 자동 fallback + opt-out 환경변수 방식.
- 고려했던 대안:
  1) 사용자에게 매번 `DOCKER_CONFIG=/tmp/...` 수동 지정 요구.
  2) `~/.docker/config.json` 영구 수정 가이드만 제공.
  3) 스크립트 내부에서 자동 fallback(채택).
- 대안 대비 실제 이점(근거/관측 포함):
  1) 운영자가 실수 없이 동일 명령으로 재배포 가능.
  2) 기존 배포 플로우 변경 최소(스크립트 호출 방식 유지).
  3) helper 이슈 재발 시 자동 완화.
- 트레이드오프(단점)와 보완/완화:
  1) private registry 인증이 필요한 경우 최소 config로 pull 실패 가능.
  2) 이를 위해 `COINPILOT_KEEP_DOCKER_CREDS`/`DOCKER_CONFIG` 우선 정책 유지.

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `configure_docker_creds_fallback()` 내부 의도/불변조건/엣지케이스 설명.
  2) private registry 실패 모드와 우회 환경변수 사용 지점 설명.
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 불변조건(invariants)
  - 엣지케이스/실패 케이스
  - 대안 대비 판단 근거(필요 시)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - fallback 자동 적용, opt-out, cleanup, 문법 검증까지 수행.
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음.
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음.

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - redeploy 스크립트가 Docker Desktop helper 이슈를 자동 완화하도록 개선됨.
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 필요 시 `deploy/deploy_to_minikube.sh`에도 동일 fallback 정책 확장.
  2) private registry 사용 가능성이 생기면 인증 보존 fallback(예: auths 복제) 강화.

---

## 11. (선택) Phase 2+ 선반영/추가 구현 결과
- 없음.

---

## 12. References
- 링크:
  - `docs/work-plans/17-12_redeploy_docker_creds_fallback_plan.md`
  - `docs/work-plans/17-07_latest_dual_redeploy_script_plan.md`
  - `scripts/redeploy_latest_minikube.sh`
