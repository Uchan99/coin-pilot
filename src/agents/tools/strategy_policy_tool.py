from typing import Any, Dict

from src.config.strategy import get_config


def run_strategy_policy_tool() -> Dict[str, Any]:
    """
    현재 전략 설정(YAML/기본값)을 사람이 읽기 쉬운 정책 데이터로 반환합니다.
    """
    cfg = get_config()

    regime_exit: Dict[str, Dict[str, Any]] = {}
    for regime, section in cfg.REGIMES.items():
        exit_cfg = section.get("exit", {})
        regime_exit[regime] = {
            "take_profit_pct": float(exit_cfg.get("take_profit_pct", 0.0)) * 100.0,
            "stop_loss_pct": float(exit_cfg.get("stop_loss_pct", 0.0)) * 100.0,
            "trailing_stop_pct": float(exit_cfg.get("trailing_stop_pct", 0.0)) * 100.0,
            "trailing_stop_activation_pct": float(exit_cfg.get("trailing_stop_activation_pct", 0.0)) * 100.0,
            "rsi_overbought": int(exit_cfg.get("rsi_overbought", 0)),
            "rsi_exit_min_profit_pct": float(exit_cfg.get("rsi_exit_min_profit_pct", 0.0)) * 100.0,
            "time_limit_hours": int(exit_cfg.get("time_limit_hours", 0)),
        }

    risk_limits = {
        "max_position_size_pct": float(cfg.MAX_POSITION_SIZE) * 100.0,
        "max_daily_loss_pct": float(cfg.MAX_DAILY_LOSS) * 100.0,
        "max_daily_buy_count": int(cfg.MAX_DAILY_TRADES),
        "cooldown_after_losses": int(cfg.COOLDOWN_AFTER_CONSECUTIVE_LOSSES),
        "cooldown_hours": int(cfg.COOLDOWN_HOURS),
        "min_trade_interval_minutes": int(cfg.MIN_TRADE_INTERVAL_MINUTES),
    }

    return {
        "strategy_name": "Adaptive Mean Reversion (Regime-based)",
        "regime_exit_policy": regime_exit,
        "risk_limits": risk_limits,
    }
