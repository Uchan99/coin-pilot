# 24-02 트러블슈팅: Discord `/positions` 호출 시 `/api/mobile/positions` 500 (psycopg2 누락)

**작성일**: 2026-03-02  
**작성자**: Codex  
**관련 계획**: `docs/work-plans/24_discord_mobile_chatbot_query_plan.md`  
**관련 결과**: `docs/work-result/24_discord_mobile_chatbot_query_result.md`

---

## 1) 증상
- Discord Slash Command 응답:
  - `조회 실패: Server error '500 Internal Server Error' for url 'http://bot:8000/api/mobile/positions'`

### 해결한 문제(요약)
- 해결 전: `/positions` 호출 시 Mobile API가 500 반환.
- 해결 후: bot 이미지에 `psycopg2-binary`를 포함해 동기 DB 경로가 정상 동작하고 500이 제거됨.

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

---

## 5) 정량 근거(결과/운영 검증 대조)
출처: `docs/work-result/24_discord_mobile_chatbot_query_result.md` (Phase 3), 운영 수동 검증 로그

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| `/positions` 500 오류 관측 건수 | 1 | 0 | -1 | -100.0 |
| 모바일 명령 재검증 성공 건수(3개 명령 기준) | 0 | 3 | +3 | N/A |

정량 기록이 없는 항목:
- 평균 응답시간(ms)은 해당 시점에 별도 수집하지 않아 기록하지 않음.
