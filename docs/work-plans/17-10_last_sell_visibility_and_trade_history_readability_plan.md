# 17-10. 마지막 SELL 가시성 개선 및 Trade History 가독성 향상 계획

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P0

---

## 1. 배경

현재 챗봇 `portfolio_status` 응답은 보유 포지션 중심 요약만 제공해,
"마지막 SELL이 무엇이었는지"와 "손익 여부"를 즉시 확인하기 어렵다.

또한 Trade History 페이지도 체결가/수량 중심이라,
SELL 기준 `매수가/매도가/실현손익(KRW)/수익률(%)` 확인이 불편하다.

---

## 2. 목표

1. 챗봇이 마지막 SELL 요약을 직접 응답하도록 개선
2. Trade History 페이지에서 SELL 손익 정보를 한눈에 볼 수 있도록 컬럼 강화
3. 기존 17번 챗봇 고도화 흐름(에픽-서브태스크)과 문서 추적성 유지

---

## 3. 아키텍처 선택 및 대안

### 선택안 (채택)
- `trade_history_tool` 신규 추가
- Router에 `trade_history` intent/node 추가
- Trade History 페이지에 계산 컬럼(`entry_avg_price`, `realized_pnl_krw`, `realized_pnl_pct`) 추가

### 대안 1
- 기존 `portfolio_tool`에 마지막 SELL 정보만 붙이기
- 장점: 변경량 작음
- 단점: 의도 분리 불명확, 거래이력 질의 확장성 제한

### 대안 2
- `strategy_review_tool`를 재활용해 마지막 SELL 추출
- 장점: 중복 계산 감소
- 단점: 리뷰용 집계 로직과 단건 조회 요구가 혼합

### 대안 3
- 대시보드만 개선하고 챗봇은 유지
- 장점: UI 개선 빠름
- 단점: 챗봇 질의 해결 불가

### 트레이드오프
- 툴/intent 추가로 라우터 복잡도는 증가하지만,
  사용자의 "마지막 SELL 확인" 요구를 결정론적으로 처리할 수 있다.

---

## 4. 구현 범위

1. `src/agents/tools/trade_history_tool.py` (신규)
- 최근 체결 내역 조회
- 마지막 SELL 상세(시간/심볼/매도가/수량/매수가/실현손익/수익률) 산출

2. `src/agents/router.py`
- `trade_history` intent 추가
- fast-path 키워드("마지막 sell", "최근 매도", "체결 내역" 등) 분기
- `trade_history_node` 신규 응답 포맷 추가

3. `src/dashboard/pages/4_history.py`
- 표시 컬럼 강화: 매수가/실현손익/수익률/레짐/청산사유
- SELL이 아닌 행은 해당 컬럼 N/A 처리

4. 테스트
- `tests/agents/test_router_intent.py` 케이스 추가
- `tests/agents/test_trade_history_tool.py` 신규

---

## 5. 검증

```bash
python3 -m py_compile src/agents/tools/trade_history_tool.py src/agents/router.py src/dashboard/pages/4_history.py tests/agents/test_router_intent.py tests/agents/test_trade_history_tool.py
PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_router_intent.py tests/agents/test_trade_history_tool.py
```

---

## 6. 산출물

1. 챗봇 마지막 SELL 응답 기능
2. Trade History 상세 손익 컬럼
3. 결과 문서: `docs/work-result/17-10_last_sell_visibility_and_trade_history_readability_result.md`

---

## 7. 변경 이력

### 2026-02-20

1. 계획서 작성
2. `trade_history` intent/tool 및 Trade History 상세 손익 컬럼이 코드 기준 반영됨을 확인
3. 테스트(`test_router_intent`, `test_trade_history_tool`) 보강 및 통과 확인
4. `마지막 매매 결과가 어떻게돼?` 질의를 `trade_history` intent로 고정 분류하도록 키워드 보강
