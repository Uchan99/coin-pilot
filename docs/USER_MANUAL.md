# CoinPilot User Manual

Last Updated: 2026-02-23  
Version: v3.3 (Compose 운영 기준)

---

## 1. 개요
CoinPilot는 규칙 기반 자동매매 + AI 보조 분석 시스템이다.  
현재 운영 기본 모드는 **Docker Compose**이며, Minikube는 레거시/검증용으로 유지한다.

관련:
- 시작 가이드: `docs/daily-startup-guide.md`
- 데이터 이관/복구: `docs/runbooks/18_data_migration_runbook.md`
- 전환/복구 트러블슈팅: `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`

---

## 2. 대시보드 접속

### 2.1 서비스 실행
```bash
cd /home/syt07203/workspace/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml up -d
```

### 2.2 주소
- Dashboard: `http://127.0.0.1:8501`
- n8n: `http://127.0.0.1:5678`
- Grafana: `http://127.0.0.1:3000`
- Prometheus: `http://127.0.0.1:9090`

주의:
- Compose 모드에서는 `kubectl port-forward`가 필요 없다.

---

## 3. 로그인/접근 제어

### 3.1 Dashboard
- 접속 시 `DASHBOARD_ACCESS_PASSWORD` 입력 필요

### 3.2 n8n
- `N8N_BASIC_AUTH_USER` / `N8N_BASIC_AUTH_PASSWORD`로 로그인

### 3.3 Grafana
- `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD` 사용

---

## 4. 화면별 기능

### 4.1 Overview
- 총 평가액, 잔고, 누적 손익, 거래 횟수 확인
- 보유 포지션(있을 때) 수익률/평가금 확인

### 4.2 Market
- 캔들 차트
- Bot Brain (실시간 상태, 지표, 사유)
- 레짐(BULL/SIDEWAYS/BEAR/UNKNOWN)

### 4.3 Risk
- 일일 리스크 상태, 거래 제한/쿨다운 확인

### 4.4 History
- 체결 내역 조회

### 4.5 System
- DB/Redis/n8n 연결 상태
- 최근 AI 의사결정 이력(`agent_decisions`)

---

## 5. 운영 명령 모음

### 5.1 상태 확인
```bash
cd /home/syt07203/workspace/coin-pilot/deploy/cloud/oci
docker compose -f docker-compose.prod.yml ps
```

### 5.2 로그 확인
```bash
docker logs --tail 200 coinpilot-bot
docker logs --tail 200 coinpilot-collector
docker logs --tail 200 coinpilot-dashboard
```

### 5.3 bot만 재시작
```bash
docker compose --env-file .env -f docker-compose.prod.yml restart bot
```

### 5.4 bot+dashboard 재빌드
```bash
docker compose --env-file .env -f docker-compose.prod.yml up -d --build bot dashboard
```

---

## 6. 보안 점검

배포/설정 변경 후 반드시 실행:
```bash
cd /home/syt07203/workspace/coin-pilot
./scripts/security/preflight_security_check.sh
```

주요 점검 항목:
1. `deploy/cloud/oci/.env` 권한 600
2. 필수 시크릿 미설정/기본값 사용 여부
3. n8n env 접근 차단 설정
4. n8n webhook secret 검증 노드 존재
5. 내부 서비스 포트 직접 노출 금지

---

## 7. 자주 보는 이슈

### 7.1 System 페이지 `agent_decisions` 오류
- 원인: DB 스키마 누락
- 조치: 마이그레이션 적용
- 참고: `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`

### 7.2 Overview 데이터가 비어 보임
- 원인1: 현재 DB에 해당 데이터가 실제로 없음
- 원인2: Minikube DB와 Compose DB가 분리된 상태
- 참고: `docs/runbooks/18_data_migration_runbook.md`

### 7.3 n8n 상태가 Error
1. `docker compose ... ps n8n dashboard`
2. dashboard 컨테이너 내부에서 `http://n8n:5678/healthz` 확인

---

## 8. Legacy: Minikube 운영 명령
레거시/검증 용도:
```bash
minikube start
kubectl get pods -n coin-pilot-ns
```

현재 기본 운영은 Compose이므로, Minikube 명령은 필요 시에만 사용한다.
