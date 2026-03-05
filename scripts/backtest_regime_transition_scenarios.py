"""
레짐 전환 구간 전략 시나리오 비교 백테스트
파일: scripts/backtest_regime_transition_scenarios.py
실행 예시:
  PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 120
  PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --symbols KRW-BTC,KRW-ETH --output /tmp/regime_scenarios.csv

목적:
- baseline(현재 전략) 대비 전환 민감도/진입/청산 완화 시나리오를 정량 비교한다.
- 실운영 핫픽스 적용 전에 "수익-리스크 동시 개선" 여부를 빠르게 검증한다.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

from src.config.strategy import StrategyConfig, get_config
from scripts.backtest_v3 import Trade, load_market_data, simulate_trades


@dataclass
class ScenarioResult:
    name: str
    symbol: str
    trades: int
    wins_count: int
    losses_count: int
    win_rate_pct: float
    total_pnl_pct: float
    total_profit_krw: float
    gross_profit_krw: float
    gross_loss_abs_krw: float
    avg_profit_krw_per_trade: float
    avg_win_krw: float
    avg_loss_krw_abs: float
    reward_risk_ratio: float
    profit_factor: float
    max_drawdown_krw: float


@dataclass
class ScenarioSpec:
    """
    시나리오 정의.
    - configure: 전략 파라미터(레짐/진입/청산) 수정 함수
    - symbol_size_multipliers: 심볼별 포지션 배율 오버라이드(미지정 심볼은 1.0)
    """
    configure: Callable[[StrategyConfig], None]
    symbol_size_multipliers: dict[str, float] | None = None


def _configure_baseline(cfg: StrategyConfig) -> None:
    """기준선 시나리오: 현재 전략값 유지."""
    return


def _configure_transition_sensitive(cfg: StrategyConfig) -> None:
    """
    전환 민감도 완화 시나리오.
    - MA50/MA200 이격 임계값을 완화해 BULL/BEAR 전환을 조금 더 빠르게 인식한다.
    """
    cfg.BULL_THRESHOLD_PCT = 1.5
    cfg.BEAR_THRESHOLD_PCT = -1.5


def _configure_bull_entry_relaxed(cfg: StrategyConfig) -> None:
    """
    상승장 진입 완화 시나리오.
    - BULL 구간 RSI 기준을 소폭 완화해 전환 초반 진입 누락을 줄이는 실험.
    """
    bull_entry = cfg.REGIMES["BULL"]["entry"]
    bull_entry["rsi_14_max"] = 55
    bull_entry["rsi_7_trigger"] = 40
    bull_entry["rsi_7_recover"] = 40


def _configure_exit_rr_rebalanced(cfg: StrategyConfig) -> None:
    """
    청산 손익비 재조정 시나리오.
    - 평균 손실 대비 평균 이익을 키우기 위한 보수적 조정안.
    """
    for regime in ("BULL", "SIDEWAYS", "BEAR"):
        exit_cfg = cfg.REGIMES[regime]["exit"]
        exit_cfg["take_profit_pct"] = max(exit_cfg["take_profit_pct"], 0.04)
        exit_cfg["stop_loss_pct"] = min(exit_cfg["stop_loss_pct"], 0.03)


SYMBOL_REBALANCED_MULTIPLIERS = {
    # 요청 반영:
    # - DOGE/XRP 비중 축소
    # - BTC/ETH/SOL 비중 확대
    # - 배율 합(1.2*3 + 0.7*2 = 5.0)을 맞춰 총 리스크 레벨을 최대한 유지
    "KRW-BTC": 1.2,
    "KRW-ETH": 1.2,
    "KRW-SOL": 1.2,
    "KRW-XRP": 0.7,
    "KRW-DOGE": 0.7,
}


SCENARIOS: dict[str, ScenarioSpec] = {
    "baseline": ScenarioSpec(configure=_configure_baseline),
    "transition_sensitive": ScenarioSpec(configure=_configure_transition_sensitive),
    "bull_entry_relaxed": ScenarioSpec(configure=_configure_bull_entry_relaxed),
    "exit_rr_rebalanced": ScenarioSpec(configure=_configure_exit_rr_rebalanced),
    "symbol_rebalanced": ScenarioSpec(
        configure=_configure_baseline,
        symbol_size_multipliers=SYMBOL_REBALANCED_MULTIPLIERS,
    ),
    "transition_sensitive_symbol_rebalanced": ScenarioSpec(
        configure=_configure_transition_sensitive,
        symbol_size_multipliers=SYMBOL_REBALANCED_MULTIPLIERS,
    ),
}


def _trade_profit_krw(trade: Trade) -> float:
    if trade.pnl_net is None:
        return 0.0
    return trade.pnl_net * trade.position_size


def _compute_max_drawdown_krw(trades: list[Trade]) -> float:
    """
    실현손익 누적곡선 기준 최대 낙폭(절대 KRW)을 계산한다.
    - 백테스트가 포지션 단위로 종료손익을 기록하므로,
      종료 시점 순서대로 누적해 peak-to-trough 낙폭을 측정한다.
    """
    ordered = sorted(
        (t for t in trades if t.exit_time is not None),
        key=lambda t: t.exit_time,  # type: ignore[arg-type]
    )
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    for trade in ordered:
        equity += _trade_profit_krw(trade)
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return max_dd


def _analyze_trades(name: str, symbol: str, trades: list[Trade]) -> ScenarioResult:
    total_trades = len(trades)
    profits = [_trade_profit_krw(t) for t in trades]
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p <= 0]

    total_profit = sum(profits)
    total_pnl_pct = sum((t.pnl_net or 0.0) for t in trades) * 100.0
    win_rate = (len(wins) / total_trades * 100.0) if total_trades else 0.0
    avg_trade = (total_profit / total_trades) if total_trades else 0.0
    avg_win = (sum(wins) / len(wins)) if wins else 0.0
    avg_loss_abs = (abs(sum(losses) / len(losses))) if losses else 0.0
    reward_risk = (avg_win / avg_loss_abs) if avg_loss_abs > 0 else 0.0

    gross_profit = sum(wins)
    gross_loss_abs = abs(sum(losses))
    profit_factor = (gross_profit / gross_loss_abs) if gross_loss_abs > 0 else 0.0
    max_dd = _compute_max_drawdown_krw(trades)

    return ScenarioResult(
        name=name,
        symbol=symbol,
        trades=total_trades,
        wins_count=len(wins),
        losses_count=len(losses),
        win_rate_pct=win_rate,
        total_pnl_pct=total_pnl_pct,
        total_profit_krw=total_profit,
        gross_profit_krw=gross_profit,
        gross_loss_abs_krw=gross_loss_abs,
        avg_profit_krw_per_trade=avg_trade,
        avg_win_krw=avg_win,
        avg_loss_krw_abs=avg_loss_abs,
        reward_risk_ratio=reward_risk,
        profit_factor=profit_factor,
        max_drawdown_krw=max_dd,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="레짐 전환 구간 시나리오 백테스트 비교"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="백테스트 데이터 기간(일). 기본값: 90",
    )
    parser.add_argument(
        "--symbols",
        type=str,
        default="",
        help="대상 심볼 콤마구분 (예: KRW-BTC,KRW-ETH). 미지정 시 전략 기본 심볼 사용",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="결과 CSV 출력 경로(옵션)",
    )
    return parser.parse_args()


async def _load_frames(symbols: list[str], days: int) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = await load_market_data(symbol, days=days)
        frames[symbol] = frame
    return frames


async def main() -> None:
    args = _parse_args()
    base_config = get_config()
    symbols = (
        [s.strip() for s in args.symbols.split(",") if s.strip()]
        if args.symbols
        else list(base_config.SYMBOLS)
    )
    frames = await _load_frames(symbols, args.days)

    results: list[ScenarioResult] = []
    for scenario_name, scenario_spec in SCENARIOS.items():
        scenario_cfg = copy.deepcopy(base_config)
        scenario_spec.configure(scenario_cfg)
        if scenario_spec.symbol_size_multipliers is not None:
            # backtest_v3가 config의 배율을 직접 적용하므로, 시나리오별 배율은
            # post-processing 곱이 아니라 설정 오버라이드로 주입한다.
            scenario_cfg.SYMBOL_POSITION_MULTIPLIERS = (
                scenario_spec.symbol_size_multipliers.copy()
            )

        for symbol in symbols:
            frame = frames.get(symbol)
            if frame is None or frame.empty:
                continue
            trades = simulate_trades(frame, scenario_cfg, symbol)
            results.append(_analyze_trades(scenario_name, symbol, trades))

    if not results:
        print("결과 없음: 데이터 또는 거래가 부족합니다.")
        return

    df = pd.DataFrame([r.__dict__ for r in results])
    agg = (
        df.groupby("name", as_index=False)
        .agg(
            trades=("trades", "sum"),
            wins_count=("wins_count", "sum"),
            losses_count=("losses_count", "sum"),
            total_pnl_pct=("total_pnl_pct", "sum"),
            total_profit_krw=("total_profit_krw", "sum"),
            gross_profit_krw=("gross_profit_krw", "sum"),
            gross_loss_abs_krw=("gross_loss_abs_krw", "sum"),
            max_drawdown_krw=("max_drawdown_krw", "sum"),
        )
    )
    # 심볼별 단순 평균이 아닌, 시나리오 전체 합계 기반 파생 지표를 계산한다.
    agg["win_rate_pct"] = (
        agg["wins_count"] / agg["trades"].where(agg["trades"] > 0, 1) * 100.0
    )
    agg["avg_profit_krw_per_trade"] = (
        agg["total_profit_krw"] / agg["trades"].where(agg["trades"] > 0, 1)
    )
    agg["avg_win_krw"] = (
        agg["gross_profit_krw"] / agg["wins_count"].where(agg["wins_count"] > 0, 1)
    )
    agg["avg_loss_krw_abs"] = (
        agg["gross_loss_abs_krw"]
        / agg["losses_count"].where(agg["losses_count"] > 0, 1)
    )
    agg["reward_risk_ratio"] = (
        agg["avg_win_krw"] / agg["avg_loss_krw_abs"].where(agg["avg_loss_krw_abs"] > 0, 1)
    )
    agg["profit_factor"] = (
        agg["gross_profit_krw"]
        / agg["gross_loss_abs_krw"].where(agg["gross_loss_abs_krw"] > 0, 1)
    )
    agg = agg[
        [
            "name",
            "trades",
            "win_rate_pct",
            "total_pnl_pct",
            "total_profit_krw",
            "avg_profit_krw_per_trade",
            "avg_win_krw",
            "avg_loss_krw_abs",
            "reward_risk_ratio",
            "profit_factor",
            "max_drawdown_krw",
        ]
    ].sort_values(by="total_profit_krw", ascending=False)

    print("\n=== Scenario Summary ===")
    print(agg.to_string(index=False))
    print("\n=== Scenario x Symbol ===")
    print(df.sort_values(by=["name", "symbol"]).to_string(index=False))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        agg.to_csv(out_path, index=False)
        print(f"\n[OK] summary csv saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
