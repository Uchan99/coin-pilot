import src.agents.router as router


def _reset_runtime_state() -> None:
    with router._runtime_guard_lock:
        router._session_last_request_ts.clear()
        router._response_cache.clear()


def test_session_cooldown_blocks_rapid_requests(monkeypatch):
    _reset_runtime_state()
    monkeypatch.setattr(router, "CHAT_SESSION_COOLDOWN_SECONDS", 1.5)

    now = {"value": 1000.0}
    monkeypatch.setattr(router.time, "time", lambda: now["value"])

    blocked, _ = router._is_cooldown_blocked("s1")
    assert blocked is False

    blocked, reason = router._is_cooldown_blocked("s1")
    assert blocked is True
    assert "요청 간격이 너무 짧습니다" in reason

    now["value"] = 1002.0
    blocked, _ = router._is_cooldown_blocked("s1")
    assert blocked is False


def test_cache_ttl_and_lookup(monkeypatch):
    _reset_runtime_state()
    monkeypatch.setattr(router, "CHAT_CACHE_TTL_SECONDS", 10)
    monkeypatch.setattr(router, "CHAT_CACHE_MAX_ENTRIES", 8)

    now = {"value": 2000.0}
    monkeypatch.setattr(router.time, "time", lambda: now["value"])

    router._set_cached_response("s1", "q1", "a1")
    assert router._get_cached_response("s1", "q1") == "a1"

    now["value"] = 2012.0
    assert router._get_cached_response("s1", "q1") is None


def test_safety_footer_and_output_budget(monkeypatch):
    monkeypatch.setattr(router, "CHAT_MAX_OUTPUT_CHARS", 120)
    long_text = "x" * 300

    response = router._ensure_safety_footer(long_text, "market_outlook")

    assert router.SAFETY_DISCLAIMER in response
    assert router.SCENARIO_NOTE in response
    assert "응답 길이 제한" in response
    assert len(response) <= 200


def test_premium_review_escalation_decision(monkeypatch):
    monkeypatch.setattr(router, "CHAT_ENABLE_PREMIUM_REVIEW", True)
    monkeypatch.setattr(router, "CHAT_PREMIUM_REVIEW_MIN_QUERY_LEN", 20)

    high_query = "최근 30일 전략 장단점 원인 분석하고 개선 근거와 리스크 패턴까지 알려줘"
    low_query = "전략 리뷰 해줘"

    assert router._should_escalate_premium_review(high_query) is True
    assert router._should_escalate_premium_review(low_query) is False


def test_normalize_session_id():
    assert router._normalize_session_id(None) == "default"
    assert router._normalize_session_id("") == "default"
    assert router._normalize_session_id("  user-1  ") == "user-1"
