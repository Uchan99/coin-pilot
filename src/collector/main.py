import asyncio
import httpx
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy import select, desc

from src.common.db import get_db_session
from src.common.models import MarketData

UPBIT_API_URL = "https://api.upbit.com/v1/candles/minutes/1"

class UpbitCollector:
    """
    Upbit API를 통해 시장 데이터를 수집하고 DB에 저장하는 클래스
    """
    def __init__(self, symbol: str = "KRW-BTC"):
        self.symbol = symbol

    async def get_last_candle_time(self) -> Optional[datetime]:
        """
        DB에 저장된 가장 최근 캔들의 시간을 조회합니다.
        """
        async with get_db_session() as session:
            stmt = select(MarketData.timestamp).where(
                MarketData.symbol == self.symbol
            ).order_by(desc(MarketData.timestamp)).limit(1)
            
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def backfill(self):
        """
        마지막 수집 시점부터 현재까지의 누락된 데이터를 채웁니다.
        (페이지네이션 및 중복 방지 포함)
        """
        print(f"[*] Checking for missing data for {self.symbol}...")
        last_time = await self.get_last_candle_time()
        
        if not last_time:
            print("[!] No previous data found. Fetching initial 200 candles.")
            candles = await self.fetch_candles(count=200)
            await self.save_candles(candles)
            return

        # 공백 계산 (분 단위)
        # MarketData timestamp is usually UTC (naive or aware depending on DB driver settings)
        # Upbit API is UTC.
        now = datetime.now(timezone.utc)
        
        # last_time이 naive라면 aware로 변환 (DB 설정에 따라 다름)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
            
        delta = now - last_time
        missing_minutes = int(delta.total_seconds() / 60)
        
        if missing_minutes <= 1:
            print("[*] Data is up to date.")
            return

        print(f"[*] Found gap of {missing_minutes} minutes. Starting backfill...")
        
        # Pagination Logic (fetch in chunks of 200)
        remaining_count = missing_minutes
        total_backfilled = 0
        
        # 최신 데이터부터 과거로 가는 API가 아니라, 
        # Upbit API는 `to` 파라미터가 없으면 가장 최신 n개를 줌.
        # `to` 파라미터를 쓰면 특정 시점 이전의 데이터를 줌.
        # Backfill은 "과거의 빈 부분"을 채워야 하는데,
        # Upbit API 구조상 'to' 없이 요청하면 가장 최신 데이터(이미 있을 수 있음)부터 받아옴.
        # 따라서, 200개 이상 비어있다면, 
        # 1. 가장 최신 200개 (Current -> Current-200m) : save_candles가 중복 무시
        # 2. 그 다음 200개 (Current-200m -> Current-400m) : ...
        # 형태로 'to'를 써서 뒤로 가면서 채워야 함?
        # 아니면 Start(Last Time) -> End(Now) 순방향으로 채워야 하나?
        # Upbit API는 역방향(최신 -> 과거) 제공. `to` 파라미터가 "언제까지(마지막)" 기준.
        #
        # 전략: 
        # missing_minutes가 1000분이다 (약 16시간).
        # Loop 1: to=Now, count=200 -> 가져와서 저장 (Now ~ Now-200)
        # Loop 2: to=(Now-200m), count=200 -> 저장 (Now-200 ~ Now-400)
        # ... 반복
        
        cursor_time = now
        
        while remaining_count > 0:
            fetch_count = min(remaining_count, 200)
            
            # API Call
            candles = await self.fetch_candles(count=fetch_count, to=cursor_time.isoformat())
            
            if not candles:
                break
                
            await self.save_candles(candles)
            n = len(candles)
            total_backfilled += n
            
            # Update Cursor (가장 오래된 캔들의 시간)
            # Upbit returns sorted DESC (latest first) usually? 
            # API response: [latest, ..., oldest]
            last_candle_in_batch = candles[-1] # Oldest in this batch
            last_ts_str = last_candle_in_batch["candle_date_time_utc"]
            # ISOFormat str -> datetime
            cursor_time = datetime.fromisoformat(last_ts_str).replace(tzinfo=timezone.utc)
            
            remaining_count -= n
            print(f"[*] Fetched {n} candles. Remaining gap approx: {remaining_count} mins")
            
            # API Rate Limit Safety
            await asyncio.sleep(0.1)
            
            # 무한루프 방지 (더 이상 과거 데이터가 없거나 겹칠 때)
            if n < fetch_count: 
                break
                
        print(f"[+] Backfill completed. Total processed: {total_backfilled} candles.")

    async def fetch_candles(self, count: int = 1, to: str = None) -> List[Dict[str, Any]]:
        """
        Upbit API로부터 캔들 데이터를 가져옵니다.
        """
        params = {
            "market": self.symbol,
            "count": count
        }
        if to:
            params["to"] = to
            
        async with httpx.AsyncClient() as client:
            response = await client.get(UPBIT_API_URL, params=params)
            response.raise_for_status()
            return response.json()

    async def save_candles(self, candles: List[Dict[str, Any]]):
        """
        수집된 캔들 데이터를 데이터베이스에 저장합니다. (중복 무시)
        """
        from sqlalchemy.dialects.postgresql import insert
        
        async with get_db_session() as session:
            for candle in candles:
                # Upbit 응답 데이터를 MarketData 모델 딕셔너리로 변환
                data_dict = {
                    "symbol": candle["market"],
                    "interval": "1m",
                    "open_price": Decimal(str(candle["opening_price"])),
                    "high_price": Decimal(str(candle["high_price"])),
                    "low_price": Decimal(str(candle["low_price"])),
                    "close_price": Decimal(str(candle["trade_price"])),
                    "volume": Decimal(str(candle["candle_acc_trade_volume"])),
                    "timestamp": datetime.fromisoformat(candle["candle_date_time_utc"]).replace(tzinfo=timezone.utc)
                }
                
                # Bulk Insert with ON CONFLICT DO NOTHING
                # 개별 insert가 아닌 bulk로 하는게 좋지만, 여기선 loop 구조 유지하되 stmt 변경
                stmt = insert(MarketData).values(**data_dict)
                stmt = stmt.on_conflict_do_nothing(
                    constraint='uq_market_data_symbol_interval_ts'
                )
                await session.execute(stmt)
                
            # 세션은 get_db_session 컨텍스트 매니저에 의해 자동 커밋됨

from src.config.strategy import get_config

async def main():
    """
    수집기 실행 메인 루프 - 멀티 심볼 지원
    
    기존 단일 심볼 수집에서 설정 파일(src.config.strategy)에 정의된 
    모든 심볼을 순차적으로 수집하도록 변경함.
    """
    # 롤백 모드 자동 반영을 위해 get_config() 사용
    config = get_config()
    print(f"[*] Starting Upbit Collector for {len(config.SYMBOLS)} symbols...")
    print(f"[*] Target Symbols: {config.SYMBOLS}")

    # 각 심볼별 수집기 인스턴스 생성
    collectors = [UpbitCollector(symbol=symbol) for symbol in config.SYMBOLS]
    
    # 1. 초기화: 모든 심볼에 대해 데이터 공백(Backfill) 채우기
    # 서버 재시작 시 누락된 데이터를 보정하기 위함
    for collector in collectors:
        print(f"[*] Backfilling {collector.symbol}...")
        try:
            await collector.backfill()
        except Exception as e:
            print(f"[!] Backfill failed for {collector.symbol}: {e}")
        # API Rate Limit 보호 (Upbit 초당 10회 제한)
        await asyncio.sleep(0.2)
    
    print("[*] Backfill completed. Entering main loop...")

    # 2. 메인 루프: 1분 간격으로 최신 데이터 수집
    while True:
        loop_start = datetime.now()
        
        try:
            for collector in collectors:
                # print(f"[*] Fetching {collector.symbol} at {datetime.now()}...")
                
                # 최신 캔들 1개 조회
                candles = await collector.fetch_candles(count=1)
                await collector.save_candles(candles)
                
                # print(f"[+] {collector.symbol}: Saved {len(candles)} candle(s).")

                # API 호출 간격 제어 (Rate Limit 준수)
                await asyncio.sleep(0.2)

        except Exception as e:
            print(f"[!] Critical Error in Collector Loop: {e}")
        
        # 다음 1분 봉 생성까지 대기
        # 수집 시간(약 1~2초)을 고려하여 55초 대기
        await asyncio.sleep(55)

if __name__ == "__main__":
    asyncio.run(main())
