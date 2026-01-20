import asyncio
import httpx
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any

from src.common.db import get_db_session
from src.common.models import MarketData

UPBIT_API_URL = "https://api.upbit.com/v1/candles/minutes/1"

class UpbitCollector:
    """
    Upbit API를 통해 시장 데이터를 수집하고 DB에 저장하는 클래스
    """
    def __init__(self, symbol: str = "KRW-BTC"):
        self.symbol = symbol

    async def fetch_candles(self, count: int = 1) -> List[Dict[str, Any]]:
        """
        Upbit API로부터 캔들 데이터를 가져옵니다.
        """
        params = {
            "market": self.symbol,
            "count": count
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(UPBIT_API_URL, params=params)
            response.raise_for_status()
            return response.json()

    async def save_candles(self, candles: List[Dict[str, Any]]):
        """
        수집된 캔들 데이터를 데이터베이스에 저장합니다.
        """
        async with get_db_session() as session:
            for candle in candles:
                # Upbit 응답 데이터를 MarketData 모델로 변환
                market_data = MarketData(
                    symbol=candle["market"],
                    interval="1m",
                    open_price=Decimal(str(candle["opening_price"])),
                    high_price=Decimal(str(candle["high_price"])),
                    low_price=Decimal(str(candle["low_price"])),
                    close_price=Decimal(str(candle["trade_price"])),
                    volume=Decimal(str(candle["candle_acc_trade_volume"])),
                    # Upbit timestamp 형식: 2023-01-01T00:00:00
                    timestamp=datetime.fromisoformat(candle["candle_date_time_utc"])
                )
                session.add(market_data)
            # 세션은 get_db_session 컨텍스트 매니저에 의해 자동 커밋됨

async def main():
    """
    수집기 실행 메인 루프
    """
    collector = UpbitCollector(symbol="KRW-BTC")
    print(f"[*] Starting Upbit Collector for {collector.symbol}...")
    
    while True:
        try:
            print(f"[*] Fetching data at {datetime.now()}...")
            candles = await collector.fetch_candles(count=1)
            await collector.save_candles(candles)
            print(f"[+] Saved {len(candles)} candle(s).")
        except Exception as e:
            print(f"[!] Error occurred: {e}")
        
        # 1분 간격 수집 (간단한 구현)
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
