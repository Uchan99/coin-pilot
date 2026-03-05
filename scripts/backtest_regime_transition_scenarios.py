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
    win_rate_pct: float
    total_pnl_pct: float
    total_profit_krw: float
    avg_profit_krw_per_trade: float
    avg_win_krw: float
    avg_loss_krw_abs: float
    reward_risk_ratio: float
    profit_factor: float
    max_drawdown_krw: float


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


SCENARIOS: dict[str, Callable[[StrategyConfig], None]] = {
    "baseline": _configure_baseline,
    "transition_sensitive": _configure_transition_sensitive,
    "bull_entry_relaxed": _configure_bull_entry_relaxed,
    "exit_rr_rebalanced": _configure_exit_rr_rebalanced,
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
        win_rate_pct=win_rate,
        total_pnl_pct=total_pnl_pct,
        total_profit_krw=total_profit,
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
    for scenario_name, scenario_fn in SCENARIOS.items():
        scenario_cfg = copy.deepcopy(base_config)
        scenario_fn(scenario_cfg)

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
            win_rate_pct=("win_rate_pct", "mean"),
            total_pnl_pct=("total_pnl_pct", "sum"),
            total_profit_krw=("total_profit_krw", "sum"),
            avg_profit_krw_per_trade=("avg_profit_krw_per_trade", "mean"),
            reward_risk_ratio=("reward_risk_ratio", "mean"),
            profit_factor=("profit_factor", "mean"),
            max_drawdown_krw=("max_drawdown_krw", "sum"),
        )
        .sort_values(by="total_profit_krw", ascending=False)
    )

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
