# 18 트러블슈팅: Compose 전환 후 Bot Brain 상태 미표시

작성일: 2026-02-23  
관련 계획: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`  
관련 결과: `docs/work-result/18_cloud_migration_cost_optimized_result.md`

---

## 1. 증상
- 대시보드 `Bot Brain: KRW-BTC (Live Status)`에서 아래 경고가 표시됨.
  - `Bot Status not found for KRW-BTC`
- Redis 상태 키 확인 시 `bot:status:*` 키가 비어 있음.

## 2. 원인(복합)
1. DB 스키마 불일치
- `daily_risk_state.buy_count`, `daily_risk_state.sell_count` 누락으로 bot 루프가 예외 종료됨.

2. 누락 마이그레이션
- `news_articles` 테이블 미생성으로 RSS ingest 경로에서 예외가 발생함.

3. Compose 환경변수 불일치
- bot/collector 일부 코드 경로가 `REDIS_HOST/REDIS_PORT`를 사용하지만 compose에는 `REDIS_URL`만 설정되어 `localhost:6379`로 잘못 접속함.

## 3. 조치 내용
1. DB 마이그레이션 적용
- `v3_2_1_trade_count_split.sql`로 `buy_count/sell_count` 보강
- `v3_3_0_news_rss_only.sql` 포함 v3 마이그레이션 적용

2. Compose 설정 보정
- `deploy/cloud/oci/docker-compose.prod.yml`에서 `bot`, `collector`에 아래 추가:
  - `REDIS_HOST=redis`
  - `REDIS_PORT=6379`

3. 대시보드 안내 문구 보정
- `src/dashboard/pages/2_market.py`의 K8s 전용 안내(`kubectl`)를 Compose 운영 기준 경고로 변경

## 4. 검증
1. 서비스 상태
```bash
docker compose -f deploy/cloud/oci/docker-compose.prod.yml ps
```

2. Bot 로그
```bash
docker logs --tail 120 coinpilot-bot
```

3. Redis 상태 키
```bash
docker exec coinpilot-redis redis-cli --scan --pattern 'bot:status:*'
```

검증 결과:
- bot 프로세스 정상 기동 확인
- `bot:status:KRW-BTC` 포함 심볼별 키 생성 확인

## 5. 재발 방지
1. 신규 환경 배포 직후 v3 마이그레이션 적용 여부를 체크리스트에 포함
2. Compose 설정 변경 시 `docker compose config` + `bot 로그`를 동시 확인
3. 대시보드 운영 문구를 현재 배포 방식(Compose/K8s)과 일치하게 유지
