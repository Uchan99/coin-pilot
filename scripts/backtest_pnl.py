"""
v2.5 듀얼 RSI 전략 수익률 백테스트
파일: scripts/backtest_pnl.py
실행: PYTHONPATH=. python scripts/backtest_pnl.py

시뮬레이션 내용:
- 진입: v2.5 듀얼 RSI 조건 충족 시 매수
- 청산: Take Profit(+5%), Stop Loss(-3%), RSI(14)>70, 48시간 초과
- 수수료: 0.05% (업비트 기준)
"""
import asyncio
import pandas as pd
from dataclasses import dataclass
from datetime import timedelta
from typing import List, Optional
from sqlalchemy import select, desc
from src.config.strategy import StrategyConfig, get_config
from src.common.db import get_db_session
from src.common.models import MarketData
from src.common.indicators import calculate_rsi, calculate_ma, calculate_bb

@dataclass
class Trade:
    """거래 기록"""
    symbol: str
    entry_time: pd.Timestamp
    entry_price: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_pct: Optional[float] = None
    pnl_net: Optional[float] = None  # 수수료 차감 후

# 상수
FEE_RATE = 0.0005  # 0.05% (업비트)
POSITION_SIZE = 100000  # 건당 10만원 가정

def add_indicators_to_df(df: pd.DataFrame, config: StrategyConfig) -> pd.DataFrame:
    """DataFrame에 지표 추가"""
    df = df.copy()

    # RSI(14), RSI(7)
    df['rsi'] = calculate_rsi(df['close'], period=config.RSI_PERIOD)
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

def check_entry_signal(row: pd.Series, config: StrategyConfig) -> bool:
    """v2.5 진입 조건 체크"""
    ma_tolerance = getattr(config, 'MA_TOLERANCE', 0.97)
    rsi_crossover = getattr(config, 'RSI_SHORT_CROSSOVER', 30)

    # 조건 1: RSI(14) < 40
    cond_rsi14 = row['rsi'] < config.RSI_OVERSOLD

    # 조건 2: RSI(7) 30 상향 돌파
    cond_rsi7 = (row['rsi_short_prev'] < rsi_crossover) and (row['rsi_short'] >= rsi_crossover)

    # 조건 3: Price >= MA × 0.97
    cond_ma = row['close'] >= (row['ma_trend'] * ma_tolerance)

    # 조건 4: Volume > 1.2x
    cond_vol = row['vol_ratio'] > config.VOLUME_MULTIPLIER

    return cond_rsi14 and cond_rsi7 and cond_ma and cond_vol

def check_exit_signal(row: pd.Series, entry_price: float, entry_time: pd.Timestamp,
                      config: StrategyConfig) -> tuple:
    """청산 조건 체크 -> (should_exit, reason)"""
    current_price = row['close']
    pnl_pct = (current_price - entry_price) / entry_price

    # 1. Take Profit (+5%)
    if pnl_pct >= config.TAKE_PROFIT:
        return True, f"TP (+{pnl_pct*100:.2f}%)"

    # 2. Stop Loss (-3%)
    if pnl_pct <= -config.STOP_LOSS:
        return True, f"SL ({pnl_pct*100:.2f}%)"

    # 3. RSI 과매수 (>70)
    if row['rsi'] > config.RSI_OVERBOUGHT:
        return True, f"RSI ({row['rsi']:.1f})"

    # 4. 시간 초과 (48시간)
    hold_time = row['timestamp'] - entry_time
    if hold_time > timedelta(hours=config.MAX_HOLD_HOURS):
        return True, f"Time ({hold_time.total_seconds()/3600:.0f}h)"

    return False, ""

def simulate_trades(df: pd.DataFrame, config: StrategyConfig, symbol: str) -> List[Trade]:
    """거래 시뮬레이션"""
    trades = []
    position = None  # 현재 포지션
    cooldown_until = None  # 쿨다운 (같은 코인 재진입 방지)

    df_clean = df.dropna().reset_index(drop=True)

    for idx, row in df_clean.iterrows():
        current_time = row['timestamp']

        # 포지션 보유 중 -> 청산 조건 확인
        if position:
            should_exit, reason = check_exit_signal(row, position.entry_price,
                                                     position.entry_time, config)
            if should_exit:
                position.exit_time = current_time
                position.exit_price = row['close']
                position.exit_reason = reason

                # 수익률 계산 (수수료 포함)
                gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
                fee_cost = FEE_RATE * 2  # 매수 + 매도
                position.pnl_pct = gross_pnl
                position.pnl_net = gross_pnl - fee_cost

                trades.append(position)
                position = None
                cooldown_until = current_time + timedelta(minutes=config.MIN_TRADE_INTERVAL_MINUTES)

        # 포지션 없음 -> 진입 조건 확인
        else:
            # 쿨다운 체크
            if cooldown_until and current_time < cooldown_until:
                continue

            if check_entry_signal(row, config):
                position = Trade(
                    symbol=symbol,
                    entry_time=current_time,
                    entry_price=row['close']
                )

    # 마지막 포지션이 청산되지 않았으면 현재가로 청산 처리
    if position and len(df_clean) > 0:
        last_row = df_clean.iloc[-1]
        position.exit_time = last_row['timestamp']
        position.exit_price = last_row['close']
        position.exit_reason = "End"
        gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
        position.pnl_pct = gross_pnl
        position.pnl_net = gross_pnl - (FEE_RATE * 2)
        trades.append(position)

    return trades

async def load_market_data(symbol: str, config: StrategyConfig, days: int = 30) -> pd.DataFrame:
    """DB에서 시장 데이터 로드"""
    limit = days * 24 * 60  # 분 단위

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

def print_trade_summary(trades: List[Trade], symbol: str):
    """거래 요약 출력"""
    if not trades:
        print(f"  거래 없음")
        return

    total_trades = len(trades)
    wins = [t for t in trades if t.pnl_net and t.pnl_net > 0]
    losses = [t for t in trades if t.pnl_net and t.pnl_net <= 0]

    win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0

    total_pnl_pct = sum(t.pnl_net for t in trades if t.pnl_net) * 100
    avg_pnl = total_pnl_pct / total_trades if total_trades > 0 else 0

    # 예상 수익금 (건당 10만원 기준)
    total_profit = sum(t.pnl_net * POSITION_SIZE for t in trades if t.pnl_net)

    print(f"  거래: {total_trades}건 (승: {len(wins)}, 패: {len(losses)})")
    print(f"  승률: {win_rate:.1f}%")
    print(f"  총 수익률: {total_pnl_pct:+.2f}% (평균 {avg_pnl:+.2f}%/건)")
    print(f"  예상 수익: {total_profit:+,.0f}원 (건당 {POSITION_SIZE/10000:.0f}만원 기준)")

    # 청산 사유 분석
    reasons = {}
    for t in trades:
        r = t.exit_reason.split()[0] if t.exit_reason else "Unknown"
        reasons[r] = reasons.get(r, 0) + 1
    print(f"  청산 사유: {reasons}")

async def main():
    config = get_config()

    print("=" * 70)
    print("v2.5 듀얼 RSI 전략 수익률 백테스트")
    print("=" * 70)
    print()
    print("전략 조건:")
    print(f"  - RSI(14) < {config.RSI_OVERSOLD}")
    print(f"  - RSI(7) {getattr(config, 'RSI_SHORT_CROSSOVER', 30)} 상향 돌파")
    print(f"  - Price >= MA({config.MA_TREND_PERIOD}) × {getattr(config, 'MA_TOLERANCE', 0.97)}")
    print(f"  - Volume > {config.VOLUME_MULTIPLIER}x")
    print()
    print("청산 조건:")
    print(f"  - Take Profit: +{config.TAKE_PROFIT*100:.0f}%")
    print(f"  - Stop Loss: -{config.STOP_LOSS*100:.0f}%")
    print(f"  - RSI 과매수: > {config.RSI_OVERBOUGHT}")
    print(f"  - 최대 보유: {config.MAX_HOLD_HOURS}시간")
    print()
    print(f"수수료: {FEE_RATE*100:.2f}% (매수+매도)")
    print(f"건당 투자금: {POSITION_SIZE/10000:.0f}만원 가정")
    print()
    print("-" * 70)

    all_trades = []

    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol, config)
        if df.empty:
            print(f"\n{symbol}: 데이터 없음")
            continue

        data_days = len(df) / (24 * 60)
        trades = simulate_trades(df, config, symbol)
        all_trades.extend(trades)

        print(f"\n{symbol} ({data_days:.1f}일치 데이터):")
        print_trade_summary(trades, symbol)

    # 전체 요약
    print()
    print("=" * 70)
    print("전체 요약")
    print("=" * 70)

    if all_trades:
        total_trades = len(all_trades)
        wins = [t for t in all_trades if t.pnl_net and t.pnl_net > 0]
        win_rate = len(wins) / total_trades * 100

        total_pnl_pct = sum(t.pnl_net for t in all_trades if t.pnl_net) * 100
        total_profit = sum(t.pnl_net * POSITION_SIZE for t in all_trades if t.pnl_net)

        print(f"총 거래: {total_trades}건")
        print(f"승률: {win_rate:.1f}%")
        print(f"누적 수익률: {total_pnl_pct:+.2f}%")
        print(f"예상 총 수익: {total_profit:+,.0f}원")

        # 최근 거래 상세
        print()
        print("-" * 70)
        print("최근 거래 상세 (최대 5건):")
        for t in all_trades[-5:]:
            print(f"  [{t.symbol}] {t.entry_time.strftime('%m/%d %H:%M')} → {t.exit_time.strftime('%m/%d %H:%M') if t.exit_time else '?'}")
            print(f"    {t.entry_price:,.0f} → {t.exit_price:,.0f} ({t.pnl_pct*100:+.2f}%) [{t.exit_reason}]")
    else:
        print("거래 없음")

if __name__ == "__main__":
    asyncio.run(main())
