# 24. 디스코드 모바일 조회/대화형 챗봇(포지션·수익률 질의) 구축 계획

**작성일**: 2026-02-27  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/21_live_trading_transition_1m_krw_plan.md`, `docs/work-plans/23_nextjs_dashboard_gradual_migration_plan.md`  
**승인 정보**: 승인자 / 승인 시각 / 승인 코멘트

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 현재 알림은 Discord로 수신 가능하나, 모바일에서 “현재 보유 종목/수익률/리스크 상태”를 즉시 질의할 채널이 없음.
  - 웹 대시보드는 모바일 운영 시 접근성/즉시성이 떨어짐.
- 왜 즉시 대응이 필요했는지:
  - 실거래 전환 전 운영자가 모바일에서 상태를 빠르게 확인할 수 있어야 대응 속도와 안전성이 올라감.

## 1. 문제 요약
- 증상:
  - 모바일 사용 중 상태 조회가 불편하고, 질의형 운영(“지금 수익률?”, “보유 포지션?”)이 불가능.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: Discord 알림은 단방향, 조회형 상호작용 부재
  - 리스크: 상태 확인 지연으로 운영 판단 지연
  - 데이터: 현재 챗봇/DB 조회 기능이 Discord와 직접 연결되지 않음
  - 비용: 운영 시간/의사결정 지연 비용 증가
- 재현 조건:
  - 모바일에서 Discord 앱만 사용하는 운영 상황

## 2. 목표 / 비목표
### 2.1 목표
1. Discord Slash Command로 핵심 조회 제공:
   - `/positions`, `/pnl`, `/status`, `/risk`, `/ask`
2. 기존 CoinPilot 챗봇/조회 로직 재사용(API 어댑터 방식)
3. 읽기 전용 운영(주문 실행 명령 금지)으로 보안 리스크 최소화
4. 모바일 환경에서 3초 내 기본 조회 응답 목표

### 2.2 비목표
1. 본 단계에서 Discord를 통한 실주문(BUY/SELL) 기능은 구현하지 않음
2. MCP 기반 툴 서버 전환은 범위 밖(향후 확장 옵션으로만 기록)
3. 대시보드 UI 개편은 본 계획 범위 밖(22/23 스트림에서 처리)

## 3. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **Discord Bot(신규) → CoinPilot API(기존) 호출** 어댑터 구조

- 고려 대안:
  1) Discord Bot이 DB/Redis에 직접 연결
  2) Discord Bot이 CoinPilot API만 호출 (채택)
  3) MCP 서버 구성 후 Discord 에이전트가 MCP 툴 호출

- 대안 비교:
  1) DB 직접 연결:
    - 장점: API 우회로 단순 조회 가능
    - 단점: 권한/보안/스키마 의존 증가, 중복 로직 발생
  2) API 어댑터(채택):
    - 장점: 기존 비즈니스 로직 재사용, 보안 경계 단순, 유지보수 유리
    - 단점: API 응답 지연에 의존
  3) MCP:
    - 장점: 장기적으로 다중 툴 통합에 유리
    - 단점: 현재 요구 대비 복잡도 과다, 도입 비용 큼

## 4. 기능 범위(Phase별)
### Phase 1: 읽기 전용 Slash Command MVP
1. `/positions`: 보유 종목/평가손익/비중
2. `/pnl`: 일간/누적 손익 요약
3. `/status`: bot/collector/db/n8n 상태 요약
4. `/risk`: 금일 리스크 상태(연속 손실, 일일 거래 수, 제한 여부)

### Phase 2: 대화형 질의(`/ask`)
1. Discord 명령 텍스트를 기존 챗봇 API로 전달
2. 응답 길이/민감정보 마스킹/타임아웃 처리
3. 실패 시 fallback 템플릿 응답

### Phase 3: 운영 고도화
1. role/channel allowlist
2. rate limit + abuse guard
3. 감사 로그(누가/언제/무엇을 질의했는지)

## 5. 구현/수정 내용 (예정)
- 신규(예상):
  1) `src/discord_bot/` (봇 서비스 코드)
  2) `deploy/docker/discord-bot.Dockerfile`
  3) `config/discord/commands.yaml` 또는 코드 내 명령 정의
  4) `docs/work-result/24_discord_mobile_chatbot_query_result.md`

- 수정(예상):
  1) `deploy/cloud/oci/docker-compose.prod.yml` (discord-bot 서비스 추가)
  2) `deploy/cloud/oci/.env.example` (DISCORD_BOT_TOKEN 등)
  3) 기존 FastAPI 라우터(필요 시 조회 전용 엔드포인트 확장)

- 환경변수(초안):
  - `DISCORD_BOT_TOKEN`
  - `DISCORD_GUILD_ID`
  - `DISCORD_ALLOWED_CHANNEL_IDS`
  - `DISCORD_ALLOWED_ROLE_IDS`
  - `DISCORD_QUERY_RATE_LIMIT_PER_MIN`
  - `COINPILOT_API_BASE_URL`
  - `COINPILOT_API_SHARED_SECRET` (내부 인증용)

## 6. 보안/운영 가드레일
1. 읽기 전용 정책(주문/실행 엔드포인트 호출 금지)
2. 허용된 서버/채널/역할만 명령 실행
3. 민감정보 마스킹(키/정확 잔고 세부치 노출 제한 정책)
4. API 호출 timeout/retry/backoff
5. 질의 실패율/지연시간 모니터링

## 7. 검증 기준
- 재현 케이스에서 해결 확인:
  1) 모바일 Discord에서 `/positions`, `/pnl`, `/status`, `/risk` 정상 응답
  2) 권한 없는 사용자/채널에서 차단 동작
- 회귀 테스트:
  - 기존 n8n 알림 및 bot 매매 루프 영향 없음
- 운영 체크:
  - 24h 관측에서 에러율/타임아웃률 임계치 이하
  - 응답 지연 p95 목표(예: 3초) 준수 여부 확인

## 8. 롤백
- 코드 롤백:
  - discord-bot 서비스 관련 커밋 revert
- 운영 롤백:
  - compose에서 discord-bot 서비스 비활성화
  - 기존 알림 단방향 운영으로 즉시 복귀
- 데이터/스키마 롤백:
  - 원칙적으로 없음(조회형 중심)

## 9. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 작성
  - 구현 후 `docs/work-result/24_discord_mobile_chatbot_query_result.md` 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 채널 정책/조회 권한 정책을 공식 규칙으로 확정 시 Charter changelog 반영

## 10. 후속 조치
1. MCP 확장 검토 문서(장기 옵션) 별도 작성  
2. Discord 명령 사용 통계 기반 UX 개선  
3. 실거래 전환 후 운영 runbook에 모바일 대응 절차 추가
