from datetime import datetime, timedelta, timezone

from src.agents.tools.sell_timing_tool import evaluate_sell_signals


def _exit_cfg():
    return {
        "take_profit_pct": 0.03,
        "stop_loss_pct": 0.04,
        "trailing_stop_pct": 0.025,
        "trailing_stop_activation_pct": 0.01,
        "rsi_overbought": 70,
        "rsi_exit_min_profit_pct": 0.01,
        "time_limit_hours": 48,
    }


def test_evaluate_sell_signals_take_profit_trigger():
    result = evaluate_sell_signals(
        current_price=103.5,
        entry_price=100.0,
        high_water_mark=104.0,
        rsi14=60.0,
        opened_at=datetime.now(timezone.utc) - timedelta(hours=2),
        exit_cfg=_exit_cfg(),
    )

    assert result["recommendation"] == "매도 고려"
    assert any("익절 기준" in s for s in result["signals"])


def test_evaluate_sell_signals_hold_state():
    result = evaluate_sell_signals(
        current_price=101.0,
        entry_price=100.0,
        high_water_mark=101.2,
        rsi14=55.0,
        opened_at=datetime.now(timezone.utc) - timedelta(hours=2),
        exit_cfg=_exit_cfg(),
    )

    assert result["recommendation"] in {"홀드/관찰", "분할익절 준비"}


def test_evaluate_sell_signals_stop_loss_warning():
    result = evaluate_sell_signals(
        current_price=96.8,
        entry_price=100.0,
        high_water_mark=100.5,
        rsi14=45.0,
        opened_at=datetime.now(timezone.utc) - timedelta(hours=4),
        exit_cfg=_exit_cfg(),
    )

    # -4% 손절선 바로 직전 구간이므로 경계 또는 즉시 매도 신호 중 하나로 판단
    assert result["recommendation"] in {"손절 경계", "매도 고려"}
