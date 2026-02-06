"""
변경 전후 시그널 발생 횟수 비교 (v2.5 듀얼 RSI 전략)
파일: scripts/backtest_signal_count.py
실행: PYTHONPATH=. python scripts/backtest_signal_count.py

v2.5 전략:
- RSI(14) < 40: 중기 과매도 확인
- RSI(7) 30 상향 돌파: 반등 모멘텀 확인
- Price >= MA(20) × 0.97: MA 근처 진입 허용
- Volume > 1.2x: 거래량 동반
"""
import asyncio
import pandas as pd
from sqlalchemy import select, desc
from src.config.strategy import StrategyConfig, CONSERVATIVE_CONFIG, get_config
from src.common.db import get_db_session
from src.common.models import MarketData
from src.common.indicators import calculate_rsi, calculate_ma, calculate_bb

def add_indicators_to_df(df: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    """DataFrame에 지표 컬럼 추가 (전체 행에 대해)"""
    df = df.copy()

    # RSI(14) 중기
    df['rsi'] = calculate_rsi(df['close'], period=config.RSI_PERIOD)

    # RSI(7) 단기 + 이전값
    rsi_short_period = getattr(config, 'RSI_SHORT_PERIOD', 7)
    df['rsi_short'] = calculate_rsi(df['close'], period=rsi_short_period)
    df['rsi_short_prev'] = df['rsi_short'].shift(1)

    # MA
    df['ma_trend'] = calculate_ma(df['close'], period=config.MA_TREND_PERIOD)

    # Bollinger Bands
    bb = calculate_bb(df['close'], period=20, std_dev=2.0)
    df['bb_lower'] = bb['BBL']

    # Volume Ratio
    vol_ma_20 = df['volume'].rolling(window=20).mean()
    df['vol_ratio'] = df['volume'] / vol_ma_20

    return df

def count_signals_old(df: pd.DataFrame, config: StrategyConfig) -> int:
    """기존 단일 RSI 전략 시그널 카운트 (v2.4)"""
    signals = 0
    for _, row in df.dropna().iterrows():
        conditions = [
            row['rsi'] < config.RSI_OVERSOLD,
            row['close'] > row['ma_trend'],
            row['vol_ratio'] > config.VOLUME_MULTIPLIER,
        ]
        if config.USE_BB_CONDITION:
            conditions.append(row['close'] <= row['bb_lower'])

        if all(conditions):
            signals += 1
    return signals

def count_signals_new(df: pd.DataFrame, config: StrategyConfig) -> tuple:
    """v2.5 듀얼 RSI 전략 시그널 카운트"""
    signals = 0
    signal_details = []

    ma_tolerance = getattr(config, 'MA_TOLERANCE', 0.97)
    rsi_crossover = getattr(config, 'RSI_SHORT_CROSSOVER', 30)

    for idx, row in df.dropna().iterrows():
        # 조건 1: RSI(14) < 40
        cond_rsi14 = row['rsi'] < config.RSI_OVERSOLD

        # 조건 2: RSI(7) 30 상향 돌파
        cond_rsi7_crossover = (row['rsi_short_prev'] < rsi_crossover) and (row['rsi_short'] >= rsi_crossover)

        # 조건 3: Price >= MA(20) * 0.97
        ma_threshold = row['ma_trend'] * ma_tolerance
        cond_ma = row['close'] >= ma_threshold

        # 조건 4: Volume > 1.2x
        cond_vol = row['vol_ratio'] > config.VOLUME_MULTIPLIER

        # BB 조건 (선택적)
        if config.USE_BB_CONDITION:
            cond_bb = row['close'] <= row['bb_lower']
            all_conditions = cond_rsi14 and cond_rsi7_crossover and cond_ma and cond_vol and cond_bb
        else:
            all_conditions = cond_rsi14 and cond_rsi7_crossover and cond_ma and cond_vol

        if all_conditions:
            signals += 1
            signal_details.append({
                'timestamp': row.get('timestamp', idx),
                'rsi14': row['rsi'],
                'rsi7': row['rsi_short'],
                'rsi7_prev': row['rsi_short_prev'],
                'close': row['close'],
                'ma_trend': row['ma_trend'],
                'vol_ratio': row['vol_ratio']
            })

    return signals, signal_details

async def load_market_data(symbol: str, config: StrategyConfig, limit: int = 90*24*60) -> pd.DataFrame:
    """DB에서 시장 데이터 로드 (limit: 분 단위, 기본 3개월)"""
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
        return add_indicators_to_df(df, config)

async def main():
    # 기존 조건 (v2.4 단순 RSI)
    old_config = StrategyConfig(
        RSI_OVERSOLD=40,
        MA_TREND_PERIOD=20,
        VOLUME_MULTIPLIER=1.2,
        USE_BB_CONDITION=False
    )

    # 새 조건 (v2.5 듀얼 RSI)
    new_config = get_config()

    print("=" * 60)
    print("시그널 발생 비교: v2.4 vs v2.5 듀얼 RSI 전략")
    print("=" * 60)
    print()
    print("v2.4 조건 (단순 RSI):")
    print(f"  - RSI(14) < {old_config.RSI_OVERSOLD}")
    print(f"  - Price > MA({old_config.MA_TREND_PERIOD})")
    print(f"  - Volume > {old_config.VOLUME_MULTIPLIER}x")
    print()
    print("v2.5 조건 (듀얼 RSI):")
    print(f"  - RSI(14) < {new_config.RSI_OVERSOLD}")
    print(f"  - RSI(7) {getattr(new_config, 'RSI_SHORT_CROSSOVER', 30)} 상향 돌파")
    print(f"  - Price >= MA({new_config.MA_TREND_PERIOD}) × {getattr(new_config, 'MA_TOLERANCE', 0.97)}")
    print(f"  - Volume > {new_config.VOLUME_MULTIPLIER}x")
    print()
    print("-" * 60)

    total_old, total_new = 0, 0
    all_signal_details = []

    for symbol in new_config.SYMBOLS:
        df = await load_market_data(symbol, new_config)
        if df.empty:
            print(f"{symbol}: 데이터 없음")
            continue

        data_days = len(df) / (24 * 60)  # 분 데이터 → 일 환산

        old_signals = count_signals_old(df, old_config)
        new_signals, details = count_signals_new(df, new_config)

        total_old += old_signals
        total_new += new_signals
        all_signal_details.extend([(symbol, d) for d in details])

        print(f"{symbol} ({data_days:.1f}일치 데이터):")
        print(f"  v2.4 시그널: {old_signals}건")
        print(f"  v2.5 시그널: {new_signals}건")
        if old_signals > 0:
            change = ((new_signals - old_signals) / old_signals) * 100
            print(f"  변화: {change:+.1f}%")
        print()

    print("-" * 60)
    print(f"총계: v2.4 {total_old}건 → v2.5 {total_new}건")
    if total_old > 0:
        print(f"변화율: {((total_new - total_old) / total_old) * 100:+.1f}%")

    # 최근 시그널 상세 출력 (최대 5건)
    if all_signal_details:
        print()
        print("-" * 60)
        print("v2.5 시그널 상세 (최근 5건):")
        for symbol, detail in all_signal_details[-5:]:
            print(f"  [{symbol}] {detail['timestamp']}")
            print(f"    RSI14: {detail['rsi14']:.1f}, RSI7: {detail['rsi7_prev']:.1f}→{detail['rsi7']:.1f}")
            print(f"    Price: {detail['close']:,.0f}, MA×0.97: {detail['ma_trend']*0.97:,.0f}")
            print(f"    Vol: {detail['vol_ratio']:.2f}x")

if __name__ == "__main__":
    asyncio.run(main())
