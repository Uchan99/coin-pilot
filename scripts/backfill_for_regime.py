"""
레짐 판단을 위한 과거 1분봉 데이터 수집
파일: scripts/backfill_for_regime.py
실행: PYTHONPATH=. python scripts/backfill_for_regime.py

MA200(1시간봉) 계산을 위해 최소 200시간 = 12,000개 1분봉 필요
"""
import asyncio
import httpx
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.dialects.postgresql import insert
from src.common.db import get_db_session
from src.common.models import MarketData

# 대상 심볼 목록 (get_config() 대신 직접 정의 - 설정 로딩 오류 방지)
DEFAULT_SYMBOLS = ["KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-DOGE"]

# 업비트 API는 한 번에 200개까지만 반환
BATCH_SIZE = 200
# 200시간 = 12,000분 (레짐 판단에 필요한 최소량)
TARGET_MINUTES = 12000


async def fetch_candles_batch(client: httpx.AsyncClient, symbol: str, to: datetime = None) -> list:
    """업비트에서 1분봉 200개 가져오기"""
    url = "https://api.upbit.com/v1/candles/minutes/1"
    params = {"market": symbol, "count": BATCH_SIZE}
    if to:
        params["to"] = to.strftime("%Y-%m-%dT%H:%M:%S")

    resp = await client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


async def save_candles(candles: list) -> int:
    """DB에 캔들 저장"""
    if not candles:
        return 0

    async with get_db_session() as session:
        count = 0
        for candle in candles:
            try:
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

                stmt = insert(MarketData).values(**data_dict)
                stmt = stmt.on_conflict_do_nothing(
                    constraint='uq_market_data_symbol_interval_ts'
                )
                await session.execute(stmt)
                count += 1
            except Exception as e:
                pass  # 중복 무시

        await session.commit()
        return count


async def backfill_symbol(symbol: str):
    """특정 심볼의 과거 데이터 수집"""
    print(f"\n[{symbol}] 과거 데이터 수집 시작...")

    total_saved = 0
    to_time = None

    async with httpx.AsyncClient(timeout=30) as client:
        # 60번 반복 = 200 * 60 = 12,000개
        iterations = TARGET_MINUTES // BATCH_SIZE

        for i in range(iterations):
            try:
                candles = await fetch_candles_batch(client, symbol, to_time)

                if not candles:
                    print(f"  [{i+1}/{iterations}] 더 이상 데이터 없음")
                    break

                saved = await save_candles(candles)
                total_saved += saved

                # 가장 오래된 캔들의 시간을 다음 요청의 to로 사용
                oldest = candles[-1]
                to_time = datetime.fromisoformat(oldest["candle_date_time_utc"])

                if (i + 1) % 10 == 0:
                    print(f"  [{i+1}/{iterations}] {total_saved}개 저장됨 (oldest: {to_time})")

                # API Rate Limit 방지 (초당 10회 제한)
                await asyncio.sleep(0.15)

            except httpx.HTTPStatusError as e:
                print(f"  API 에러: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"  에러: {e}")
                await asyncio.sleep(0.5)

    print(f"[{symbol}] 완료: {total_saved}개 저장됨")
    return total_saved


async def main():
    symbols = DEFAULT_SYMBOLS

    print("=" * 60)
    print("레짐 판단용 과거 데이터 수집")
    print("=" * 60)
    print(f"대상 코인: {symbols}")
    print(f"목표: {TARGET_MINUTES}개 1분봉 (= {TARGET_MINUTES/60:.0f}시간 = {TARGET_MINUTES/60/24:.1f}일)")
    print()

    total = 0
    for symbol in symbols:
        saved = await backfill_symbol(symbol)
        total += saved

    print()
    print("=" * 60)
    print(f"전체 완료: {total}개 저장됨")
    print("=" * 60)
    print()
    print("이제 봇을 재시작하면 레짐 판단이 가능합니다:")
    print("  kubectl rollout restart deployment/bot -n coin-pilot-ns")


if __name__ == "__main__":
    asyncio.run(main())
