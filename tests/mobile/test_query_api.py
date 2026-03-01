import pytest
from fastapi import HTTPException

from src.mobile import query_api


def test_mobile_api_rejects_invalid_secret(monkeypatch):
    monkeypatch.setenv("COINPILOT_API_SHARED_SECRET", "test-secret")
    with pytest.raises(HTTPException) as exc_info:
        query_api._require_mobile_api_secret("wrong")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_mobile_positions_returns_payload(monkeypatch):
    monkeypatch.setenv("COINPILOT_API_SHARED_SECRET", "test-secret")

    monkeypatch.setattr(
        query_api,
        "run_portfolio_tool",
        lambda: {
            "cash_krw": 1000000.0,
            "holdings_value_krw": 0.0,
            "total_valuation_krw": 1000000.0,
            "holdings": [],
            "risk_snapshot": {
                "date": "2026-03-01",
                "total_pnl": 0.0,
                "buy_count": 0,
                "sell_count": 0,
                "trade_count": 0,
                "consecutive_losses": 0,
                "is_trading_halted": False,
            },
        },
    )

    payload = await query_api.get_positions(None)
    assert payload["ok"] is True
    assert payload["data"]["total_valuation_krw"] == 1000000.0


@pytest.mark.asyncio
async def test_mobile_ask_returns_answer(monkeypatch):
    monkeypatch.setenv("COINPILOT_API_SHARED_SECRET", "test-secret")

    async def _fake_process_chat(message: str, session_id: str | None = None) -> str:
        assert message == "지금 상태 알려줘"
        assert session_id == "discord-user-1"
        return "테스트 응답"

    monkeypatch.setattr(query_api, "process_chat", _fake_process_chat)

    payload = await query_api.ask_mobile(
        query_api.AskRequest(query="지금 상태 알려줘", session_id="discord-user-1"),
        None,
    )
    assert payload["ok"] is True
    assert payload["data"]["answer"] == "테스트 응답"
    assert isinstance(payload["latency_ms"], int)
