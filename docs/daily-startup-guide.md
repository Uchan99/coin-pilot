# CoinPilot Daily Startup Guide

작성일: 2026-02-06  
최종 업데이트: 2026-02-23  
목적: 데스크톱/WSL 재시작 후 운영 환경을 빠르게 복구하기 위한 일일 체크리스트

관련 문서:
- 사용자 가이드: `docs/USER_MANUAL.md`
- 데이터 이관: `docs/runbooks/18_data_migration_runbook.md`
- 보안 사전점검: `scripts/security/preflight_security_check.sh`
- 전환/복구 트러블슈팅: `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`

---

## 0. 운영 모드 기준 (중요)
현재 기본 운영 모드는 **Docker Compose**다.

| 모드 | 상태 | 사용 목적 |
|---|---|---|
| Docker Compose (OCI/로컬) | **Primary** | 일일 운영, 장애 복구, 보안 점검 |
| Minikube (K8s) | Legacy/검증용 | K8s 실험, 과거 데이터 원본 확인 |

전환 배경과 비교는 아래 문서에 기록되어 있다.
- `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`

---

## 1. 매일 시작 절차 (Compose 기준)

### 1.1 작업 경로 이동
```bash
cd /home/syt07203/workspace/coin-pilot
```

### 1.2 보안 사전 점검
```bash
./scripts/security/preflight_security_check.sh
```

성공 기준:
- 마지막 줄이 `[RESULT] PASSED`

실패 시:
- `deploy/cloud/oci/.env`의 필수 키/권한(600)부터 수정

### 1.3 서비스 기동
```bash
cd deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml up -d
```

### 1.4 서비스 상태 확인
```bash
docker compose -f docker-compose.prod.yml ps
```

정상 기준:
- `coinpilot-db`, `coinpilot-redis`, `coinpilot-collector`, `coinpilot-bot`, `coinpilot-dashboard`, `coinpilot-n8n`, `coinpilot-prometheus`, `coinpilot-grafana` 모두 `Up`

### 1.5 빠른 로그 점검
```bash
docker logs --tail 100 coinpilot-bot
docker logs --tail 100 coinpilot-collector
```

---

## 2. 접속 주소 (Compose)

기본은 로컬 루프백 바인딩:
- Dashboard: `http://127.0.0.1:8501`
- n8n: `http://127.0.0.1:5678`
- Grafana: `http://127.0.0.1:3000`
- Prometheus: `http://127.0.0.1:9090`

주의:
- Compose 모드에서는 `kubectl port-forward`가 필요 없다.
- 같은 포트를 `kubectl port-forward`가 점유하면 Compose 바인딩 충돌이 발생한다.

---

## 3. 배포/재기동 루틴

### 3.1 bot + dashboard만 재빌드
```bash
cd /home/syt07203/workspace/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml up -d --build bot dashboard
```

### 3.2 전체 재기동
```bash
docker compose --env-file .env -f docker-compose.prod.yml down
docker compose --env-file .env -f docker-compose.prod.yml up -d
```

### 3.3 종료
```bash
docker compose --env-file .env -f docker-compose.prod.yml stop
```

---

## 4. 보안 운영 체크 (일일/변경 후)

핵심 항목:
1. 외부 공개 포트 정책 유지 (`22/80/443`만 외부 허용, 내부 서비스 직접 노출 금지)
2. `deploy/cloud/oci/.env` 권한 `600`
3. n8n 기본 인증 활성화 및 계정값 적용
4. `N8N_BLOCK_ENV_ACCESS_IN_NODE=true`
5. 모든 워크플로우에 webhook secret 검증 노드 유지
6. dashboard 접근 비밀번호(`DASHBOARD_ACCESS_PASSWORD`) 사용

자동 확인:
```bash
cd /home/syt07203/workspace/coin-pilot
./scripts/security/preflight_security_check.sh
```

---

## 5. 장애 시 즉시 확인

### 5.1 Bot Brain 상태 미표시
1. `docker logs --tail 200 coinpilot-bot`
2. `docker exec coinpilot-redis redis-cli --scan --pattern 'bot:status:*'`
3. DB 스키마 확인: `agent_decisions`, `daily_risk_state` 컬럼 누락 여부

참고:
- `docs/troubleshooting/18_compose_bot_status_missing_after_migration.md`
- `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`

### 5.2 System Health n8n 빨간색
1. `docker compose -f docker-compose.prod.yml ps n8n dashboard`
2. `docker exec coinpilot-dashboard sh -lc 'curl -sS -o /tmp/h.out -w \"%{http_code}\\n\" http://n8n:5678/healthz; cat /tmp/h.out'`

---

## 6. Legacy: Minikube 모드 (필요할 때만)

Minikube는 현재 기본 운영 모드가 아니다.
데이터 원본 검증/과거 환경 비교 시에만 사용한다.

```bash
minikube start
kubectl get pods -n coin-pilot-ns
```

주의:
- Minikube와 Compose를 동시에 운영할 수 있지만, 같은 로컬 포트 포워딩은 충돌할 수 있다.
- 원본 데이터 확인 후에는 Compose 기준 DB 동기화 절차를 따른다.

---

## 7. 일일 마감 체크
1. 에러 로그 장기 반복 없음
2. `preflight` 결과 `PASSED`
3. 필요 시 백업 스크립트 수동 실행
```bash
./scripts/backup/postgres_backup.sh
./scripts/backup/redis_backup.sh
```
