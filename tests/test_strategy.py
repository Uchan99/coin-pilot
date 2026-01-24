import pytest
import pandas as pd
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from src.engine.strategy import MeanReversionStrategy
from src.common.indicators import get_all_indicators
from tests.fixtures.candle_data import get_mean_reversion_entry_scenario

def test_mean_reversion_entry_signal():
    # 1. 시나리오 데이터 준비 (모든 조건 만족하는 시점 포함)
    df = get_mean_reversion_entry_scenario()
    
    # 2. 지표 계산
    indicators = get_all_indicators(df)
    
    # 3. 전략 객체 생성 및 신호 확인
    strategy = MeanReversionStrategy()
    signal = strategy.check_entry_signal(indicators)
    
    assert signal is True

def test_mean_reversion_exit_tp():
    strategy = MeanReversionStrategy(tp_ratio=0.05)
    
    indicators = {"close": 105.0, "rsi": 50}
    position_info = {
        "avg_price": 100.0,
        "opened_at": datetime.now(timezone.utc) - timedelta(hours=1)
    }
    
    should_exit, reason = strategy.check_exit_signal(indicators, position_info)
    assert should_exit is True
    assert "Take Profit" in reason

def test_mean_reversion_exit_sl():
    strategy = MeanReversionStrategy(sl_ratio=0.03)
    
    indicators = {"close": 96.0, "rsi": 50}
    position_info = {
        "avg_price": 100.0,
        "opened_at": datetime.now(timezone.utc) - timedelta(hours=1)
    }
    
    should_exit, reason = strategy.check_exit_signal(indicators, position_info)
    assert should_exit is True
    assert "Stop Loss" in reason

def test_mean_reversion_exit_time():
    strategy = MeanReversionStrategy(max_hold_hours=48)
    
    indicators = {"close": 100.0, "rsi": 50}
    # 50시간 전 진입
    position_info = {
        "avg_price": 100.0,
        "opened_at": datetime.now(timezone.utc) - timedelta(hours=50)
    }
    
    should_exit, reason = strategy.check_exit_signal(indicators, position_info)
    assert should_exit is True
    assert "Time Exit" in reason
