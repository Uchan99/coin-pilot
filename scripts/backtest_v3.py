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
import argparse
import asyncio
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Optional, Dict
from sqlalchemy import select, desc
from src.config.strategy import StrategyConfig, get_config, load_strategy_config
from src.common.db import get_db_session
from src.common.models import MarketData
from src.common.indicators import (
    calculate_rsi, calculate_ma, calculate_bb,
    resample_to_hourly, detect_regime, check_bb_touch_recovery,
    calculate_volume_ratios
)
from src.analysis.multi_evidence import (
    detect_order_blocks, detect_fvg, detect_swing_fractals,
    calculate_atr, calculate_htf_trend, calculate_structural_rr,
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
    df['bb_mid'] = bb['BBM']

    # Volume Ratio
    vol_ma_20 = df['volume'].rolling(window=20).mean()
    df['vol_ratio'] = df['volume'] / vol_ma_20
    
    # Volume Ratios (Survey)
    df['vol_ratios'] = calculate_volume_ratios(df['volume'], period=20)

    return df


def get_regime(row: pd.Series, config: StrategyConfig) -> str:
    """행에서 레짐 판단"""
    ma50 = row.get('ma50')
    ma200 = row.get('ma200')
    return detect_regime(
        ma50, ma200, 
        bull_threshold=config.BULL_THRESHOLD_PCT, 
        bear_threshold=config.BEAR_THRESHOLD_PCT
    )


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

    # 3. v3.1: RSI(7) 최소 반등 폭 체크
    min_bounce_pct = entry.get("min_rsi_7_bounce_pct")
    if min_bounce_pct is not None:
        rsi_bounce = row['rsi_short'] - row['rsi_short_prev']
        if rsi_bounce < min_bounce_pct:
            return False

    # MA 조건
    if entry["ma_condition"] == "crossover":
        if row['close'] <= row['ma20']:
            return False
    elif entry["ma_condition"] == "proximity":
        prox = entry.get("ma_proximity_pct", 0.97)
        if row['close'] < row['ma20'] * prox:
            return False
    elif entry["ma_condition"] == "proximity_or_above":
        prox = entry.get("ma_proximity_pct", 0.97)
        if row['close'] < row['ma20'] * prox:
            return False

    # 5. v3.1: BB 하단 체크 (Falling Knife 방지)
    if entry.get("require_price_above_bb_lower") and not pd.isna(row['bb_lower']):
        if row['close'] < row['bb_lower']:
            return False

    # 6. 거래량 상한 조건
    if entry.get("volume_ratio") is not None:
        if pd.isna(row['vol_ratio']) or row['vol_ratio'] < entry["volume_ratio"]:
            return False

    # 7. v3.1: 거래량 하한 조건
    if entry.get("volume_min_ratio") is not None:
        if pd.isna(row['vol_ratio']) or row['vol_ratio'] < entry["volume_min_ratio"]:
            return False

    # 8. v3.1: 거래량 급증 체크 (BEAR 전용)
    if entry.get("volume_surge_check"):
        vol_surge_ratio = entry.get("volume_surge_ratio", 2.0)
        # 최근 3캔들 확인 (현재 포함)
        recent_ratios = df.iloc[max(0, idx-2):idx+1]['vol_ratios'].tolist()
        if any(v >= vol_surge_ratio for v in recent_ratios):
            return False

    # 9. 횡보장 BB 터치 회복 조건
    if regime == "SIDEWAYS" and entry.get("bb_enabled"):
        lookback = entry.get("bb_touch_lookback", 3)
        if idx < lookback + 1:
            return False
        recent_df = df.iloc[idx - lookback:idx + 1][['close', 'bb_lower']].copy()
        if not check_bb_touch_recovery(recent_df, lookback):
            return False

    return True


def check_exit_signal(row: pd.Series, trade: Trade, config: StrategyConfig,
                      bb_min_profit: float = 0.01, rsi_ob_override: float = None) -> tuple:
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

    # 4. RSI 과매수 (조건부) — BB_MIDLINE_EXIT보다 우선
    # RSI 과매수 시 추가 상승 가능성 → RSI_OVERBOUGHT에 맡김
    rsi_threshold = rsi_ob_override if rsi_ob_override is not None else exit_cfg["rsi_overbought"]
    if row['rsi'] > rsi_threshold:
        if pnl_pct >= exit_cfg["rsi_exit_min_profit_pct"]:
            return True, "RSI_OVERBOUGHT"

    # 5. BB 중심선(MA20) 도달 익절 — SIDEWAYS 전용 (v3.4)
    # RSI가 과매수가 아닌데 MA20 도달 = 모멘텀 약한 회귀 → 수익 확정
    if trade.regime == "SIDEWAYS":
        bb_mid = row.get('bb_mid') if hasattr(row, 'get') else row['bb_mid']
        if pd.notna(bb_mid) and row['close'] >= bb_mid:
            if pnl_pct >= bb_min_profit:
                return True, "BB_MIDLINE_EXIT"

    # 6. 시간 초과
    hold_time = row['timestamp'] - trade.entry_time
    if hold_time > timedelta(hours=exit_cfg["time_limit_hours"]):
        return True, "TIME_LIMIT"

    return False, ""


def simulate_trades(df: pd.DataFrame, config: StrategyConfig, symbol: str,
                    bb_min_profit: float = 0.01, rsi_ob_override: float = None) -> List[Trade]:
    """거래 시뮬레이션 (v3.0 레짐 기반)"""
    trades = []
    position = None
    cooldown_until = None

    df_clean = df.dropna(subset=['rsi', 'ma50', 'ma200']).reset_index(drop=True)

    for idx, row in df_clean.iterrows():
        current_time = row['timestamp']
        regime = get_regime(row, config)

        # 포지션 보유 중 -> 청산 체크
        if position:
            should_exit, reason = check_exit_signal(row, position, config, bb_min_profit, rsi_ob_override)
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
                # 실거래(main.py)와 동일하게 심볼별 비중 배율을 적용한다.
                # 목적:
                # - 백테스트/실거래 사이징 규칙을 일치시켜 핫픽스 효과를 왜곡 없이 검증
                # - 심볼별 배율 미정의/비정상 값은 config 폴백(1.0)으로 처리
                symbol_multiplier = config.get_symbol_position_multiplier(symbol)
                effective_ratio = float(size_ratio) * float(symbol_multiplier)
                if effective_ratio <= 0:
                    continue

                position = Trade(
                    symbol=symbol,
                    regime=regime,
                    entry_time=current_time,
                    entry_price=row['close'],
                    position_size=BASE_POSITION_SIZE * effective_ratio,
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


async def run_compare_bb_guards(config: StrategyConfig, guard_values: list):
    """BB_MIDLINE_EXIT 가드 수치별 비교 백테스트"""
    # 데이터 한 번만 로드
    market_data = {}
    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol)
        if not df.empty and len(df) >= 200:
            market_data[symbol] = df

    print("=" * 90)
    print("BB_MIDLINE_EXIT 최소 수익 가드 비교 백테스트")
    print("=" * 90)
    print(f"비교 값: {[f'{v*100:.1f}%' for v in guard_values]}")
    print(f"심볼: {list(market_data.keys())}")
    print()

    # 각 가드 값으로 시뮬레이션
    results = []
    for guard in guard_values:
        all_trades = []
        for symbol, df in market_data.items():
            trades = simulate_trades(df, config, symbol, bb_min_profit=guard)
            all_trades.extend(trades)

        # SIDEWAYS 통계
        sw_trades = [t for t in all_trades if t.regime == "SIDEWAYS"]
        sw_wins = [t for t in sw_trades if t.pnl_net and t.pnl_net > 0]
        sw_total_pnl = sum(t.pnl_net for t in sw_trades if t.pnl_net) * 100
        sw_avg_win = (sum(t.pnl_net for t in sw_wins if t.pnl_net) / len(sw_wins) * 100) if sw_wins else 0
        sw_losses = [t for t in sw_trades if t.pnl_net and t.pnl_net <= 0]
        sw_avg_loss = (sum(t.pnl_net for t in sw_losses if t.pnl_net) / len(sw_losses) * 100) if sw_losses else 0

        # 청산 사유 집계
        sw_reasons = {}
        for t in sw_trades:
            r = t.exit_reason or "UNKNOWN"
            sw_reasons[r] = sw_reasons.get(r, 0) + 1

        # 전체 통계
        total_pnl = sum(t.pnl_net for t in all_trades if t.pnl_net) * 100
        total_profit = sum(t.pnl_net * t.position_size for t in all_trades if t.pnl_net)
        total_wins = len([t for t in all_trades if t.pnl_net and t.pnl_net > 0])
        win_rate = total_wins / len(all_trades) * 100 if all_trades else 0

        # BB_MIDLINE_EXIT 거래 상세
        bb_exits = [t for t in sw_trades if t.exit_reason == "BB_MIDLINE_EXIT"]
        bb_avg_pnl = (sum(t.pnl_net for t in bb_exits if t.pnl_net) / len(bb_exits) * 100) if bb_exits else 0

        results.append({
            "guard": guard,
            "total_trades": len(all_trades),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_profit": total_profit,
            "sw_trades": len(sw_trades),
            "sw_win_rate": len(sw_wins) / len(sw_trades) * 100 if sw_trades else 0,
            "sw_pnl": sw_total_pnl,
            "sw_avg_win": sw_avg_win,
            "sw_avg_loss": sw_avg_loss,
            "sw_reasons": sw_reasons,
            "bb_exits": len(bb_exits),
            "bb_avg_pnl": bb_avg_pnl,
        })

    # 비교 테이블 출력
    print("-" * 90)
    print(f"{'가드':>6} | {'전체':>5} | {'승률':>6} | {'누적PnL':>9} | {'예상수익':>10} | "
          f"{'SW건수':>5} | {'SW승률':>6} | {'SW PnL':>9} | {'SW avg_W':>8} | {'SW avg_L':>8}")
    print("-" * 90)
    for r in results:
        print(f"{r['guard']*100:>5.1f}% | {r['total_trades']:>5} | {r['win_rate']:>5.1f}% | "
              f"{r['total_pnl']:>+8.2f}% | {r['total_profit']:>+9,.0f}원 | "
              f"{r['sw_trades']:>5} | {r['sw_win_rate']:>5.1f}% | {r['sw_pnl']:>+8.2f}% | "
              f"{r['sw_avg_win']:>+7.2f}% | {r['sw_avg_loss']:>+7.2f}%")

    # SIDEWAYS 청산 사유 상세
    print()
    print("-" * 90)
    print("SIDEWAYS 청산 사유 분포:")
    print("-" * 90)
    all_reasons = set()
    for r in results:
        all_reasons.update(r["sw_reasons"].keys())
    all_reasons = sorted(all_reasons)

    header = f"{'가드':>6}"
    for reason in all_reasons:
        header += f" | {reason:>16}"
    header += f" | {'BB avg_pnl':>10}"
    print(header)
    print("-" * 90)
    for r in results:
        line = f"{r['guard']*100:>5.1f}%"
        for reason in all_reasons:
            cnt = r["sw_reasons"].get(reason, 0)
            line += f" | {cnt:>16}"
        line += f" | {r['bb_avg_pnl']:>+9.2f}%"
        print(line)

    print()
    print("=" * 90)


async def run_compare_rsi(config: StrategyConfig, rsi_values: list):
    """RSI 과매수 임계값별 비교 백테스트 (BB 가드 1.0% 고정)"""
    market_data = {}
    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol)
        if not df.empty and len(df) >= 200:
            market_data[symbol] = df

    bb_guard_fixed = 0.01  # 1.0% 고정

    print("=" * 90)
    print("RSI 과매수 임계값 비교 백테스트 (BB 가드 1.0% 고정)")
    print("=" * 90)
    print(f"비교 RSI: {rsi_values}")
    print(f"심볼: {list(market_data.keys())}")
    print()

    results = []
    for rsi_val in rsi_values:
        all_trades = []
        for symbol, df in market_data.items():
            trades = simulate_trades(df, config, symbol,
                                     bb_min_profit=bb_guard_fixed,
                                     rsi_ob_override=rsi_val)
            all_trades.extend(trades)

        # SIDEWAYS 통계
        sw_trades = [t for t in all_trades if t.regime == "SIDEWAYS"]
        sw_wins = [t for t in sw_trades if t.pnl_net and t.pnl_net > 0]
        sw_total_pnl = sum(t.pnl_net for t in sw_trades if t.pnl_net) * 100
        sw_avg_win = (sum(t.pnl_net for t in sw_wins if t.pnl_net) / len(sw_wins) * 100) if sw_wins else 0
        sw_losses = [t for t in sw_trades if t.pnl_net and t.pnl_net <= 0]
        sw_avg_loss = (sum(t.pnl_net for t in sw_losses if t.pnl_net) / len(sw_losses) * 100) if sw_losses else 0

        sw_reasons = {}
        for t in sw_trades:
            r = t.exit_reason or "UNKNOWN"
            sw_reasons[r] = sw_reasons.get(r, 0) + 1

        total_pnl = sum(t.pnl_net for t in all_trades if t.pnl_net) * 100
        total_profit = sum(t.pnl_net * t.position_size for t in all_trades if t.pnl_net)
        total_wins = len([t for t in all_trades if t.pnl_net and t.pnl_net > 0])
        win_rate = total_wins / len(all_trades) * 100 if all_trades else 0

        # RSI_OVERBOUGHT 상세
        rsi_exits = [t for t in sw_trades if t.exit_reason == "RSI_OVERBOUGHT"]
        rsi_avg_pnl = (sum(t.pnl_net for t in rsi_exits if t.pnl_net) / len(rsi_exits) * 100) if rsi_exits else 0

        results.append({
            "rsi": rsi_val,
            "total_trades": len(all_trades),
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_profit": total_profit,
            "sw_trades": len(sw_trades),
            "sw_win_rate": len(sw_wins) / len(sw_trades) * 100 if sw_trades else 0,
            "sw_pnl": sw_total_pnl,
            "sw_avg_win": sw_avg_win,
            "sw_avg_loss": sw_avg_loss,
            "sw_reasons": sw_reasons,
            "rsi_exits": len(rsi_exits),
            "rsi_avg_pnl": rsi_avg_pnl,
        })

    # 비교 테이블
    print("-" * 90)
    print(f"{'RSI':>5} | {'전체':>5} | {'승률':>6} | {'누적PnL':>9} | {'예상수익':>10} | "
          f"{'SW건수':>5} | {'SW승률':>6} | {'SW PnL':>9} | {'SW avg_W':>8} | {'SW avg_L':>8}")
    print("-" * 90)
    for r in results:
        print(f"{r['rsi']:>5} | {r['total_trades']:>5} | {r['win_rate']:>5.1f}% | "
              f"{r['total_pnl']:>+8.2f}% | {r['total_profit']:>+9,.0f}원 | "
              f"{r['sw_trades']:>5} | {r['sw_win_rate']:>5.1f}% | {r['sw_pnl']:>+8.2f}% | "
              f"{r['sw_avg_win']:>+7.2f}% | {r['sw_avg_loss']:>+7.2f}%")

    # 청산 사유 분포
    print()
    print("-" * 90)
    print("SIDEWAYS 청산 사유 분포:")
    print("-" * 90)
    all_reasons = set()
    for r in results:
        all_reasons.update(r["sw_reasons"].keys())
    all_reasons = sorted(all_reasons)

    header = f"{'RSI':>5}"
    for reason in all_reasons:
        header += f" | {reason:>16}"
    header += f" | {'RSI_OB avg':>10}"
    print(header)
    print("-" * 90)
    for r in results:
        line = f"{r['rsi']:>5}"
        for reason in all_reasons:
            cnt = r["sw_reasons"].get(reason, 0)
            line += f" | {cnt:>16}"
        line += f" | {r['rsi_avg_pnl']:>+9.2f}%"
        print(line)

    print()
    print("=" * 90)


# ──────────────────────────────────────────────
# 다중 근거 (Multi-Evidence) 비교 백테스트
# ──────────────────────────────────────────────
ME_SCENARIOS = [
    ("baseline",     "기준선 (Rule Engine)"),
    ("ob",           "+OB 근처"),
    ("fvg",          "+FVG 근처"),
    ("fractal",      "+스윙 지지"),
    ("rr2",          "+R:R≥2.0"),
    ("rr3",          "+R:R≥3.0"),
    ("htf",          "+HTF 정렬"),
    ("2ev_rr2",      "+2근거+R:R≥2.0"),
    ("2ev_rr3",      "+2근거+R:R≥3.0"),
    ("2ev_rr3_htf",  "+2근거+R:R≥3.0+HTF"),
]


def _compute_me_at_entry(df_slice: pd.DataFrame, atr_val: float) -> Dict:
    """
    진입 시점까지의 데이터(df_slice)로 다중 근거 피처 계산.
    - OB/FVG/Fractal: lookback=168 (7일) 윈도우
    - HTF: 4시간봉 리샘플 후 MA20 기울기 + HH/HL 패턴
    - R:R: 구조적 SL(스윙 저점 or OB 하단) / TP(스윙 고점 or 약세 OB)
    """
    current_price = df_slice.iloc[-1]["close"]

    ob = detect_order_blocks(df_slice, lookback=168)
    fvg = detect_fvg(df_slice, lookback=168)
    fractal = detect_swing_fractals(df_slice, lookback=168)
    htf = calculate_htf_trend(df_slice)

    # 구조적 SL: 스윙 저점 vs 강세 OB 하단 중 더 가까운(높은) 것
    structural_sl = None
    if fractal["nearest_swing_low"]:
        structural_sl = fractal["nearest_swing_low"]["price"]
    if ob["nearest_bullish_ob"]:
        ob_low = ob["nearest_bullish_ob"]["price_low"]
        if structural_sl is None or ob_low > structural_sl:
            structural_sl = ob_low

    # 구조적 TP: 스윙 고점 vs 약세 OB 상단 중 더 가까운(낮은) 것
    structural_tp = None
    if fractal["nearest_swing_high"]:
        structural_tp = fractal["nearest_swing_high"]["price"]
    if ob["nearest_bearish_ob"]:
        ob_high = ob["nearest_bearish_ob"]["price_high"]
        if structural_tp is None or ob_high < structural_tp:
            structural_tp = ob_high

    rr = calculate_structural_rr(current_price, structural_sl, structural_tp, atr_val)

    return {"ob": ob, "fvg": fvg, "fractal": fractal, "htf": htf, "rr": rr}


def _passes_me_filter(me: Dict, scenario: str) -> bool:
    """
    시나리오별 다중 근거 필터 통과 여부 판단.
    baseline은 항상 통과, 나머지는 해당 조건 충족 시 통과.
    """
    ob, fvg, fractal = me["ob"], me["fvg"], me["fractal"]
    htf, rr = me["htf"], me["rr"]

    if scenario == "baseline":
        return True

    # 개별 필터 시나리오
    if scenario == "ob":
        return ob.get("price_in_ob") or ob.get("has_bullish_ob_nearby")
    if scenario == "fvg":
        return fvg.get("price_in_fvg") or fvg.get("has_bullish_fvg_nearby")
    if scenario == "fractal":
        return fractal.get("near_swing_support")
    if scenario == "rr2":
        return rr.get("rr_ratio", 0) >= 2.0 and rr.get("risk_pct", 0) > 0
    if scenario == "rr3":
        return rr.get("rr_valid", False)
    if scenario == "htf":
        return htf.get("htf_trend") != "BEARISH"

    # 복합 필터: 다중 근거 스코어링
    # R:R 기본 체크
    if scenario == "2ev_rr2":
        if rr.get("rr_ratio", 0) < 2.0 or rr.get("risk_pct", 0) <= 0:
            return False
    elif scenario in ("2ev_rr3", "2ev_rr3_htf"):
        if not rr.get("rr_valid", False):
            return False

    # HTF 추가 체크 (2ev_rr3_htf만)
    if scenario == "2ev_rr3_htf" and htf.get("htf_trend") == "BEARISH":
        return False

    # 근거 수 계산: R:R 통과 = 1점, 이후 개별 근거 추가
    score = 1  # R:R 통과
    if ob.get("price_in_ob") or ob.get("has_bullish_ob_nearby"):
        score += 1
    if fvg.get("price_in_fvg") or fvg.get("has_bullish_fvg_nearby"):
        score += 1
    if fractal.get("near_swing_support"):
        score += 1
    if htf.get("htf_trend") != "BEARISH":
        score += 1

    return score >= 2


def simulate_trades_me(
    df: pd.DataFrame, config: StrategyConfig, symbol: str,
    scenario: str = "baseline",
    bb_min_profit: float = 0.01,
) -> List[Trade]:
    """
    다중 근거 필터가 적용된 거래 시뮬레이션.
    baseline 시나리오는 기존 Rule Engine 진입 로직 그대로 사용,
    나머지 시나리오는 Rule Engine 진입 조건 통과 후 추가 ME 필터 적용.
    """
    trades = []
    position = None
    cooldown_until = None

    df_clean = df.dropna(subset=['rsi', 'ma50', 'ma200']).reset_index(drop=True)

    # baseline이 아닌 경우 ATR 사전 계산
    atr_series = None
    if scenario != "baseline":
        atr_series = calculate_atr(df_clean)

    for idx, row in df_clean.iterrows():
        current_time = row['timestamp']
        regime = get_regime(row, config)

        # 포지션 보유 중 → 청산 체크
        if position:
            should_exit, reason = check_exit_signal(row, position, config, bb_min_profit)
            if should_exit:
                position.exit_time = current_time
                position.exit_price = row['close']
                position.exit_reason = reason
                gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
                position.pnl_pct = gross_pnl
                position.pnl_net = gross_pnl - (FEE_RATE * 2)
                trades.append(position)
                position = None
                cooldown_until = current_time + timedelta(minutes=30)

        # 포지션 미보유 → 진입 체크
        else:
            if cooldown_until and current_time < cooldown_until:
                continue

            if check_entry_signal(row, regime, config, df_clean, idx):
                # 다중 근거 필터 (baseline 제외)
                if scenario != "baseline":
                    atr_val = atr_series.iloc[idx] if pd.notna(atr_series.iloc[idx]) else 0
                    me = _compute_me_at_entry(df_clean.iloc[:idx + 1], atr_val)
                    if not _passes_me_filter(me, scenario):
                        continue

                size_ratio = config.REGIMES.get(regime, {}).get("position_size_ratio", 0.0)
                symbol_multiplier = config.get_symbol_position_multiplier(symbol)
                effective_ratio = float(size_ratio) * float(symbol_multiplier)
                if effective_ratio <= 0:
                    continue

                position = Trade(
                    symbol=symbol,
                    regime=regime,
                    entry_time=current_time,
                    entry_price=row['close'],
                    position_size=BASE_POSITION_SIZE * effective_ratio,
                    high_water_mark=row['close'],
                )

    # 마지막 포지션 청산
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


async def run_compare_multi_evidence(config: StrategyConfig):
    """
    다중 근거 시나리오 10개 비교 백테스트.
    각 시나리오는 기존 Rule Engine 진입 조건 + 추가 ME 필터 조합.
    baseline 대비 필터율/승률/수익률 변화를 비교 테이블로 출력.
    """
    market_data = {}
    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol)
        if not df.empty and len(df) >= 200:
            market_data[symbol] = df

    print("=" * 105)
    print("다중 근거 기술적 분석 (Multi-Evidence TA) 비교 백테스트")
    print("=" * 105)
    print(f"심볼: {list(market_data.keys())}")
    print(f"시나리오: {len(ME_SCENARIOS)}개")
    print()

    results = []
    for sc_name, sc_desc in ME_SCENARIOS:
        print(f"  시뮬레이션 중: {sc_desc}...", flush=True)
        all_trades = []
        for symbol, df_data in market_data.items():
            trades = simulate_trades_me(df_data, config, symbol, scenario=sc_name)
            all_trades.extend(trades)

        total = len(all_trades)
        wins = [t for t in all_trades if t.pnl_net and t.pnl_net > 0]
        losses = [t for t in all_trades if t.pnl_net and t.pnl_net <= 0]
        total_pnl = sum(t.pnl_net for t in all_trades if t.pnl_net) * 100
        total_profit = sum(t.pnl_net * t.position_size for t in all_trades if t.pnl_net)
        win_rate = len(wins) / total * 100 if total > 0 else 0
        avg_win = (sum(t.pnl_net for t in wins) / len(wins) * 100) if wins else 0
        avg_loss = (sum(t.pnl_net for t in losses) / len(losses) * 100) if losses else 0

        reasons = {}
        for t in all_trades:
            r = t.exit_reason or "UNKNOWN"
            reasons[r] = reasons.get(r, 0) + 1

        # 레짐별 거래 수
        regime_counts = {}
        for t in all_trades:
            regime_counts[t.regime] = regime_counts.get(t.regime, 0) + 1

        results.append({
            "name": sc_name, "desc": sc_desc,
            "total": total, "wins": len(wins), "losses": len(losses),
            "win_rate": win_rate,
            "total_pnl": total_pnl, "total_profit": total_profit,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "reasons": reasons, "regime_counts": regime_counts,
        })

    # ── 결과 테이블 ──
    baseline_total = results[0]["total"] if results else 1
    print()
    print("-" * 105)
    print(f"{'시나리오':<26} | {'거래':>4} | {'승률':>6} | {'누적PnL':>9} | {'예상수익':>10} | "
          f"{'avg_W':>7} | {'avg_L':>7} | {'필터율':>6}")
    print("-" * 105)
    for r in results:
        filter_rate = (1 - r["total"] / baseline_total) * 100 if baseline_total > 0 else 0
        print(f"{r['desc']:<26} | {r['total']:>4} | {r['win_rate']:>5.1f}% | "
              f"{r['total_pnl']:>+8.2f}% | {r['total_profit']:>+9,.0f}원 | "
              f"{r['avg_win']:>+6.2f}% | {r['avg_loss']:>+6.2f}% | {filter_rate:>5.1f}%")

    # ── 청산 사유 분포 ──
    print()
    print("-" * 105)
    print("청산 사유 분포:")
    print("-" * 105)
    all_reasons = sorted({r for res in results for r in res["reasons"]})

    header = f"{'시나리오':<26}"
    for reason in all_reasons:
        header += f" | {reason:>12}"
    print(header)
    print("-" * 105)
    for r in results:
        line = f"{r['desc']:<26}"
        for reason in all_reasons:
            cnt = r["reasons"].get(reason, 0)
            line += f" | {cnt:>12}"
        print(line)

    # ── 레짐별 거래 분포 ──
    print()
    print("-" * 105)
    print("레짐별 거래 수:")
    print("-" * 105)
    all_regimes = sorted({r for res in results for r in res["regime_counts"]})
    header = f"{'시나리오':<26}"
    for regime in all_regimes:
        header += f" | {regime:>10}"
    print(header)
    print("-" * 105)
    for r in results:
        line = f"{r['desc']:<26}"
        for regime in all_regimes:
            cnt = r["regime_counts"].get(regime, 0)
            line += f" | {cnt:>10}"
        print(line)

    print()
    print("=" * 105)


async def main():
    parser = argparse.ArgumentParser(description="v3 백테스트")
    parser.add_argument("--config", default=None, help="전략 YAML 경로 (기본: config/strategy_v3.yaml)")
    parser.add_argument("--bb-min-profit", type=float, default=None,
                        help="BB_MIDLINE_EXIT 최소 수익 가드 (예: 0.01 = 1%%). 미지정 시 0.3%%")
    parser.add_argument("--compare-bb-guards", action="store_true",
                        help="BB_MIDLINE_EXIT 가드 수치 비교 모드 (0%%, 0.3%%, 0.5%%, 1.0%%, 1.5%%, 2.0%%, OFF)")
    parser.add_argument("--compare-rsi", action="store_true",
                        help="RSI 과매수 임계값 비교 모드 (55, 60, 65, 70, 75) BB 가드 1.0%% 고정")
    parser.add_argument("--multi-evidence", action="store_true",
                        help="다중 근거 기술적 분석 시나리오 10개 비교 모드 (OB/FVG/Fractal/R:R/HTF)")
    args = parser.parse_args()

    config = load_strategy_config(args.config) if args.config else get_config()

    # BB 가드 비교 모드
    if args.compare_bb_guards:
        guard_values = [999.0, 0.003, 0.005, 0.01, 0.015, 0.02]
        await run_compare_bb_guards(config, guard_values)
        return

    # RSI 임계값 비교 모드
    if args.compare_rsi:
        rsi_values = [55, 60, 65, 70, 75]
        await run_compare_rsi(config, rsi_values)
        return

    # 다중 근거 비교 모드
    if args.multi_evidence:
        await run_compare_multi_evidence(config)
        return

    # 단일 가드 값 지정 시 적용
    bb_min_profit = args.bb_min_profit if args.bb_min_profit is not None else 0.01

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
    print(f"BB_MIDLINE_EXIT 최소 수익 가드: {bb_min_profit*100:.1f}%")
    print()
    print("-" * 70)

    all_trades = []

    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol)
        if df.empty or len(df) < 200:
            print(f"\n{symbol}: 데이터 부족 ({len(df)} candles)")
            continue

        data_days = len(df) / 24  # 1시간봉 기준
        trades = simulate_trades(df, config, symbol, bb_min_profit=bb_min_profit)
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
