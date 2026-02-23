# 18. 클라우드 마이그레이션(가성비 최적화) 구현 결과

작성일: 2026-02-22
작성자: Codex (GPT-5)
관련 계획서: docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md
상태: Implemented (Phase A~C 기반 산출물)
완료 범위: Phase A 준비 + Phase B 기반 구성 + Phase C 백업 자동화 스크립트
선반영/추가 구현: 있음(Prometheus/Grafana 운영 체크리스트)
관련 트러블슈팅:
- `docs/troubleshooting/18_oci_a1_flex_capacity_and_throttle_retry.md`
- `docs/troubleshooting/18_compose_bot_status_missing_after_migration.md`
- `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`

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

### 2.4 A1.Flex 용량 부족 자동 재시도 자동화
- 파일/모듈:
  - `scripts/cloud/oci_retry_launch_a1_flex.sh`
  - `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md`
- 변경 내용:
  - `coinpilot-ins` + `VM.Standard.A1.Flex`(2 OCPU/12GB) 고정 조건으로 launch 재시도 로직 구현
  - 실패 원인 중 `Out of capacity for shape`만 재시도하고, 권한/파라미터 오류는 즉시 중단
  - SSH keypair를 로컬에 생성/재사용해 private key 분실 리스크를 운영 절차로 통제
  - `DISCORD_WEBHOOK_URL` 기반 선택적 알림(시작/진행/재시도/성공/오류) 추가
- 효과/의미:
  - Chuncheon 단일 AD 환경에서 수동 재시도 부담을 줄이고 성공 시점 포착 확률을 높임

### 2.5 초보자 A~Z 가이드 + 재부팅 재개 동선 보강
- 파일/모듈:
  - `docs/runbooks/18_oci_a1_flex_a_to_z_guide.md`
  - `scripts/cloud/run_oci_retry_from_env.sh`
  - `scripts/cloud/oci_retry.env.example`
  - `.gitignore`
- 변경 내용:
  - User/Tenancy/Compartment/Subnet/AD/이미지 조회를 포함한 A~Z 튜토리얼 신규 작성
  - 재부팅 후 `run_oci_retry_from_env.sh` 1줄 실행으로 재개 가능하도록 래퍼 스크립트 추가
  - 민감정보 파일(`scripts/cloud/oci_retry.env`) 커밋 방지 규칙 추가
- 효과/의미:
  - 학습자/초보자 기준으로 중단 없는 작업 재개와 운영 실수를 줄일 수 있음

### 2.6 429(TooManyRequests) 재시도 백오프 정책 보강
- 파일/모듈:
  - `scripts/cloud/oci_retry_launch_a1_flex.sh`
  - `scripts/cloud/oci_retry.env.example`
  - `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md`
- 변경 내용:
  - `InternalError/capacity` 외에 `TooManyRequests(429)`도 재시도 대상으로 추가
  - 429는 고정 600초 대신 지수 백오프 + 지터로 재시도하도록 분기
  - 기본값: `THROTTLE_RETRY_BASE_SECONDS=900`, `THROTTLE_RETRY_MAX_SECONDS=3600`, `THROTTLE_JITTER_MAX_SECONDS=120`
- 효과/의미:
  - 장시간 재시도 중 발생하는 OCI API 스로틀링으로 인한 조기 종료를 방지
  - 재시도 간격이 유연해져 사용자/테넌시 단위 rate limit 충돌을 완화

---

## 3. 변경 파일 목록
### 3.1 수정
1) `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`
2) `docs/runbooks/18_data_migration_runbook.md`
3) `docs/PROJECT_CHARTER.md`
4) `.gitignore`

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
10) `scripts/cloud/oci_retry_launch_a1_flex.sh`
11) `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md`
12) `scripts/cloud/run_oci_retry_from_env.sh`
13) `scripts/cloud/oci_retry.env.example`
14) `docs/runbooks/18_oci_a1_flex_a_to_z_guide.md`
15) `docs/troubleshooting/18_oci_a1_flex_capacity_and_throttle_retry.md`

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
  - `bash -n scripts/cloud/oci_retry_launch_a1_flex.sh`
  - `bash -n scripts/cloud/run_oci_retry_from_env.sh`
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
  - 추가 리스크: 작업 환경에 `oci` CLI가 없어 A1 자동 재시도 스크립트는 문법 검증까지만 수행

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
  - A1.Flex capacity 부족이 반복되어 CLI 자동 재시도 방식과 runbook을 추가
  - 사용자 요청에 따라 학생용 A~Z 가이드와 재부팅 후 재개 동선을 별도 문서/스크립트로 추가
  - 장시간 재시도 중 429로 프로세스가 종료되어, 429 전용 백오프 재시도 정책을 추가
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
- `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md`
- `docs/runbooks/18_oci_a1_flex_a_to_z_guide.md`
- `docs/troubleshooting/18_oci_a1_flex_capacity_and_throttle_retry.md`
- `deploy/cloud/oci/docker-compose.prod.yml`

---

## Phase 2 (2026-02-23): Compose 전환 후 Bot 상태 미표시 복구

### 1) 추가 구현/수정
- 파일:
  - `deploy/cloud/oci/docker-compose.prod.yml`
  - `src/dashboard/pages/2_market.py`
- 변경:
  - `bot`, `collector`에 `REDIS_HOST=redis`, `REDIS_PORT=6379`를 명시해 코드 경로별 Redis 접속 불일치 제거
  - 대시보드 경고 문구에서 K8s 전용 안내(`kubectl`)를 Compose 운영 기준으로 수정

### 2) 운영 DB 조치
- 적용 SQL(운영 DB):
  - `daily_risk_state`에 `buy_count`, `sell_count` 컬럼 추가
  - `migrations/v3_3_0_news_rss_only.sql` 적용으로 `news_articles` 등 RSS 테이블 생성

### 3) 검증
- 명령:
  - `docker compose -f deploy/cloud/oci/docker-compose.prod.yml ps`
  - `docker logs --tail 120 coinpilot-bot`
  - `docker exec coinpilot-redis redis-cli --scan --pattern 'bot:status:*'`
- 결과:
  - bot 정상 기동
  - `bot:status:KRW-BTC` 포함 심볼별 상태 키 생성 확인

### 4) 트레이드오프/리스크
- `migrations/v3_1_reject_tracking.sql`는 현재 DB에 `agent_decisions` 테이블이 없어 적용 실패(비핵심 경로)
- 따라서 추후 스키마 기준선 정리(환경별 필수/선택 마이그레이션 분리)가 필요
