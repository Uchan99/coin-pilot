"""
변경 전후 시그널 발생 횟수 비교
파일: scripts/backtest_signal_count.py
실행: PYTHONPATH=. python scripts/backtest_signal_count.py

참고: get_all_indicators()는 마지막 행의 Dict만 반환하므로,
      시그널 카운팅을 위해 지표를 직접 계산합니다.
"""
import asyncio
import pandas as pd
from sqlalchemy import select, desc
from src.config.strategy import StrategyConfig, CONSERVATIVE_CONFIG, get_config
from src.common.db import get_db_session
from src.common.models import MarketData
from src.common.indicators import calculate_rsi, calculate_ma, calculate_bb

def add_indicators_to_df(df: pd.DataFrame, ma_period: int = 50) -> pd.DataFrame:
    """DataFrame에 지표 컬럼 추가 (전체 행에 대해)"""
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'], period=14)
    df['ma_trend'] = calculate_ma(df['close'], period=ma_period)  # config 기반 MA 기간
    bb = calculate_bb(df['close'], period=20, std_dev=2.0)
    df['bb_lower'] = bb['BBL']

    # vol_ratio는 rolling 계산 (indicators.py의 함수는 단일 시점용이라 여기서 직접 계산)
    vol_ma_20 = df['volume'].rolling(window=20).mean()
    df['vol_ratio'] = df['volume'] / vol_ma_20

    return df

def count_signals(df: pd.DataFrame, config: StrategyConfig) -> int:
    """시그널 발생 횟수 계산"""
    signals = 0
    for _, row in df.dropna().iterrows():
        conditions = [
            row['rsi'] < config.RSI_OVERSOLD,
            row['close'] > row['ma_trend'],  # ma_200 -> ma_trend
            row['vol_ratio'] > config.VOLUME_MULTIPLIER,
        ]
        if config.USE_BB_CONDITION:
            conditions.append(row['close'] <= row['bb_lower'])

        if all(conditions):
            signals += 1
    return signals

async def load_market_data(symbol: str, ma_period: int = 50, limit: int = 90*24*60) -> pd.DataFrame:
    """DB에서 시장 데이터 로드 (limit: 분 단위)"""
    async with get_db_session() as session:
        stmt = select(MarketData).where(
            MarketData.symbol == symbol
        ).order_by(desc(MarketData.timestamp)).limit(limit)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        if not rows:
            return pd.DataFrame()

        data = [{
            "timestamp": r.timestamp,
            "open": float(r.open_price),
            "high": float(r.high_price),
            "low": float(r.low_price),
            "close": float(r.close_price),
            "volume": float(r.volume)
        } for r in reversed(rows)]

        df = pd.DataFrame(data)
        return add_indicators_to_df(df, ma_period=ma_period)

async def main():
    old_config = CONSERVATIVE_CONFIG
    new_config = get_config()

    print("=== 시그널 발생 비교 (최근 3개월) ===\n")
    print(f"기존 조건: RSI<{old_config.RSI_OVERSOLD}, MA{old_config.MA_TREND_PERIOD}, Vol>{old_config.VOLUME_MULTIPLIER}x, BB={old_config.USE_BB_CONDITION}")
    print(f"변경 조건: RSI<{new_config.RSI_OVERSOLD}, MA{new_config.MA_TREND_PERIOD}, Vol>{new_config.VOLUME_MULTIPLIER}x, BB={new_config.USE_BB_CONDITION}\n")

    total_old, total_new = 0, 0
    for symbol in new_config.SYMBOLS:
        # 새 조건용 데이터 로드 (MA50)
        df_new = await load_market_data(symbol, ma_period=new_config.MA_TREND_PERIOD)
        if df_new.empty:
            print(f"{symbol}: 데이터 없음")
            continue

        if symbol == "KRW-BTC":
            # 기존 조건용 데이터 로드 (MA200)
            df_old = await load_market_data(symbol, ma_period=old_config.MA_TREND_PERIOD)
            old_signals = count_signals(df_old, old_config)
            total_old += old_signals
            print(f"{symbol} (기존 MA{old_config.MA_TREND_PERIOD}): {old_signals}건")

        new_signals = count_signals(df_new, new_config)
        total_new += new_signals
        print(f"{symbol} (변경 MA{new_config.MA_TREND_PERIOD}): {new_signals}건")

    print(f"\n총계: {total_old}건 → {total_new}건")
    if total_old > 0:
        print(f"증가율: {total_new / total_old:.1f}배")
    else:
        print(f"증가율: ∞배 (기존 0건)")

if __name__ == "__main__":
    asyncio.run(main())
