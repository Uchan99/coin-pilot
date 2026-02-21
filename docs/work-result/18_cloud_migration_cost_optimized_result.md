# 18. 클라우드 마이그레이션(가성비 최적화) 구현 결과

작성일: 2026-02-21
작성자: Codex (GPT-5)
관련 계획서: docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md
상태: Implemented (Phase A~C 기반 산출물)
완료 범위: Phase A 준비 + Phase B 기반 구성 + Phase C 백업 자동화 스크립트
선반영/추가 구현: 있음(Prometheus/Grafana 운영 체크리스트)
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - OCI VM 기반 Compose 운영을 위한 배포/운영 산출물 생성
  - n8n + Prometheus + Grafana를 포함한 클라우드 전용 compose 스택 작성
  - 데이터 백업 스크립트와 마이그레이션 runbook 작성
- 목표(요약):
  - 18번 계획의 미구현 산출물을 코드/문서로 구체화해 즉시 실행 가능한 상태로 전환
- 이번 구현이 해결한 문제(한 줄):
  - "계획은 있으나 클라우드 실행 파일이 없는 상태"를 "실행 가능한 IaC/Runbook 상태"로 전환

---

## 2. 구현 내용(핵심 위주)
### 2.1 클라우드 운영 Compose 스택 구성
- 파일/모듈:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `deploy/cloud/oci/monitoring/prometheus.yml`
  - `deploy/cloud/oci/monitoring/grafana/provisioning/dashboards/provider.yaml`
  - `deploy/cloud/oci/.env.example`
- 변경 내용:
  - core(`db`, `redis`, `collector`, `bot`, `dashboard`) + `n8n` + `prometheus` + `grafana` 통합
  - bot 외부 포트 미노출(`expose`), dashboard/n8n/monitoring은 loopback 바인딩
  - bot/dashboard 환경변수를 K8s 기준에 맞춰 보강(`LLM_MODE`, `OPENAI_API_KEY`, `N8N_URL`, `N8N_WEBHOOK_SECRET` 등)
  - Prometheus 타겟을 Compose 서비스명(`bot:8000`) 기준으로 분리 구성
- 효과/의미:
  - Minikube 의존 없이 단일 VM에서 18번 목표 구성을 실행 가능한 형태로 확보

### 2.2 운영 자동화(bootstrap/systemd/backup)
- 파일/모듈:
  - `deploy/cloud/oci/bootstrap.sh`
  - `deploy/cloud/oci/systemd/coinpilot-compose.service`
  - `scripts/backup/postgres_backup.sh`
  - `scripts/backup/redis_backup.sh`
- 변경 내용:
  - Ubuntu VM 초기 설치 자동화(docker/compose/git)
  - systemd 기반 재부팅 자동복구 서비스 정의
  - Postgres/Redis 백업 스크립트(일간 7일 + 주간 4주 retention)
- 효과/의미:
  - 수동 실행 의존도를 줄이고, 운영 복구/백업 절차를 표준화

### 2.3 운영 문서화 및 체크리스트 보강
- 파일/모듈:
  - `docs/runbooks/18_data_migration_runbook.md`
  - `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`
- 변경 내용:
  - Minikube -> OCI PostgreSQL/Redis 마이그레이션 절차 문서화
  - 계획서 상태를 `In Progress`로 전환
  - Prometheus/Grafana 실사용 체크리스트(일일/이상징후/주간리뷰) 추가
- 효과/의미:
  - "연결은 되었지만 활용 미숙" 상태에서 운영 가능한 표준 점검 루틴 확보

---

## 3. 변경 파일 목록
### 3.1 수정
1) `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`

### 3.2 신규
1) `deploy/cloud/oci/docker-compose.prod.yml`
2) `deploy/cloud/oci/.env.example`
3) `deploy/cloud/oci/bootstrap.sh`
4) `deploy/cloud/oci/systemd/coinpilot-compose.service`
5) `deploy/cloud/oci/monitoring/prometheus.yml`
6) `deploy/cloud/oci/monitoring/grafana/provisioning/dashboards/provider.yaml`
7) `scripts/backup/postgres_backup.sh`
8) `scripts/backup/redis_backup.sh`
9) `docs/runbooks/18_data_migration_runbook.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점:
  - DB 스키마 변경이 없으므로 코드 롤백만으로 복구 가능

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `bash -n deploy/cloud/oci/bootstrap.sh scripts/backup/postgres_backup.sh scripts/backup/redis_backup.sh`
  - `docker compose -f deploy/cloud/oci/docker-compose.prod.yml config`
  - `rg --files deploy/cloud/oci scripts/backup docs/runbooks | sort`
- 결과:
  - shell syntax check 통과
  - compose config 파싱 통과
  - `.env` 미주입 상태로 필수 키 경고(UPBIT/LLM/N8N)는 예상 동작
  - 신규 파일 경로 생성 확인

### 5.2 테스트 검증
- 실행 명령:
  - 없음 (이번 작업은 인프라/문서/스크립트 산출물 중심)
- 결과:
  - 단위테스트 미실행
  - 리스크: 실제 OCI 환경에서 1회 기동 검증이 추가로 필요

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - 로컬 정적 검증만 수행
- 결과:
  - OCI 실제 기동/복원 리허설은 후속 작업으로 남아 있음

---

## 6. 배포/운영 확인 체크리스트(필수)
1) `.env` 생성 및 `chmod 600` 적용
2) `docker compose -f deploy/cloud/oci/docker-compose.prod.yml up -d --build` 기동
3) `docker compose -f deploy/cloud/oci/docker-compose.prod.yml ps`에서 전 서비스 healthy 확인
4) Prometheus Targets에서 `coinpilot-core` `UP` 확인
5) Grafana 로그인 후 `coinpilot_active_positions`, `coinpilot_total_pnl` 시계열 확인
6) `scripts/backup/postgres_backup.sh`, `scripts/backup/redis_backup.sh` 수동 1회 실행 후 백업 파일 생성 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - OCI 단일 VM + Docker Compose + 선택적 모니터링(내부 loopback 노출)
- 고려했던 대안:
  1) Managed Kubernetes(EKS/AKS/OKE)
  2) OCI VM + k3s
  3) OCI VM + Docker Compose (채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 기존 Dockerfile/compose 자산을 그대로 활용해 착수 속도가 가장 빠름
  2) 소규모 워크로드에 대해 운영 복잡도와 고정비가 가장 낮음
  3) 18번 계획의 "가성비 + 상시운영" 목표와 직접 부합
- 트레이드오프(단점)와 보완/완화:
  1) K8s-native 오토스케일/롤링업데이트 기능 제한 -> systemd 자동복구 + runbook으로 운영 안정성 보완
  2) 단일 노드 SPOF 리스크 -> 백업 자동화 + 병행 전환/롤백 전략으로 완화

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `scripts/backup/postgres_backup.sh` retention/주간보관 정책 설명
  2) `scripts/backup/redis_backup.sh` Redis 버전별 AOF 구조 차이 대응 의도 설명
  3) `deploy/cloud/oci/bootstrap.sh` 운영 변경 최소화 원칙 설명
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 보관 정책 불변조건(invariants)
  - 실패 가능 지점(인증/파일 구조/권한)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - Phase B(Compose 확장), Phase C(백업 자동화), Runbook/Result 문서 산출물 생성
- 변경/추가된 부분(왜 바뀌었는지):
  - Prometheus/Grafana 운영 체크리스트를 계획서에 추가(실사용성 개선 목적)
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 18번 구현 착수에 필요한 핵심 파일은 생성 완료
  - 실제 OCI 서버에서의 기동/이관 리허설은 아직 미실행
- 후속 작업(다음 plan 번호로 넘길 것):
  1) OCI VM 실배포 및 데이터 복원 리허설(Phase B/C 런타임 검증)
  2) 24h 무중단/재부팅 자동복구/백업복원 테스트 결과를 본 문서에 Phase 2로 추가

---

## 12. References
- `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`
- `docs/runbooks/18_data_migration_runbook.md`
- `deploy/cloud/oci/docker-compose.prod.yml`
