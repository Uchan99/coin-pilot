# 18-10. systemd Compose pull guard 적용 계획

**작성일**: 2026-02-25  
**작성자**: Codex (GPT-5)  
**상태**: Fixed  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  

---

## 0. 트리거(Why started)
- OCI VM에서 `coinpilot-compose.service` 활성화 시 `ExecStartPre=/usr/bin/docker compose ... pull` 단계가 실패했다.
- `bot:latest`, `collector:latest`, `dashboard:latest`는 로컬 빌드 이미지라 Docker Hub pull 대상이 아니므로 서비스 시작이 차단됐다.

## 1. 문제 요약
- 증상: `systemctl enable --now coinpilot-compose.service` 실패 (`pull access denied for bot/dashboard/collector`).
- 영향 범위(기능/리스크/데이터/비용): 재부팅 자동복구(systemd) 미작동.
- 재현 조건: 로컬 빌드 이미지를 사용하는 Compose 파일에서 `ExecStartPre ... pull`을 강제 실행할 때.

## 2. 원인 분석
- 가설: `ExecStartPre`가 buildable image를 레지스트리 pull 대상으로 처리해 실패.
- 조사 과정: systemd status 로그의 실패 지점 확인 (`ExecStartPre` 단계).
- Root cause: systemd 유닛의 pull 전략이 “레지스트리 이미지 + 로컬 빌드 이미지 혼합” 운영 모델과 불일치.

## 3. 대응 전략
- 단기 핫픽스: `ExecStartPre`를 `pull --ignore-buildable`로 변경하고 실패 무시(`-` prefix) 적용.
- 근본 해결: runbook/systemd 템플릿을 동일 정책으로 갱신해 재발 방지.
- 안전장치(가드레일/차단/쿨다운/timeout 등): pull 실패가 전체 서비스 기동을 막지 않게 설계.

## 4. 구현/수정 내용
- 변경 파일:
  - `deploy/cloud/oci/systemd/coinpilot-compose.service`
  - `docs/runbooks/18_data_migration_runbook.md`
- DB 변경(있다면): 없음.
- 주의점: 원격 레지스트리 이미지 pull 실패를 무시하므로, 실제 운영 이미지 pull 실패는 `ExecStart` 로그에서 별도 확인 필요.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - `systemctl start coinpilot-compose.service`가 성공해야 함.
- 회귀 테스트:
  - `docker compose ... ps`에서 core 서비스가 `Up` 상태여야 함.
- 운영 체크:
  - 재부팅 후 systemd 자동기동 확인.

## 6. 롤백
- 코드 롤백: service 파일을 이전 `ExecStartPre=/usr/bin/docker compose -f docker-compose.prod.yml pull`로 복원.
- 데이터/스키마 롤백: 해당 없음.

## 7. 문서 반영
- work-plan/work-result 업데이트: 수행.
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역: NO (운영 절차 보정, 핵심 정책/정의 변경 없음).

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  - 운영 템플릿 변경 시 실제 OCI VM에서 `systemctl start` dry-run 검증 절차를 체크리스트에 추가.
  - 주간 점검 항목에 `systemctl status coinpilot-compose.service` 포함.

## 9. 아키텍처 선택/대안/트레이드오프
- 선택: `ExecStartPre=-docker compose pull --ignore-buildable` + `ExecStart=up -d --build`
- 대안:
  1. `ExecStartPre` 제거 후 `ExecStart`만 사용
  2. 내부 registry를 구축해 `bot/dashboard/collector`도 push 후 pull 방식 통일
  3. `oneshot` 대신 `restart=always` 타입의 별도 래퍼 스크립트 서비스
- 선택 근거:
  - 1은 단순하지만 원격 이미지 최신화가 사라짐.
  - 2는 가장 정합적이나 현재 범위 대비 인프라 비용/복잡도 과다.
  - 3은 유지보수 포인트가 늘어 운영 복잡도 증가.
- 트레이드오프:
  - pull 실패를 무시하므로 사전 감지는 약해짐.
  - 보완으로 `systemctl status`/`docker compose ps` 운영 점검을 필수화.

## 10. 계획 변경 이력
- 2026-02-25: 초안 작성.
- 2026-02-25: 구현 완료.
  - `deploy/cloud/oci/systemd/coinpilot-compose.service` pre-pull guard 반영
  - `docs/runbooks/18_data_migration_runbook.md` 주의사항 반영
  - 결과/트러블슈팅 문서 연결:
    - `docs/work-result/18-10_systemd_compose_pull_guard_result.md`
    - `docs/troubleshooting/18-10_systemd_compose_pull_guard.md`
