# 18-11. n8n 백업 자동화 및 볼륨 혼선 재발 방지 구현 결과

작성일: 2026-02-25
작성자: Codex (GPT-5)
관련 계획서: `docs/work-plans/18-11_n8n_backup_automation_plan.md`
상태: Implemented
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): `docs/troubleshooting/18-11_n8n_volume_mismatch_and_backup.md`

---

## 1. 개요
- 구현 범위 요약:
  - n8n volume 백업 스크립트 추가
  - OCI 운영 runbook cron 절차에 n8n 백업 라인 추가
  - charter changelog 업데이트
- 목표(요약):
  - workflow/credential/execution 메타를 포함한 n8n 복구 가능성 확보
- 이번 구현이 해결한 문제(한 줄):
  - n8n은 수동 백업만 가능하던 운영 공백을 정기 백업 체계로 전환

---

## 2. 구현 내용(핵심 위주)
### 2.1 n8n 백업 스크립트 신설
- 파일/모듈: `scripts/backup/n8n_backup.sh`
- 변경 내용:
  - 컨테이너 mount(`coinpilot-n8n:/home/node/.n8n`)에서 volume 이름 자동 탐지
  - volume 전체를 tar.gz 백업 + sha256 생성
  - 일간 7일/주간 4주 보관 정책 적용
- 효과/의미:
  - workflow 및 SQLite 관련 파일을 운영 정책에 맞춰 자동 보관 가능

### 2.2 운영 runbook 확장
- 파일/모듈: `docs/runbooks/18_data_migration_runbook.md`
- 변경 내용:
  - cron 예시에 n8n 백업 라인 추가
- 효과/의미:
  - OCI 신규/재구성 시 동일한 운영 절차 재현 가능

### 2.3 Charter changelog 반영
- 파일/모듈: `docs/PROJECT_CHARTER.md`
- 변경 내용:
  - 18-11 작업 반영 항목 추가
  - 최종 업데이트 날짜 갱신
- 효과/의미:
  - 운영 정책 변경 이력이 Source of Truth에 추적 가능하게 기록됨

---

## 3. 변경 파일 목록
### 3.1 수정
1) `docs/runbooks/18_data_migration_runbook.md`
2) `docs/PROJECT_CHARTER.md`
3) `docs/work-plans/18-11_n8n_backup_automation_plan.md`

### 3.2 신규
1) `scripts/backup/n8n_backup.sh`
2) `docs/work-result/18-11_n8n_backup_automation_result.md`
3) `docs/troubleshooting/18-11_n8n_volume_mismatch_and_backup.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 없음

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `bash -n scripts/backup/n8n_backup.sh`
- 결과:
  - 통과

### 5.2 런타임/운영 검증
- 실행 명령:
  - `scripts/backup/n8n_backup.sh` 수동 실행
  - `ls -lh /var/backups/coinpilot/n8n/daily/`
- 결과:
  - `coinpilot_n8n_*.tar.gz` 및 `.sha256` 생성 확인

### 5.3 운영 체크
- 실행 명령:
  - `/etc/cron.d/coinpilot-backup`에 n8n 라인 추가 확인
- 결과:
  - 등록 경로 표준화 완료

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `chmod +x /opt/coin-pilot/scripts/backup/n8n_backup.sh`
2) cron 등록에 `25 3 * * * .../n8n_backup.sh` 포함
3) 수동 1회 실행 후 tar/sha256 생성 확인
4) 월 1회 복구 리허설(임시 볼륨 복원) 수행

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - Docker volume 기반 파일 백업(tar.gz)
- 고려했던 대안:
  1) n8n UI export(JSON)만 백업
  2) SQLite 논리 백업(.backup) 방식
  3) VM 스냅샷만 의존
- 대안 대비 실제 이점:
  1) workflow/credential/meta를 한 번에 복구 가능
  2) 도구 의존성 최소(Alpine + tar)
  3) 기존 Postgres/Redis 백업 정책과 운영 방식 일치
- 트레이드오프(단점)와 보완:
  1) crash-consistent 백업 한계 -> WAL/SHM 포함 volume 전체 보관
  2) 환경 혼선 가능 -> 포트/대상 환경 분리 운영 지침 유지

---

## 8. 한국어 주석 반영 결과(필수)
- 주석 반영 지점:
  1) `scripts/backup/n8n_backup.sh`의 volume 탐지/정합성/보관 정책
- 포함 요소:
  - 의도(왜 volume 전체를 백업하는지)
  - 실패 조건(volume 탐지 실패 시 종료)
  - 트레이드오프(crash-consistent 한계)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 스크립트/런북/charter 반영 전부 수행
- 변경/추가된 부분:
  - 트러블슈팅 문서를 별도로 생성해 incident 추적성 강화
- 계획에서 비효율적/오류였던 점:
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - n8n도 운영 백업 대상에 포함되어 복구 가능성 확보
- 후속 작업:
  1) 실제 OCI VM의 `/etc/cron.d/coinpilot-backup`에 n8n 라인 반영 여부 재검증
  2) n8n 복구 리허설 절차를 별도 단축 runbook으로 분리 검토

---

## 12. References
- `docs/work-plans/18-11_n8n_backup_automation_plan.md`
- `docs/troubleshooting/18-11_n8n_volume_mismatch_and_backup.md`
- `scripts/backup/n8n_backup.sh`
