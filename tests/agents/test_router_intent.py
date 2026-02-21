from src.agents.router import _classify_intent_fast_path, _infer_symbol


def test_fast_path_strategy_review_intent():
    intent = _classify_intent_fast_path("최근 매매 기준으로 전략 장단점 분석해줘")
    assert intent == "strategy_review"


def test_fast_path_market_outlook_intent():
    intent = _classify_intent_fast_path("지금 비트코인 시장 전망 어때?")
    assert intent == "market_outlook"


def test_fast_path_portfolio_intent():
    intent = _classify_intent_fast_path("현재 포트폴리오와 잔고 보여줘")
    assert intent == "portfolio_status"


def test_fast_path_strategy_policy_intent():
    intent = _classify_intent_fast_path("현재 매도 전략이 어떻게돼?")
    assert intent == "strategy_policy"


def test_fast_path_sell_timing_intent():
    intent = _classify_intent_fast_path("지금 보유중인 종목들 언제 매도하는게 좋아보여?")
    assert intent == "sell_timing_advice"


def test_fast_path_buy_decision_intent():
    intent = _classify_intent_fast_path("BTC 현재 기준으로 매수 안하는게 좋은거지")
    assert intent == "action_recommendation"


def test_fast_path_trade_history_intent():
    intent = _classify_intent_fast_path("마지막 SELL이 뭐야? 얼마에 사서 얼마에 팔았어?")
    assert intent == "trade_history"


def test_fast_path_trade_history_intent_last_trade_result():
    intent = _classify_intent_fast_path("마지막 매매 결과가 어떻게돼?")
    assert intent == "trade_history"


def test_infer_symbol_aliases():
    assert _infer_symbol("비트코인 시장 알려줘") == "KRW-BTC"
    assert _infer_symbol("ETH 전망") == "KRW-ETH"
    assert _infer_symbol("xrp 리스크") == "KRW-XRP"
