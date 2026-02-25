# 18-11. n8n 볼륨 혼선 및 백업 공백 트러블슈팅 / 핫픽스

작성일: 2026-02-25
상태: Fixed
우선순위: P1
관련 문서:
- Plan: `docs/work-plans/18-11_n8n_backup_automation_plan.md`
- Result: `docs/work-result/18-11_n8n_backup_automation_result.md`
- Charter update 필요: YES

---

## 1. 트리거(왜 시작했나)
- 운영 중 n8n 접속 시 기존 workflow가 사라진 것처럼 보였고 setup 재진입 화면이 나타남.
- 기존 알림/자동화가 중단될 수 있어 즉시 원인 확인이 필요했음.

---

## 2. 증상/영향
- 증상:
  - `POST /webhook/trade` 등에서 `webhook is not registered`(404)
  - 브라우저에서 n8n Owner setup 화면 재등장
- 영향:
  - 워크플로우 Active 상태 상실 시 Discord 알림 체인 중단
  - 운영자가 수동 재설정에 시간 소모
- 발생 조건:
  - WSL과 OCI를 동시에 사용하며 `localhost:5678`로 접속 대상이 혼재될 때

---

## 3. 재현/관측 정보
- 관측:
  - WSL Docker volume `oci_coinpilot_n8n_data` 내 `database.sqlite`/WAL/event log 존재 확인
  - OCI n8n은 별도 volume 기반으로 신규 상태 노출
- 핵심 로그:
  - n8n 자체는 `n8n ready on ::, port 5678`로 정상
  - webhook 404는 workflow 활성/등록 컨텍스트 불일치에서 발생

---

## 4. 원인 분석
- 가설 목록:
  1) workflow가 실제 삭제됨
  2) n8n DB 손상
  3) 볼륨/환경 혼선(WSL vs OCI)
- 조사 과정:
  - volume 내부 파일 존재 여부 및 SQLite 파일 크기 비교
  - 터널 포트 분리(`localhost:15678`) 후 대상 인스턴스 확인
- Root cause:
  - 데이터 유실이 아니라 서로 다른 인스턴스/volume 접속 혼선

---

## 5. 해결 전략
- 단기 핫픽스:
  - 기존 n8n volume 아카이브를 OCI 쪽 volume으로 복원
- 근본 해결:
  - n8n 백업 스크립트 추가 + cron 정기 백업 절차 문서화
- 안전장치:
  - SHA256 생성 및 보관 주기(일7/주4) 적용

---

## 6. 수정 내용
- 변경 요약:
  - n8n volume 백업 자동화 스크립트 신설
  - 운영 runbook cron 항목 확장
  - charter changelog 반영
- 변경 파일:
  - `scripts/backup/n8n_backup.sh`
  - `docs/runbooks/18_data_migration_runbook.md`
  - `docs/PROJECT_CHARTER.md`
- 롤백 방법:
  - cron의 n8n 라인 제거 + 스크립트 미사용

---

## 7. 검증
- 실행 명령/절차:
  - `bash -n scripts/backup/n8n_backup.sh`
  - `scripts/backup/n8n_backup.sh` 수동 실행
  - `ls -lh /var/backups/coinpilot/n8n/daily/`
- 결과:
  - tar.gz + sha256 생성 확인

운영 확인 체크:
1) n8n workflow 5개 Active
2) webhook 5종 호출 시 `Workflow was started` 응답

---

## 8. 재발 방지
- 가드레일:
  - n8n도 Postgres/Redis와 동일하게 정기 백업 대상에 포함
  - OCI 접속은 포트 분리(`localhost:15678`)로 환경 혼선을 차단
- 문서 반영:
  - plan/result/troubleshooting 상호 링크 반영 완료
  - charter changelog 반영 완료

---

## 9. References
- `scripts/backup/n8n_backup.sh`
- `docs/runbooks/18_data_migration_runbook.md`
- `docs/work-plans/18-11_n8n_backup_automation_plan.md`

## 10. 배운점
- “유실처럼 보이는 증상”은 실제 삭제가 아니라 컨텍스트(대상 인스턴스) 불일치일 수 있다.
- 운영 자동화에서 백업 범위는 DB뿐 아니라 워크플로우 실행 플랫폼(n8n)까지 포함해야 한다.
