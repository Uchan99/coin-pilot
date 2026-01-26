import asyncio
import sys
from src.collector.main import UpbitCollector

async def fetch_history():
    """
    대시보드 차트용 과거 데이터 200개 수집
    """
    print("[*] Starting Historical Data Fetch (200 candles)...")
    collector = UpbitCollector(symbol="KRW-BTC")
    
    try:
        # Upbit API는 최대 200개까지 요청 가능
        candles = await collector.fetch_candles(count=200)
        
        if candles:
            # DB 저장
            # save_candles 함수가 내부적으로 session을 열고 닫으므로 바로 호출 가능
            # 단, main.py의 save_candles가 bulk insert가 아니라 loop insert라 조금 느릴 수 있음
            from src.common.db import get_db_session
            from src.common.models import MarketData
            from datetime import datetime
            from decimal import Decimal

            async with get_db_session() as session:
                print(f"[*] Saving {len(candles)} candles to DB...")
                for candle in candles:
                    # 중복 방지 로직이 없으므로 try-except로 감싸거나, 간단히 구현
                    # 여기서는 데모용이므로 그냥 입력 시도 (PK 충돌 시 에러날 수 있음)
                    try:
                        md = MarketData(
                            symbol=candle["market"],
                            interval="1m",
                            open_price=Decimal(str(candle["opening_price"])),
                            high_price=Decimal(str(candle["high_price"])),
                            low_price=Decimal(str(candle["low_price"])),
                            close_price=Decimal(str(candle["trade_price"])),
                            volume=Decimal(str(candle["candle_acc_trade_volume"])),
                            timestamp=datetime.fromisoformat(candle["candle_date_time_utc"])
                        )
                        session.add(md)
                    except Exception as e:
                        print(f"Skipping error: {e}")
                
                await session.commit()
            print("[+] Successfully saved historical data.")
        else:
            print("[-] No data received from Upbit.")
            
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    asyncio.run(fetch_history())
