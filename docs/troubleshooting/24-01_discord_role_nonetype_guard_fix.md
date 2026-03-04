# 24-01 트러블슈팅: Discord Slash Command `NoneType role.id` 예외로 인한 "애플리케이션이 응답하지 않았어요"

**작성일**: 2026-03-02  
**작성자**: Codex  
**관련 계획**: `docs/work-plans/24_discord_mobile_chatbot_query_plan.md`  
**관련 결과**: `docs/work-result/24_discord_mobile_chatbot_query_result.md`

---

## 1) 증상
Discord Slash Command(`/positions`, `/status`, `/ask`) 실행 시 사용자 화면에서 다음 메시지가 표시됨.

- `애플리케이션이 응답하지 않았어요`

컨테이너 로그:
- `AttributeError: 'NoneType' object has no attribute 'id'`
- 발생 위치: `src/discord_bot/main.py` `_check_access()` 내 role 추출 구간

### 해결한 문제(요약)
- 해결 전: 권한 검사 예외로 Slash Command가 무응답 처리됨.
- 해결 후: `None` role/raw payload fallback을 처리해 명령이 정상 응답 또는 명시적 오류 응답을 반환.

---

## 2) 원인
권한 검사에서 `interaction.user.roles`를 순회할 때 `None` 요소가 포함될 수 있는 케이스를 가정하지 않아 예외가 발생했다.

추가로, guild 관련 캐시/intent 상황에 따라 역할 정보가 `interaction.user` 대신 raw payload(`interaction.data.member.roles`)에만 존재할 수 있는데 이에 대한 fallback이 없었다.

---

## 3) 조치
1. `intents = discord.Intents(guilds=True)`로 보강
2. 역할 ID 추출 로직을 안전화:
   - `None` role 방어
   - raw payload 역할 ID fallback 병합
3. `app_commands` 전역 에러 핸들러 추가:
   - 예외 발생 시에도 사용자에게 에러 응답을 반환하여 무응답 상태를 방지

수정 파일:
- `src/discord_bot/main.py`

---

## 4) 재검증 방법
```bash
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --profile discord-bot --env-file .env -f docker-compose.prod.yml up -d --build --no-deps discord-bot
docker compose --env-file .env -f docker-compose.prod.yml logs --since=10m -f discord-bot
```

Discord에서 `/positions`, `/status`, `/ask`를 실행해 다음 확인:
1. 더 이상 `NoneType role.id` 예외가 발생하지 않는지
2. 실패 시에도 "무응답" 대신 에러 텍스트 응답이 반환되는지

---

## 5) 정량 근거(결과/운영 로그 대조)
출처: `docs/work-result/24_discord_mobile_chatbot_query_result.md` (Phase 2), 운영 로그 샘플

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 예외가 관측된 명령 종류 수 | 3 | 0 | -3 | -100.0 |
| 사용자 체감 무응답 상태(발생=1, 미발생=0) | 1 | 0 | -1 | -100.0 |

정량 기록이 없는 항목:
- 명령당 실패율(%)은 당시 전체 호출 건수 로그를 보관하지 않아 계산하지 않음.
