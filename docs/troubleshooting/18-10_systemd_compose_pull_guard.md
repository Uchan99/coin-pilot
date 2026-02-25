# 18-10. systemd Compose pull 실패 트러블슈팅 / 핫픽스

작성일: 2026-02-25
상태: Fixed
우선순위: P1
관련 문서:
- Plan: `docs/work-plans/18-10_systemd_compose_pull_guard_plan.md`
- Result: `docs/work-result/18-10_systemd_compose_pull_guard_result.md`
- Charter update 필요: NO

---

## 1. 트리거(왜 시작했나)
- OCI VM에서 `coinpilot-compose.service` 활성화 시 바로 실패.
- 실패 지점이 재부팅 자동복구 경로(systemd)라 운영 안정성 영향이 큼.

---

## 2. 증상/영향
- 증상:
  - `systemctl enable --now coinpilot-compose.service` 실패
  - `ExecStartPre=/usr/bin/docker compose ... pull` 단계에서 `pull access denied` 발생
- 영향(리스크/데이터/비용/운영):
  - 재부팅 시 자동 기동이 깨져 수동 복구 필요
- 발생 조건/재현 조건:
  - Compose 파일에 로컬 빌드 이미지(`bot:latest`, `collector:latest`, `dashboard:latest`)가 포함된 상태에서 강제 pull 실행

---

## 3. 재현/관측 정보
- 재현 절차:
  1. systemd 유닛 등록
  2. `systemctl start coinpilot-compose.service`
- 핵심 로그/에러 메시지:
  - `pull access denied for bot, repository does not exist`
  - `Control process exited ... status=1/FAILURE`

---

## 4. 원인 분석
- 가설 목록:
  1) Docker daemon 문제
  2) compose 경로/권한 문제
  3) 로컬 빌드 이미지를 pull 대상으로 처리한 유닛 정책 문제
- 조사 과정(무엇을 확인했는지):
  - `systemctl status`에서 실패 지점이 `ExecStartPre pull`임을 확인
  - 동일 Compose 스택은 수동 `up -d --build`로 정상 동작 확인
- Root cause(결론):
  - systemd `ExecStartPre`가 buildable image를 registry pull 대상으로 취급해 실패

---

## 5. 해결 전략
- 단기 핫픽스:
  - `ExecStartPre=-docker compose ... pull --ignore-buildable`
- 근본 해결:
  - 저장소의 systemd 템플릿 자체를 동일 정책으로 수정
  - runbook에 원인/주의점 반영
- 안전장치:
  - pre-pull 실패가 전체 기동 실패로 전이되지 않게 `-` prefix 사용

---

## 6. 수정 내용
- 변경 요약:
  - systemd 유닛 pre-pull 정책 보강
  - 운영 runbook 주의사항 추가
- 변경 파일:
  - `deploy/cloud/oci/systemd/coinpilot-compose.service`
  - `docs/runbooks/18_data_migration_runbook.md`
- DB/스키마 변경(있다면): 없음
- 롤백 방법(필수):
  - `ExecStartPre`를 기존 pull 명령으로 되돌린 뒤 daemon-reload

---

## 7. 검증
- 실행 명령/절차:
  - `sudo systemctl daemon-reload`
  - `sudo systemctl start coinpilot-compose.service`
  - `systemctl status coinpilot-compose.service --no-pager -l`
- 결과:
  - service가 `active` 상태로 올라오면 통과

- 운영 확인 체크:
  1) `docker compose ... ps`에서 core 서비스 Up
  2) 재부팅 후 service 자동기동 확인

---

## 8. 재발 방지
- 가드레일:
  - 로컬 빌드 이미지가 있는 Compose 스택은 systemd pre-pull에 `--ignore-buildable` 적용
- 문서 반영:
  - plan/result 업데이트 여부: YES
  - troubleshooting 링크 추가 여부: YES
  - PROJECT_CHARTER.md 변경: 없음

---

## 9. References
- `deploy/cloud/oci/systemd/coinpilot-compose.service`
- `docs/runbooks/18_data_migration_runbook.md`

## 10. 배운점
- Compose 운영에서 image source(레지스트리 vs 로컬 빌드) 혼합 여부를 systemd 설계에 반영해야 한다.
- `ExecStartPre` 실패를 무조건 치명 처리하면 실제 운영복구가 과도하게 취약해진다.
