# 17-08. 챗봇 Phase 5 (비용/안전 가드레일) 구현 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17-08_phase5_chat_guardrails_and_model_tiering_plan.md`

---

## 1. 구현 요약

17번 계획의 Phase 5 항목을 구현했다.

1. 모델 계층화
- 기본 경로는 기존 모델 정책(Haiku/LLM_MODE)을 유지
- 고난도 전략 리뷰 질의에 한해 `premium_review` 모델(Sonnet 기본) 조건부 승격

2. 호출 통제(백엔드 공통)
- 세션 쿨다운
- 동일 질의 캐시(TTL/LRU)
- 입력 길이 제한
- 출력 길이 예산
- 타임아웃/에러 시 보수적 fallback

3. 안전장치 강화
- 공통 후처리에서 안전 고지문 누락 방지
- 시장/전략/행동 계열 응답에 시나리오 해석 문구 강제

---

## 2. 아키텍처 결정 기록

### 선택안
- `router.py`의 `process_chat()` 경로에 공통 runtime guard 추가
- `strategy_review_node`에서만 조건부 premium 모델 호출

### 대안 비교
1. 프론트 전용 가드레일
- 장점: 구현 간단
- 단점: 다른 진입점(API/확장 UI)에서 우회 가능

2. Redis 기반 분산 가드레일
- 장점: 다중 파드 일관성
- 단점: 현 단계 구현 부담 큼

3. 모든 리뷰 질의 Sonnet 강제
- 장점: 품질 잠재력
- 단점: 비용 급증

### 트레이드오프
- 인메모리 상태는 멀티 파드 완전 공유가 되지 않지만,
  현재 운영(빠른 반복 배포)에서는 구현 복잡도를 낮추면서도 호출 통제 효과를 즉시 확보했다.

---

## 3. 변경 파일

1. `src/agents/factory.py`
- `model_type="premium_review"` 분기 추가
- `get_premium_review_llm()` 추가

2. `src/agents/router.py`
- 세션 쿨다운, 동일 질의 캐시, 입력/출력 길이 제한, 안전 후처리 추가
- `process_chat(message, session_id=None)` 시그니처 확장
- `process_chat_sync(message, session_id=None)` 시그니처 확장
- 전략 리뷰 노드에 고난도 질의 조건부 premium 코멘트 추가

3. `src/dashboard/components/floating_chat.py`
- 세션 고유 ID 생성 후 `process_chat_sync(..., session_id=...)`로 전달

4. `src/dashboard/pages/06_chatbot.py`
- 대화 초기화 시 세션 ID도 함께 초기화

5. `.env.example`
- Phase 5 가드레일 환경변수 추가

6. `tests/agents/test_phase5_chat_guardrails.py` (신규)
- 쿨다운/캐시/길이예산/승격판정 테스트

7. `docs/work-plans/17_chatbot_trading_assistant_upgrade_plan.md`
- Phase 5 구현 진행 로그 추가

---

## 4. 검증

실행:
```bash
python3 -m py_compile src/agents/factory.py src/agents/router.py src/dashboard/components/floating_chat.py tests/agents/test_phase5_chat_guardrails.py
```

결과:
- 통과

실행:
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_phase5_chat_guardrails.py tests/agents/test_router_intent.py tests/agents/test_guardrails.py tests/common/test_async_utils.py
```

결과:
- `17 passed`

---

## 5. 운영 파라미터

`.env` 조정 가능 항목:
- `CHAT_SESSION_COOLDOWN_SECONDS`
- `CHAT_CACHE_TTL_SECONDS`
- `CHAT_CACHE_MAX_ENTRIES`
- `CHAT_MAX_INPUT_CHARS`
- `CHAT_MAX_OUTPUT_CHARS`
- `CHAT_ENABLE_PREMIUM_REVIEW`
- `CHAT_PREMIUM_REVIEW_MIN_QUERY_LEN`
- `CHAT_PREMIUM_REVIEW_TIMEOUT_SEC`
- `LLM_PREMIUM_MODEL`

---

## 6. 남은 과제

1. 멀티 파드 운영 시 Redis 기반 분산 캐시/쿨다운으로 확장
2. premium 승격 조건(키워드 기반) 고도화
3. 전략 리뷰 premium 코멘트 품질/비용 모니터링 지표 추가
