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

## 7. 운영 등록 (systemd / cron)

### 7.1 systemd 등록 (재부팅 자동복구)
```bash
sudo cp /opt/coin-pilot/deploy/cloud/oci/systemd/coinpilot-compose.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now coinpilot-compose.service
sudo systemctl status coinpilot-compose.service
```

### 7.2 cron 등록 (일간 백업 자동화)
```bash
sudo crontab -e
```

아래 항목 추가:
```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
5 3 * * * /opt/coin-pilot/scripts/backup/postgres_backup.sh >> /var/log/coinpilot-postgres-backup.log 2>&1
15 3 * * * /opt/coin-pilot/scripts/backup/redis_backup.sh >> /var/log/coinpilot-redis-backup.log 2>&1
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
- Backup scripts: `scripts/backup/postgres_backup.sh`, `scripts/backup/redis_backup.sh`
