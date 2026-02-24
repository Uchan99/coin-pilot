# 18-08. Grafana Datasource UID 정렬 구현 결과

작성일: 2026-02-23
작성자: Codex (GPT-5)
관련 계획서: `docs/work-plans/18-08_grafana_datasource_uid_alignment_plan.md`
상태: Verified
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅: `docs/troubleshooting/18-03_grafana_no_data_with_prometheus_ok.md`

---

## 1. 개요
- 구현 범위 요약:
  - Grafana datasource provisioning에 고정 UID(`prometheus`)를 추가.
- 목표(요약):
  - dashboard의 datasource uid 참조와 실제 datasource uid를 일치시켜 `No data` 가능성 제거.
- 이번 구현이 해결한 문제(한 줄):
  - datasource UID 드리프트 가능성을 제거했다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 Datasource UID 고정
- 파일/모듈:
  - `deploy/monitoring/grafana-provisioning/datasources.yaml`
- 변경 내용:
  - `uid: prometheus` 추가
- 효과/의미:
  - `coinpilot-overview.json`의 `uid: prometheus` 참조와 정렬

### 2.2 런타임 반영
- 실행:
  - grafana 서비스 재시작
- 효과:
  - provisioning 설정 재적용

---

## 3. 변경 파일 목록
### 3.1 수정
1) `deploy/monitoring/grafana-provisioning/datasources.yaml`

### 3.2 신규
1) `docs/work-plans/18-08_grafana_datasource_uid_alignment_plan.md`
2) `docs/work-result/18-08_grafana_datasource_uid_alignment_result.md`
3) `docs/troubleshooting/18-03_grafana_no_data_with_prometheus_ok.md`

---

## 4. DB/스키마 변경
- 없음

---

## 5. 검증 결과
### 5.1 정적 검증
- provisioning 파일 마운트 확인
- grafana 컨테이너 내부 파일 확인(`uid: prometheus`)

### 5.2 런타임 반영
- `docker compose --env-file deploy/cloud/oci/.env -f deploy/cloud/oci/docker-compose.prod.yml restart grafana`
- 상태: `coinpilot-grafana Up`

---

## 6. 결론
- datasource UID 정렬 적용 완료.
- UI에서 `CoinPilot Overview` 새로고침 후 패널 값 확인 필요.
