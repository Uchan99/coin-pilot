
import asyncio
import httpx
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any, Optional
import time

from src.common.db import get_db_session
from src.common.models import MarketData

# Upbit API 엔드포인트
UPBIT_API_MINUTE = "https://api.upbit.com/v1/candles/minutes/1"
UPBIT_API_DAY = "https://api.upbit.com/v1/candles/days"

class HistoricalDataBackfiller:
    """
    Upbit API에서 과거 데이터를 가져와 DB에 채워넣는 클래스
    """
    def __init__(self, symbol: str = "KRW-BTC"):
        self.symbol = symbol

    async def fetch_candles(self, url: str, count: int, to: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        특정 시점 이전의 캔들 데이터를 가져옵니다.
        
        Args:
            url: API 엔드포인트 URL
            count: 가져올 캔들 개수 (최대 200)
            to: 해당 시점 이전 데이터 조회 (ISO 8601 형식)
        """
        params = {
            "market": self.symbol,
            "count": count
        }
        if to:
            params["to"] = to
            
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            # Rate Limit 방지: 초당 10회 제한 (0.15초 대기 시 안정적)
            await asyncio.sleep(0.15)
            
            if response.status_code != 200:
                print(f"[!] Error fetching candles: {response.status_code} - {response.text}")
                return []
                
            return response.json()

    async def save_candles(self, candles: List[Dict[str, Any]], interval: str):
        """
        가져온 캔들 데이터를 DB에 저장합니다.
        """
        async with get_db_session() as session:
            saved_count = 0
            for candle in candles:
                # Upbit 응답 형식이 일봉과 분봉이 약간 다름 (candle_date_time_utc는 공통)
                timestamp = datetime.fromisoformat(candle["candle_date_time_utc"]).replace(tzinfo=timezone.utc)
                
                # 중복 데이터 확인 (이미 존재하는 timestamp/interval/symbol 조합은 건너뜀)
                stmt = select(exists().where(
                    (MarketData.symbol == self.symbol) &
                    (MarketData.interval == interval) &
                    (MarketData.timestamp == timestamp)
                ))
                already_exists = await session.scalar(stmt)
                
                if not already_exists:
                    market_data = MarketData(
                        symbol=self.symbol,
                        interval=interval,
                        timestamp=timestamp,
                        open_price=Decimal(str(candle["opening_price"])),
                        high_price=Decimal(str(candle["high_price"])),
                        low_price=Decimal(str(candle["low_price"])),
                        close_price=Decimal(str(candle["trade_price"])),
                        volume=Decimal(str(candle["candle_acc_trade_volume"]))
                    )
                    session.add(market_data)
                    saved_count += 1
            await session.commit()
            print(f"  [+] Prepared {saved_count} {interval} candles for database.")

    async def backfill_days(self, days: int = 200):
        """
        과거 일봉 데이터를 백필합니다.
        """
        print(f"[*] Starting backfill for {self.symbol} (Days: {days})...")
        # 일봉은 한 번에 최대 200개까지 가능하므로 루프 불필요할 수 있으나 확장성 고려
        candles = await self.fetch_candles(UPBIT_API_DAY, count=days)
        if candles:
            await self.save_candles(candles, interval="1d")
            print(f"[OK] Backfilled {len(candles)} daily candles.")

    async def backfill_minutes(self, total_minutes: int = 200 * 1440):
        """
        과거 분봉 데이터를 백필합니다. (200일 = 288,000분)
        """
        print(f"[*] Starting backfill for {self.symbol} (Minutes: {total_minutes})...")
        
        batch_size = 200
        remaining = total_minutes
        last_to = None
        total_saved = 0
        
        while remaining > 0:
            count = min(remaining, batch_size)
            candles = await self.fetch_candles(UPBIT_API_MINUTE, count=count, to=last_to)
            
            if not candles:
                break
                
            await self.save_candles(candles, interval="1m")
            total_saved += len(candles)
            remaining -= len(candles)
            
            # 다음 요청을 위한 시점 설정 (가장 오래된 캔들의 시간)
            last_timestamp = candles[-1]["candle_date_time_utc"]
            last_to = last_timestamp.replace("T", " ") # Upbit 'to' 파라미터 형식 대응
            
            print(f"  [-] Total minutes saved: {total_saved} / {total_minutes}")
            
            # 너무 방대한 양을 한꺼번에 할 경우 DB 부하 및 시간 소요가 크므로 
            # 200일치 분봉은 테스트 단계에서는 수천 개 수준으로 조정 가능
            if total_saved >= 1000: # 테스트용 제한 (필요 시 조절)
                print("[!] Threshold reached for minutes backfill (Test mode: 1000 candles).")
                break

        print(f"[OK] Backfilled total {total_saved} minute candles.")

async def main():
    backfiller = HistoricalDataBackfiller(symbol="KRW-BTC")
    
    # 1. 일봉 백필 (MA 200일용)
    await backfiller.backfill_days(days=200)
    
    # 2. 분봉 백필 (최근 전략 테스트용)
    # 실제 200일치는 너무 오래 걸리므로 최근 2000분(약 1.4일) 정도만 시범 백필
    await backfiller.backfill_minutes(total_minutes=2000)

if __name__ == "__main__":
    asyncio.run(main())
