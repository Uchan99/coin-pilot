# 18. 클라우드 마이그레이션(가성비 최적화) 계획

**작성일**: 2026-02-19  
**상태**: In Progress (2026-02-21)  
**우선순위**: P1 (상시 운영 안정성 + 비용 최적화)

---

## 0. 현재 프로젝트/클라우드 비교 요약

### 0.1 현재 프로젝트 리소스 현황 (코드 설정 기준)

현재 Kubernetes 매니페스트의 `requests/limits` 기준 코어 서비스(6개: bot, collector, dashboard, db, redis, n8n) 합계:

- Requests 합계
  - CPU: `600m`
  - Memory: `1,472Mi` (약 `1.44Gi`)
- Limits 합계
  - CPU: `2,600m`
  - Memory: `2,944Mi` (약 `2.88Gi`)
- 최소 스토리지(PVC 요청): `3Gi` (`db 1Gi + redis 1Gi + n8n 1Gi`)

운영 참고:
- Prometheus/Grafana는 일부 매니페스트에서 리소스 요청치가 미설정이므로 실제 운영 메모리 여유분이 필요
- 현재 클러스터에서 `kubectl top`은 `Metrics API not available` 상태라 실사용량 실측값은 미확보

### 0.2 권장 최소 인프라 사이즈

- 모니터링 포함 운영: `4 vCPU / 8GB RAM` 권장
- 경량 운영(모니터링 최소화): `2 vCPU / 4GB RAM` 가능

### 0.3 클라우드 서비스 비교 (요약)

1. Oracle Cloud (OCI)
- 장점: Always Free(Ampere A1/Block Volume 등) 활용 시 비용 최저
- 장점: 현재 프로젝트 규모에서 단일 VM 또는 경량 K8s(k3s) 운영에 유리
- 단점: Free 리소스는 리전/시점에 따라 가용성 변동 가능

2. AWS
- 장점: 생태계/확장성/운영 도구 성숙
- 단점: EKS는 control plane 고정비가 있어 소규모 프로젝트에 불리
- 대안: 단일 VM/LightSail 기반 운영은 가능

3. Azure
- 장점: AKS Free tier 시작이 가능하고 엔터프라이즈 연동 강점
- 단점: 동일 소규모 워크로드 기준 체감 비용이 OCI 대비 불리한 경우가 잦음

### 0.4 결론 (현 시점 권장)

- 1순위: **OCI + 단일 VM(Docker Compose) 또는 OCI + k3s**
- 2순위: AWS/Azure 단일 VM
- 비권장(현 단계): 소규모 워크로드에서 Managed K8s(EKS/AKS/OKE Enhanced) 선적용

---

## 1. 배경 및 문제 정의

현재는 Minikube 기반 배포로 개발/운영을 진행하고 있어, 데스크톱이 항상 켜져 있어야 서비스가 유지된다. 이 구조는 아래 운영 리스크가 있다.

1. 상시 가동 불가: PC 종료/절전 시 서비스 중단
2. 운영 일관성 부족: 로컬 환경 상태에 따라 가용성 변동
3. 모니터링 연속성 저하: 장시간 지표/로그 유지에 한계

목표는 **저비용으로 24/7 안정 운영 가능한 클라우드 환경**으로 전환하는 것이다.

---

## 2. 목표

### 2.1 기능 목표

1. 24/7 상시 운영 가능한 클라우드 런타임 확보
2. 현재 서비스 구성(bot/collector/dashboard/db/redis/n8n + monitoring) 동일 기능 유지
3. 배포/롤백 절차 표준화
4. 장애 시 재시작/복구 자동화

### 2.2 비용/운영 목표

1. 초기 월 인프라 비용 최소화(가능하면 Free/Tier 범위 활용)
2. 운영 복잡도 최소화(소규모 팀 기준)
3. 추후 Managed K8s 전환 가능한 이식성 유지

---

## 2.3 기술 스택 선택 이유 및 대안 비교

### 선택 기술 (1차)
- OCI VM + Docker Compose(현재 compose 자산 재사용)
- Caddy/Nginx + TLS(HTTPS)
- DB/Redis 볼륨 백업 스크립트 + cron

### 선택 이유
1. 현재 프로젝트는 단일 노드에서도 충분히 운영 가능
2. 기존 `deploy/docker-compose.yml` 재사용으로 전환 속도 빠름
3. Managed K8s 대비 고정비/운영비가 낮음

### 대안 비교

1. Managed Kubernetes(EKS/AKS/OKE) 즉시 전환
- 장점: 운영 표준화, 확장성
- 단점: 초기 비용/복잡도 과다, 현재 규모 대비 과설계

2. VM + k3s
- 장점: K8s 경험 유지, 추후 이관 용이
- 단점: Compose 대비 운영 난이도 증가

3. VM + Compose (선택)
- 장점: 가장 단순/저비용, 현재 자산 재사용
- 단점: K8s-native 운영 기능 일부 제한

### 예상 월 비용 범위(USD, 추정)

아래 금액은 2026-02-19 기준 계획 수립용 추정치이며, 리전/트래픽/스토리지/백업 정책에 따라 달라질 수 있다.

1. 최소 (POC/저비용 운영)
- 구성: OCI Always Free 범위 최대 활용, 모니터링 최소화
- 범위: **$0 ~ $10 / 월**
- 포함: 기본 컴퓨트(Free 범위), 소량 부가 스토리지/도메인/백업 부대비용

2. 권장 (현재 프로젝트 상시 운영)
- 구성: `4 vCPU / 8GB`급 단일 VM + Compose + 기본 모니터링
- 범위: **$20 ~ $60 / 월**
- 포함: VM + 블록스토리지 + 백업/소량 egress

3. 확장 (운영 여유/관측성 강화)
- 구성: 모니터링 상시 + 백업 보존 강화 + 스테이징 병행 또는 상위 스펙
- 범위: **$80 ~ $180 / 월**
- 포함: 추가 컴퓨트/스토리지/네트워크 여유분

참고 비교(동급 대안):
- AWS Lightsail Linux 번들: 4GB 플랜 `$24/월`, 8GB 플랜 `$44/월` (스토리지/트래픽 정책 별도 확인 필요)
- AKS/EKS/OKE Enhanced 같은 Managed K8s는 control plane 및 부가 리소스 비용으로 소규모 프로젝트에 상대적으로 불리할 수 있음

---

## 3. 목표 아키텍처

### 3.1 Phase 1 (권장): OCI 단일 VM + Docker Compose

- VM: `4 vCPU / 8GB RAM` (시작), 스토리지 80~120GB
- 구성
  - reverse proxy: Caddy/Nginx
  - app: bot, collector, dashboard, n8n
  - data: postgres(timescale), redis
  - ops: prometheus, grafana(선택)
- 백업
  - Postgres daily dump
  - Redis AOF + 주기 스냅샷
- 배포 파일
  - `docker-compose.prod.yml`에 core + n8n + monitoring 서비스를 명시적으로 포함

### 3.2 Phase 2 (선택): OCI VM + k3s

- 현재 k8s 매니페스트 재사용률을 높여 점진적 전환
- 운영 안정화 후 필요 시 OKE/AKS/EKS 검토

---

## 4. 구현 범위

## Phase A. 클라우드 준비 및 보안 기반 구축 (P0)

### 4.1 작업
1. OCI 계정/리전/가용영역 확정
2. VM 생성(권장 스펙 4vCPU/8GB)
3. 네트워크/방화벽 설정
   - 허용: `22`, `80`, `443` (+ 내부 모니터링 포트는 private)
   - 외부 노출 대상 명시: 기본 `dashboard(443)`만 외부 공개, `bot/collector/db/redis`는 내부망 전용
4. 도메인/DNS 연결
5. 시크릿 관리 방식 확정 (`.env` + OS 권한 + vault 대체안)

### 4.2 완료 기준
- SSH 접속, 도메인 연결, TLS 발급 가능 상태

---

## Phase B. 애플리케이션 이관 (P0)

### 4.3 작업
1. 컨테이너 이미지 빌드/배포 방식 확정
   - 옵션1: VM에서 직접 build
   - 옵션2: GHCR/ECR 등 레지스트리 push 후 pull
2. `deploy/docker-compose.yml` 클라우드용 오버라이드 작성
   - 리소스 제한
   - 볼륨 경로
   - restart 정책
   - n8n + monitoring(prometheus/grafana) 서비스 추가
3. 환경변수 동기화
   - `.env.example`을 K8s `secret.yaml.example` 기준으로 정렬
   - bot: `LLM_MODE`, `N8N_URL`, `N8N_WEBHOOK_SECRET`, `OPENAI_API_KEY` 등 누락 항목 반영
   - dashboard: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `UPBIT_ACCESS_KEY`, `UPBIT_SECRET_KEY` 반영
   - 보안: `bot` 포트는 외부 바인딩 금지(내부 `expose` 또는 loopback 제한)
4. Prometheus 타겟 경로 전환
   - K8s DNS -> Compose 서비스명(`bot:8000`)으로 변경
5. 서비스 기동 및 헬스체크
6. 대시보드/봇/n8n 접속 검증

### 4.4 데이터 마이그레이션 절차 (필수)

1. PostgreSQL
   - `pg_dump`(minikube) -> 전송 -> `pg_restore`(cloud)
   - 검증: 테이블 건수(`market_data`, `trading_history`, `daily_risk_state`) 일치 확인
2. Redis
   - AOF/RDB export 후 cloud로 복원(또는 cold start 정책 선택)
3. DB 초기화 전략 명시
   - 경로 A: `pg_dump/restore` 사용 시 `init.sql` 재실행 금지
   - 경로 B: 빈 DB 시작 시 `init.sql` -> `migrations/*` 순차 적용
4. 마이그레이션 버전 정합성 체크
   - `v3_2_1`, `v3_2_2` 등 필수 스키마 적용 여부 검증
### 4.5 완료 기준
- 핵심 서비스 6개가 VM 재부팅 후 자동 기동
- 기본 기능(수집/판단/대시보드 조회/알림) 정상 동작
- 데이터 이관 후 핵심 테이블 row count/샘플 조회 정합성 확인

---

## Phase C. 데이터 보호/운영 자동화 (P0)

### 4.6 작업
1. Postgres 백업 스크립트 + cron(일간)
2. Redis 백업 정책 확정(AOF 유지 + 주기 보관)
3. 로그 로테이션 설정
4. 장애 대응 runbook 작성
5. 백업 보관 정책(retention) 명시
   - 예: 일간 7일 + 주간 4주 보관

### 4.7 완료 기준
- 복구 리허설(백업 복원) 1회 통과
- 운영 Runbook 문서화 완료

---

## Phase D. 비용 최적화 및 모니터링 튜닝 (P1)

### 4.8 작업
1. 1주 운영 후 CPU/MEM/디스크 실사용량 수집
2. VM 스펙 다운/업 시뮬레이션
3. 모니터링 스택 상시 운영 여부 결정
   - 비용 절감을 위해 Prom/Grafana는 필요 시만 기동 가능
4. 스케일 전략 정의
   - 트래픽/워크로드 증가 시 k3s 또는 Managed K8s 전환 기준 수립
5. 아키텍처/이미지 호환성 점검
   - OCI Ampere A1(ARM64) 사용 시 이미지 호환성 확인
   - 필요 시 `docker buildx` multi-arch 빌드 또는 x86 VM 선택

### 4.9 완료 기준
- 월 비용 추정치 ±15% 이내 정확도 확보
- 리소스 과/부족 없는 안정 스펙 확정

---

## 5. 파일/모듈 계획

신규(권장):
- `deploy/cloud/oci/bootstrap.sh`
- `deploy/cloud/oci/docker-compose.prod.yml`
- `deploy/cloud/oci/systemd/coinpilot-compose.service`
- `deploy/cloud/oci/.env.example`
- `scripts/backup/postgres_backup.sh`
- `scripts/backup/redis_backup.sh`
- `docs/runbooks/18_data_migration_runbook.md`

수정:
- `deploy/docker-compose.yml` (환경 분리 변수 정리)
- `docs/PROJECT_CHARTER.md` (배포 전략 업데이트)

문서:
- `docs/work-result/18_cloud_migration_cost_optimized_result.md`
- `docs/troubleshooting/18_cloud_migration_and_ops.md`

---

## 6. 검증 계획

### 6.1 기능 검증
1. bot/collector/dashboard/n8n 정상 동작
2. DB/Redis 연결 및 읽기/쓰기 정상
3. AI Decision/Discord 알림 정상
4. Prometheus scrape 타겟이 Compose 서비스명 기준으로 수집되는지 확인

### 6.2 운영 검증
1. 24시간 연속 가동 중 무중단
2. VM 재부팅 후 서비스 자동 복구
3. 백업/복구 시나리오 검증
4. 데이터 이관 정합성 검증(row count + 샘플 레코드)

### 6.3 비용 검증
1. 1주 운영비 추적(컴퓨트/스토리지/네트워크)
2. 모니터링 on/off 비용 차이 측정
3. 목표 예산 범위 충족 여부 판단

---

## 7. 릴리즈 전략

1. Step 1: 클라우드 환경만 먼저 구축(서비스 미오픈)
2. Step 2: 내부 테스트 데이터로 dry-run + 데이터 이관 리허설
3. Step 3: 운영 전환(기존 Minikube 병행 24~48h)
   - 병행 기간 중 한쪽 bot은 read-only 또는 비활성화하여 중복 매매 방지
4. Step 4: 안정화 후 Minikube 상시 운영 중단

롤백:
- 장애 시 Minikube 환경으로 즉시 트래픽 복귀
- 클라우드 환경은 원인 분석 후 재시도

---

## 8. 리스크 및 대응

1. 클라우드 자원/리전 가용성 문제
- 대응: 대체 리전/대체 VM 타입 후보 사전 확보

2. 시크릿 유출 리스크
- 대응: 최소 권한, `.env` 권한 제한, 키 주기적 교체

3. 데이터 손실 리스크
- 대응: 일간 백업 + 복구 리허설 + 보관 정책

4. 비용 급증
- 대응: 예산 알림, 리소스 상한, 모니터링 선택적 운영

---

## 9. 선행/후행 의존성

선행 권장:
- 14/15/16/17 핵심 변경 중 최소 P0 범위 안정화 후 이관
- 이미지 빌드 파이프라인(로컬 build vs 레지스트리) 결정

후행:
- 클라우드 안정화 후 CI/CD 자동 배포 계획(19번) 수립 권장

---

## 10. 산출물

1. 클라우드 운영 배포 스크립트/설정
2. 백업/복구 자동화 스크립트
3. 전환 체크리스트 + 운영 runbook
4. 결과 문서(work-result) + Charter 반영

---

## 11. 리뷰 코멘트 반영 이력

### Round 1 (2026-02-19) — Claude Code Review

### 반영 결과 요약

1. [major] compose에 n8n/monitoring 누락: **반영 완료**
- 변경: Phase B에 `docker-compose.prod.yml` 확장 작업 명시
- 위치: `3.1`, `4.3`

2. [major] 환경변수 불일치: **반영 완료**
- 변경: `.env.example` 동기화 + bot/dashboard 누락 변수 반영 명시
- 위치: `4.3`, `5`

3. [major] 데이터 마이그레이션 미기술: **반영 완료**
- 변경: `4.4 데이터 마이그레이션 절차` 신규 추가
- 위치: `4.4`, `6.2`, `7`

4. [major] DB 초기화 전략 미정: **반영 완료**
- 변경: `pg_restore 경로` vs `init.sql + migrations 경로` 분기 명시
- 위치: `4.4`

5. [minor] reverse proxy/외부 노출 정책: **반영 완료**
- 변경: 외부 공개 대상 최소화 정책 명시
- 위치: `4.1`

6. [minor] Prometheus 타겟 전환: **반영 완료**
- 변경: K8s DNS -> Compose 서비스명 전환 항목 추가
- 위치: `4.3`, `6.1`

7. [minor] systemd 가이드 필요: **반영 완료**
- 변경: service 파일 산출물 유지 + runbook 산출물 추가
- 위치: `5`

8. [minor] ARM64 호환성 확인: **반영 완료**
- 변경: Ampere A1 호환성 점검 및 buildx/x86 대안 명시
- 위치: `4.8`

9. [minor] bot 포트 노출 보안: **반영 완료**
- 변경: bot 외부 바인딩 금지 정책 명시
- 위치: `4.3`

10. [minor] 백업 retention 미정: **반영 완료**
- 변경: 일간/주간 보관 정책 추가
- 위치: `4.6`

11. [minor] 병행 운영 중 중복 매매 리스크: **반영 완료**
- 변경: 병행 기간 bot read-only/비활성화 정책 추가
- 위치: `7`

## Claude Code Review

**검증일**: 2026-02-19
**검증 기준**: 현행 프로젝트 구성 대비 계획 정합성, 누락 항목, 운영 리스크

### 현행 인프라 크로스 체크

| # | 항목 | 판정 | 비고 |
|---|------|------|------|
| 1 | K8s 리소스 합계 (계획서 0.1) | ✅ 정확 | 실측: bot(100m/256Mi), collector(50m/128Mi), dashboard(100m/256Mi), db(200m/512Mi), redis(50m/64Mi), n8n(100m/256Mi) → requests CPU 600m, MEM ~1,472Mi 일치 |
| 2 | docker-compose.yml 존재 | ✅ 확인 | `deploy/docker-compose.yml` — db, redis, collector, bot, dashboard 5개 서비스 정의 |
| 3 | Dockerfile 존재 | ✅ 확인 | `deploy/docker/` 하위 bot, collector, dashboard 3개 |
| 4 | K8s 매니페스트 존재 | ✅ 확인 | `k8s/` 하위 apps(4), db(3), monitoring(5), base(3), jobs(1) |
| 5 | Monitoring 구성 | ✅ 확인 | Prometheus config + Grafana provisioning(datasources, dashboards 2개) 존재 |
| 6 | Secret 관리 | ✅ 확인 | K8s: `secret.yaml` + `secret.yaml.example`. 7개 시크릿(ANTHROPIC_API_KEY, OPENAI_API_KEY, UPBIT_ACCESS/SECRET, N8N_WEBHOOK_SECRET, DISCORD_WEBHOOK_URL, DB_PASSWORD) |

### Major Findings

1. **docker-compose.yml에 n8n/monitoring 서비스 누락**
   - 현재 `deploy/docker-compose.yml`에는 db, redis, collector, bot, dashboard 5개만 정의
   - **n8n**, **prometheus**, **grafana**가 빠져 있음
   - 계획서 Phase B에서 "6개 핵심 서비스" 기동을 완료 기준으로 잡았으나, n8n은 compose에 없어서 클라우드 전환 시 추가 작성이 필요
   - **조치**: Phase B 작업(4.3)에 "n8n + monitoring 서비스를 `docker-compose.prod.yml`에 추가" 명시 필요

2. **환경변수 불일치 — docker-compose vs K8s**
   - K8s 매니페스트에는 `LLM_MODE`, `N8N_URL`, `N8N_WEBHOOK_SECRET`, `OPENAI_API_KEY`, `DISCORD_WEBHOOK_URL`, `UPBIT_ACCESS/SECRET_KEY(dashboard)` 등이 설정되어 있으나, 현재 docker-compose.yml에는 일부만 반영됨
   - 특히 bot 서비스: compose에 `ANTHROPIC_API_KEY`만 있고, `LLM_MODE`, `N8N_URL`, `N8N_WEBHOOK_SECRET`, `OPENAI_API_KEY` 누락
   - dashboard 서비스: compose에 `DATABASE_URL`만 있고, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `UPBIT_ACCESS/SECRET_KEY` 누락 (챗봇 기능에 필요)
   - **조치**: Phase B에서 `.env.example` 파일을 K8s secret 기준으로 작성하고, compose의 환경변수를 완전히 맞추는 작업 명시 필요

3. **데이터 마이그레이션 절차 미기술**
   - 계획서에 "dry-run → 운영 전환" 단계는 있으나, **기존 Minikube의 PostgreSQL/Redis 데이터를 클라우드로 이관하는 구체적 절차**가 없음
   - 현재 운영 중인 `market_data`, `trading_history`, `daily_risk_state` 등의 데이터 보존이 필수
   - **조치**: Phase B 또는 별도 섹션에 "데이터 마이그레이션 절차" 추가 (pg_dump → scp → pg_restore, Redis RDB export 등)

4. **DB 초기화 스크립트(`init.sql`) 의존**
   - docker-compose.yml이 `./db/init.sql`을 마운트하여 초기화하는데, 이 스크립트는 빈 DB에서만 실행됨
   - 클라우드 전환 시 기존 데이터를 마이그레이션하면 init.sql이 중복 실행될 수 있고, 빈 DB로 시작하면 `migrations/` 폴더의 스키마 변경(v3_2_1, v3_2_2 등)을 순차 적용해야 함
   - **조치**: 마이그레이션 전략 명시 — "pg_dump 복원 사용 시 init.sql 스킵" 또는 "빈 DB + init.sql + migrations 순차 적용" 중 선택

### Minor Findings

1. **Reverse Proxy 필요성 재검토**: Caddy/Nginx를 Phase A에 포함했으나, 현재 대시보드는 Streamlit(8501), bot은 FastAPI(8000)으로 직접 노출 중. 외부 접근이 대시보드 조회 정도라면 Streamlit의 `--server.address 0.0.0.0` + 포트 직접 노출도 가능. TLS가 필요하면 Caddy가 가장 단순하긴 하나, 계획서에 어떤 서비스를 외부 노출할지 명시가 없음.

2. **Prometheus 타겟 설정 변경**: 현재 `deploy/monitoring/prometheus-config.yaml`은 K8s 서비스 DNS(예: `bot.coin-pilot-ns.svc:8000`)를 타겟으로 사용할 가능성이 높음. Docker Compose 환경에서는 `bot:8000` 형태로 변경 필요. Phase B 작업에 반영 권장.

3. **systemd 서비스 파일**: 계획서 5장에 `deploy/cloud/oci/systemd/coinpilot-compose.service` 작성을 명시한 것은 좋음. 다만 `docker compose` vs `docker-compose` (V1/V2) 차이, `WorkingDirectory`, `ExecStartPre`(pull) 등 구체적인 service 파일 내용 가이드가 있으면 구현 시 혼선이 줄어듦.

4. **OCI Always Free ARM(Ampere A1) 호환성**: OCI Free Tier의 핵심인 Ampere A1은 ARM64 아키텍처. 현재 Dockerfile들이 x86 기반으로 빌드되고 있을 가능성이 높음. ARM64에서 `timescale/timescaledb:latest-pg15`, `redis:alpine` 등 이미지 호환 여부 확인 필요. 비호환 시 `docker buildx`로 multi-arch 빌드하거나 x86 VM 선택이 필요하며, 이는 비용에 영향.

5. **bot 서비스 포트 노출 보안**: docker-compose.yml에서 bot이 `8000:8000`으로 호스트 바인딩됨. 클라우드에서는 내부 전용 서비스(bot, collector)의 포트를 호스트에 바인딩하지 않는 것이 안전. `expose`로 변경하거나 `127.0.0.1:8000:8000`으로 제한 필요.

6. **백업 보관 정책**: Phase C에서 "일간 백업"을 명시했으나, 보관 기간(retention)이 없음. 디스크 용량 관리를 위해 "최근 7일 보관, 주간 1건은 30일 보관" 등의 정책 명시 권장.

7. **Minikube → Cloud 병행 운영 시 데이터 충돌**: 릴리즈 전략 Step 3에서 24~48h 병행을 언급. 두 환경이 동일한 Upbit API로 데이터를 수집하면 문제 없으나, bot이 두 곳에서 동시에 매매 판단을 내리면 중복 주문 리스크가 있음. 병행 기간 중 한쪽 bot은 read-only 모드로 운영하는 것이 안전.

### 구조적 의견

계획의 Phase 분리(A→B→C→D)와 비용 추정이 체계적이며, OCI Free Tier 활용 판단도 현 프로젝트 규모에 적합합니다. 다만 **인프라 마이그레이션 계획에서 가장 중요한 "데이터 이관"과 "환경변수 동기화"가 구체적으로 빠져 있어**, 실제 구현 시 가장 큰 삽질 포인트가 될 수 있습니다.

### 종합 판정: **PASS (조건부)** ✅

Major 4건(n8n/monitoring compose 누락, 환경변수 불일치, 데이터 마이그레이션 미기술, DB 초기화 전략)을 Phase B 착수 전에 반영하면 구현 가능.

### Round 2 최종 검증 (2026-02-19)

**판정: APPROVED** ✅ — 미해결 항목 없음. 구현 착수 가능.

- Major 4건 반영 확인 완료
  - n8n/monitoring compose 포함 (3.1:L143-150, 4.3:L187)
  - 환경변수 동기화 + `.env.example` (4.3:L188-192, 5:L258)
  - 데이터 마이그레이션 절차 신규 추가 (4.4:L198-209)
  - DB 초기화 경로 A/B 분기 명시 (4.4:L205-207)
- Minor 7건 반영 확인 완료
  - 외부 노출 정책 (4.1:L168)
  - Prometheus 타겟 전환 (4.3:L193-194, 6.1:L279)
  - runbook 산출물 (5:L261)
  - ARM64 호환성 점검 (4.8:L242-244)
  - bot 포트 보안 (4.3:L192)
  - 백업 retention (4.6:L224-225)
  - 병행 운영 중복 매매 방지 (7:L299)

---

## 12. 참고 자료

- Oracle Cloud Free Tier: https://www.oracle.com/cloud/free/
- Oracle OKE Pricing: https://www.oracle.com/cloud/cloud-native/container-engine-kubernetes/pricing/
- AWS EKS Pricing: https://aws.amazon.com/eks/pricing/
- AWS Lightsail Pricing: https://aws.amazon.com/lightsail/pricing/
- Azure AKS Pricing: https://azure.microsoft.com/en-au/pricing/details/kubernetes-service
- Azure AKS Tier 문서: https://learn.microsoft.com/azure/aks/free-standard-pricing-tiers
- Azure B-series VM: https://azure.microsoft.com/en-us/pricing/details/virtual-machines/series/

---

## 13. Prometheus/Grafana 운영 체크리스트 (실행 단계 추가)

아래 체크리스트는 "연결은 되어 있으나 실사용이 미숙한 상태"를 빠르게 벗어나기 위한 최소 운영 절차다.

### 13.1 일일 점검 (5분)
1. Prometheus `Status > Targets`에서 `coinpilot-core`가 `UP`인지 확인
2. Prometheus Explore에서 `up` 쿼리 결과 확인
3. Grafana 대시보드에서 아래 4개 지표 최근 6시간 추세 확인
   - `coinpilot_active_positions`
   - `coinpilot_total_pnl`
   - `coinpilot_trade_count_total`
   - `coinpilot_api_latency_seconds_sum / coinpilot_api_latency_seconds_count`

### 13.2 이상 징후 확인
1. `up == 0` 발생 시 bot 컨테이너/네트워크 우선 점검
2. `coinpilot_api_latency_seconds_*` 급등 시 거래소 API 지연 여부 확인
3. `coinpilot_trade_count_total` 장시간 변화 없음 + bot health 실패 동반 시 봇 동작 중단 의심

### 13.3 주간 운영 리뷰
1. 7일 기준 평균 API 지연 및 최대치 기록
2. 알림 실패(n8n webhook 실패) 로그 건수 기록
3. VM 자원(CPU/MEM/Disk) 사용률을 월 비용과 함께 기록해 스펙 조정 근거 확보

---

## 14. 계획 변경 이력

### 2026-02-21
1. 상태를 `Draft`에서 `In Progress`로 변경
2. Prometheus/Grafana 실사용 가이드를 `13. 운영 체크리스트`로 추가
3. 18번 산출물 구현(Compose/백업/Runbook/Result) 착수 기준을 명시
