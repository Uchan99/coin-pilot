
import asyncio
from src.config.strategy import StrategyConfig
from src.engine.strategy import MeanReversionStrategy
from src.common.indicators import get_all_indicators

async def test():
    config = StrategyConfig()
    strategy = MeanReversionStrategy(config)

    print(f'=== 시그널 테스트 설정 확인 ===')
    print(f'RSI Threshold: < {config.RSI_OVERSOLD}')
    print(f'Volume Multiplier: > {config.VOLUME_MULTIPLIER}x')
    print(f'BB Condition: {config.USE_BB_CONDITION}')
    print(f'Target Symbols: {config.SYMBOLS}')
    
    # Mock Indicators for testing logic
    mock_indicators = {
        "rsi": 32.0,                  # < 33 (Pass)
        "ma_200": 50000000,
        "close": 55000000,            # > MA200 (Pass)
        "vol_ratio": 1.4,             # > 1.3 (Pass)
        "bb_lower": 54000000
    }
    
    print(f'\n[Case 1] RSI 32, Vol 1.4 (All Pass)')
    result = strategy.check_entry_signal(mock_indicators)
    print(f'Result: {result} (Expected: True)')

    mock_indicators_fail = {
        "rsi": 35.0,                  # > 33 (Fail)
        "ma_200": 50000000,
        "close": 55000000,
        "vol_ratio": 1.4,
        "bb_lower": 54000000
    }
    print(f'\n[Case 2] RSI 35 (Fail)')
    result = strategy.check_entry_signal(mock_indicators_fail)
    print(f'Result: {result} (Expected: False)')

asyncio.run(test())
