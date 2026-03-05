import pytest

from src.agents import factory


@pytest.fixture(autouse=True)
def clear_factory_caches():
    # env 기반 동작을 테스트하므로 캐시를 매 케이스 초기화한다.
    factory.get_llm_mode.cache_clear()
    factory.get_default_model_name.cache_clear()
    factory._build_anthropic_llm.cache_clear()
    factory._build_openai_llm.cache_clear()
    yield
    factory.get_llm_mode.cache_clear()
    factory.get_default_model_name.cache_clear()
    factory._build_anthropic_llm.cache_clear()
    factory._build_openai_llm.cache_clear()


def test_select_ai_decision_route_primary_when_canary_disabled(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
    monkeypatch.setenv("AI_DECISION_PRIMARY_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_DECISION_PRIMARY_MODEL", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("AI_CANARY_ENABLED", "false")

    route = factory.select_ai_decision_route(
        symbol="KRW-BTC",
        strategy_name="AdaptiveMeanReversion",
        market_context=[{"timestamp": "2026-03-04T00:00:00Z"}],
        indicators={"rsi": 42.0},
    )

    assert route["provider"] == "anthropic"
    assert route["model"] == "claude-haiku-4-5-20251001"
    assert route["route_label"] == "primary"
    assert route["canary_enabled"] is False


def test_select_ai_decision_route_canary_is_deterministic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("AI_DECISION_PRIMARY_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_DECISION_PRIMARY_MODEL", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_CANARY_PROVIDER", "openai")
    monkeypatch.setenv("AI_CANARY_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("AI_CANARY_PERCENT", "10")
    monkeypatch.setattr(factory, "_deterministic_bucket", lambda _: 3)

    kwargs = {
        "symbol": "KRW-ETH",
        "strategy_name": "AdaptiveMeanReversion",
        "market_context": [{"timestamp": "2026-03-04T01:00:00Z"}],
        "indicators": {"rsi": 47.2},
    }
    first = factory.select_ai_decision_route(**kwargs)
    second = factory.select_ai_decision_route(**kwargs)

    assert first["route_label"] == "canary"
    assert first["provider"] == "openai"
    assert first["model"] == "gpt-4o-mini"
    assert second["route_label"] == "canary"
    assert first["seed"] == second["seed"]
    assert first["bucket"] == second["bucket"] == 3


def test_select_ai_decision_route_fallback_when_canary_provider_key_missing(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AI_DECISION_PRIMARY_PROVIDER", "anthropic")
    monkeypatch.setenv("AI_DECISION_PRIMARY_MODEL", "claude-haiku-4-5-20251001")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_CANARY_PROVIDER", "openai")
    monkeypatch.setenv("AI_CANARY_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("AI_CANARY_PERCENT", "10")
    monkeypatch.setattr(factory, "_deterministic_bucket", lambda _: 0)

    route = factory.select_ai_decision_route(
        symbol="KRW-SOL",
        strategy_name="AdaptiveMeanReversion",
        market_context=[{"timestamp": "2026-03-04T02:00:00Z"}],
        indicators={"rsi": 39.8},
    )

    assert route["provider"] == "anthropic"
    assert route["route_label"] == "primary-fallback"
    assert route["canary_enabled"] is True


def test_select_ai_decision_route_clamps_percent_to_20(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("AI_CANARY_ENABLED", "true")
    monkeypatch.setenv("AI_CANARY_PERCENT", "99")
    monkeypatch.setattr(factory, "_deterministic_bucket", lambda _: 25)

    route = factory.select_ai_decision_route(
        symbol="KRW-XRP",
        strategy_name="AdaptiveMeanReversion",
        market_context=[{"timestamp": "2026-03-04T03:00:00Z"}],
        indicators={"rsi": 31.2},
    )

    assert route["canary_percent"] == 20
    assert route["route_label"] == "primary"
