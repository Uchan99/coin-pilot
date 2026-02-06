import pytest
from src.engine.strategy import TrailingStop, MeanReversionStrategy
from src.config.strategy import StrategyConfig

def test_trailing_stop_logic():
    # 1. 상승 시 HWM 갱신 테스트
    ts = TrailingStop(entry_price=100.0, trailing_stop_pct=0.03, activation_pct=0.01)
    
    # +0.5% 상승 (활성화 안 됨)
    assert ts.update(100.5) is False
    assert ts.high_water_mark == 100.5
    
    # +1.5% 상승 (활성화 됨, HWM 갱신)
    assert ts.update(101.5) is False
    assert ts.high_water_mark == 101.5
    
    # 하락하지만 트리거 안 됨 (101.5 * 0.97 = 98.455)
    assert ts.update(100.0) is False
    
    # 설정된 스탑 라인 이하로 하락 (트리거)
    assert ts.update(98.0) is True

def test_strategy_entry_signal_regime_logic():
    config = StrategyConfig()
    strategy = MeanReversionStrategy(config)
    
    # 1. BULL 레짐 진입 테스트
    indicators_bull = {
        "regime": "BULL",
        "rsi": 40,
        "rsi_short": 41,
        "rsi_short_prev": 39,
        "ma_trend": 1000,
        "close": 1005, # crossover
        "vol_ratio": 1.5
    }
    assert strategy.check_entry_signal(indicators_bull) is True
    
    # 2. BEAR 레짐 보수적 진입 테스트
    indicators_bear = {
        "regime": "BEAR",
        "rsi": 35,
        "rsi_short": 31,
        "rsi_short_prev": 29,
        "ma_trend": 1000,
        "close": 980, # proximity (97%이상)
    }
    assert strategy.check_entry_signal(indicators_bear) is True

def test_strategy_exit_rsi_conditional():
    config = StrategyConfig()
    strategy = MeanReversionStrategy(config)
    
    # RSI > 70 이지만 수익이 < 1% 인 경우 (SIDEWAYS)
    pos = {"avg_price": 100, "opened_at": None, "regime": "SIDEWAYS"}
    indicators = {"close": 100.5, "rsi": 75}
    should_exit, reason = strategy.check_exit_signal(indicators, pos)
    assert should_exit is False
    
    # RSI > 70 이고 수익이 > 1% 인 경우 (SIDEWAYS)
    indicators_exit = {"close": 101.5, "rsi": 75}
    should_exit, reason = strategy.check_exit_signal(indicators_exit, pos)
    assert should_exit is True
    assert reason == "RSI_OVERBOUGHT"

if __name__ == "__main__":
    pytest.main([__file__])
