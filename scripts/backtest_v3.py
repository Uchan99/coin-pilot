"""
v3.0 마켓 레짐 기반 적응형 전략 백테스트
파일: scripts/backtest_v3.py
실행: PYTHONPATH=. python scripts/backtest_v3.py

시뮬레이션 내용:
- 레짐 감지: MA50/MA200 이격도 기반 (BULL/SIDEWAYS/BEAR)
- 진입: 레짐별 RSI/MA/Volume 조건 적용
- 청산: 레짐별 TP/SL/트레일링스탑/RSI/시간제한 적용
- 수수료: 0.05% (업비트 기준)
"""
import asyncio
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Optional, Dict
from sqlalchemy import select, desc
from src.config.strategy import StrategyConfig, get_config
from src.common.db import get_db_session
from src.common.models import MarketData
from src.common.indicators import (
    calculate_rsi, calculate_ma, calculate_bb,
    resample_to_hourly, detect_regime, check_bb_touch_recovery
)

@dataclass
class Trade:
    """거래 기록"""
    symbol: str
    regime: str
    entry_time: pd.Timestamp
    entry_price: float
    position_size: float  # 레짐별 비중 적용
    high_water_mark: float = 0.0
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl_pct: Optional[float] = None
    pnl_net: Optional[float] = None

# 상수
FEE_RATE = 0.0005  # 0.05% (업비트)
BASE_POSITION_SIZE = 100000  # 기본 건당 10만원


def add_indicators_to_df(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame에 지표 추가 (1시간봉 기준)"""
    df = df.copy()

    # RSI(14), RSI(7)
    df['rsi'] = calculate_rsi(df['close'], period=14)
    df['rsi_short'] = calculate_rsi(df['close'], period=7)
    df['rsi_short_prev'] = df['rsi_short'].shift(1)

    # MA (레짐 판단용)
    df['ma20'] = calculate_ma(df['close'], period=20)
    df['ma50'] = calculate_ma(df['close'], period=50)
    df['ma200'] = calculate_ma(df['close'], period=200)

    # Bollinger Bands
    bb = calculate_bb(df['close'], period=20, std_dev=2.0)
    df['bb_lower'] = bb['BBL']

    # Volume Ratio
    vol_ma_20 = df['volume'].rolling(window=20).mean()
    df['vol_ratio'] = df['volume'] / vol_ma_20

    return df


def get_regime(row: pd.Series) -> str:
    """행에서 레짐 판단"""
    ma50 = row.get('ma50')
    ma200 = row.get('ma200')
    return detect_regime(ma50, ma200)


def check_entry_signal(row: pd.Series, regime: str, config: StrategyConfig, df: pd.DataFrame, idx: int) -> bool:
    """레짐별 진입 조건 체크"""
    if regime == "UNKNOWN":
        return False

    regime_config = config.REGIMES.get(regime)
    if not regime_config:
        return False

    entry = regime_config["entry"]

    # RSI(14) 조건
    if row['rsi'] > entry["rsi_14_max"]:
        return False

    # RSI(7) 반등 조건
    if pd.isna(row['rsi_short_prev']) or pd.isna(row['rsi_short']):
        return False
    if not (row['rsi_short_prev'] < entry["rsi_7_trigger"] and row['rsi_short'] >= entry["rsi_7_recover"]):
        return False

    # MA 조건
    if entry["ma_condition"] == "crossover":
        if row['close'] <= row['ma20']:
            return False
    elif entry["ma_condition"] == "proximity":
        prox = entry.get("ma_proximity_pct", 0.97)
        if row['close'] < row['ma20'] * prox:
            return False

    # 거래량 조건
    if entry.get("volume_ratio") is not None:
        if pd.isna(row['vol_ratio']) or row['vol_ratio'] < entry["volume_ratio"]:
            return False

    # 횡보장 BB 조건
    if regime == "SIDEWAYS" and entry.get("bb_enabled"):
        lookback = entry.get("bb_touch_lookback", 3)
        if idx < lookback + 1:
            return False
        recent_df = df.iloc[idx - lookback:idx + 1][['close', 'bb_lower']].copy()
        if not check_bb_touch_recovery(recent_df, lookback):
            return False

    return True


def check_exit_signal(row: pd.Series, trade: Trade, config: StrategyConfig) -> tuple:
    """레짐별 청산 조건 체크 (트레일링 스탑 포함)"""
    regime_config = config.REGIMES.get(trade.regime, config.REGIMES["SIDEWAYS"])
    exit_cfg = regime_config["exit"]

    current_price = row['close']
    entry_price = trade.entry_price
    pnl_pct = (current_price - entry_price) / entry_price

    # 1. Stop Loss (최우선)
    if pnl_pct <= -exit_cfg["stop_loss_pct"]:
        return True, "STOP_LOSS"

    # 2. 트레일링 스탑
    # HWM 갱신
    if current_price > trade.high_water_mark:
        trade.high_water_mark = current_price

    # 활성화 조건: 수익 1% 이상
    if pnl_pct >= exit_cfg["trailing_stop_activation_pct"]:
        stop_price = trade.high_water_mark * (1 - exit_cfg["trailing_stop_pct"])
        if current_price <= stop_price:
            return True, "TRAILING_STOP"

    # 3. Take Profit
    if pnl_pct >= exit_cfg["take_profit_pct"]:
        return True, "TAKE_PROFIT"

    # 4. RSI 과매수 (조건부)
    if row['rsi'] > exit_cfg["rsi_overbought"]:
        if pnl_pct >= exit_cfg["rsi_exit_min_profit_pct"]:
            return True, "RSI_OVERBOUGHT"

    # 5. 시간 초과
    hold_time = row['timestamp'] - trade.entry_time
    if hold_time > timedelta(hours=exit_cfg["time_limit_hours"]):
        return True, "TIME_LIMIT"

    return False, ""


def simulate_trades(df: pd.DataFrame, config: StrategyConfig, symbol: str) -> List[Trade]:
    """거래 시뮬레이션 (v3.0 레짐 기반)"""
    trades = []
    position = None
    cooldown_until = None

    df_clean = df.dropna(subset=['rsi', 'ma50', 'ma200']).reset_index(drop=True)

    for idx, row in df_clean.iterrows():
        current_time = row['timestamp']
        regime = get_regime(row)

        # 포지션 보유 중 -> 청산 체크
        if position:
            should_exit, reason = check_exit_signal(row, position, config)
            if should_exit:
                position.exit_time = current_time
                position.exit_price = row['close']
                position.exit_reason = reason

                gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
                fee_cost = FEE_RATE * 2
                position.pnl_pct = gross_pnl
                position.pnl_net = gross_pnl - fee_cost

                trades.append(position)
                position = None
                cooldown_until = current_time + timedelta(minutes=30)

        # 포지션 미보유 -> 진입 체크
        else:
            if cooldown_until and current_time < cooldown_until:
                continue

            if check_entry_signal(row, regime, config, df_clean, idx):
                # 레짐별 포지션 사이징
                size_ratio = config.REGIMES.get(regime, {}).get("position_size_ratio", 0.0)
                if size_ratio == 0:
                    continue

                position = Trade(
                    symbol=symbol,
                    regime=regime,
                    entry_time=current_time,
                    entry_price=row['close'],
                    position_size=BASE_POSITION_SIZE * size_ratio,
                    high_water_mark=row['close']
                )

    # 마지막 포지션 청산 처리
    if position and len(df_clean) > 0:
        last_row = df_clean.iloc[-1]
        position.exit_time = last_row['timestamp']
        position.exit_price = last_row['close']
        position.exit_reason = "END"
        gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
        position.pnl_pct = gross_pnl
        position.pnl_net = gross_pnl - (FEE_RATE * 2)
        trades.append(position)

    return trades


async def load_market_data(symbol: str, days: int = 90) -> pd.DataFrame:
    """DB에서 시장 데이터 로드 후 1시간봉으로 리샘플링"""
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
            "open_price": float(r.open_price),
            "high_price": float(r.high_price),
            "low_price": float(r.low_price),
            "close_price": float(r.close_price),
            "volume": float(r.volume)
        } for r in reversed(rows)]

        df_1m = pd.DataFrame(data)

        # 1시간봉 리샘플링
        df_1h = resample_to_hourly(df_1m)
        df_1h = df_1h.reset_index()
        df_1h.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

        return add_indicators_to_df(df_1h)


def print_regime_summary(trades: List[Trade]):
    """레짐별 거래 요약"""
    if not trades:
        return

    regime_stats = {}
    for t in trades:
        if t.regime not in regime_stats:
            regime_stats[t.regime] = {"trades": [], "wins": 0, "losses": 0}
        regime_stats[t.regime]["trades"].append(t)
        if t.pnl_net and t.pnl_net > 0:
            regime_stats[t.regime]["wins"] += 1
        else:
            regime_stats[t.regime]["losses"] += 1

    print("\n" + "=" * 70)
    print("레짐별 성과 분석")
    print("=" * 70)

    for regime, stats in regime_stats.items():
        total = len(stats["trades"])
        wins = stats["wins"]
        win_rate = (wins / total * 100) if total > 0 else 0
        total_pnl = sum(t.pnl_net for t in stats["trades"] if t.pnl_net) * 100
        avg_pnl = total_pnl / total if total > 0 else 0

        # 청산 사유 분석
        reasons = {}
        for t in stats["trades"]:
            r = t.exit_reason or "Unknown"
            reasons[r] = reasons.get(r, 0) + 1

        print(f"\n[{regime}]")
        print(f"  거래: {total}건 (승: {wins}, 패: {stats['losses']})")
        print(f"  승률: {win_rate:.1f}%")
        print(f"  수익률: {total_pnl:+.2f}% (평균 {avg_pnl:+.2f}%/건)")
        print(f"  청산 사유: {reasons}")


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

    # 가중 평균 수익 (포지션 사이즈 고려)
    total_profit = sum(t.pnl_net * t.position_size for t in trades if t.pnl_net)

    print(f"  거래: {total_trades}건 (승: {len(wins)}, 패: {len(losses)})")
    print(f"  승률: {win_rate:.1f}%")
    print(f"  총 수익률: {total_pnl_pct:+.2f}% (평균 {avg_pnl:+.2f}%/건)")
    print(f"  예상 수익: {total_profit:+,.0f}원 (레짐별 비중 적용)")


async def main():
    config = get_config()

    print("=" * 70)
    print("v3.0 마켓 레짐 기반 적응형 전략 백테스트")
    print("=" * 70)
    print()
    print("레짐 판단 기준:")
    print("  - BULL: MA50 > MA200 + 2%")
    print("  - SIDEWAYS: |MA50 - MA200| <= 2%")
    print("  - BEAR: MA50 < MA200 - 2%")
    print()
    print("레짐별 설정:")
    for regime, cfg in config.REGIMES.items():
        entry = cfg["entry"]
        exit_ = cfg["exit"]
        print(f"  [{regime}]")
        print(f"    진입: RSI14<{entry['rsi_14_max']}, RSI7↑{entry['rsi_7_recover']}, MA:{entry['ma_condition']}")
        print(f"    청산: TP+{exit_['take_profit_pct']*100:.0f}%, SL-{exit_['stop_loss_pct']*100:.0f}%, TS-{exit_['trailing_stop_pct']*100:.1f}%")
        print(f"    비중: {cfg.get('position_size_ratio', 1.0)*100:.0f}%")
    print()
    print(f"수수료: {FEE_RATE*100:.2f}% (매수+매도)")
    print(f"기본 투자금: {BASE_POSITION_SIZE/10000:.0f}만원/건")
    print()
    print("-" * 70)

    all_trades = []

    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol)
        if df.empty or len(df) < 200:
            print(f"\n{symbol}: 데이터 부족 ({len(df)} candles)")
            continue

        data_days = len(df) / 24  # 1시간봉 기준
        trades = simulate_trades(df, config, symbol)
        all_trades.extend(trades)

        print(f"\n{symbol} ({data_days:.1f}일치 1시간봉 데이터):")
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
        total_profit = sum(t.pnl_net * t.position_size for t in all_trades if t.pnl_net)

        print(f"총 거래: {total_trades}건")
        print(f"승률: {win_rate:.1f}%")
        print(f"누적 수익률: {total_pnl_pct:+.2f}%")
        print(f"예상 총 수익: {total_profit:+,.0f}원")

        # 레짐별 상세
        print_regime_summary(all_trades)

        # 최근 거래 상세
        print()
        print("-" * 70)
        print("최근 거래 상세 (최대 10건):")
        for t in all_trades[-10:]:
            print(f"  [{t.symbol}][{t.regime}] {t.entry_time.strftime('%m/%d %H:%M')} → {t.exit_time.strftime('%m/%d %H:%M') if t.exit_time else '?'}")
            print(f"    {t.entry_price:,.0f} → {t.exit_price:,.0f} ({t.pnl_pct*100:+.2f}%) [{t.exit_reason}]")
    else:
        print("거래 없음")


if __name__ == "__main__":
    asyncio.run(main())
