# 17-02. 챗봇 매수 의사결정 질문 의도 보정 계획

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P0

---

## 1. 문제

질문: "BTC 현재 기준으로 매수 안하는게 좋은거지"  
기대: 매수 보류/진입 제안 (행동 권고)  
실제: 시장 브리핑 데이터 나열

원인:
- Fast-path 키워드에서 `매수` + 판단형 문장 패턴(안하는게/좋은거지/해도 될까)을 충분히 `action_recommendation`으로 분류하지 못함.

---

## 2. 목표

1. 매수/진입 의사결정형 질문을 `action_recommendation`으로 우선 분류
2. action 응답 첫 줄에 결론(관망/분할진입/보류)을 명시
3. 회귀 테스트 추가

---

## 3. 구현 범위

1. `src/agents/router.py`
- fast-path에 "매수/진입 + 판단형 표현" 규칙 추가
- LLM 분류 설명문에 action intent 기준 보강
- `action_recommendation_node` 응답을 "결론" 중심으로 조정

2. `tests/agents/test_router_intent.py`
- "BTC 현재 기준으로 매수 안하는게 좋은거지" 케이스 추가

---

## 4. 검증

```bash
python3 -m py_compile src/agents/router.py tests/agents/test_router_intent.py
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_router_intent.py
```

---

## 5. 산출물

1. 코드 수정: `src/agents/router.py`
2. 테스트 수정: `tests/agents/test_router_intent.py`
3. 결과 문서: `docs/work-result/17-02_chatbot_buy_action_intent_fix_result.md`

---

## 6. 변경 이력

### 2026-02-20

1. fast-path에 `매수/진입 + 판단형 표현` 분기 추가 완료
2. `action_recommendation_node`의 결론 우선 응답 포맷 반영 완료
3. 회귀 테스트(`test_fast_path_buy_decision_intent`) 추가 및 통과
