# 17-01. 챗봇 컨설턴트 응답 품질 개선 구현 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17-01_chatbot_consultant_intent_sell_strategy_plan.md`

---

## 1. 구현 요약

사용자 질문 오분류 이슈를 해결하기 위해 아래를 반영했다.

1. 라우팅 의도 분리
- `strategy_policy` (전략/규칙 설명)
- `sell_timing_advice` (보유 포지션 매도 타이밍 코칭)

2. 전용 도구 추가
- `src/agents/tools/strategy_policy_tool.py`
- `src/agents/tools/sell_timing_tool.py`

3. Fast-path 키워드 우선순위 조정
- "매도 타이밍" 질문이 포트폴리오 요약으로 빠지지 않도록 우선 분기
- "현재 매도 전략" 질문이 성과 리뷰로 빠지지 않도록 정책 분기

---

## 2. 설계 결정 기록

### 2.1 왜 이 구조를 선택했는가

기존 문제는 "전략 설명"과 "전략 리뷰"가 동일 경로로 처리되어 발생했다. 이를 해결하기 위해 라우팅 의도를 분리하고, 각 의도에 맞는 도구를 독립적으로 둔 구조를 채택했다.

### 2.2 고려한 대안

1. `strategy_review_tool` 내부 분기만 추가
- 장점: 구현량 적음
- 단점: 역할 혼합으로 유지보수 어려움

2. 프롬프트만 수정해 의도 분리 유도
- 장점: 빠름
- 단점: 결정론 부족, 재현성 낮음

3. 의도 + 도구 분리 (**채택**)
- 장점: 테스트 가능, 동작 예측 가능
- 단점: 파일/분기 수 증가

### 2.3 트레이드오프

- 규칙 기반 코칭은 최신 뉴스/이벤트를 직접 반영하지 못함
- 이를 완화하기 위해 기준값(익절/손절/트레일링/시간제한)을 명시하고 "자동 실행 아님" 고지를 유지했다.

---

## 3. 주요 변경 파일

1. `src/agents/router.py`
- Intent 추가: `strategy_policy`, `sell_timing_advice`
- 노드 추가: 전략 정책 설명, 매도 타이밍 코칭
- 키워드 Fast-path 우선순위 조정

2. `src/agents/tools/strategy_policy_tool.py` (신규)
- `StrategyConfig` 기반 레짐별 청산 규칙 및 하드 리스크 한도 반환

3. `src/agents/tools/sell_timing_tool.py` (신규)
- 포지션/현재가/RSI/레짐 기반 규칙 평가
- 포지션별 `매도 고려`, `분할익절 준비`, `손절 경계`, `홀드/관찰` 반환

4. `tests/agents/test_router_intent.py`
- 전략 정책/매도 타이밍 분기 테스트 추가

5. `tests/agents/test_sell_timing_tool.py` (신규)
- 매도 신호 계산 로직 유닛 테스트 추가

---

## 4. 검증

### 4.1 문법 검증

```bash
python3 -m py_compile src/agents/router.py src/agents/tools/strategy_policy_tool.py src/agents/tools/sell_timing_tool.py tests/agents/test_router_intent.py tests/agents/test_sell_timing_tool.py
```

결과:
- 통과

### 4.2 테스트

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_router_intent.py tests/agents/test_sell_timing_tool.py
```

결과:
- `9 passed`

### 4.3 관련 회귀 확인

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_sql_agent_safety.py tests/common/test_async_utils.py tests/agents/test_guardrails.py
```

결과:
- `9 passed`

---

## 5. 사용자 체감 개선 포인트

1. "현재 매도 전략이 어떻게돼?" 질문이 더 이상 성과 리뷰 실패 메시지로 가지 않고, 레짐별 매도 규칙 설명을 반환한다.
2. "보유 종목 언제 매도?" 질문이 포트폴리오 숫자 나열이 아니라 포지션별 매도 타이밍 코칭으로 응답한다.

---

## 6. 한계 및 후속

1. 뉴스 RAG/외부 이벤트 반영은 아직 미구현(별도 계획 이후 반영)
2. 현재 코칭은 규칙 기반이며, 고급 시나리오(거시 이벤트/온체인/오더북)는 후속 통합 필요
