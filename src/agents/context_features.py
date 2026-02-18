from typing import Any, Dict, List, Tuple

import pandas as pd


def build_market_context(hourly_df: pd.DataFrame, target_candles: int = 24) -> List[Dict[str, Any]]:
    """
    AI 분석용 1시간봉 컨텍스트를 생성합니다.
    """
    if hourly_df is None or hourly_df.empty:
        return []

    context_df = hourly_df.tail(max(1, int(target_candles))).copy().reset_index()
    if "index" in context_df.columns and "timestamp" not in context_df.columns:
        context_df = context_df.rename(columns={"index": "timestamp"})

    if "timestamp" in context_df.columns:
        context_df["timestamp"] = context_df["timestamp"].apply(
            lambda ts: ts.isoformat() if hasattr(ts, "isoformat") else ts
        )

    return context_df.to_dict(orient="records")


def compute_bear_context_features(hourly_df: pd.DataFrame, window: int = 8) -> Dict[str, float]:
    """
    BEAR 레짐에서 AI 판단 보조용 요약 피처를 계산합니다.
    """
    default = {
        "bear_downtrend_ratio_8h": 0.0,
        "bear_volume_recovery_ratio_8h": 1.0,
        "bear_rebound_from_recent_low_pct_8h": 0.0,
    }
    if hourly_df is None or len(hourly_df) < 2:
        return default

    tail = hourly_df.tail(max(2, int(window))).copy()
    closes = tail["close"].astype(float)
    volumes = tail["volume"].astype(float)

    diffs = closes.diff().dropna()
    downtrend_ratio = float((diffs < 0).mean()) if len(diffs) > 0 else 0.0

    recent_low = float(closes.min())
    current_close = float(closes.iloc[-1])
    rebound_pct = ((current_close - recent_low) / recent_low * 100) if recent_low > 0 else 0.0

    prev_avg_vol = float(volumes.iloc[:-1].mean()) if len(volumes) > 1 else 0.0
    volume_recovery_ratio = float(volumes.iloc[-1] / prev_avg_vol) if prev_avg_vol > 0 else 1.0

    return {
        "bear_downtrend_ratio_8h": round(downtrend_ratio, 4),
        "bear_volume_recovery_ratio_8h": round(volume_recovery_ratio, 4),
        "bear_rebound_from_recent_low_pct_8h": round(rebound_pct, 4),
    }


def should_run_ai_analysis(
    regime: str,
    indicators: Dict[str, Any],
    market_context_len: int,
    entry_config: Dict[str, Any] | None = None,
) -> Tuple[bool, str]:
    """
    명백한 노이즈 케이스를 AI 호출 전에 필터링합니다.
    """
    cfg = entry_config or {}

    if not cfg.get("ai_prefilter_enabled", True):
        return True, ""

    min_context = int(cfg.get("ai_prefilter_min_context_candles", 12))
    if market_context_len < min_context:
        return False, f"AI 컨텍스트 부족 ({market_context_len} < {min_context})"

    if regime != "BEAR":
        return True, ""

    max_downtrend_ratio = float(cfg.get("ai_prefilter_max_downtrend_ratio", 0.85))
    min_rebound_pct = float(cfg.get("ai_prefilter_min_rebound_pct", 0.4))
    min_volume_recovery = float(cfg.get("ai_prefilter_min_volume_recovery_ratio", 0.7))

    downtrend_ratio = float(indicators.get("bear_downtrend_ratio_8h", 0.0))
    rebound_pct = float(indicators.get("bear_rebound_from_recent_low_pct_8h", 0.0))
    volume_recovery = float(indicators.get("bear_volume_recovery_ratio_8h", 1.0))

    if downtrend_ratio >= max_downtrend_ratio and rebound_pct < min_rebound_pct:
        return (
            False,
            (
                "Falling knife pre-filter: "
                f"downtrend={downtrend_ratio:.2f}, rebound={rebound_pct:.2f}%"
            ),
        )

    if volume_recovery < min_volume_recovery:
        return False, f"Volume recovery pre-filter: {volume_recovery:.2f} < {min_volume_recovery:.2f}"

    return True, ""
