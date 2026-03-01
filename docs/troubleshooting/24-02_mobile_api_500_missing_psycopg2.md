# 24-02 트러블슈팅: Discord `/positions` 호출 시 `/api/mobile/positions` 500 (psycopg2 누락)

**작성일**: 2026-03-02  
**작성자**: Codex  
**관련 계획**: `docs/work-plans/24_discord_mobile_chatbot_query_plan.md`  
**관련 결과**: `docs/work-result/24_discord_mobile_chatbot_query_result.md`

---

## 1) 증상
- Discord Slash Command 응답:
  - `조회 실패: Server error '500 Internal Server Error' for url 'http://bot:8000/api/mobile/positions'`

## 2) 원인
- `src/mobile/query_api.py`의 `/positions`는 `run_portfolio_tool()`을 호출
- 해당 tool은 `get_sync_db_url()`로 `postgresql+psycopg2` 동기 엔진을 사용
- bot 이미지 의존성(`requirements-bot.txt`)에 `psycopg2-binary`가 없어 런타임에서 DB 드라이버 로딩 실패

## 3) 조치
- `requirements-bot.txt`에 `psycopg2-binary==2.9.9` 추가

## 4) 재검증
```bash
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --env-file .env -f docker-compose.prod.yml up -d --build --no-deps bot
docker compose --env-file .env -f docker-compose.prod.yml logs --since=10m bot | tail -n 120
```

Discord에서 `/positions`, `/pnl`, `/ask` 재검증:
- 500 에러 미발생
- 정상 응답 확인

