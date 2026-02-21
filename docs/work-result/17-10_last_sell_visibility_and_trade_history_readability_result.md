# 17-10. 마지막 SELL 가시성 개선 및 Trade History 가독성 향상 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17-10_last_sell_visibility_and_trade_history_readability_plan.md`

---

## 1. 구현 요약

1. 코드 기준으로는 이미 `trade_history` intent/tool과 Trade History 손익 컬럼이 반영되어 있음을 확인했다.

2. 이번 작업에서는 해당 기능의 회귀 방지를 위해 테스트를 보강하고,
   17 메인 문서와 연계되는 하위 결과 문서를 정리했다.

---

## 2. 아키텍처 결정 기록

### 선택안
- 기존 반영 기능은 유지하고, 테스트로 동작 보증을 강화

### 대안 비교
1. `portfolio_tool`에 마지막 SELL만 덧붙이기
- 장점: 변경량 작음
- 단점: 거래이력 질의가 포트폴리오 의도와 혼합

2. `strategy_review_tool` 재활용
- 장점: 기존 매칭 로직 재사용
- 단점: 집계 중심 구조라 단건 조회 UX에 부적합

3. 대시보드만 개선
- 장점: 빠름
- 단점: 챗봇 질문 해결 불가

### 트레이드오프
- 기능 변경은 최소화(0)에 가깝지만, 테스트 보강으로 회귀 리스크를 낮췄다.

---

## 3. 변경 파일

1. `tests/agents/test_router_intent.py`
- `trade_history` fast-path 테스트 추가

2. `tests/agents/test_trade_history_tool.py` (신규)
- NO_DATA 케이스
- 마지막 SELL 손익 계산 케이스

3. `trade_history` fast-path 분류 보강
- "마지막 매매 결과가 어떻게돼?" 문장을 `trade_history`로 분류하도록 키워드 추가

---

## 4. 검증

실행:
```bash
python3 -m py_compile src/agents/tools/trade_history_tool.py src/agents/router.py src/dashboard/pages/4_history.py tests/agents/test_router_intent.py tests/agents/test_trade_history_tool.py
```

결과:
- 통과

실행:
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_router_intent.py tests/agents/test_trade_history_tool.py
```

결과:
- `10 passed`

추가 회귀:
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_guardrails.py tests/agents/test_phase5_chat_guardrails.py
```

결과:
- `8 passed`

---

## 5. 사용자 확인 포인트

1. 챗봇 질문
- "마지막 SELL이 뭐야?"
- "마지막 SELL 손해본거야?"

2. Trade History 페이지
- SELL 행에서 `Entry Avg`, `Realized PnL (KRW)`, `Realized PnL (%)` 노출 확인

---

## 6. 남은 과제

1. `entry_avg_price` 누락 SELL의 경우 FIFO 보완 계산(현재는 계산 불가로 표시)
2. 챗봇에서 최근 3건 SELL 비교 요약 템플릿 강화
