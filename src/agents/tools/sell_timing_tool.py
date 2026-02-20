from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from src.agents.tools._db import fetch_all, fetch_one
from src.config.strategy import get_config
from src.engine.strategy import MeanReversionStrategy


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        dt = pd.to_datetime(value).to_pydatetime()
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _compute_rsi(prices: pd.Series, window: int = 14) -> Optional[float]:
    if len(prices) < window + 1:
        return None

    delta = prices.diff()
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)

    avg_gain = gains.rolling(window=window).mean().iloc[-1]
    avg_loss = losses.rolling(window=window).mean().iloc[-1]

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def _get_latest_regime(symbol: str) -> str:
    coin_symbol = symbol.split("-")[-1] if "-" in symbol else symbol
    row = fetch_one(
        """
        SELECT regime
        FROM regime_history
        WHERE coin_symbol = :coin_symbol
        ORDER BY detected_at DESC
        LIMIT 1
        """,
        {"coin_symbol": coin_symbol},
    )
    return str(row.get("regime")) if row and row.get("regime") else "UNKNOWN"


def _get_symbol_rsi14(symbol: str) -> Optional[float]:
    rows = fetch_all(
        """
        SELECT close_price
        FROM market_data
        WHERE symbol = :symbol
        ORDER BY timestamp DESC
        LIMIT 120
        """,
        {"symbol": symbol},
    )
    if not rows:
        return None

    series = pd.Series([float(r.get("close_price") or 0.0) for r in rows[::-1]])
    series = series[series > 0]
    if series.empty:
        return None
    return _compute_rsi(series, window=14)


def evaluate_sell_signals(
    *,
    current_price: float,
    entry_price: float,
    high_water_mark: Optional[float],
    rsi14: Optional[float],
    opened_at: Optional[datetime],
    exit_cfg: Dict[str, Any],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    단일 포지션의 매도 신호를 규칙 기반으로 평가합니다.

    한국어 유지보수 메모:
    - 이 함수는 "판단 근거를 재현 가능"하게 만드는 핵심 로직입니다.
    - 신호 우선순위는 실운영 엔진과 동일하게 손절/트레일링/익절/RSI/시간제한 순서를 따릅니다.
    - 데이터 부족 시 무리한 추천을 피하기 위해, 트리거 미충족으로 간주하고 경계 가격만 제공합니다.
    """
    if entry_price <= 0 or current_price <= 0:
        return {
            "recommendation": "데이터 부족",
            "signals": ["진입가 또는 현재가 데이터가 유효하지 않습니다."],
            "pnl_pct": None,
            "hold_hours": None,
            "thresholds": {},
        }

    now_utc = now or datetime.now(timezone.utc)
    pnl_pct = (current_price - entry_price) / entry_price * 100.0

    take_profit_pct = float(exit_cfg.get("take_profit_pct", 0.0)) * 100.0
    stop_loss_pct = float(exit_cfg.get("stop_loss_pct", 0.0)) * 100.0
    trailing_stop_pct = float(exit_cfg.get("trailing_stop_pct", 0.0))
    trailing_activation_pct = float(exit_cfg.get("trailing_stop_activation_pct", 0.0)) * 100.0
    rsi_overbought = int(exit_cfg.get("rsi_overbought", 70))
    rsi_exit_min_profit_pct = float(exit_cfg.get("rsi_exit_min_profit_pct", 0.0)) * 100.0
    time_limit_hours = int(exit_cfg.get("time_limit_hours", 0))

    hwm = high_water_mark if high_water_mark and high_water_mark > 0 else max(entry_price, current_price)
    trailing_stop_price = hwm * (1.0 - trailing_stop_pct)
    trailing_active = (pnl_pct >= trailing_activation_pct) or (hwm > entry_price * (1 + trailing_activation_pct / 100.0))

    hold_hours = None
    if opened_at is not None:
        hold_hours = max(0.0, (now_utc - opened_at).total_seconds() / 3600.0)

    trigger_signals: List[str] = []

    if pnl_pct <= -stop_loss_pct:
        trigger_signals.append(f"손절 기준 도달 ({pnl_pct:+.2f}% <= -{stop_loss_pct:.2f}%)")

    if trailing_active and current_price <= trailing_stop_price:
        trigger_signals.append(
            f"트레일링 스탑 트리거 (현재가 {current_price:,.0f} <= 기준가 {trailing_stop_price:,.0f})"
        )

    if pnl_pct >= take_profit_pct:
        trigger_signals.append(f"익절 기준 도달 ({pnl_pct:+.2f}% >= +{take_profit_pct:.2f}%)")

    if rsi14 is not None and rsi14 > rsi_overbought and pnl_pct >= rsi_exit_min_profit_pct:
        trigger_signals.append(
            f"RSI 과매수 청산 조건 충족 (RSI {rsi14:.1f} > {rsi_overbought}, 수익률 {pnl_pct:+.2f}%)"
        )

    if hold_hours is not None and time_limit_hours > 0 and hold_hours >= time_limit_hours:
        trigger_signals.append(f"보유 시간 제한 도달 ({hold_hours:.1f}h >= {time_limit_hours}h)")

    if trigger_signals:
        recommendation = "매도 고려"
    elif pnl_pct >= take_profit_pct * 0.7:
        recommendation = "분할익절 준비"
    elif pnl_pct <= -stop_loss_pct * 0.7:
        recommendation = "손절 경계"
    else:
        recommendation = "홀드/관찰"

    thresholds = {
        "take_profit_pct": take_profit_pct,
        "stop_loss_pct": stop_loss_pct,
        "trailing_activation_pct": trailing_activation_pct,
        "trailing_stop_price": trailing_stop_price,
        "rsi_overbought": rsi_overbought,
        "time_limit_hours": time_limit_hours,
    }

    return {
        "recommendation": recommendation,
        "signals": trigger_signals,
        "pnl_pct": pnl_pct,
        "hold_hours": hold_hours,
        "thresholds": thresholds,
        "rsi14": rsi14,
        "trailing_active": trailing_active,
    }


def run_sell_timing_tool() -> Dict[str, Any]:
    """
    현재 보유 포지션별로 "지금 매도해야 하는지"를 규칙 기반으로 분석합니다.
    """
    positions = fetch_all(
        """
        SELECT
            p.symbol,
            p.quantity,
            p.avg_price,
            p.high_water_mark,
            p.opened_at,
            p.regime AS entry_regime,
            m.close_price AS current_price
        FROM positions p
        LEFT JOIN (
            SELECT DISTINCT ON (symbol) symbol, close_price
            FROM market_data
            ORDER BY symbol, timestamp DESC
        ) m ON p.symbol = m.symbol
        ORDER BY p.symbol
        """
    )

    if not positions:
        return {
            "status": "NO_POSITION",
            "message": "현재 보유 포지션이 없어 매도 타이밍 분석 대상이 없습니다.",
            "positions": [],
        }

    cfg = get_config()
    strategy = MeanReversionStrategy(cfg)

    analyzed: List[Dict[str, Any]] = []

    for row in positions:
        symbol = str(row.get("symbol") or "")
        qty = float(row.get("quantity") or 0.0)
        entry_price = float(row.get("avg_price") or 0.0)
        current_price = float(row.get("current_price") or 0.0)
        hwm = float(row.get("high_water_mark") or 0.0)
        opened_at = _parse_dt(row.get("opened_at"))

        if not symbol or qty <= 0 or entry_price <= 0 or current_price <= 0:
            continue

        current_regime = _get_latest_regime(symbol)
        entry_regime = str(row.get("entry_regime") or current_regime or "SIDEWAYS")
        if entry_regime == "UNKNOWN":
            entry_regime = "SIDEWAYS"
        if current_regime == "UNKNOWN":
            current_regime = entry_regime

        adjusted_exit_cfg = strategy.get_adjusted_exit_config(entry_regime, current_regime)
        rsi14 = _get_symbol_rsi14(symbol)

        evaluation = evaluate_sell_signals(
            current_price=current_price,
            entry_price=entry_price,
            high_water_mark=hwm if hwm > 0 else None,
            rsi14=rsi14,
            opened_at=opened_at,
            exit_cfg=adjusted_exit_cfg,
        )

        analyzed.append(
            {
                "symbol": symbol,
                "quantity": qty,
                "entry_price": entry_price,
                "current_price": current_price,
                "entry_regime": entry_regime,
                "current_regime": current_regime,
                **evaluation,
            }
        )

    if not analyzed:
        return {
            "status": "NO_DATA",
            "message": "포지션 데이터는 있으나 분석 가능한 가격 데이터가 부족합니다.",
            "positions": [],
        }

    return {
        "status": "OK",
        "positions": analyzed,
        "summary": {
            "total_positions": len(analyzed),
            "sell_consider_count": sum(1 for p in analyzed if p["recommendation"] == "매도 고려"),
            "warning_count": sum(1 for p in analyzed if p["recommendation"] in {"매도 고려", "손절 경계"}),
        },
    }
