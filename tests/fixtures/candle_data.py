import pandas as pd
from datetime import datetime, timedelta, timezone

def get_oversold_candles(count: int = 100) -> pd.DataFrame:
    """
    RSI가 점진적으로 낮아져 과매도 구간(30 미만)에 진입하는 데이터 생성
    """
    base_price = 50000.0
    data = []
    now = datetime.now(timezone.utc)
    
    for i in range(count):
        # 가격이 계속 하락하는 형태
        price = base_price - (i * 100)
        data.append({
            "timestamp": now - timedelta(minutes=count - i),
            "open": price + 50,
            "high": price + 100,
            "low": price - 100,
            "close": price,
            "volume": 1000 + (i * 10)
        })
    
    return pd.DataFrame(data)

def get_mean_reversion_entry_scenario() -> pd.DataFrame:
    """
    전략 진입 조건을 모두 만족하는 시나리오 데이터 생성:
    1. RSI < 30
    2. Price > MA 200
    3. Price <= BB Lower
    4. Vol Ratio > 1.5
    """
    count = 300 
    data = []
    now = datetime.now(timezone.utc)
    
    # 1~200: 횡보장 (MA 200 형성)
    # Price = 50000 -> MA 200 ~= 50000
    for i in range(200):
        price = 50000.0 + (i % 10) # 약간의 노이즈
        data.append({
            "timestamp": now - timedelta(minutes=count - i),
            "open": price, "high": price + 5, "low": price - 5, "close": price,
            "volume": 100
        })
        
    # 201~290: 강한 상승추세
    # 50000 -> 100000
    last_price = data[-1]["close"]
    for i in range(90):
        price = last_price + ((i + 1) * 500)
        data.append({
            "timestamp": now - timedelta(minutes=100 - i),
            "open": price, "high": price + 5, "low": price - 50, "close": price,
            "volume": 100
        })
        
    # 291~299: 연쇄 폭락 시작
    # 95000 -> 85000
    last_price = data[-1]["close"]
    for i in range(9):
        price = last_price - ((i + 1) * 1000)
        data.append({
            "timestamp": now - timedelta(minutes=10 - i),
            "open": price + 500, "high": price + 1000, "low": price - 100, "close": price,
            "volume": 200
        })
        
    # 마지막 행: 결정적 진입 시점 (V자 하방 정점 + 거래량 폭발)
    # 현재가 ~= 75000 | MA 200 ~= 50000 ~ 60000
    entry_price = data[-1]["close"] - 10000 # 85000 -> 75000
    data.append({
        "timestamp": now,
        "open": entry_price + 1000,
        "high": entry_price + 2000,
        "low": entry_price - 100,
        "close": entry_price,
        "volume": 1000 # 거래량 대폭발
    })
    
    return pd.DataFrame(data)
