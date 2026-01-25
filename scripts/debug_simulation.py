import asyncio
import pandas as pd
from decimal import Decimal
from datetime import datetime, timezone
import random

from src.common.db import get_db_session
from src.engine.executor import PaperTradingExecutor
from src.engine.strategy import MeanReversionStrategy

async def force_simulate():
    """
    강제로 매수 신호를 발생시켜 AI Agent를 테스트하는 디버깅 스크립트
    """
    symbol = "KRW-BTC"
    print(f"[*] Starting FORCED AI Simulation for {symbol}...")
    
    executor = PaperTradingExecutor()
    strategy = MeanReversionStrategy()
    
    # 가짜 데이터 생성 (RSI가 25가 나오도록 유도하거나, 그냥 지표값을 조작)
    indicators = {
        "rsi": 25.0,  # 과매도 상태
        "bb_lower_hit": True,
        "ma_200": 100000.0,
        "close": 90000.0, # MA200 아래
        "market_context": [
            {"close": 100, "volume": 1000, "timestamp": datetime.now()} for _ in range(10)
        ]
    }
    
    async with get_db_session() as session:
        # 강제 매수 시도
        print("[*] Triggering Buy Signal...")
        
        # 잔고 확보 (Paper Trading용 업데이트가 필요할 수 있음)
        # 여기서는 생략하고 바로 execute_order 호출
        
        price = Decimal("90000")
        quantity = Decimal("0.1")
        
        success = await executor.execute_order(
            session, symbol, "BUY", price, quantity, 
            "DebugStrategy", indicators
        )
        
        if success:
            print("[+] Trade Executed (AI Approved)")
        else:
            print("[-] Trade Rejected (AI Denied or Error)")

if __name__ == "__main__":
    asyncio.run(force_simulate())
