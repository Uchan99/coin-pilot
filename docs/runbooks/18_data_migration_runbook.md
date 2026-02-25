# 18. Minikube -> OCI 데이터 마이그레이션 Runbook

작성일: 2026-02-21
상태: Ready
관련 계획서: docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md

---

## 1. 목적
- Minikube에서 운영 중인 PostgreSQL/Redis 데이터를 OCI VM 환경으로 안전하게 이관한다.
- 목표는 데이터 정합성(row count + 샘플 레코드) 검증까지 완료하는 것이다.

## 2. 사전 조건
1. 원본(minikube)과 대상(OCI VM)에 모두 SSH 가능
2. 대상 서버에 `deploy/cloud/oci/docker-compose.prod.yml` 배치 완료
3. 대상 서버 `.env` 설정 완료
4. 대상 서비스는 최초 이관 시 `collector/bot` 중지 상태 권장(중복 write 방지)

## 3. PostgreSQL 이관

### 3.1 원본에서 덤프 생성
```bash
kubectl -n coin-pilot-ns exec -it statefulset/db -- \
  sh -c 'PGPASSWORD="$DB_PASSWORD" pg_dump -U postgres -d coinpilot -Fc -f /tmp/coinpilot.dump'
kubectl -n coin-pilot-ns cp coin-pilot-ns/db-0:/tmp/coinpilot.dump ./coinpilot.dump
```

### 3.2 대상 서버로 전송
```bash
scp ./coinpilot.dump <oci-user>@<oci-host>:/tmp/coinpilot.dump
```

### 3.3 대상 DB 복원
```bash
ssh <oci-user>@<oci-host>
cd /opt/coin-pilot/deploy/cloud/oci

docker compose -f docker-compose.prod.yml up -d db
sleep 10

docker cp /tmp/coinpilot.dump coinpilot-db:/tmp/coinpilot.dump
docker exec -it coinpilot-db sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_restore -U postgres -d coinpilot --clean --if-exists /tmp/coinpilot.dump'
```

### 3.4 Timescale 충돌 시 우회 경로(권장)
`pg_restore` 중 아래와 같은 오류가 발생하면 전체 dump 복원을 중단하고, data-only 경로로 전환한다.
- `extension "timescaledb" has already been loaded with another version`
- `_timescaledb_internal` 스키마 관련 오류

우회 절차:
1. 대상 DB 재생성
```bash
docker exec -u postgres coinpilot-db psql -d postgres -v ON_ERROR_STOP=1 \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='coinpilot';" \
  -c "DROP DATABASE IF EXISTS coinpilot;" \
  -c "CREATE DATABASE coinpilot;"
```

2. 대상 baseline 스키마 생성
```bash
docker exec -i -u postgres coinpilot-db psql -d coinpilot -v ON_ERROR_STOP=1 < /opt/coin-pilot/deploy/db/init.sql
for f in /opt/coin-pilot/migrations/004_add_pgvector.sql \
         /opt/coin-pilot/migrations/v3_0_regime_trading.sql \
         /opt/coin-pilot/migrations/v3_1_reject_tracking.sql \
         /opt/coin-pilot/migrations/v3_2_1_trade_count_split.sql \
         /opt/coin-pilot/migrations/v3_2_2_post_exit_tracking.sql \
         /opt/coin-pilot/migrations/v3_3_0_news_rss_only.sql \
         /opt/coin-pilot/migrations/v3_3_1_agent_decisions_baseline.sql; do
  docker exec -i -u postgres coinpilot-db psql -d coinpilot -v ON_ERROR_STOP=1 < "$f"
done
```

3. 원본에서 public 데이터만 export/import
```bash
kubectl -n coin-pilot-ns exec db-0 -- pg_dump -U postgres -d coinpilot --data-only \
  --table=public.account_state \
  --table=public.daily_risk_state \
  --table=public.trading_history \
  --table=public.positions \
  --table=public.risk_audit \
  --table=public.agent_decisions \
  --table=public.regime_history \
  --table=public.news_articles \
  --table=public.news_summaries \
  --table=public.news_risk_scores \
  --table=public.market_data > /tmp/k8s_public_data.sql

docker exec -u postgres coinpilot-db psql -d coinpilot -v ON_ERROR_STOP=1 -c \
  "TRUNCATE TABLE account_state, daily_risk_state, trading_history, positions, risk_audit, agent_decisions, regime_history, news_articles, news_summaries, news_risk_scores, market_data RESTART IDENTITY CASCADE;"

docker exec -i -u postgres coinpilot-db psql -d coinpilot -v ON_ERROR_STOP=1 < /tmp/k8s_public_data.sql
```

4. `market_data`가 0건이면 CSV `\copy`로 별도 이관
```bash
kubectl -n coin-pilot-ns exec db-0 -- psql -U postgres -d coinpilot -c \
  "\\copy (SELECT id, symbol, interval, open_price, high_price, low_price, close_price, volume, timestamp FROM market_data ORDER BY timestamp, id) TO STDOUT WITH CSV" \
  > /tmp/k8s_market_data.csv

docker exec -u postgres coinpilot-db psql -d coinpilot -v ON_ERROR_STOP=1 -c "TRUNCATE TABLE market_data;"
docker exec -i -u postgres coinpilot-db psql -d coinpilot -v ON_ERROR_STOP=1 -c \
  "\\copy market_data(id, symbol, interval, open_price, high_price, low_price, close_price, volume, timestamp) FROM STDIN WITH CSV" \
  < /tmp/k8s_market_data.csv
```

## 4. Redis 이관

### 4.1 원본에서 데이터 추출
- 정책 A(권장): cold start 허용 시 Redis는 신규 시작
- 정책 B(보존): RDB/AOF 파일을 이관

정책 B 예시:
```bash
kubectl -n coin-pilot-ns exec -it statefulset/redis -- sh -c 'redis-cli BGSAVE'
kubectl -n coin-pilot-ns cp coin-pilot-ns/redis-0:/data ./redis-data
```

### 4.2 대상 복원
```bash
scp -r ./redis-data <oci-user>@<oci-host>:/tmp/redis-data
ssh <oci-user>@<oci-host>

docker compose -f /opt/coin-pilot/deploy/cloud/oci/docker-compose.prod.yml stop redis
# 주의: 기존 /data를 덮어쓰기 전에 백업을 반드시 남길 것
# docker cp /tmp/redis-data/. coinpilot-redis:/data/
docker compose -f /opt/coin-pilot/deploy/cloud/oci/docker-compose.prod.yml start redis
```

## 5. 정합성 검증

### 5.1 핵심 테이블 row count 비교
```bash
# source(minikube)
kubectl -n coin-pilot-ns exec -it statefulset/db -- psql -U postgres -d coinpilot -c "select count(*) from market_data;"
kubectl -n coin-pilot-ns exec -it statefulset/db -- psql -U postgres -d coinpilot -c "select count(*) from trading_history;"
kubectl -n coin-pilot-ns exec -it statefulset/db -- psql -U postgres -d coinpilot -c "select count(*) from daily_risk_state;"

# target(OCI)
docker exec -it coinpilot-db psql -U postgres -d coinpilot -c "select count(*) from market_data;"
docker exec -it coinpilot-db psql -U postgres -d coinpilot -c "select count(*) from trading_history;"
docker exec -it coinpilot-db psql -U postgres -d coinpilot -c "select count(*) from daily_risk_state;"
```

### 5.2 샘플 레코드 확인
```bash
docker exec -it coinpilot-db psql -U postgres -d coinpilot -c "select * from trading_history order by created_at desc limit 5;"
```

## 6. Cutover 체크리스트
1. 대상 환경에서 `dashboard` 접속 정상 확인
2. `bot` health + `/metrics` 노출 확인
3. Prometheus Targets에서 `coinpilot-core`가 `UP` 확인
4. 병행 운영 시 한쪽 `bot`은 read-only 또는 중지 상태 유지
5. 외부 공개 포트 정책 확인 (`22`, `80`, `443`만 허용)

## 6.1 보안 사전 점검(권장)
배포 직전에 아래 스크립트로 시크릿/포트/워크플로우 가드를 한 번에 확인한다.

```bash
cd /opt/coin-pilot
./scripts/security/preflight_security_check.sh /opt/coin-pilot/deploy/cloud/oci/.env
```

성공 기준:
- `[RESULT] PASSED` 출력
- 실패 항목이 있으면 cutover 전에 반드시 수정

## 7. 운영 등록 (systemd / cron)

### 7.1 systemd 등록 (재부팅 자동복구)
```bash
sudo cp /opt/coin-pilot/deploy/cloud/oci/systemd/coinpilot-compose.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now coinpilot-compose.service
sudo systemctl status coinpilot-compose.service
```

참고:
- `bot:latest`, `collector:latest`, `dashboard:latest`는 로컬 빌드 이미지이므로
  service 파일의 `ExecStartPre`는 `pull --ignore-buildable` 정책을 사용해야 한다.
- 해당 옵션이 없으면 `pull access denied`로 systemd 기동이 실패할 수 있다.

### 7.2 cron 등록 (일간 백업 자동화)
```bash
sudo crontab -e
```

아래 항목 추가:
```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
5 3 * * * /opt/coin-pilot/scripts/backup/postgres_backup.sh >> /var/log/coinpilot/postgres-backup.log 2>&1
15 3 * * * /opt/coin-pilot/scripts/backup/redis_backup.sh >> /var/log/coinpilot/redis-backup.log 2>&1
25 3 * * * /opt/coin-pilot/scripts/backup/n8n_backup.sh >> /var/log/coinpilot/n8n-backup.log 2>&1
```

등록 확인:
```bash
sudo systemctl list-unit-files | grep coinpilot-compose
sudo crontab -l | grep coinpilot
```

## 8. 롤백
1. 대상 OCI의 `bot/collector` 중지
2. 기존 Minikube `bot/collector` 재활성화
3. 원인 분석 후 재이관

## 9. 참고
- Plan: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`
- Compose: `deploy/cloud/oci/docker-compose.prod.yml`
- Backup scripts: `scripts/backup/postgres_backup.sh`, `scripts/backup/redis_backup.sh`, `scripts/backup/n8n_backup.sh`
- A1 capacity retry: `docs/runbooks/18_oci_a1_flex_auto_retry_runbook.md`, `scripts/cloud/oci_retry_launch_a1_flex.sh`
