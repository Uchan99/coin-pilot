# 24. 디스코드 모바일 조회/대화형 챗봇 구축 결과

**작성일**: 2026-03-01  
**작성자**: Codex  
**관련 계획**: `docs/work-plans/24_discord_mobile_chatbot_query_plan.md`
**관련 트러블슈팅**: `docs/troubleshooting/24_mobile_visibility_gap_discord_query_need.md`

---

## 1) 구현 요약
이번 작업에서 Discord 모바일 조회용 읽기 전용 어댑터를 구현했다.

1. `bot` 서비스에 내부 조회 API 추가
1. 신규 `discord-bot` 서비스 추가(슬래시 커맨드 `/positions`, `/pnl`, `/status`, `/risk`, `/ask`)
1. API 공유 시크릿 기반 인증(`X-Api-Secret`) 및 채널/역할 allowlist, 사용자 단위 rate limit 적용
1. OCI Compose/.env.example 반영 및 단위 테스트 추가

---

## 2) 변경 파일

### 코드
1. `src/mobile/query_api.py`
1. `src/mobile/__init__.py`
1. `src/bot/main.py`
1. `src/discord_bot/main.py`
1. `src/discord_bot/__init__.py`
1. `tests/mobile/test_query_api.py`

### 배포/의존성
1. `deploy/docker/discord-bot.Dockerfile`
1. `requirements-discord-bot.txt`
1. `deploy/cloud/oci/docker-compose.prod.yml`
1. `deploy/cloud/oci/.env.example`

### 문서
1. `docs/work-plans/24_discord_mobile_chatbot_query_plan.md` (승인 상태 반영)
1. `docs/checklists/remaining_work_master_checklist.md` (24 상태 in_progress 전환)
1. `docs/PROJECT_CHARTER.md` (참고 문서/변경 이력 반영)

---

## 3) 아키텍처 결정

### 선택
- **Discord Bot -> CoinPilot Mobile API 어댑터 구조**를 채택했다.

### 이유
1. 기존 DB/리스크/챗봇 로직 재사용이 가능해 중복 구현을 피할 수 있다.
1. Discord 쪽에는 조회/표시 로직만 두고, 도메인 로직은 `bot`에 유지해 변경 비용을 줄인다.
1. 보안 경계를 `X-Api-Secret`으로 단순화할 수 있다.

### 고려한 대안
1. Discord Bot이 DB 직접 조회
1. n8n 워크플로로 양방향 챗봇 구현
1. MCP 서버 먼저 도입 후 Discord를 MCP 클라이언트로 연결

### 트레이드오프
1. API 어댑터는 DB 직접 조회보다 네트워크 홉이 1단계 늘어난다.
1. 대신 권한/스키마 결합이 낮아지고, 향후 API 스펙 기준으로 UI/채널 확장이 쉬워진다.
1. MCP 선도입보다 구현 복잡도는 낮지만, 다중 툴 오케스트레이션 고도화는 후속 과제로 남는다.

---

## 4) 검증 결과

### 로컬 단위 검증
```bash
.venv/bin/python -m py_compile src/mobile/query_api.py src/discord_bot/main.py
.venv/bin/pytest -q tests/mobile/test_query_api.py
```

실행 결과:
- `tests/mobile/test_query_api.py` 3건 통과

### 운영 반영 검증(수동)
```bash
cd /opt/coin-pilot/deploy/cloud/oci
docker compose --profile discord-bot --env-file .env -f docker-compose.prod.yml up -d --build bot discord-bot
docker compose --env-file .env -f docker-compose.prod.yml ps
docker compose --env-file .env -f docker-compose.prod.yml logs --since=10m discord-bot | tail -n 80
```

Discord에서 확인할 항목:
1. `/positions`, `/pnl`, `/status`, `/risk` 응답 여부
1. `/ask` 응답 여부 및 2000자 초과 시 메시지 절단 처리
1. 허용 채널/역할 외 접근 차단 여부

---

## 5) 운영 변수

신규/필수 환경 변수:
1. `COINPILOT_API_SHARED_SECRET` (bot + discord-bot 공통)
1. `DISCORD_BOT_TOKEN`

신규/선택 환경 변수:
1. `DISCORD_GUILD_ID`
1. `DISCORD_ALLOWED_CHANNEL_IDS`
1. `DISCORD_ALLOWED_ROLE_IDS`
1. `DISCORD_QUERY_RATE_LIMIT_PER_MIN`
1. `DISCORD_BOT_EPHEMERAL_DEFAULT`
1. `DISCORD_API_TIMEOUT_SEC`
1. `COINPILOT_API_BASE_URL`

---

## 6) 남은 작업
1. OCI 실환경에서 슬래시 명령 동기화/권한 정책 최종 점검
1. `/수익률` 한국어 명령 UX는 Discord 명령 네이밍 제약을 고려해 alias 안내/설명문으로 보완
1. 장기적으로 24 작업 완료 후 `21-03` 카나리 실험으로 우선순위 이동

---

## Phase 2) 운영 핫픽스 (2026-03-02)

### 이슈
- Discord Slash Command 실행 시 `NoneType role.id` 예외로 무응답 발생

### 조치
1. `src/discord_bot/main.py` 권한 검사 로직 보강
   - `roles` 순회 시 `None` 방어
   - `interaction.data.member.roles` fallback 병합
1. `discord.Intents(guilds=True)` 적용
1. app command 전역 에러 핸들러 추가(예외 발생 시 사용자에게 오류 메시지 반환)

### 관련 트러블슈팅
- `docs/troubleshooting/24-01_discord_role_nonetype_guard_fix.md`

## Phase 3) 운영 핫픽스 (2026-03-02)

### 이슈
- Discord `/positions` 호출 시 bot `/api/mobile/positions`가 500 반환

### 조치
1. `requirements-bot.txt`에 `psycopg2-binary==2.9.9` 추가
1. bot 이미지 재빌드 후 Mobile API 재검증

### 관련 트러블슈팅
- `docs/troubleshooting/24-02_mobile_api_500_missing_psycopg2.md`
