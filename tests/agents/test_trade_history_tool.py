from datetime import datetime, timezone

from src.agents.tools.trade_history_tool import run_trade_history_tool


def test_trade_history_tool_no_data(monkeypatch):
    monkeypatch.setattr("src.agents.tools.trade_history_tool.fetch_all", lambda *a, **k: [])

    result = run_trade_history_tool()

    assert result["status"] == "NO_DATA"
    assert result["last_sell"] is None


def test_trade_history_tool_last_sell_realized_pnl(monkeypatch):
    sample_rows = [
        {
            "filled_at_kst": datetime(2026, 2, 20, 21, 0, tzinfo=timezone.utc),
            "symbol": "KRW-ETH",
            "side": "SELL",
            "price": 3950000,
            "quantity": 0.1,
            "entry_avg_price": 4000000,
            "regime": "SIDEWAYS",
            "exit_reason": "TAKE_PROFIT",
        },
        {
            "filled_at_kst": datetime(2026, 2, 20, 20, 0, tzinfo=timezone.utc),
            "symbol": "KRW-ETH",
            "side": "BUY",
            "price": 4000000,
            "quantity": 0.1,
            "entry_avg_price": None,
            "regime": "SIDEWAYS",
            "exit_reason": "UNKNOWN",
        },
    ]

    monkeypatch.setattr("src.agents.tools.trade_history_tool.fetch_all", lambda *a, **k: sample_rows)

    result = run_trade_history_tool()

    assert result["status"] == "OK"
    assert result["sell_count"] == 1
    last_sell = result["last_sell"]
    assert last_sell["symbol"] == "KRW-ETH"
    assert last_sell["realized_pnl_krw"] == -5000.0
    assert round(last_sell["realized_pnl_pct"], 2) == -1.25
