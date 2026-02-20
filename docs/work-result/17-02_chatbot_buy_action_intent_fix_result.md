# 17-02. 챗봇 매수 의사결정 질문 의도 보정 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17-02_chatbot_buy_action_intent_fix_plan.md`

---

## 1. 문제 재현

질문: "BTC 현재 기준으로 매수 안하는게 좋은거지"  
기존 동작: `market_outlook`으로 분류되어 시장 지표 브리핑만 반환  
기대 동작: 매수 보류/진입 권고를 포함한 행동 제안

---

## 2. 변경 내용

1. `src/agents/router.py`
- `_is_action_decision_query()` 추가
  - `매수/진입` + `판단형 표현(안하는게, 해도, 할까, 맞아?, 좋은지 등)` 조합을 `action_recommendation`으로 분류
- `IntentDecision` 설명문 보강
  - action intent를 "buy/entry/hold decision guidance"로 명확화
- `action_recommendation_node` 응답 포맷 개선
  - 첫 줄에 `결론:`을 명시하여 질문 의도에 직접 답변

2. `tests/agents/test_router_intent.py`
- 신규 테스트 추가:
  - `test_fast_path_buy_decision_intent`

---

## 3. 검증

### 3.1 문법/테스트

```bash
python3 -m py_compile src/agents/router.py tests/agents/test_router_intent.py
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_router_intent.py
```

결과:
- `7 passed`

### 3.2 분류 확인

검증 문장:
- "BTC 현재 기준으로 매수 안하는게 좋은거지"

결과:
- `action_recommendation`

---

## 4. 기대 효과

1. 행동 권고 질문에 대해 데이터 나열이 아니라 결론 중심 응답 제공
2. 사용자 체감 품질 개선(질문-응답 정합성 향상)

---

## 5. 남은 과제

1. LLM slow-path에서도 동일 기준을 더 강하게 따르도록 분류 프롬프트 규칙 추가 검토
2. 실사용 로그 기준 오분류 샘플 수집 후 fast-path 패턴 지속 튜닝
