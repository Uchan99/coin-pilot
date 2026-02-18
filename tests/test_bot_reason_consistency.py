from src.bot.main import build_status_reason
from src.config.strategy import StrategyConfig
from src.engine.strategy import MeanReversionStrategy


def test_reason_matches_strategy_on_sideways_bb_fail():
    config = StrategyConfig()
    strategy = MeanReversionStrategy(config)

    indicators = {
        "regime": "SIDEWAYS",
        "rsi": 40,
        "rsi_short": 42,
        "rsi_short_prev": 41,
        "rsi_short_min_lookback": 38,
        "rsi_short_recovery_lookback": 5,
        "ma_trend": 1000,
        "close": 980,
        "bb_lower": 970,
        "bb_touch_recovery": False,
        "vol_ratio": 0.5,
        "recent_vol_ratios": [0.8, 0.9, 1.0],
    }

    assert strategy.check_entry_signal(indicators) is False
    reason = build_status_reason(indicators, None, config)
    assert "BB 터치 회복 대기" in reason


def test_reason_matches_strategy_on_bull_success():
    config = StrategyConfig()
    strategy = MeanReversionStrategy(config)

    indicators = {
        "regime": "BULL",
        "rsi": 40,
        "rsi_short": 43,
        "rsi_short_prev": 41,
        "rsi_short_min_lookback": 39,
        "rsi_short_recovery_lookback": 5,
        "ma_trend": 1000,
        "close": 1005,
        "bb_lower": 980,
        "bb_touch_recovery": True,
        "vol_ratio": 1.5,
        "recent_vol_ratios": [1.0, 1.1, 1.2],
    }

    assert strategy.check_entry_signal(indicators) is True
    reason = build_status_reason(indicators, None, config)
    assert "진입 조건 충족" in reason
