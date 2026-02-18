import pytest
import pandas as pd
from src.common.indicators import (
    calculate_rsi, calculate_ma, calculate_bb, 
    calculate_volume_ratio, get_all_indicators, InsufficientDataError
)
from tests.fixtures.candle_data import get_oversold_candles

def test_calculate_rsi_success():
    df = get_oversold_candles(count=30)
    rsi = calculate_rsi(df['close'], period=14)
    
    assert isinstance(rsi, pd.Series)
    assert len(rsi) == 30
    # RSI는 0~100 사이여야 함
    assert 0 <= rsi.iloc[-1] <= 100
    # 하락하는 데이터이므로 RSI가 낮아야 함 (작성한 fixture 특성)
    assert rsi.iloc[-1] < 50

def test_calculate_rsi_insufficient_data():
    df = get_oversold_candles(count=10)
    with pytest.raises(InsufficientDataError):
        calculate_rsi(df['close'], period=14)

def test_calculate_ma_success():
    df = get_oversold_candles(count=50)
    ma = calculate_ma(df['close'], period=20)
    
    assert len(ma) == 50
    assert not pd.isna(ma.iloc[-1])
    assert pd.isna(ma.iloc[0]) # 앞부분은 계산 불가로 NaN

def test_calculate_bb_success():
    df = get_oversold_candles(count=30)
    bb = calculate_bb(df['close'], period=20)
    
    # BB 결과는 DataFrame (하단, 중앙, 상단 등)
    assert isinstance(bb, pd.DataFrame)
    assert bb.shape[1] >= 3
    assert not pd.isna(bb.iloc[-1, 0]) # Lower Band

def test_calculate_volume_ratio():
    volumes = pd.Series([100] * 20 + [200]) # 평균 100, 현재 200
    ratio = calculate_volume_ratio(volumes, period=20)
    
    assert ratio == 2.0

def test_get_all_indicators_includes_lookback_fields():
    df = get_oversold_candles(count=120)
    indicators = get_all_indicators(
        df,
        rsi_short_recovery_lookback=5,
        bb_touch_lookback=30
    )

    assert "rsi_short_min_lookback" in indicators
    assert "rsi_short_recovery_lookback" in indicators
    assert indicators["rsi_short_recovery_lookback"] == 5
    assert "bb_touch_recovery" in indicators
    assert "bb_touch_lookback" in indicators
    assert indicators["bb_touch_lookback"] == 30
