# 18. WSL/OCI 로컬-클라우드 통합 운영 마스터 Runbook

작성일: 2026-02-25  
상태: Ready  
대상: CoinPilot 운영/개발을 직접 수행하는 사용자(초보~중급)  
관련 계획: `docs/work-plans/18-12_wsl_oci_local_cloud_operations_master_runbook_plan.md`, `docs/work-plans/18-13_oci_24h_monitoring_checklist_plan.md`, `docs/work-plans/18-14_oci_24h_monitoring_script_automation_plan.md`  
관련 결과: `docs/work-result/18-12_wsl_oci_local_cloud_operations_master_runbook_result.md`, `docs/work-result/18-13_oci_24h_monitoring_checklist_result.md`, `docs/work-result/18-14_oci_24h_monitoring_script_automation_result.md`  

관련 문서:
- 인스턴스 생성/OCI CLI: `docs/runbooks/18_oci_a1_flex_a_to_z_guide.md`
- A1 용량 자동 재시도: `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md`
- 데이터 이관/운영 등록(systemd/cron): `docs/runbooks/18_data_migration_runbook.md`
- OCI 런타임 보안 점검: `docs/runbooks/20-01_oci_runtime_security_verification_checklist.md`

---

## 0. 이 문서의 목적

이 문서는 아래를 한 번에 이해시키는 "통합 운영 기준" 문서다.

1. WSL(로컬)과 OCI(클라우드)의 역할 차이
2. 지금 서비스가 실제로 어디에서 돌아가는지 판단하는 방법
3. 운영 시 어떤 터미널에서 어떤 명령을 실행해야 하는지
4. 백업/복구/모니터링/알람까지 포함한 운영 루틴
5. 오늘 실제 발생했던 혼선(포트/볼륨/n8n) 재발 방지

---

## 1. 큰 그림: 환경별 역할

| 환경 | 목적 | 장점 | 단점 | 권장 사용 시점 |
|---|---|---|---|---|
| WSL 로컬 | 개발/디버깅/실험 | 빠른 수정, 즉시 테스트 | PC 종료 시 중단, 포트 혼선 쉬움 | 코드 변경, 실험, 임시 테스트 |
| OCI VM | 운영(24x7) | 항상 켜짐, 재부팅 자동복구 가능 | 원격 관리 필요, 비용/보안 관리 필요 | 실제 운영, 지속 관찰 |
| Minikube | K8s 검증(레거시) | K8s 실험 가능 | 현재 운영 표준 아님 | 과거 환경 재현, K8s 학습 |

현재 CoinPilot 운영 표준은 **OCI + Docker Compose**다.

---

## 2. 헷갈리지 않는 법: "지금 어디를 보고 있나"

### 2.1 프롬프트로 구분
- WSL: `syt07203@HYC09:...`
- OCI: `ubuntu@coinpilot-ins:...`

### 2.2 systemd 명령으로 구분
- 아래 명령은 **OCI에서만** 성공한다.
```bash
systemctl status coinpilot-compose.service
```
- WSL에서 치면 `Unit ... could not be found`가 정상 반응이다.

### 2.3 localhost 포트 혼선 방지
같은 `localhost`라도 환경이 다르면 전혀 다른 서비스를 가리킬 수 있다.

운영 접속은 아래처럼 "로컬 포트 별칭"을 고정한다.

```powershell
ssh -i "C:\Users\syt07\.ssh\ssh-key-2026-02-24.key" \
  -L 18501:127.0.0.1:8501 \
  -L 15678:127.0.0.1:5678 \
  -L 13000:127.0.0.1:3000 \
  -L 19090:127.0.0.1:9090 \
  ubuntu@168.107.40.180
```

브라우저 접속:
- Dashboard: `http://localhost:18501`
- n8n: `http://localhost:15678`
- Grafana: `http://localhost:13000`
- Prometheus: `http://localhost:19090`

---

## 3. OCI에 실제로 구성된 운영 스택

서비스(Compose):
1. `coinpilot-db` (TimescaleDB)
2. `coinpilot-redis`
3. `coinpilot-collector`
4. `coinpilot-bot`
5. `coinpilot-dashboard`
6. `coinpilot-n8n`
7. `coinpilot-prometheus`
8. `coinpilot-grafana`

자동복구:
- systemd unit: `coinpilot-compose.service`
- 상태 기준:
  - `enabled`
  - `active (exited)` 또는 `active`

핵심 포인트:
- `active (exited)`는 oneshot service 특성상 정상이다.
- 컨테이너가 `Up`이면 서비스는 정상 운영 중이다.

---

## 4. 왜 Minikube에서 Compose로 전환했나

### 4.1 전환 이유
1. 비용/리소스 효율
- 단일 VM에서 운영 가능
- Free/PAYG 범위 내 관리가 쉬움

2. 운영 단순성
- `docker compose up -d`로 전체 스택 제어
- 초보자 운영 난이도 낮음

3. 현재 규모 적합성
- CoinPilot 현재 트래픽/컴포넌트 수 기준으로 K8s 오버헤드가 큼

### 4.2 트레이드오프
- K8s 고급 기능(오토스케일, 롤링 전략 다양성)은 제한
- 대신 systemd + 백업 + 알람으로 운영 안정성 보완

---

## 5. 네트워크/보안 기준 (OCI)

### 5.1 보안 규칙 기본
- Ingress 허용:
  - `22` (SSH)
  - `80` (HTTP)
  - `443` (HTTPS)
- 내부 서비스 포트(`5432/6379/5678/8000/8501/9090/3000`)는 외부 비공개

### 5.2 Source/Destination 규칙 핵심
- SSH 룰은 Source를 본인 공인 IP `/32`로 제한 권장
- HTTP/HTTPS는 `0.0.0.0/0` 허용 가능
- Security List에서:
  - Source Port Range: 보통 `All`
  - Destination Port Range: 서비스 포트(22,80,443)

### 5.3 시크릿/환경변수
운영 기준 env 파일:
- `/opt/coin-pilot/deploy/cloud/oci/.env`

검증:
```bash
cd /opt/coin-pilot
./scripts/security/preflight_security_check.sh /opt/coin-pilot/deploy/cloud/oci/.env
```

성공 기준:
- `[RESULT] PASSED`

---

## 6. 일일 운영 루틴 (OCI)

### 6.1 상태 점검 1분 루틴
```bash
systemctl status coinpilot-compose.service --no-pager
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml ps
```

### 6.2 오류 징후 확인
```bash
docker compose --env-file .env -f docker-compose.prod.yml logs --since=10m bot | egrep -i "critical|traceback|undefined|failed"
```

### 6.3 메트릭 정상 확인
- Prometheus target `coinpilot-core`가 `UP`
- Grafana 룰 3개가 `Normal`

---

## 7. 백업/복구 체계 (운영 핵심)

### 7.1 백업 대상
1. Postgres: `scripts/backup/postgres_backup.sh`
2. Redis: `scripts/backup/redis_backup.sh`
3. n8n: `scripts/backup/n8n_backup.sh`

### 7.2 보관 정책
- 일간 7일
- 주간 4주
- SHA256 무결성 파일 생성

### 7.3 cron 등록 예시 (`/etc/cron.d/coinpilot-backup`)
```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
SHELL=/bin/bash
5 3 * * * root /opt/coin-pilot/scripts/backup/postgres_backup.sh >> /var/log/coinpilot/postgres-backup.log 2>&1
15 3 * * * root /opt/coin-pilot/scripts/backup/redis_backup.sh >> /var/log/coinpilot/redis-backup.log 2>&1
25 3 * * * root /opt/coin-pilot/scripts/backup/n8n_backup.sh >> /var/log/coinpilot/n8n-backup.log 2>&1
```

### 7.4 수동 백업 테스트
```bash
sudo /opt/coin-pilot/scripts/backup/postgres_backup.sh
sudo /opt/coin-pilot/scripts/backup/redis_backup.sh
sudo /opt/coin-pilot/scripts/backup/n8n_backup.sh
```

### 7.5 복구 리허설
- Postgres: 임시 DB(`coinpilot_restore_check`)에 restore 테스트
- Redis/n8n: tar 파일 목록 확인 + sha256 검증

---

## 8. n8n 운영 기준 (이번 작업 핵심)

### 8.1 webhook 404 의미
`The requested webhook ... is not registered`는 보통 아래 둘 중 하나다.
1. 해당 workflow가 Active가 아님
2. 다른 n8n 인스턴스를 보고 있음(WSL/OCI 혼선)

### 8.2 운영 규칙
1. OCI n8n 접속은 반드시 `localhost:15678` (터널) 사용
2. workflow 수정 후 `Save` + `Active ON`
3. 테스트는 Production URL(`/webhook/...`) 기준으로 검증

### 8.3 webhook secret 검증
각 workflow는 `x-webhook-secret` 헤더와 `.env`의 `N8N_WEBHOOK_SECRET`를 비교한다.
- 헤더가 맞아야 Discord 노드로 진행됨
- 틀리면 조용히 drop되어 외부 오남용을 줄임

### 8.4 n8n 데이터가 사라진 것처럼 보일 때
실제 삭제보다 "다른 볼륨"을 보고 있을 가능성이 높다.

확인:
```bash
docker volume ls | grep n8n
docker inspect coinpilot-n8n --format '{{ range .Mounts }}{{ if eq .Destination "/home/node/.n8n" }}{{ .Name }}{{ end }}{{ end }}'
```

---

## 9. 모니터링/알람 기준

### 9.1 Grafana 핵심 룰
1. `BotDown`
- 쿼리: `up{job="coinpilot-core"}`
- 조건: `Is below 1`
- for: `2m`

2. `ApiLatencyP95High`
- 쿼리: `histogram_quantile(0.95, sum(rate(coinpilot_api_latency_seconds_bucket[5m])) by (le))`
- 조건: `Is above 2`
- for: `10m`

3. `VolatilityMetricMissing`
- 쿼리: `count(coinpilot_volatility_index)`
- 조건: `Is below 1`
- for: `15m`

### 9.2 NoData 정책
`DatasourceNoData` 영어 알림이 오면 룰의 `No data` 처리값을 `Normal(OK)`로 조정한다.

---

## 10. 자주 헷갈린 질문 정리 (FAQ)

1. "IDE/PC 끄면 서비스도 꺼지나요?"
- 아니오. OCI VM에서 systemd로 계속 동작한다.

2. "WSL에서 `systemctl ... coinpilot-compose`가 not found인데요?"
- 정상. 해당 서비스는 OCI VM에만 존재한다.

3. "Grafana 기본 ID/PW는?"
- 기본값 대신 `.env`의 `GRAFANA_ADMIN_USER/PASSWORD`를 사용한다.

4. "Compose가 뭐예요?"
- 여러 컨테이너를 한 파일로 묶어 함께 기동/중지하는 방식이다.

5. "왜 webhook 테스트가 404인가요?"
- workflow inactive 또는 잘못된 n8n 인스턴스 접속 가능성이 가장 높다.

---

## 11. 점검 체크리스트

### 11.1 매일 시작
1. systemd 상태 확인
2. compose `ps` 확인
3. bot 오류 로그 확인
4. Grafana alert 상태 확인
5. 필요 시 n8n webhook 스모크 1회

### 11.2 매주
1. Postgres/Redis/n8n 백업 파일 생성 추세 확인
2. 복구 리허설 1회
3. OCI 보안규칙/예산/쿼터 변경 여부 점검

### 11.3 24시간 집중 모니터링 점검표 (설정 변경/재배포 직후)
아래는 "설정 변경 직후" 또는 "재배포 직후"에 한 번 수행하는 집중 점검표다.

자동 실행(권장):
```bash
cd /opt/coin-pilot
scripts/ops/check_24h_monitoring.sh all
```

| 체크포인트 | 점검 항목 | 명령/위치 | 성공 기준 | 이상 시 조치 |
|---|---|---|---|---|
| T+0m | 서비스 기동 상태 | `docker compose ... ps` | 핵심 8개 서비스 `Up` | `logs`로 실패 서비스 우선 확인 후 재기동 |
| T+0m | bot 초기화 오류 | `logs --since=10m bot` | `critical/traceback/undefined` 없음 | 스키마/환경변수/Redis 연결 재검증 |
| T+1h | 메트릭 수집 연속성 | Prometheus Targets, bot `/metrics` | `coinpilot-core` `UP` 유지 | scrape 설정/네트워크 확인 |
| T+1h | 알림 라우팅 정상 | Grafana Alert Rules + Discord | 테스트/실제 알림 수신 확인 | Notification policy/contact point 재확인 |
| T+6h | 거래/의사결정 흐름 | bot 로그(Entry/AI/Risk) | 로그 공백 없이 주기 동작 | 스케줄러 중단/에러 여부 확인 |
| T+12h | 배치 작업 정상 | `RSS ingest`, `daily report` 로그 | 실패(`failed`) 누적 없음 | n8n workflow active 및 webhook 점검 |
| T+24h | 백업/복구 준비 | `/var/backups/coinpilot` | 3종 백업 파일 생성 확인 | cron 상태/스크립트 권한 점검 |

실행 명령(OCI):
```bash
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml ps
docker compose --env-file .env -f docker-compose.prod.yml logs --since=30m bot | grep -Ei "critical|traceback|undefined|failed"
docker compose --env-file .env -f docker-compose.prod.yml logs --since=30m n8n | grep -Ei "error|failed|webhook"
sudo find /var/backups/coinpilot -type f | tail -n 20
```

---

## 12. 다음 단계 (실거래 전환 전)

1. 24~48시간 burn-in 운영 관찰
2. Plan 21 기준(100만 KRW) 리스크 파라미터 최종 확정
3. 알림 오탐/누락 없는지 마지막 검증

---

## 13. 빠른 명령 모음

### 13.1 OCI 서비스 상태
```bash
systemctl status coinpilot-compose.service --no-pager
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml ps
```

### 13.2 백업 수동 실행
```bash
sudo /opt/coin-pilot/scripts/backup/postgres_backup.sh
sudo /opt/coin-pilot/scripts/backup/redis_backup.sh
sudo /opt/coin-pilot/scripts/backup/n8n_backup.sh
```

### 13.3 n8n 웹훅 quick probe
```bash
SECRET=$(grep '^N8N_WEBHOOK_SECRET=' /opt/coin-pilot/deploy/cloud/oci/.env | cut -d= -f2-)
curl -sS -X POST "http://localhost:5678/webhook/trade" \
  -H "Content-Type: application/json" \
  -H "x-webhook-secret: $SECRET" \
  -d '{"side":"BUY","symbol":"KRW-BTC","price":100,"quantity":0.001}'
```

### 13.4 24시간 점검 자동화 스크립트
```bash
cd /opt/coin-pilot
scripts/ops/check_24h_monitoring.sh all
scripts/ops/check_24h_monitoring.sh t0
scripts/ops/check_24h_monitoring.sh t24h
scripts/ops/check_24h_monitoring.sh all --output /var/log/coinpilot/monitoring-24h.log
```

---

## 14. 변경 이력
- 2026-02-25: 최초 작성 (WSL/OCI 혼선 복구 경험 및 운영 표준 통합 반영)
- 2026-02-26: 18-13 반영, 재배포/설정 변경 직후 적용 가능한 24시간 집중 모니터링 점검표(T+0m/1h/6h/12h/24h) 추가
- 2026-02-26: 18-14 반영, 24시간 점검 자동화 스크립트(`scripts/ops/check_24h_monitoring.sh`) 사용법 추가
