# 18-10. systemd Compose pull guard 적용 결과

작성일: 2026-02-25
작성자: Codex (GPT-5)
관련 계획서: `docs/work-plans/18-10_systemd_compose_pull_guard_plan.md`
상태: Implemented
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): `docs/troubleshooting/18-10_systemd_compose_pull_guard.md`

---

## 1. 개요
- 구현 범위 요약:
  - OCI systemd 기동 실패 원인 제거
  - 운영 runbook에 재발 방지 주의점 반영
- 목표(요약):
  - `coinpilot-compose.service`가 로컬 빌드 이미지 환경에서도 안정적으로 기동
- 이번 구현이 해결한 문제(한 줄):
  - `ExecStartPre pull` 실패로 인한 systemd 자동복구 불능 문제 해결

---

## 2. 구현 내용(핵심 위주)
### 2.1 systemd pre-pull 정책 보강
- 파일/모듈: `deploy/cloud/oci/systemd/coinpilot-compose.service`
- 변경 내용:
  - `ExecStartPre=/usr/bin/docker compose -f docker-compose.prod.yml pull`
  - -> `ExecStartPre=-/usr/bin/docker compose -f docker-compose.prod.yml pull --ignore-buildable`
- 효과/의미:
  - 로컬 빌드 이미지 pull 실패가 서비스 시작 실패로 전이되지 않음

### 2.2 runbook 주의사항 반영
- 파일/모듈: `docs/runbooks/18_data_migration_runbook.md`
- 변경 내용:
  - 7.1 systemd 섹션에 `--ignore-buildable` 필요성/실패 증상 명시
- 효과/의미:
  - 운영자 재현/복구 시간이 단축되고 동일 장애 재발 가능성 감소

---

## 3. 변경 파일 목록
### 3.1 수정
1) `deploy/cloud/oci/systemd/coinpilot-compose.service`
2) `docs/runbooks/18_data_migration_runbook.md`

### 3.2 신규
1) `docs/work-plans/18-10_systemd_compose_pull_guard_plan.md`
2) `docs/work-result/18-10_systemd_compose_pull_guard_result.md`
3) `docs/troubleshooting/18-10_systemd_compose_pull_guard.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 없음

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `sed -n '1,220p' deploy/cloud/oci/systemd/coinpilot-compose.service`
  - `rg -n "ignore-buildable|pull access denied" docs/runbooks/18_data_migration_runbook.md`
- 결과:
  - 통과: service/runbook 모두 수정 반영 확인

### 5.2 테스트 검증
- 실행 명령:
  - 운영 VM에서 사용자 수행: `systemctl start coinpilot-compose.service`, `systemctl status ...`
- 결과:
  - 로그 기반으로 원인 재현 확인 완료, 수정 후 운영 재검증 진행 중

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법: `docker compose ... ps`
- 결과: 사용자가 기존 스택 정상 기동 상태를 이미 확인한 상태

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `sudo systemctl daemon-reload`
2) `sudo systemctl start coinpilot-compose.service`
3) `systemctl status coinpilot-compose.service --no-pager -l`
4) `docker compose --env-file /opt/coin-pilot/deploy/cloud/oci/.env -f /opt/coin-pilot/deploy/cloud/oci/docker-compose.prod.yml ps`
5) `sudo reboot` 후 2~4 반복

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - pre-pull은 수행하되 buildable image는 제외하고 실패 무시
- 고려했던 대안:
  1) pre-pull 제거
  2) 내부 registry push/pull 방식으로 통일
  3) 별도 래퍼 서비스 도입
- 대안 대비 실제 이점(근거/관측 포함):
  1) 변경 폭 최소
  2) 기존 운영 명령 체계 유지
  3) 즉시 장애 해소 가능
- 트레이드오프(단점)와 보완/완화:
  1) pre-pull 실패가 즉시 에러로 드러나지 않음 -> `status/ps` 점검 절차로 보완
  2) 레지스트리 일관성은 미흡 -> 추후 private registry 도입 시 개선

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) 코드 변경 없음(설정/문서 수정 작업)
  2) runbook에 운영자 주의 설명 추가
- 주석에 포함한 핵심 요소:
  - 의도/왜(why): buildable image pull 실패 방지
  - 실패 케이스: `pull access denied`

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - service + runbook 동시 수정
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 재부팅 자동복구 경로의 구조적 실패 원인 제거 완료
- 후속 작업(다음 plan 번호로 넘길 것):
  1) 백업 cron 등록 + 복구 리허설
  2) Grafana Alert Rule 실전 연결

---

## 12. References
- `docs/work-plans/18-10_systemd_compose_pull_guard_plan.md`
- `docs/troubleshooting/18-10_systemd_compose_pull_guard.md`
- `deploy/cloud/oci/systemd/coinpilot-compose.service`
