# 18-11. n8n 백업 자동화 및 볼륨 혼선 재발 방지 계획

**작성일**: 2026-02-25  
**작성자**: Codex (GPT-5)  
**상태**: Fixed  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  
**관련 트러블슈팅**: `docs/troubleshooting/18-11_n8n_volume_mismatch_and_backup.md`  

---

## 0. 트리거(Why started)
- 운영 중 n8n이 신규 setup 화면으로 열려 기존 workflow 유실처럼 보이는 사고가 발생했다.
- 원인은 실제 삭제가 아니라 환경별 Docker volume 혼선(WSL vs OCI)로 확인됐다.
- 현재 Postgres/Redis는 cron 백업이 있으나 n8n(volume/sqlite)은 자동 백업이 없어 운영 리스크가 남아 있다.

## 1. 문제 요약
- 증상:
  - 동일 `localhost:5678` 접근 시 서로 다른 n8n 인스턴스를 혼동
  - OCI n8n에서 workflow 미등록/비활성 상태 발생
- 영향 범위(기능/리스크/데이터/비용):
  - Discord 알림 체인 중단 가능성
  - workflow 수동 재구성 비용 증가
- 재현 조건:
  - 다중 환경(WSL + OCI) 동시 운영 + 로컬호스트 포트 재사용

## 2. 원인 분석
- 가설:
  1) workflow 파일 자체 삭제
  2) n8n DB 손상
  3) 서로 다른 volume/인스턴스 접속 혼선
- 조사 과정:
  - WSL volume(`oci_coinpilot_n8n_data`) 내부 `database.sqlite`와 event log 존재 확인
  - OCI n8n은 별도 환경으로 신규 setup 경로 진입 확인
- Root cause:
  - 데이터 유실이 아니라 운영 접속 경로/볼륨 분리 인지 부족

## 3. 대응 전략
- 단기 핫픽스:
  - n8n volume 백업 스크립트 신규 작성
  - cron 스케줄에 n8n 백업 추가
- 근본 해결:
  - runbook에 n8n 백업 라인 명시 및 운영 체크리스트 통합
  - charter changelog에 운영 정책 업데이트 기록
- 안전장치:
  - 일간 7일/주간 4주 보관 + SHA256 무결성 파일 생성

## 4. 아키텍처 선택 및 대안
- 선택:
  - Docker named volume 기반 tar.gz 백업(`docker run -v <volume>:/v ... tar`)
- 고려 대안:
  1) n8n UI export(JSON)만 주기 백업
  2) SQLite 내부 `.backup` 명령 기반 논리 백업
  3) 전체 VM 스냅샷에만 의존
- 채택 근거:
  - 1은 credentials/execution metadata 누락 가능성
  - 2는 컨테이너 내부 sqlite 도구/정합성 절차 추가 필요
  - 3은 복구 단위가 너무 커서 운영 복구 속도 저하
- 트레이드오프:
  - 파일시스템 스냅샷 특성상 완전 트랜잭션 백업이 아님
  - 다만 WAL/SHM 포함 volume 전체 백업으로 운영 복구에는 충분

## 5. 구현/수정 내용
- 변경 파일(예정):
  - `scripts/backup/n8n_backup.sh` (신규)
  - `docs/runbooks/18_data_migration_runbook.md` (cron 항목 확장)
  - `docs/PROJECT_CHARTER.md` (changelog 반영)
- DB 변경: 없음

## 6. 검증 기준
- 수동 실행 시:
  - `/var/backups/coinpilot/n8n/daily/*.tar.gz` 생성
  - `.sha256` 생성 및 검증 통과
- cron 등록 시:
  - `/etc/cron.d/coinpilot-backup`에 n8n 라인 존재
- 복구 가능성 확인:
  - tar 목록 조회(`tar -tzf`) 성공

## 7. 롤백
- 코드 롤백:
  - 신규 스크립트 삭제 + runbook/cron 라인 제거
- 데이터 롤백:
  - 기존 백업 파일은 보존, 운영 영향 없음

## 8. 문서 반영
- work-result 작성: `docs/work-result/18-11_n8n_backup_automation_result.md`
- troubleshooting 연계: `docs/troubleshooting/18-11_n8n_volume_mismatch_and_backup.md`
- charter 변경: 운영 백업 정책 변경사항 changelog 기록

## 9. 계획 변경 이력
- 2026-02-25: 초안 작성.
- 2026-02-25: 구현 완료.
  - 신규: `scripts/backup/n8n_backup.sh`
  - 수정: `docs/runbooks/18_data_migration_runbook.md`, `docs/PROJECT_CHARTER.md`
  - 결과/트러블슈팅 연결:
    - `docs/work-result/18-11_n8n_backup_automation_result.md`
    - `docs/troubleshooting/18-11_n8n_volume_mismatch_and_backup.md`
