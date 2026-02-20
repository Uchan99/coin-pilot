# 17-08. 챗봇 Phase 5 (비용/안전 가드레일) 구현 계획

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P0

---

## 1. 배경

17번 계획의 Phase 5는 아직 "고도화" 항목으로 남아 있으며,
현재 챗봇은 일부 가드레일(프론트 세션 쿨다운/캐시, 노드별 안전 문구)은 있으나
백엔드 공통 레이어에서의 일관된 호출 통제가 부족하다.

---

## 2. 목표

1. 모델 계층화
- 기본 모델은 기존 정책(Haiku) 유지
- 고난도 전략 리뷰 요청 시에만 조건부 Sonnet 승격

2. 호출 통제(백엔드 공통)
- 세션 쿨다운
- 동일 질의 캐시(TTL/LRU)
- 입력 길이 제한 + 출력 길이 예산
- 에러/타임아웃 시 보수적 fallback 유지

3. 답변 안전장치 보강
- 안전 고지문 누락 방지(공통 후처리)
- 시장/행동/전략 계열 응답에 시나리오 기반 해석 문구 강제

---

## 3. 아키텍처 선택 및 대안

### 선택안 (채택)
- `router.py`의 `process_chat()` 경로에 공통 runtime guard 레이어 추가
- `factory.py`에 `premium_review` 모델 타입 확장
- `strategy_review_node`에서 복잡도 조건 충족 시만 premium 모델 사용

### 대안 1
- 프론트(Streamlit) 가드레일만 강화
- 장점: 빠름
- 단점: API/다른 UI 채널에서 우회 가능

### 대안 2
- Redis 기반 분산 가드레일로 즉시 확장
- 장점: 멀티 프로세스/멀티 파드 일관성 높음
- 단점: 현재 범위 대비 구현 부담 큼

### 대안 3
- 모든 분석 질의를 Sonnet으로 상향
- 장점: 품질 잠재력
- 단점: 비용 급증, 속도 저하

### 트레이드오프
- 인메모리 가드레일은 파드 재시작/다중 파드에서 상태가 완전 공유되지는 않음.
- 하지만 현재 운영 목표(단일 latest 반복 운영)에서 구현/검증 속도와 비용 통제의 균형이 가장 적절함.

---

## 4. 구현 범위

1. `src/agents/factory.py`
- `model_type="premium_review"` 분기 추가
- `LLM_PREMIUM_MODEL` 환경변수(기본 Sonnet) 지원

2. `src/agents/router.py`
- Phase 5 runtime guard 상수/인메모리 상태 추가
- 세션 쿨다운 + 동일 질의 캐시(TTL/LRU) 추가
- 입력/출력 길이 예산 적용
- 공통 안전 고지문/시나리오 해석 문구 후처리
- `process_chat(message, session_id=None)` 시그니처 확장
- `strategy_review_node` 조건부 premium 모델 승격 + 실패 시 deterministic fallback

3. `src/dashboard/components/floating_chat.py`
- 세션별 고유 ID 생성
- `process_chat_sync(prompt, session_id=...)`로 호출

4. `src/dashboard/pages/06_chatbot.py`
- 대화 초기화 시 세션 ID 초기화로 백엔드 세션 가드레일 상태도 함께 리셋

5. `.env.example`
- Phase 5 관련 환경변수 추가

6. 테스트 추가
- `tests/agents/test_phase5_chat_guardrails.py`
  - 쿨다운 동작
  - 동일 질의 캐시 동작
  - 입력/출력 길이 제한
  - 전략 리뷰 승격 조건 판정

---

## 5. 검증

```bash
python3 -m py_compile src/agents/factory.py src/agents/router.py src/dashboard/components/floating_chat.py tests/agents/test_phase5_chat_guardrails.py
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_phase5_chat_guardrails.py tests/agents/test_router_intent.py tests/agents/test_guardrails.py
```

---

## 6. 산출물

1. 코드 변경
- `src/agents/factory.py`
- `src/agents/router.py`
- `src/dashboard/components/floating_chat.py`
- `.env.example`
- `tests/agents/test_phase5_chat_guardrails.py`

2. 결과 문서
- `docs/work-result/17-08_phase5_chat_guardrails_and_model_tiering_result.md`

---

## 7. 변경 이력

### 2026-02-20

1. 계획서 작성
2. 모델 계층화(`premium_review`) 및 백엔드 공통 런타임 가드레일 구현 완료
3. 테스트(`test_phase5_chat_guardrails`) 추가 및 통과 확인
