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
    calculate_structural_rr_net, merge_zones, apply_spatial_capacity,
    detect_significant_swing_lows, detect_bos, resample_to_4h,
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


@dataclass
class TradeME(Trade):
    """Phase 1-2 구조적 청산용 거래 기록 — 구조적 SL/TP + BE 방어 + 트레일링 추적"""
    structural_sl: Optional[float] = None      # 구조적 SL 가격 (진입 시 설정)
    structural_tp: Optional[float] = None      # 구조적 TP 가격 (진입 시 설정)
    current_sl: Optional[float] = None         # 현재 활성 SL (BE/트레일링으로 상향)
    be_triggered: bool = False                  # BE 발동 여부
    rr_ratio: float = 0.0                       # 진입 시 Net R:R
    risk_pct: float = 0.0                       # 구조적 SL 거리 (%)


# 상수
FEE_RATE = 0.0005  # 0.05% (업비트)
BASE_POSITION_SIZE = 100000  # 기본 건당 10만원
EQUITY = 1_000_000  # 캡 역산 기준 자산 (100만원)


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


# ════════════════════════════════════════════════════════════════════
# Phase 1-2: 구조적 청산 + 확장 백테스트
# ════════════════════════════════════════════════════════════════════

def calculate_position_size_capped(
    equity: float,
    structural_sl_pct: float,
    max_order: float,
    risk_per_trade: float = 0.02,
    min_order: float = 5000,
    sl_max_pct: float = 5.0,
    sl_min_pct: float = 0.3,
) -> tuple:
    """
    캡 역산(Capped Inverse) 포지션 사이징 (v4.0 최종).
    per-trade 리스크 정규화: SL 넓은 타점은 비중 축소, SL 좁은 타점은 비중 확대.
    현물 캡: max_order 초과 불가 (레버리지 불가 제약).

    공식: final_size = min((equity × 0.02) / structural_sl_pct, max_order)
    극단값 가드: SL > 5% 또는 < 0.3% 시 진입 스킵.

    Returns: (position_size, skip_reason)  — skip_reason이 None이면 진입 가능
    """
    if structural_sl_pct <= 0:
        return 0, "sl_zero"
    if structural_sl_pct > sl_max_pct:
        return 0, "sl_too_wide"
    if structural_sl_pct < sl_min_pct:
        return 0, "sl_too_tight"

    calculated = (equity * risk_per_trade) / (structural_sl_pct / 100)
    final = min(calculated, max_order)

    if final < min_order:
        return 0, "below_min_order"

    return final, None


def check_exit_signal_structural(
    row, trade: TradeME, df: pd.DataFrame, idx: int,
    config: StrategyConfig,
    be_threshold_r: float = 1.5,
    swing_condition: str = "A",
) -> tuple:
    """
    순수 구조적 청산 로직 — SL/TP 모두 구조적 레벨 사용.
    R:R이 낮은 Mean-reversion 환경에서는 TP가 수익을 절단하므로, A안(sl_only) 권장.
    """
    current_price = row["close"]

    # 1. 구조적 SL (최우선)
    if trade.current_sl is not None and current_price <= trade.current_sl:
        if trade.be_triggered:
            return True, "BE_STOP"
        return True, "STRUCTURAL_SL"

    # 2. BE 체크 — 미발동 + 현재 수익 ≥ be_threshold × risk
    if be_threshold_r is not None and not trade.be_triggered and trade.risk_pct > 0:
        pnl_pct = (current_price - trade.entry_price) / trade.entry_price * 100
        if pnl_pct >= be_threshold_r * trade.risk_pct:
            trade.current_sl = trade.entry_price
            trade.be_triggered = True

    # 3. 구조적 트레일링
    _apply_structural_trailing(trade, df, idx, swing_condition)

    # 4. 구조적 TP
    if trade.structural_tp is not None and current_price >= trade.structural_tp:
        return True, "STRUCTURAL_TP"

    # 5. 시간 초과
    regime_config = config.REGIMES.get(trade.regime, config.REGIMES["SIDEWAYS"])
    exit_cfg = regime_config["exit"]
    hold_time = row["timestamp"] - trade.entry_time
    if hold_time > timedelta(hours=exit_cfg["time_limit_hours"]):
        return True, "TIME_LIMIT"

    return False, ""


def check_exit_signal_hybrid(
    row, trade: TradeME, df: pd.DataFrame, idx: int,
    config: StrategyConfig,
    be_threshold_r: float = None,
    swing_condition: str = None,
    bb_min_profit: float = 0.01,
) -> tuple:
    """
    A안: 하이브리드 청산 — 구조적 SL + 기존 익절 로직 보존.

    핵심 원리 (외부 피드백):
    - 손실은 구조적 SL(-1.13%)로 자르고
    - 수익은 기존 BB_MIDLINE/TP/RSI/TRAILING까지 끌고 간다
    - 이론적 R:R = avg_win(1.85%) / avg_loss(1.13%) ≈ 1.6:1
    - 승률 45~50%만 나와도 누적 PnL 우상향

    청산 우선순위:
    1. 구조적 SL (or BE_STOP): 가격이 구조적 손절선 하회
    2. BE 체크: 미발동 + 수익 ≥ be_threshold × risk → SL을 진입가로 이동
    3. 구조적 트레일링: 유의미한 스윙 저점 형성 시 SL 상향
    4~8. 기존 고정 청산: TRAILING_STOP → TAKE_PROFIT → RSI_OVERBOUGHT → BB_MIDLINE → TIME_LIMIT
    """
    current_price = row["close"]
    entry_price = trade.entry_price
    pnl_pct = (current_price - entry_price) / entry_price

    # ── 1. 구조적 SL (최우선 — 고정 SL 대체) ──
    if trade.current_sl is not None and current_price <= trade.current_sl:
        if trade.be_triggered:
            return True, "BE_STOP"
        return True, "STRUCTURAL_SL"

    # ── 2. BE 체크 — 꼬리 리스크 방어 (Tail Risk 필수 방어 기제) ──
    #   가격이 목표치의 99%까지 갔다가 악재로 수직 하락 시, SL을 진입가로 이동하여 손실 0
    if be_threshold_r is not None and not trade.be_triggered and trade.risk_pct > 0:
        pnl_pct_abs = (current_price - entry_price) / entry_price * 100
        if pnl_pct_abs >= be_threshold_r * trade.risk_pct:
            trade.current_sl = entry_price
            trade.be_triggered = True

    # ── 3. 구조적 트레일링 ──
    _apply_structural_trailing(trade, df, idx, swing_condition)

    # ── 4~8. 기존 고정 청산 (수익 보존 — 구조적 TP 대신 기존 로직 사용) ──
    regime_config = config.REGIMES.get(trade.regime, config.REGIMES["SIDEWAYS"])
    exit_cfg = regime_config["exit"]

    # 4. HWM 갱신 + 트레일링 스탑
    if current_price > trade.high_water_mark:
        trade.high_water_mark = current_price
    if pnl_pct >= exit_cfg["trailing_stop_activation_pct"]:
        stop_price = trade.high_water_mark * (1 - exit_cfg["trailing_stop_pct"])
        if current_price <= stop_price:
            return True, "TRAILING_STOP"

    # 5. Take Profit
    if pnl_pct >= exit_cfg["take_profit_pct"]:
        return True, "TAKE_PROFIT"

    # 6. RSI 과매수
    if row["rsi"] > exit_cfg["rsi_overbought"]:
        if pnl_pct >= exit_cfg["rsi_exit_min_profit_pct"]:
            return True, "RSI_OVERBOUGHT"

    # 7. BB 중심선 익절 (SIDEWAYS 전용)
    if trade.regime == "SIDEWAYS":
        bb_mid = row.get("bb_mid") if hasattr(row, "get") else row["bb_mid"]
        if pd.notna(bb_mid) and row["close"] >= bb_mid:
            if pnl_pct >= bb_min_profit:
                return True, "BB_MIDLINE_EXIT"

    # 8. 시간 초과
    hold_time = row["timestamp"] - trade.entry_time
    if hold_time > timedelta(hours=exit_cfg["time_limit_hours"]):
        return True, "TIME_LIMIT"

    return False, ""


def _apply_structural_trailing(
    trade: TradeME, df: pd.DataFrame, idx: int, swing_condition: str,
):
    """
    구조적 트레일링: 유의미한 스윙 저점 형성 시 SL 상향.
    check_exit_signal_structural / check_exit_signal_hybrid 양쪽에서 공유.
    """
    if not swing_condition or trade.current_sl is None or idx < 4:
        return

    # 진입 이후 데이터만으로 스윙 저점 감지
    entry_idx = None
    for search_idx in range(max(0, idx - 200), idx):
        if df.iloc[search_idx]["timestamp"] == trade.entry_time:
            entry_idx = search_idx
            break

    if entry_idx is None or idx - entry_idx < 4:
        return

    current_price = df.iloc[idx]["close"]
    post_entry = df.iloc[entry_idx:idx + 1]
    sig_lows = detect_significant_swing_lows(post_entry, condition=swing_condition)
    for sl in sig_lows:
        # SL은 항상 상향만 (하향 금지)
        if sl["price"] > trade.current_sl and sl["price"] < current_price:
            trade.current_sl = sl["price"]


def _compute_me_at_entry_phase2(
    df_slice: pd.DataFrame, atr_val: float, use_zone_merge: bool = False,
) -> Dict:
    """
    Phase 1-2용 진입 시점 다중 근거 피처 계산.
    Phase 1 대비 추가: Zone 병합 + 5+5 Spatial Capacity + Net R:R.
    """
    current_price = df_slice.iloc[-1]["close"]

    ob = detect_order_blocks(df_slice, lookback=168)
    fvg = detect_fvg(df_slice, lookback=168)
    fractal = detect_swing_fractals(df_slice, lookback=168)
    htf = calculate_htf_trend(df_slice)

    # Zone 병합 (v4.1): OB/FVG 군집을 ATR×0.3 기준으로 병합
    bullish_obs = ob["unmitigated_bullish_obs"]
    bearish_obs = ob["unmitigated_bearish_obs"]
    bullish_fvgs = fvg["unmitigated_bullish_fvgs"]
    bearish_fvgs = fvg["unmitigated_bearish_fvgs"]

    if use_zone_merge and atr_val > 0:
        bullish_obs = merge_zones(bullish_obs, atr_val, price_key_low="price_low", price_key_high="price_high")
        bearish_obs = merge_zones(bearish_obs, atr_val, price_key_low="price_low", price_key_high="price_high")
        bullish_fvgs = merge_zones(bullish_fvgs, atr_val, price_key_low="gap_low", price_key_high="gap_high")
        bearish_fvgs = merge_zones(bearish_fvgs, atr_val, price_key_low="gap_low", price_key_high="gap_high")

    # 5+5 Spatial Capacity: 현재가 기준 가까운 5개씩만 유지
    bullish_obs, bearish_obs = apply_spatial_capacity(
        bullish_obs, bearish_obs, current_price, max_per_side=5,
        price_key_low="price_low", price_key_high="price_high",
    )
    bullish_fvgs, bearish_fvgs = apply_spatial_capacity(
        bullish_fvgs, bearish_fvgs, current_price, max_per_side=5,
        price_key_low="gap_low", price_key_high="gap_high",
    )

    # 구조적 SL: 스윙 저점 vs 강세 OB 하단 중 더 가까운(높은) 것
    structural_sl = None
    if fractal["nearest_swing_low"]:
        structural_sl = fractal["nearest_swing_low"]["price"]
    for b_ob in bullish_obs:
        ob_low = b_ob["price_low"]
        if ob_low < current_price:
            if structural_sl is None or ob_low > structural_sl:
                structural_sl = ob_low

    # 구조적 TP: 스윙 고점 vs 약세 OB 상단 중 더 가까운(낮은) 것
    structural_tp = None
    if fractal["nearest_swing_high"]:
        structural_tp = fractal["nearest_swing_high"]["price"]
    for b_ob in bearish_obs:
        ob_high = b_ob["price_high"]
        if ob_high > current_price:
            if structural_tp is None or ob_high < structural_tp:
                structural_tp = ob_high

    # Net R:R (슬리피지 반영)
    rr = calculate_structural_rr_net(current_price, structural_sl, structural_tp, atr_val)

    # FVG 근처 판단
    has_fvg = any(
        f["gap_low"] <= current_price <= f["gap_high"]
        for f in bullish_fvgs + bearish_fvgs
    )
    if not has_fvg:
        for bf in bullish_fvgs:
            if abs(current_price - bf.get("gap_high", 0)) / current_price <= 0.02:
                has_fvg = True
                break

    return {
        "ob": ob, "fvg": fvg, "fractal": fractal, "htf": htf, "rr": rr,
        "structural_sl": structural_sl, "structural_tp": structural_tp,
        "has_fvg_nearby": has_fvg,
    }


# Phase 1-2 시나리오 정의 — A안: 구조적 SL + 기존 청산(BB_MIDLINE/TP/RSI) 보존
# (name, description, exit_type, be_threshold, swing_cond, sizing, min_rr)
# exit_type: "fixed"=기존 전부, "sl_only"=구조적SL+기존익절(A안), "structural"=SL+TP 모두 구조적
# min_rr: None=R:R 필터 없음 (Mean-reversion에서 avg R:R 0.6:1이므로 필터 무의미)
ME2_SCENARIOS = [
    # ── 기준선 ──
    ("baseline",          "기준선 (고정 청산)",              "fixed",      None, None,  "fixed",       None),
    ("fvg_fixed",         "+FVG (고정 청산)",               "fixed",      None, None,  "fixed",       None),
    # ── A안 핵심: 구조적 SL + 기존 익절 ──
    ("fvg_sl",            "+FVG+구조적SL (A안)",            "sl_only",    None, None,  "fixed",       None),
    # ── A안 + BE 방어 (꼬리 리스크 방어 — R:R 필터 없음) ──
    ("fvg_sl_be10",       "+FVG+구조적SL+BE(1.0R)",        "sl_only",    1.0,  None,  "fixed",       None),
    ("fvg_sl_be15",       "+FVG+구조적SL+BE(1.5R)",        "sl_only",    1.5,  None,  "fixed",       None),
    ("fvg_sl_be20",       "+FVG+구조적SL+BE(2.0R)",        "sl_only",    2.0,  None,  "fixed",       None),
    # ── A안 + BE 1.5R + 스윙 트레일링 조건 비교 ──
    ("fvg_sl_be15_A",     "FVG+구조적SL+BE1.5+4h프랙탈",   "sl_only",    1.5,  "A",   "fixed",       None),
    ("fvg_sl_be15_B",     "FVG+구조적SL+BE1.5+BOS",       "sl_only",    1.5,  "B",   "fixed",       None),
    ("fvg_sl_be15_C",     "FVG+구조적SL+BE1.5+거래량",     "sl_only",    1.5,  "C",   "fixed",       None),
    # ── A안 + BE 1.5R + 캡 역산 포지션 사이징 ──
    ("fvg_sl_cap",        "+FVG+구조적SL+BE1.5+캡역산",    "sl_only",    1.5,  None,  "capped",      None),
    ("fvg_sl_cap_zone",   "+FVG+구조적SL+BE1.5+캡+Zone",  "sl_only",    1.5,  None,  "capped_zone", None),
    # ── 참고: 순수 구조적 SL+TP (이전 결과 대조용) ──
    ("fvg_struct_ref",    "+FVG+구조적 SL+TP (대조)",      "structural", None, None,  "fixed",       None),
]


def simulate_trades_me_phase2(
    df: pd.DataFrame, config: StrategyConfig, symbol: str,
    scenario_name: str, exit_type: str, be_threshold: float,
    swing_cond: str, sizing: str, min_rr: float = None,
    bb_min_profit: float = 0.01,
) -> List[TradeME]:
    """
    Phase 1-2 시뮬레이션.
    exit_type 분기:
    - "fixed": 기존 고정 청산 (baseline/fvg_fixed)
    - "sl_only": A안 하이브리드 — 구조적 SL + 기존 익절(BB_MIDLINE/TP/RSI/TRAILING/TIME_LIMIT) 보존
    - "structural": 순수 구조적 SL+TP (대조군)
    """
    trades: List[TradeME] = []
    position: Optional[TradeME] = None
    cooldown_until = None

    df_clean = df.dropna(subset=["rsi", "ma50", "ma200"]).reset_index(drop=True)
    atr_series = calculate_atr(df_clean)

    use_fvg = scenario_name != "baseline"
    use_structural_exit = exit_type == "structural"
    use_hybrid_exit = exit_type == "sl_only"
    use_capped = sizing in ("capped", "capped_zone")
    use_zone_merge = sizing == "capped_zone"

    for idx, row in df_clean.iterrows():
        current_time = row["timestamp"]
        regime = get_regime(row, config)

        # ── 포지션 보유 중 → 청산 체크 ──
        if position:
            if use_hybrid_exit and position.structural_sl is not None:
                # A안: 구조적 SL + 기존 익절 보존
                should_exit, reason = check_exit_signal_hybrid(
                    row, position, df_clean, idx, config,
                    be_threshold_r=be_threshold,
                    swing_condition=swing_cond,
                    bb_min_profit=bb_min_profit,
                )
            elif use_structural_exit and position.structural_sl is not None:
                # 순수 구조적 (대조군)
                should_exit, reason = check_exit_signal_structural(
                    row, position, df_clean, idx, config,
                    be_threshold_r=be_threshold,
                    swing_condition=swing_cond,
                )
            else:
                # 기존 고정 청산
                should_exit, reason = check_exit_signal(row, position, config, bb_min_profit)

            if should_exit:
                position.exit_time = current_time
                position.exit_price = row["close"]
                position.exit_reason = reason
                gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
                position.pnl_pct = gross_pnl
                position.pnl_net = gross_pnl - (FEE_RATE * 2)
                trades.append(position)
                position = None
                cooldown_until = current_time + timedelta(minutes=30)

        # ── 포지션 미보유 → 진입 체크 ──
        else:
            if cooldown_until and current_time < cooldown_until:
                continue

            if not check_entry_signal(row, regime, config, df_clean, idx):
                continue

            atr_val = atr_series.iloc[idx] if pd.notna(atr_series.iloc[idx]) else 0

            # FVG 필터 + 구조적 피처 계산
            if use_fvg:
                me = _compute_me_at_entry_phase2(df_clean.iloc[:idx + 1], atr_val, use_zone_merge)

                # FVG 필터: FVG 근처가 아니면 스킵
                if not me["has_fvg_nearby"]:
                    continue

                # 구조적 청산 시나리오: Net R:R 필터 (min_rr이 설정된 경우만)
                if use_structural_exit and min_rr is not None:
                    rr_net = me["rr"].get("rr_net", 0)
                    if rr_net < min_rr:
                        continue
            else:
                me = None

            # 포지션 사이징
            regime_config = config.REGIMES.get(regime, {})
            size_ratio = regime_config.get("position_size_ratio", 0.0)
            symbol_multiplier = config.get_symbol_position_multiplier(symbol)
            effective_ratio = float(size_ratio) * float(symbol_multiplier)
            if effective_ratio <= 0:
                continue

            if use_capped and me and me["rr"]["risk_pct"] > 0:
                max_order = EQUITY * effective_ratio
                pos_size, skip_reason = calculate_position_size_capped(
                    EQUITY, me["rr"]["risk_pct"], max_order,
                )
                if skip_reason:
                    continue
            else:
                pos_size = BASE_POSITION_SIZE * effective_ratio

            # TradeME 생성
            structural_sl = me["structural_sl"] if me else None
            structural_tp = me["structural_tp"] if me else None
            risk_pct = me["rr"]["risk_pct"] if me and me["rr"] else 0.0
            rr_ratio = me["rr"]["rr_net"] if me and me["rr"] else 0.0

            position = TradeME(
                symbol=symbol,
                regime=regime,
                entry_time=current_time,
                entry_price=row["close"],
                position_size=pos_size,
                high_water_mark=row["close"],
                structural_sl=structural_sl,
                structural_tp=structural_tp,
                current_sl=structural_sl,  # 초기 SL = 구조적 SL
                rr_ratio=rr_ratio,
                risk_pct=risk_pct,
            )

    # 마지막 포지션 청산
    if position and len(df_clean) > 0:
        last_row = df_clean.iloc[-1]
        position.exit_time = last_row["timestamp"]
        position.exit_price = last_row["close"]
        position.exit_reason = "END"
        gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
        position.pnl_pct = gross_pnl
        position.pnl_net = gross_pnl - (FEE_RATE * 2)
        trades.append(position)

    return trades


async def run_compare_me_phase2(config: StrategyConfig, days: int = 365):
    """
    Phase 1-2 다중 근거 + 구조적 청산 비교 백테스트.
    10개 시나리오: baseline → FVG → 구조적 청산 → BE(1.0/1.5/2.0R) → 스윙 조건(A/B/C) → 캡 역산 → Zone 병합
    """
    market_data = {}
    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol, days=days)
        if not df.empty and len(df) >= 200:
            market_data[symbol] = df

    print("=" * 130)
    print("Phase 1-2: 구조적 청산 + 캡 역산 + BE 방어 비교 백테스트")
    print("=" * 130)
    for sym, df_data in market_data.items():
        data_days = len(df_data) / 24
        print(f"  {sym}: {len(df_data)}봉 ({data_days:.0f}일)")
    print(f"시나리오: {len(ME2_SCENARIOS)}개")
    print()

    results = []
    for sc_name, sc_desc, exit_type, be_thresh, swing_cond, sizing, min_rr in ME2_SCENARIOS:
        print(f"  시뮬레이션 중: {sc_desc}...", flush=True)
        all_trades: List[TradeME] = []
        for symbol, df_data in market_data.items():
            trades = simulate_trades_me_phase2(
                df_data, config, symbol,
                sc_name, exit_type, be_thresh, swing_cond, sizing, min_rr,
            )
            all_trades.extend(trades)

        total = len(all_trades)
        wins = [t for t in all_trades if t.pnl_net and t.pnl_net > 0]
        losses = [t for t in all_trades if t.pnl_net and t.pnl_net <= 0]
        total_pnl = sum(t.pnl_net for t in all_trades if t.pnl_net) * 100
        total_profit = sum(t.pnl_net * t.position_size for t in all_trades if t.pnl_net)
        win_rate = len(wins) / total * 100 if total > 0 else 0
        avg_win = (sum(t.pnl_net for t in wins) / len(wins) * 100) if wins else 0
        avg_loss = (sum(t.pnl_net for t in losses) / len(losses) * 100) if losses else 0

        # 청산 사유 분포
        reasons = {}
        for t in all_trades:
            r = t.exit_reason or "UNKNOWN"
            reasons[r] = reasons.get(r, 0) + 1

        # 레짐별
        regime_counts = {}
        for t in all_trades:
            regime_counts[t.regime] = regime_counts.get(t.regime, 0) + 1

        # Phase 1-2 전용 지표
        avg_sl_pct = 0.0
        be_count = 0
        avg_rr = 0.0
        if all_trades:
            sl_pcts = [t.risk_pct for t in all_trades if t.risk_pct > 0]
            avg_sl_pct = sum(sl_pcts) / len(sl_pcts) if sl_pcts else 0
            be_count = sum(1 for t in all_trades if t.be_triggered)
            rrs = [t.rr_ratio for t in all_trades if t.rr_ratio > 0]
            avg_rr = sum(rrs) / len(rrs) if rrs else 0

        results.append({
            "name": sc_name, "desc": sc_desc,
            "total": total, "wins": len(wins), "losses": len(losses),
            "win_rate": win_rate,
            "total_pnl": total_pnl, "total_profit": total_profit,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "reasons": reasons, "regime_counts": regime_counts,
            "avg_sl_pct": avg_sl_pct, "be_count": be_count, "avg_rr": avg_rr,
        })

    # ── 결과 테이블 ──
    baseline_total = results[0]["total"] if results else 1
    print()
    print("-" * 130)
    print(f"{'시나리오':<28} | {'거래':>4} | {'승률':>6} | {'누적PnL':>9} | {'예상수익':>10} | "
          f"{'avg_W':>7} | {'avg_L':>7} | {'필터율':>6} | {'avgSL%':>6} | {'avgR:R':>6} | {'BE':>3}")
    print("-" * 130)
    for r in results:
        filter_rate = (1 - r["total"] / baseline_total) * 100 if baseline_total > 0 else 0
        print(f"{r['desc']:<28} | {r['total']:>4} | {r['win_rate']:>5.1f}% | "
              f"{r['total_pnl']:>+8.2f}% | {r['total_profit']:>+9,.0f}원 | "
              f"{r['avg_win']:>+6.2f}% | {r['avg_loss']:>+6.2f}% | {filter_rate:>5.1f}% | "
              f"{r['avg_sl_pct']:>5.2f}% | {r['avg_rr']:>5.1f}:1 | {r['be_count']:>3}")

    # ── 청산 사유 분포 ──
    print()
    print("-" * 130)
    print("청산 사유 분포:")
    print("-" * 130)
    all_reasons = sorted({r for res in results for r in res["reasons"]})
    header = f"{'시나리오':<28}"
    for reason in all_reasons:
        header += f" | {reason:>14}"
    print(header)
    print("-" * 130)
    for r in results:
        line = f"{r['desc']:<28}"
        for reason in all_reasons:
            cnt = r["reasons"].get(reason, 0)
            line += f" | {cnt:>14}"
        print(line)

    # ── 레짐별 거래 분포 ──
    print()
    print("-" * 130)
    print("레짐별 거래 수:")
    print("-" * 130)
    all_regimes = sorted({r for res in results for r in res["regime_counts"]})
    header = f"{'시나리오':<28}"
    for regime in all_regimes:
        header += f" | {regime:>10}"
    print(header)
    print("-" * 130)
    for r in results:
        line = f"{r['desc']:<28}"
        for regime in all_regimes:
            cnt = r["regime_counts"].get(regime, 0)
            line += f" | {cnt:>10}"
        print(line)

    print()
    print("=" * 130)


# ════════════════════════════════════════════════════════════════════
# Phase 1-2 SMC: 추세 추종형 풀백 진입 (Mean-reversion 완전 대체)
# ════════════════════════════════════════════════════════════════════

def check_entry_signal_smc(
    df: pd.DataFrame, idx: int, atr_val: float,
    use_zone_merge: bool = False,
    min_rr: float = 1.5,
) -> Optional[Dict]:
    """
    SMC 네이티브 진입 — BOS 확인 후 FVG/OB 풀백 진입.
    RSI/BB 기반 Mean-reversion을 완전히 대체.

    진입 조건 (모두 충족):
    1. HTF Trend: 4h 추세가 BEARISH가 아닌 경우 (BULLISH 또는 NEUTRAL)
    2. BOS: 최근 168봉 내 Bullish BOS 확정 + 구조 유지 (가격 > 풀백 저점)
    3. Retracement: BOS 이후 가격이 되돌림하여 미해소 강세 FVG/OB 영역에 도달
       - 현재가가 FVG 내부 또는 상단에서 2% 이내
       - 또는 현재가가 강세 OB 내부 또는 상단에서 2% 이내
    4. Net R:R ≥ min_rr: SL=FVG/OB 하단-ATR버퍼, TP=다음 유동성 고점

    핵심: '상승 추세 확인(BOS) → 눌림목(Pullback) → 수급 구간(FVG/OB) 진입'
    기존 Mean-reversion("떨어지는 칼날 잡기")과 근본적으로 다른 진입 철학.

    Returns: None (스킵) 또는 Dict with entry info
    """
    if idx < 50:  # 최소 데이터 필요
        return None

    df_slice = df.iloc[:idx + 1]
    current_price = df_slice.iloc[-1]["close"]

    # ── 1. HTF Trend ──
    htf = calculate_htf_trend(df_slice)
    if htf["htf_trend"] == "BEARISH":
        return None

    # ── 2. BOS 확인 ──
    bos = detect_bos(df_slice, lookback=168)
    if not bos["bos_active"] or bos["latest_bullish_bos"] is None:
        return None

    latest_bos = bos["latest_bullish_bos"]

    # BOS 이후 최소 2봉 경과 (풀백 형성 시간 필요)
    if idx - latest_bos["bos_idx"] < 2:
        return None

    # ── 3. FVG/OB Retracement ──
    ob = detect_order_blocks(df_slice, lookback=168)
    fvg = detect_fvg(df_slice, lookback=168)

    bullish_obs = ob["unmitigated_bullish_obs"]
    bullish_fvgs = fvg["unmitigated_bullish_fvgs"]

    # Zone 병합 (선택적)
    if use_zone_merge and atr_val > 0:
        bullish_obs = merge_zones(bullish_obs, atr_val, price_key_low="price_low", price_key_high="price_high")
        bullish_fvgs = merge_zones(bullish_fvgs, atr_val, price_key_low="gap_low", price_key_high="gap_high")

    # BOS 이후 형성된 FVG/OB 또는 BOS 전후의 FVG/OB에서 풀백 진입
    # 현재가가 강세 FVG/OB 근처(내부 or 2% 이내)인지 확인
    entry_zone = None
    entry_zone_type = None

    # FVG 확인 (우선순위 높음 — Phase 1에서 유효성 확인됨)
    for bf in bullish_fvgs:
        if bf["gap_low"] <= current_price <= bf["gap_high"]:
            entry_zone = {"low": bf["gap_low"], "high": bf["gap_high"]}
            entry_zone_type = "FVG"
            break
        if bf["gap_high"] <= current_price and (current_price - bf["gap_high"]) / current_price <= 0.02:
            entry_zone = {"low": bf["gap_low"], "high": bf["gap_high"]}
            entry_zone_type = "FVG_nearby"
            break

    # OB 확인 (FVG 없으면)
    if entry_zone is None:
        for bo in bullish_obs:
            if bo["price_low"] <= current_price <= bo["price_high"]:
                entry_zone = {"low": bo["price_low"], "high": bo["price_high"]}
                entry_zone_type = "OB"
                break
            if bo["price_high"] <= current_price and (current_price - bo["price_high"]) / current_price <= 0.02:
                entry_zone = {"low": bo["price_low"], "high": bo["price_high"]}
                entry_zone_type = "OB_nearby"
                break

    if entry_zone is None:
        return None

    # ── 4. 구조적 SL/TP + Net R:R ──
    # SL = FVG/OB 하단 - ATR 버퍼 (풀백 저점보다 아래 → 구조적으로 안전)
    structural_sl = entry_zone["low"]
    # 풀백 저점이 더 아래면 그것을 SL로 사용 (더 보수적)
    if latest_bos["pullback_low_price"] < structural_sl:
        structural_sl = latest_bos["pullback_low_price"]

    # TP = 다음 유동성 고점 (스윙 고점 or 약세 OB)
    fractal = detect_swing_fractals(df_slice, lookback=168)
    bearish_obs = ob["unmitigated_bearish_obs"]

    structural_tp = None
    if fractal["nearest_swing_high"]:
        structural_tp = fractal["nearest_swing_high"]["price"]
    for bo in bearish_obs:
        if bo["price_low"] > current_price:
            if structural_tp is None or bo["price_low"] < structural_tp:
                structural_tp = bo["price_low"]

    # Net R:R 계산 (슬리피지 반영)
    rr = calculate_structural_rr_net(
        current_price, structural_sl, structural_tp, atr_val,
        min_rr=min_rr,
    )

    if not rr["rr_valid"]:
        return None

    return {
        "structural_sl": rr["sl_price"],
        "structural_tp": rr["tp_price"],
        "risk_pct": rr["risk_pct"],
        "rr_net": rr["rr_net"],
        "rr_gross": rr["rr_ratio"],
        "entry_zone_type": entry_zone_type,
        "bos_price": latest_bos["bos_price"],
        "htf_trend": htf["htf_trend"],
    }


# SMC 시나리오 정의
# (name, desc, exit_type, be, swing, sizing, min_rr)
SMC_SCENARIOS = [
    # 기준선 (기존 RSI/BB Rule Engine)
    ("baseline",         "기준선 (RSI/BB 고정)",         "fixed",      None, None, "fixed",       None),
    ("fvg_me",           "+FVG (RSI/BB 고정)",          "fixed",      None, None, "fixed",       None),
    # SMC 진입 — 구조적 SL+TP
    ("smc_struct",       "SMC+구조적 SL+TP",            "structural", None, None, "fixed",       1.5),
    # SMC 진입 — 하이브리드 (구조적 SL + 기존 익절, 비교용)
    ("smc_hybrid",       "SMC+구조적SL+기존익절",         "sl_only",    None, None, "fixed",       1.5),
    # SMC + BE 방어
    ("smc_be10",         "SMC+구조적+BE(1.0R)",         "structural", 1.0,  None, "fixed",       1.5),
    ("smc_be15",         "SMC+구조적+BE(1.5R)",         "structural", 1.5,  None, "fixed",       1.5),
    ("smc_be20",         "SMC+구조적+BE(2.0R)",         "structural", 2.0,  None, "fixed",       1.5),
    # SMC + BE + 트레일링
    ("smc_be15_A",       "SMC+BE1.5+4h프랙탈",          "structural", 1.5,  "A",  "fixed",       1.5),
    ("smc_be15_B",       "SMC+BE1.5+BOS트레일",         "structural", 1.5,  "B",  "fixed",       1.5),
    # SMC + 캡 역산
    ("smc_cap",          "SMC+BE1.5+캡역산",            "structural", 1.5,  None, "capped",      1.5),
    ("smc_cap_zone",     "SMC+BE1.5+캡+Zone",          "structural", 1.5,  None, "capped_zone", 1.5),
    # R:R 임계값 비교
    ("smc_rr20",         "SMC+구조적 (R:R≥2.0)",        "structural", 1.5,  None, "fixed",       2.0),
    ("smc_rr30",         "SMC+구조적 (R:R≥3.0)",        "structural", 1.5,  None, "fixed",       3.0),
]


def simulate_trades_smc(
    df: pd.DataFrame, config: StrategyConfig, symbol: str,
    scenario_name: str, exit_type: str, be_threshold: float,
    swing_cond: str, sizing: str, min_rr: float = None,
    bb_min_profit: float = 0.01,
) -> List[TradeME]:
    """
    SMC 풀백 진입 시뮬레이션.
    - baseline/fvg_me: 기존 RSI/BB 진입 + 고정 청산 (대조군)
    - smc_*: BOS + FVG/OB 풀백 진입 + 구조적/하이브리드 청산
    """
    trades: List[TradeME] = []
    position: Optional[TradeME] = None
    cooldown_until = None

    df_clean = df.dropna(subset=["rsi", "ma50", "ma200"]).reset_index(drop=True)
    atr_series = calculate_atr(df_clean)

    use_smc = scenario_name.startswith("smc_")
    use_structural_exit = exit_type == "structural"
    use_hybrid_exit = exit_type == "sl_only"
    use_capped = sizing in ("capped", "capped_zone")
    use_zone_merge = sizing == "capped_zone"

    for idx, row in df_clean.iterrows():
        current_time = row["timestamp"]
        regime = get_regime(row, config)

        # ── 포지션 보유 중 → 청산 체크 ──
        if position:
            if use_hybrid_exit and position.structural_sl is not None:
                should_exit, reason = check_exit_signal_hybrid(
                    row, position, df_clean, idx, config,
                    be_threshold_r=be_threshold, swing_condition=swing_cond,
                    bb_min_profit=bb_min_profit,
                )
            elif use_structural_exit and position.structural_sl is not None:
                should_exit, reason = check_exit_signal_structural(
                    row, position, df_clean, idx, config,
                    be_threshold_r=be_threshold, swing_condition=swing_cond,
                )
            else:
                should_exit, reason = check_exit_signal(row, position, config, bb_min_profit)

            if should_exit:
                position.exit_time = current_time
                position.exit_price = row["close"]
                position.exit_reason = reason
                gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
                position.pnl_pct = gross_pnl
                position.pnl_net = gross_pnl - (FEE_RATE * 2)
                trades.append(position)
                position = None
                cooldown_until = current_time + timedelta(minutes=30)

        # ── 포지션 미보유 → 진입 체크 ──
        else:
            if cooldown_until and current_time < cooldown_until:
                continue

            atr_val = atr_series.iloc[idx] if pd.notna(atr_series.iloc[idx]) else 0

            if use_smc:
                # SMC 풀백 진입 (RSI/BB 완전 대체)
                entry = check_entry_signal_smc(
                    df_clean, idx, atr_val,
                    use_zone_merge=use_zone_merge,
                    min_rr=min_rr if min_rr else 1.5,
                )
                if entry is None:
                    continue

                structural_sl = entry["structural_sl"]
                structural_tp = entry["structural_tp"]
                risk_pct = entry["risk_pct"]
                rr_ratio = entry["rr_net"]
            else:
                # 기존 Rule Engine 진입 (대조군: baseline, fvg_me)
                if not check_entry_signal(row, regime, config, df_clean, idx):
                    continue

                # fvg_me: FVG 필터 추가
                if scenario_name == "fvg_me":
                    me = _compute_me_at_entry_phase2(df_clean.iloc[:idx + 1], atr_val)
                    if not me["has_fvg_nearby"]:
                        continue

                structural_sl = None
                structural_tp = None
                risk_pct = 0.0
                rr_ratio = 0.0

            # 포지션 사이징
            regime_config_dict = config.REGIMES.get(regime, {})
            size_ratio = regime_config_dict.get("position_size_ratio", 0.0)
            symbol_multiplier = config.get_symbol_position_multiplier(symbol)
            effective_ratio = float(size_ratio) * float(symbol_multiplier)
            if effective_ratio <= 0:
                continue

            if use_capped and risk_pct > 0:
                max_order = EQUITY * effective_ratio
                pos_size, skip_reason = calculate_position_size_capped(
                    EQUITY, risk_pct, max_order,
                )
                if skip_reason:
                    continue
            else:
                pos_size = BASE_POSITION_SIZE * effective_ratio

            position = TradeME(
                symbol=symbol,
                regime=regime,
                entry_time=current_time,
                entry_price=row["close"],
                position_size=pos_size,
                high_water_mark=row["close"],
                structural_sl=structural_sl,
                structural_tp=structural_tp,
                current_sl=structural_sl,
                rr_ratio=rr_ratio,
                risk_pct=risk_pct,
            )

    # 마지막 포지션 청산
    if position and len(df_clean) > 0:
        last_row = df_clean.iloc[-1]
        position.exit_time = last_row["timestamp"]
        position.exit_price = last_row["close"]
        position.exit_reason = "END"
        gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
        position.pnl_pct = gross_pnl
        position.pnl_net = gross_pnl - (FEE_RATE * 2)
        trades.append(position)

    return trades


async def run_compare_smc(config: StrategyConfig, days: int = 365):
    """
    SMC 풀백 진입 vs 기존 RSI/BB 비교 백테스트.
    Mean-reversion → 추세 추종형 전환의 유효성 데이터 검증.
    """
    market_data = {}
    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol, days=days)
        if not df.empty and len(df) >= 200:
            market_data[symbol] = df

    print("=" * 130)
    print("SMC Pullback 진입 vs RSI/BB Mean-reversion 비교 백테스트")
    print("=" * 130)
    for sym, df_data in market_data.items():
        data_days = len(df_data) / 24
        print(f"  {sym}: {len(df_data)}봉 ({data_days:.0f}일)")
    print(f"시나리오: {len(SMC_SCENARIOS)}개")
    print()

    results = []
    for sc_name, sc_desc, exit_type, be_thresh, swing_cond, sizing, min_rr in SMC_SCENARIOS:
        print(f"  시뮬레이션 중: {sc_desc}...", flush=True)
        all_trades: List[TradeME] = []
        for symbol, df_data in market_data.items():
            trades = simulate_trades_smc(
                df_data, config, symbol,
                sc_name, exit_type, be_thresh, swing_cond, sizing, min_rr,
            )
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

        regime_counts = {}
        for t in all_trades:
            regime_counts[t.regime] = regime_counts.get(t.regime, 0) + 1

        avg_sl_pct = 0.0
        be_count = 0
        avg_rr = 0.0
        if all_trades:
            sl_pcts = [t.risk_pct for t in all_trades if t.risk_pct > 0]
            avg_sl_pct = sum(sl_pcts) / len(sl_pcts) if sl_pcts else 0
            be_count = sum(1 for t in all_trades if t.be_triggered)
            rrs = [t.rr_ratio for t in all_trades if t.rr_ratio > 0]
            avg_rr = sum(rrs) / len(rrs) if rrs else 0

        results.append({
            "name": sc_name, "desc": sc_desc,
            "total": total, "wins": len(wins), "losses": len(losses),
            "win_rate": win_rate,
            "total_pnl": total_pnl, "total_profit": total_profit,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "reasons": reasons, "regime_counts": regime_counts,
            "avg_sl_pct": avg_sl_pct, "be_count": be_count, "avg_rr": avg_rr,
        })

    # ── 결과 테이블 ──
    baseline_total = results[0]["total"] if results else 1
    print()
    print("-" * 130)
    print(f"{'시나리오':<26} | {'거래':>4} | {'승률':>6} | {'누적PnL':>9} | {'예상수익':>10} | "
          f"{'avg_W':>7} | {'avg_L':>7} | {'필터율':>6} | {'avgSL%':>6} | {'avgR:R':>6} | {'BE':>3}")
    print("-" * 130)
    for r in results:
        filter_rate = (1 - r["total"] / baseline_total) * 100 if baseline_total > 0 else 0
        print(f"{r['desc']:<26} | {r['total']:>4} | {r['win_rate']:>5.1f}% | "
              f"{r['total_pnl']:>+8.2f}% | {r['total_profit']:>+9,.0f}원 | "
              f"{r['avg_win']:>+6.2f}% | {r['avg_loss']:>+6.2f}% | {filter_rate:>5.1f}% | "
              f"{r['avg_sl_pct']:>5.2f}% | {r['avg_rr']:>5.1f}:1 | {r['be_count']:>3}")

    # ── 청산 사유 분포 ──
    print()
    print("-" * 130)
    print("청산 사유 분포:")
    print("-" * 130)
    all_reasons = sorted({r for res in results for r in res["reasons"]})
    header = f"{'시나리오':<26}"
    for reason in all_reasons:
        header += f" | {reason:>14}"
    print(header)
    print("-" * 130)
    for r in results:
        line = f"{r['desc']:<26}"
        for reason in all_reasons:
            cnt = r["reasons"].get(reason, 0)
            line += f" | {cnt:>14}"
        print(line)

    # ── 레짐별 거래 분포 ──
    print()
    print("-" * 130)
    print("레짐별 거래 수:")
    print("-" * 130)
    all_regimes = sorted({r for res in results for r in res["regime_counts"]})
    header = f"{'시나리오':<26}"
    for regime in all_regimes:
        header += f" | {regime:>10}"
    print(header)
    print("-" * 130)
    for r in results:
        line = f"{r['desc']:<26}"
        for regime in all_regimes:
            cnt = r["regime_counts"].get(regime, 0)
            line += f" | {cnt:>10}"
        print(line)

    print()
    print("=" * 130)


# ═══════════════════════════════════════════════════════════════════════
# A안 v2: RSI/BB 진입 + FVG 필터 + 적응형 SL 하이브리드
# ═══════════════════════════════════════════════════════════════════════
# 핵심 인사이트: +FVG 시나리오가 유일한 양성 시그널(61.1% 승률)
# 문제: avg_L = -2.90% → SL을 구조적으로 줄이되, 바닥값(floor)으로 조기 청산 방지
# Adaptive SL = max(구조적_SL, 현재가 × (1 - floor%))

# (name, desc, sl_type, sl_floor, be_threshold, swing_cond, sizing)
# sl_type: "fixed"=기존3%, "structural"=FVG/OB기반, "adaptive"=max(structural, floor)
FVG_HYBRID_SCENARIOS = [
    # ── 기준선 ──
    ("baseline",        "기준선 (RSI/BB 고정)",          "fixed",      None,  None, None, "fixed"),
    ("fvg_fixed",       "+FVG (고정 청산)",             "fixed",      None,  None, None, "fixed"),
    # ── FVG + SL 방식 비교 ──
    ("fvg_struct_sl",   "+FVG+구조적SL",               "structural", None,  None, None, "fixed"),
    ("fvg_adapt15",     "+FVG+적응SL(≥1.5%)",          "adaptive",   0.015, None, None, "fixed"),
    ("fvg_adapt20",     "+FVG+적응SL(≥2.0%)",          "adaptive",   0.020, None, None, "fixed"),
    ("fvg_adapt25",     "+FVG+적응SL(≥2.5%)",          "adaptive",   0.025, None, None, "fixed"),
    # ── 적응SL 2% + BE 방어 ──
    ("fvg_ad20_be10",   "+FVG+적응2%+BE(1.0R)",        "adaptive",   0.020, 1.0,  None, "fixed"),
    ("fvg_ad20_be15",   "+FVG+적응2%+BE(1.5R)",        "adaptive",   0.020, 1.5,  None, "fixed"),
    ("fvg_ad20_be20",   "+FVG+적응2%+BE(2.0R)",        "adaptive",   0.020, 2.0,  None, "fixed"),
    # ── 적응SL 2% + BE 1.5R + 트레일링 ──
    ("fvg_ad20_trA",    "+FVG+적응2%+BE1.5+4h프랙탈",   "adaptive",   0.020, 1.5,  "A",  "fixed"),
    ("fvg_ad20_trB",    "+FVG+적응2%+BE1.5+BOS트레일",  "adaptive",   0.020, 1.5,  "B",  "fixed"),
    # ── 적응SL 2% + BE 1.5R + 캡 역산 ──
    ("fvg_ad20_cap",    "+FVG+적응2%+BE1.5+캡역산",     "adaptive",   0.020, 1.5,  None, "capped"),
    # ── 고정 SL에 BE만 추가 (참조용) ──
    ("fvg_fix_be15",    "+FVG+고정SL+BE(1.5R)",        "fixed",      None,  1.5,  None, "fixed"),
]


def simulate_trades_fvg_hybrid(
    df: pd.DataFrame, config: StrategyConfig, symbol: str,
    scenario_name: str, sl_type: str, sl_floor: float,
    be_threshold: float, swing_cond: str, sizing: str,
    bb_min_profit: float = 0.01,
) -> List[TradeME]:
    """
    A안 v2: RSI/BB 진입 + FVG 필터 + 적응형 SL 하이브리드.
    - baseline: 기존 RSI/BB + 고정 청산
    - fvg_*: RSI/BB + FVG 필터 + 적응형/구조적 SL + 기존 익절
    """
    trades: List[TradeME] = []
    position: Optional[TradeME] = None
    cooldown_until = None

    df_clean = df.dropna(subset=["rsi", "ma50", "ma200"]).reset_index(drop=True)
    atr_series = calculate_atr(df_clean)

    use_fvg_filter = scenario_name != "baseline"
    use_structural_sl = sl_type in ("structural", "adaptive")
    use_capped = sizing == "capped"
    has_be = be_threshold is not None

    for idx, row in df_clean.iterrows():
        current_time = row["timestamp"]
        regime = get_regime(row, config)

        # ── 포지션 보유 중 → 청산 체크 ──
        if position:
            if use_structural_sl and position.structural_sl is not None:
                should_exit, reason = check_exit_signal_hybrid(
                    row, position, df_clean, idx, config,
                    be_threshold_r=be_threshold, swing_condition=swing_cond,
                    bb_min_profit=bb_min_profit,
                )
            elif has_be and position.structural_sl is None:
                # 고정 SL + BE 방어 (fvg_fix_be15)
                # BE는 structural_sl 필드를 활용 — 진입가 기준 고정 SL 설정 후 BE 이동
                should_exit, reason = check_exit_signal(row, position, config, bb_min_profit)
            else:
                should_exit, reason = check_exit_signal(row, position, config, bb_min_profit)

            if should_exit:
                position.exit_time = current_time
                position.exit_price = row["close"]
                position.exit_reason = reason
                gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
                position.pnl_pct = gross_pnl
                position.pnl_net = gross_pnl - (FEE_RATE * 2)
                trades.append(position)
                position = None
                cooldown_until = current_time + timedelta(minutes=30)

        # ── 포지션 미보유 → 진입 체크 ──
        else:
            if cooldown_until and current_time < cooldown_until:
                continue

            # RSI/BB 기반 진입 조건
            if not check_entry_signal(row, regime, config, df_clean, idx):
                continue

            atr_val = atr_series.iloc[idx] if pd.notna(atr_series.iloc[idx]) else 0

            # FVG 필터 + 구조적 데이터 계산
            structural_sl = None
            structural_tp = None
            risk_pct = 0.0
            rr_ratio = 0.0

            if use_fvg_filter:
                me = _compute_me_at_entry_phase2(df_clean.iloc[:idx + 1], atr_val)
                if not me["has_fvg_nearby"]:
                    continue

                if use_structural_sl and me["structural_sl"] is not None:
                    current_price = row["close"]
                    raw_sl = me["structural_sl"]

                    if sl_type == "adaptive" and sl_floor is not None:
                        # 적응형 SL: 구조적 SL과 바닥값 중 더 넓은(낮은) 것
                        floor_price = current_price * (1 - sl_floor)
                        structural_sl = min(raw_sl, floor_price)
                    else:
                        structural_sl = raw_sl

                    # SL 거리 검증 (0.3% ~ 5%)
                    sl_dist = (current_price - structural_sl) / current_price
                    if sl_dist < 0.003 or sl_dist > 0.05:
                        structural_sl = None
                    else:
                        structural_tp = me.get("structural_tp")
                        risk_pct = sl_dist
                        if structural_tp and structural_tp > current_price:
                            tp_dist = (structural_tp - current_price) / current_price
                            rr_ratio = tp_dist / sl_dist if sl_dist > 0 else 0

            # 포지션 사이징
            regime_config_dict = config.REGIMES.get(regime, {})
            size_ratio = regime_config_dict.get("position_size_ratio", 0.0)
            symbol_multiplier = config.get_symbol_position_multiplier(symbol)
            effective_ratio = float(size_ratio) * float(symbol_multiplier)
            if effective_ratio <= 0:
                continue

            if use_capped and risk_pct > 0:
                max_order = EQUITY * effective_ratio
                pos_size, skip_reason = calculate_position_size_capped(
                    EQUITY, risk_pct, max_order,
                )
                if skip_reason:
                    continue
            else:
                pos_size = BASE_POSITION_SIZE * effective_ratio

            position = TradeME(
                symbol=symbol,
                regime=regime,
                entry_time=current_time,
                entry_price=row["close"],
                position_size=pos_size,
                high_water_mark=row["close"],
                structural_sl=structural_sl,
                structural_tp=structural_tp,
                current_sl=structural_sl,
                rr_ratio=rr_ratio,
                risk_pct=risk_pct,
            )

    # 마지막 포지션 청산
    if position and len(df_clean) > 0:
        last_row = df_clean.iloc[-1]
        position.exit_time = last_row["timestamp"]
        position.exit_price = last_row["close"]
        position.exit_reason = "END"
        gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
        position.pnl_pct = gross_pnl
        position.pnl_net = gross_pnl - (FEE_RATE * 2)
        trades.append(position)

    return trades


async def run_compare_fvg_hybrid(config: StrategyConfig, days: int = 365):
    """
    A안 v2: RSI/BB + FVG 필터 + 적응형 SL 하이브리드 비교 백테스트.
    """
    market_data = {}
    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol, days=days)
        if not df.empty and len(df) >= 200:
            market_data[symbol] = df

    print("=" * 130)
    print("A안 v2: RSI/BB + FVG 필터 + 적응형 SL 하이브리드 비교")
    print("=" * 130)
    for sym, df_data in market_data.items():
        data_days = len(df_data) / 24
        print(f"  {sym}: {len(df_data)}봉 ({data_days:.0f}일)")
    print(f"시나리오: {len(FVG_HYBRID_SCENARIOS)}개")
    print()

    results = []
    for sc_name, sc_desc, sl_type, sl_floor, be_thresh, swing_cond, sizing in FVG_HYBRID_SCENARIOS:
        print(f"  시뮬레이션 중: {sc_desc}...", flush=True)
        all_trades: List[TradeME] = []
        for symbol, df_data in market_data.items():
            trades = simulate_trades_fvg_hybrid(
                df_data, config, symbol,
                sc_name, sl_type, sl_floor, be_thresh, swing_cond, sizing,
            )
            all_trades.extend(trades)

        total = len(all_trades)
        wins = [t for t in all_trades if t.pnl_net and t.pnl_net > 0]
        losses = [t for t in all_trades if t.pnl_net and t.pnl_net <= 0]
        total_pnl = sum(t.pnl_net for t in all_trades if t.pnl_net) * 100
        total_profit = sum(t.pnl_net * t.position_size for t in all_trades if t.pnl_net)
        win_rate = len(wins) / total * 100 if total > 0 else 0
        avg_win = (sum(t.pnl_net for t in wins) / len(wins) * 100) if wins else 0
        avg_loss = (sum(t.pnl_net for t in losses) / len(losses) * 100) if losses else 0

        # 필터율 (기준선 대비)
        baseline_count = results[0]["total"] if results else total
        filter_rate = (1 - total / baseline_count) * 100 if baseline_count > 0 and results else 0

        reasons = {}
        for t in all_trades:
            r = t.exit_reason or "UNKNOWN"
            reasons[r] = reasons.get(r, 0) + 1

        regime_counts = {}
        for t in all_trades:
            regime_counts[t.regime] = regime_counts.get(t.regime, 0) + 1

        avg_sl_pct = 0.0
        be_count = 0
        avg_rr = 0.0
        sl_trades = [t for t in all_trades if t.risk_pct and t.risk_pct > 0]
        if sl_trades:
            avg_sl_pct = sum(t.risk_pct for t in sl_trades) / len(sl_trades) * 100
        rr_trades = [t for t in all_trades if t.rr_ratio and t.rr_ratio > 0]
        if rr_trades:
            avg_rr = sum(t.rr_ratio for t in rr_trades) / len(rr_trades)
        be_count = sum(1 for t in all_trades if t.be_triggered)

        results.append({
            "name": sc_name, "desc": sc_desc, "total": total, "win_rate": win_rate,
            "total_pnl": total_pnl, "total_profit": total_profit,
            "avg_win": avg_win, "avg_loss": avg_loss, "filter_rate": filter_rate,
            "reasons": reasons, "regime_counts": regime_counts,
            "avg_sl": avg_sl_pct, "avg_rr": avg_rr, "be_count": be_count,
        })

    # ── 결과 테이블 ──
    print()
    print("-" * 130)
    header = (
        f"{'시나리오':<28} | {'거래':>5} | {'승률':>7} | {'누적PnL':>10} | {'예상수익':>13} | "
        f"{'avg_W':>7} | {'avg_L':>7} | {'필터율':>7} | {'avgSL%':>6} | {'avgR:R':>6} | {'BE':>4}"
    )
    print(header)
    print("-" * 130)
    for r in results:
        print(
            f"{r['desc']:<28} | {r['total']:>5} | {r['win_rate']:>6.1f}% | "
            f"{r['total_pnl']:>+9.2f}% | {r['total_profit']:>12,.0f}원 | "
            f"{r['avg_win']:>+6.2f}% | {r['avg_loss']:>+6.2f}% | "
            f"{r['filter_rate']:>6.1f}% | {r['avg_sl']:>5.2f}% | "
            f"{r['avg_rr']:>5.1f}:1 | {r['be_count']:>4}"
        )

    # ── 청산 사유 분포 ──
    print()
    print("-" * 130)
    print("청산 사유 분포:")
    print("-" * 130)
    all_reasons = sorted({r for res in results for r in res["reasons"]})
    header = f"{'시나리오':<28}"
    for reason in all_reasons:
        header += f" | {reason:>14}"
    print(header)
    print("-" * 130)
    for r in results:
        line = f"{r['desc']:<28}"
        for reason in all_reasons:
            cnt = r["reasons"].get(reason, 0)
            line += f" | {cnt:>14}"
        print(line)

    # ── 레짐별 거래 분포 ──
    print()
    print("-" * 130)
    print("레짐별 거래 수:")
    print("-" * 130)
    all_regimes = sorted({r for res in results for r in res["regime_counts"]})
    header = f"{'시나리오':<28}"
    for regime in all_regimes:
        header += f" | {regime:>10}"
    print(header)
    print("-" * 130)
    for r in results:
        line = f"{r['desc']:<28}"
        for regime in all_regimes:
            cnt = r["regime_counts"].get(regime, 0)
            line += f" | {cnt:>10}"
        print(line)

    print()
    print("=" * 130)


# ═══════════════════════════════════════════════════════════════════════
# 레짐 필터 검증: BEAR 진입 차단 효과 + FVG 조합
# ═══════════════════════════════════════════════════════════════════════
# (name, desc, use_fvg, allowed_regimes, bb_min_profit)
# bb_min_profit: 0.01=1%(기본), 999.0=OFF, 0.015/0.02/0.025/0.03=가드 상향
REGIME_FILTER_SCENARIOS = [
    # ── 대조군 ──
    ("all",              "전체 레짐",                    False, None,                  0.01),
    ("all_fvg",          "전체+FVG",                    True,  None,                  0.01),
    # ── FVG + BB가드 변형 (핵심 테스트) ──
    ("fvg_bb10",         "FVG+BB가드1.0%",              True,  None,                  0.01),
    ("fvg_bb15",         "FVG+BB가드1.5%",              True,  None,                  0.015),
    ("fvg_bb20",         "FVG+BB가드2.0%",              True,  None,                  0.02),
    ("fvg_bb25",         "FVG+BB가드2.5%",              True,  None,                  0.025),
    ("fvg_bb30",         "FVG+BB가드3.0%",              True,  None,                  0.03),
    ("fvg_bboff",        "FVG+BB OFF",                 True,  None,                  999.0),
    # ── FVG + BB OFF + 레짐 필터 ──
    ("fvg_off_nobear",   "FVG+BB OFF+BEAR제외",         True,  ["BULL", "SIDEWAYS"],  999.0),
    ("fvg_off_sw",       "FVG+BB OFF+SIDEWAYS",        True,  ["SIDEWAYS"],          999.0),
    # ── BB OFF만 (FVG 없이) ──
    ("bboff_only",       "BB OFF (FVG 없음)",           False, None,                  999.0),
    # ── BEAR 격리 (참조) ──
    ("bear_only",        "BEAR만 (격리)",                False, ["BEAR"],              0.01),
]


def simulate_trades_regime_filter(
    df: pd.DataFrame, config: StrategyConfig, symbol: str,
    use_fvg: bool, allowed_regimes: list,
    bb_min_profit: float = 0.01,
) -> List[TradeME]:
    """레짐 필터 + FVG 필터 조합 검증용 시뮬레이션. 청산은 기존 고정 방식."""
    trades: List[TradeME] = []
    position: Optional[TradeME] = None
    cooldown_until = None

    df_clean = df.dropna(subset=["rsi", "ma50", "ma200"]).reset_index(drop=True)
    atr_series = calculate_atr(df_clean)

    for idx, row in df_clean.iterrows():
        current_time = row["timestamp"]
        regime = get_regime(row, config)

        if position:
            should_exit, reason = check_exit_signal(row, position, config, bb_min_profit)
            if should_exit:
                position.exit_time = current_time
                position.exit_price = row["close"]
                position.exit_reason = reason
                gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
                position.pnl_pct = gross_pnl
                position.pnl_net = gross_pnl - (FEE_RATE * 2)
                trades.append(position)
                position = None
                cooldown_until = current_time + timedelta(minutes=30)
        else:
            if cooldown_until and current_time < cooldown_until:
                continue

            # 레짐 필터
            if allowed_regimes and regime not in allowed_regimes:
                continue

            if not check_entry_signal(row, regime, config, df_clean, idx):
                continue

            # FVG 필터
            if use_fvg:
                atr_val = atr_series.iloc[idx] if pd.notna(atr_series.iloc[idx]) else 0
                me = _compute_me_at_entry_phase2(df_clean.iloc[:idx + 1], atr_val)
                if not me["has_fvg_nearby"]:
                    continue

            regime_config_dict = config.REGIMES.get(regime, {})
            size_ratio = regime_config_dict.get("position_size_ratio", 0.0)
            symbol_multiplier = config.get_symbol_position_multiplier(symbol)
            effective_ratio = float(size_ratio) * float(symbol_multiplier)
            if effective_ratio <= 0:
                continue

            pos_size = BASE_POSITION_SIZE * effective_ratio
            position = TradeME(
                symbol=symbol, regime=regime,
                entry_time=current_time, entry_price=row["close"],
                position_size=pos_size, high_water_mark=row["close"],
            )

    if position and len(df_clean) > 0:
        last_row = df_clean.iloc[-1]
        position.exit_time = last_row["timestamp"]
        position.exit_price = last_row["close"]
        position.exit_reason = "END"
        gross_pnl = (position.exit_price - position.entry_price) / position.entry_price
        position.pnl_pct = gross_pnl
        position.pnl_net = gross_pnl - (FEE_RATE * 2)
        trades.append(position)

    return trades


async def run_compare_regime_filter(config: StrategyConfig, days: int = 365):
    """레짐별 필터링 효과 + FVG 조합 비교."""
    market_data = {}
    for symbol in config.SYMBOLS:
        df = await load_market_data(symbol, days=days)
        if not df.empty and len(df) >= 200:
            market_data[symbol] = df

    print("=" * 130)
    print("레짐 필터 검증: BEAR 진입 차단 + FVG 필터 조합")
    print("=" * 130)
    for sym, df_data in market_data.items():
        data_days = len(df_data) / 24
        print(f"  {sym}: {len(df_data)}봉 ({data_days:.0f}일)")
    print(f"시나리오: {len(REGIME_FILTER_SCENARIOS)}개")
    print()

    results = []
    for sc_name, sc_desc, use_fvg, allowed_regimes, bb_guard in REGIME_FILTER_SCENARIOS:
        print(f"  시뮬레이션 중: {sc_desc}...", flush=True)
        all_trades: List[TradeME] = []
        for symbol, df_data in market_data.items():
            trades = simulate_trades_regime_filter(
                df_data, config, symbol, use_fvg, allowed_regimes, bb_guard,
            )
            all_trades.extend(trades)

        total = len(all_trades)
        wins = [t for t in all_trades if t.pnl_net and t.pnl_net > 0]
        losses = [t for t in all_trades if t.pnl_net and t.pnl_net <= 0]
        total_pnl = sum(t.pnl_net for t in all_trades if t.pnl_net) * 100
        total_profit = sum(t.pnl_net * t.position_size for t in all_trades if t.pnl_net)
        win_rate = len(wins) / total * 100 if total > 0 else 0
        avg_win = (sum(t.pnl_net for t in wins) / len(wins) * 100) if wins else 0
        avg_loss = (sum(t.pnl_net for t in losses) / len(losses) * 100) if losses else 0

        baseline_count = results[0]["total"] if results else total
        filter_rate = (1 - total / baseline_count) * 100 if baseline_count > 0 and results else 0

        reasons = {}
        for t in all_trades:
            r = t.exit_reason or "UNKNOWN"
            reasons[r] = reasons.get(r, 0) + 1

        regime_counts = {}
        for t in all_trades:
            regime_counts[t.regime] = regime_counts.get(t.regime, 0) + 1

        # 거래당 기대값
        ev_per_trade = (total_pnl / total) if total > 0 else 0

        results.append({
            "name": sc_name, "desc": sc_desc, "total": total, "win_rate": win_rate,
            "total_pnl": total_pnl, "total_profit": total_profit,
            "avg_win": avg_win, "avg_loss": avg_loss, "filter_rate": filter_rate,
            "reasons": reasons, "regime_counts": regime_counts,
            "ev": ev_per_trade,
        })

    # ── 결과 테이블 ──
    print()
    print("-" * 130)
    header = (
        f"{'시나리오':<22} | {'거래':>5} | {'승률':>7} | {'누적PnL':>10} | {'예상수익':>13} | "
        f"{'avg_W':>7} | {'avg_L':>7} | {'EV/건':>8} | {'필터율':>7}"
    )
    print(header)
    print("-" * 130)
    for r in results:
        pnl_marker = " ★" if r["total_pnl"] > 0 else ""
        print(
            f"{r['desc']:<22} | {r['total']:>5} | {r['win_rate']:>6.1f}% | "
            f"{r['total_pnl']:>+9.2f}% | {r['total_profit']:>12,.0f}원 | "
            f"{r['avg_win']:>+6.2f}% | {r['avg_loss']:>+6.2f}% | "
            f"{r['ev']:>+7.3f}% | {r['filter_rate']:>6.1f}%{pnl_marker}"
        )

    # ── 청산 사유 분포 ──
    print()
    print("-" * 130)
    print("청산 사유 분포:")
    print("-" * 130)
    all_reasons = sorted({r for res in results for r in res["reasons"]})
    header = f"{'시나리오':<22}"
    for reason in all_reasons:
        header += f" | {reason:>14}"
    print(header)
    print("-" * 130)
    for r in results:
        line = f"{r['desc']:<22}"
        for reason in all_reasons:
            cnt = r["reasons"].get(reason, 0)
            line += f" | {cnt:>14}"
        print(line)

    # ── 레짐별 거래 분포 ──
    print()
    print("-" * 130)
    print("레짐별 거래 수:")
    print("-" * 130)
    all_regimes = sorted({r for res in results for r in res["regime_counts"]})
    header = f"{'시나리오':<22}"
    for regime in all_regimes:
        header += f" | {regime:>10}"
    print(header)
    print("-" * 130)
    for r in results:
        line = f"{r['desc']:<22}"
        for regime in all_regimes:
            cnt = r["regime_counts"].get(regime, 0)
            line += f" | {cnt:>10}"
        print(line)

    print()
    print("=" * 130)
    print("★ = 누적 PnL 양수 (수익)")
    print("EV/건 = 거래당 기대값 (양수면 수익 전략)")
    print("=" * 130)


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
    parser.add_argument("--me-phase2", action="store_true",
                        help="Phase 1-2: 구조적 청산 + 캡 역산 + BE 방어 비교 모드")
    parser.add_argument("--smc-backtest", action="store_true",
                        help="SMC 풀백 진입 (BOS+FVG/OB) 비교 모드 — Mean-reversion 대비 검증")
    parser.add_argument("--fvg-hybrid", action="store_true",
                        help="A안 v2: RSI/BB + FVG 필터 + 적응형 SL 하이브리드 비교 모드")
    parser.add_argument("--regime-filter", action="store_true",
                        help="레짐 필터 검증: BEAR 차단 + FVG 조합 효과 비교")
    parser.add_argument("--days", type=int, default=365,
                        help="백테스트 데이터 기간 (일, 기본 365)")
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

    # Phase 1-2: 구조적 청산 비교 모드
    if args.me_phase2:
        await run_compare_me_phase2(config, days=args.days)
        return

    # SMC 풀백 진입 비교 모드
    if args.smc_backtest:
        await run_compare_smc(config, days=args.days)
        return

    # A안 v2: FVG 하이브리드 비교 모드
    if args.fvg_hybrid:
        await run_compare_fvg_hybrid(config, days=args.days)
        return

    # 레짐 필터 검증
    if args.regime_filter:
        await run_compare_regime_filter(config, days=args.days)
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
