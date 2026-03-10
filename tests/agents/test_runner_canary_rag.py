import pytest

from src.agents import runner as runner_module


def test_is_canary_rag_enabled_only_for_canary_route(monkeypatch):
    monkeypatch.setenv("AI_DECISION_RAG_CANARY_ENABLED", "true")

    assert runner_module.is_canary_rag_enabled({"route_label": "canary"}) is True
    assert runner_module.is_canary_rag_enabled({"route_label": "primary"}) is False
    assert runner_module.is_canary_rag_enabled(None) is False


def test_format_model_used_marks_canary_rag_and_fallback():
    llm_route = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "route_label": "canary",
    }

    assert runner_module.format_model_used(llm_route, rag_status="enabled") == "openai:gpt-4o-mini (canary-rag)"
    assert runner_module.format_model_used(llm_route, rag_status="fallback") == "openai:gpt-4o-mini (canary-rag-fallback)"
    assert runner_module.format_model_used(llm_route, rag_status="disabled") == "openai:gpt-4o-mini (canary)"


@pytest.mark.asyncio
async def test_build_live_canary_rag_context_returns_none_when_disabled(monkeypatch):
    monkeypatch.setenv("AI_DECISION_RAG_CANARY_ENABLED", "false")

    payload = await runner_module.build_live_canary_rag_context(
        symbol="KRW-BTC",
        strategy_name="AdaptiveMeanReversion",
        market_context=[],
        indicators={"regime": "SIDEWAYS"},
        llm_route={"route_label": "canary"},
    )

    assert payload is None


@pytest.mark.asyncio
async def test_build_live_canary_rag_context_falls_back_on_error(monkeypatch):
    monkeypatch.setenv("AI_DECISION_RAG_CANARY_ENABLED", "true")

    async def _raise(**_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(runner_module, "build_ai_decision_rag_context", _raise)

    payload = await runner_module.build_live_canary_rag_context(
        symbol="KRW-BTC",
        strategy_name="AdaptiveMeanReversion",
        market_context=[],
        indicators={"regime": "SIDEWAYS"},
        llm_route={"route_label": "canary"},
    )

    assert payload is not None
    assert payload["status"] == "fallback"
    assert payload["text"] == ""
    assert "boom" in payload["error"]
