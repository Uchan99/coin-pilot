# 17-12. Redeploy Docker Credential Helper Fallback 계획

**작성일**: 2026-02-21  
**작성자**: Codex  
**상태**: Fixed  
**관련 계획 문서**: `docs/work-plans/17-07_latest_dual_redeploy_script_plan.md`  

---

## 0. 트리거(Why started)
- `./scripts/redeploy_latest_minikube.sh` 실행 중 `error getting credentials`로 Docker build가 실패함.
- WSL 환경에서 `~/.docker/config.json`의 `credsStore=desktop.exe`가 helper 실행 실패/타임아웃을 유발함.

## 1. 문제 요약
- 증상:
  - `FROM python:3.12-slim` metadata 조회 단계에서 credential helper 에러로 build 중단.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: bot/dashboard 재배포 스크립트가 즉시 실패.
  - 운영: 롤아웃까지 도달하지 못해 핫픽스 배포 지연.
- 재현 조건:
  - Linux/WSL에서 Docker Desktop credential helper(`desktop.exe`) 설정 사용 시 재현.

## 2. 원인 분석
- 가설:
  - 공용 이미지 pull에도 Docker가 기본 credential helper를 호출하고, helper 실행이 실패해 build가 중단된다.
- 조사 과정:
  - `~/.docker/config.json` 확인(`credsStore: desktop.exe`).
  - 스크립트 실행 에러 문자열 확인(`error getting credentials`).
- Root cause:
  - redeploy 스크립트가 helper 실패 환경을 고려한 fallback이 없어 인증 경로 오류를 복구하지 못함.

## 3. 대응 전략
- 단기 핫픽스:
  - `desktop.exe` helper 감지 시 임시 `DOCKER_CONFIG`(helper 없는 최소 config) 자동 적용.
- 근본 해결:
  - redeploy 스크립트에 credential fallback/cleanup 절차를 내장해 환경 의존도를 낮춤.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 사용자가 이미 `DOCKER_CONFIG`를 지정한 경우 스크립트가 덮어쓰지 않음.
  - 임시 디렉토리는 `trap`으로 종료 시 자동 정리.
  - 필요 시 `COINPILOT_KEEP_DOCKER_CREDS=1`로 fallback 비활성화 가능하게 처리.

## 4. 구현/수정 내용
- 변경 파일:
  - `scripts/redeploy_latest_minikube.sh`
- DB 변경(있다면):
  - 없음.
- 주의점:
  - fallback config는 public image pull 기준 안전하나, private registry 인증에는 부적합할 수 있음.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - `credsStore=desktop.exe` 환경에서 스크립트가 credential 에러 없이 build 단계로 진행.
- 회귀 테스트:
  - `bash -n scripts/redeploy_latest_minikube.sh` 문법 검사 통과.
- 운영 체크:
  - 롤아웃 완료 후 `kubectl rollout status` 성공 확인.

## 6. 롤백
- 코드 롤백:
  - 스크립트 변경분 revert.
- 데이터/스키마 롤백:
  - 해당 없음.

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 결과서 작성.
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 불필요(운영 규칙/전략 변경 없음).

## 8. 후속 조치
- 필요 시 `deploy_to_minikube.sh`에도 동일 fallback 정책 적용 여부 검토.
- private registry 사용 시 auth 전달 방식(`auths` 복제 또는 별도 로그인 가이드) 문서화.
