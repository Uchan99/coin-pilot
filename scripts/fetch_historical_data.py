import asyncio
import sys
import httpx
from src.collector.main import UpbitCollector
from src.common.db import get_db_session
from src.common.models import MarketData
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.dialects.postgresql import insert

async def fetch_history():
    """
    대시보드 차트용 과거 데이터 수집 (1분봉 200개 + 일봉 200개)
    """
    symbol = "KRW-BTC"
    
    # 1. 1분봉 데이터 수집 (기존 로직)
    print("[*] Starting Historical Data Fetch (1m: 200, 1d: 200)...")
    collector = UpbitCollector(symbol=symbol)
    
    try:
        # [1m Data] Upbit API 최대 200개
        print("[*] Fetching 1m candles...")
        candles_1m = await collector.fetch_candles(count=200)
        await save_to_db(candles_1m, "1m")
        
        # [1d Data] Daily API 호출 (MA200 계산용)
        print("[*] Fetching 1d candles...")
        async with httpx.AsyncClient() as client:
            url = "https://api.upbit.com/v1/candles/days"
            resp = await client.get(url, params={"market": symbol, "count": 200})
            resp.raise_for_status()
            candles_1d = resp.json()
            
        await save_to_db(candles_1d, "1d")
        
        print("[+] Successfully saved all historical data.")
            
    except Exception as e:
        print(f"[!] Error: {e}")

async def save_to_db(candles, interval):
    if not candles:
        print(f"[-] No data received for {interval}")
        return

    async with get_db_session() as session:
        print(f"[*] Saving {len(candles)} {interval} candles to DB...")
        count = 0
        for candle in candles:
            try:
                # Upbit keys are same for 1m and 1d usually
                data_dict = {
                    "symbol": candle["market"],
                    "interval": interval,
                    "open_price": Decimal(str(candle["opening_price"])),
                    "high_price": Decimal(str(candle["high_price"])),
                    "low_price": Decimal(str(candle["low_price"])),
                    "close_price": Decimal(str(candle["trade_price"])),
                    "volume": Decimal(str(candle["candle_acc_trade_volume"])),
                    "timestamp": datetime.fromisoformat(candle["candle_date_time_utc"]).replace(tzinfo=timezone.utc)
                }
                
                stmt = insert(MarketData).values(**data_dict)
                stmt = stmt.on_conflict_do_nothing(
                    constraint='uq_market_data_symbol_interval_ts'
                )
                await session.execute(stmt)
                count += 1
            except Exception as e:
                print(f"Skipping error: {e}")
        
        await session.commit()
        print(f"[+] Saved {count} records.")

if __name__ == "__main__":
    asyncio.run(fetch_history())
