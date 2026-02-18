import pandas as pd

from src.agents.context_features import (
    build_market_context,
    compute_bear_context_features,
    should_run_ai_analysis,
)


def _hourly_df() -> pd.DataFrame:
    idx = pd.date_range("2026-02-18 00:00:00+00:00", periods=10, freq="1h")
    return pd.DataFrame(
        {
            "open": [100, 99, 98, 97, 96, 95, 95, 96, 97, 98],
            "high": [101, 100, 99, 98, 97, 96, 96, 97, 98, 99],
            "low": [99, 98, 97, 96, 95, 94, 94, 95, 96, 97],
            "close": [100, 99, 98, 97, 96, 95, 95, 96, 97, 98],
            "volume": [10, 12, 11, 10, 9, 8, 8, 9, 10, 14],
        },
        index=idx,
    )


def test_build_market_context_contains_timestamp():
    df = _hourly_df()
    context = build_market_context(df, target_candles=4)

    assert len(context) == 4
    assert "timestamp" in context[0]
    assert isinstance(context[0]["timestamp"], str)


def test_compute_bear_context_features():
    df = _hourly_df()
    features = compute_bear_context_features(df, window=8)

    assert "bear_downtrend_ratio_8h" in features
    assert "bear_volume_recovery_ratio_8h" in features
    assert "bear_rebound_from_recent_low_pct_8h" in features
    assert 0.0 <= features["bear_downtrend_ratio_8h"] <= 1.0
    assert features["bear_rebound_from_recent_low_pct_8h"] >= 0.0


def test_should_run_ai_analysis_rejects_short_context():
    ok, reason = should_run_ai_analysis(
        regime="BEAR",
        indicators={},
        market_context_len=6,
        entry_config={"ai_prefilter_min_context_candles": 12},
    )
    assert ok is False
    assert "컨텍스트 부족" in reason


def test_should_run_ai_analysis_rejects_falling_knife():
    ok, reason = should_run_ai_analysis(
        regime="BEAR",
        indicators={
            "bear_downtrend_ratio_8h": 0.9,
            "bear_rebound_from_recent_low_pct_8h": 0.2,
            "bear_volume_recovery_ratio_8h": 1.0,
        },
        market_context_len=24,
        entry_config={
            "ai_prefilter_max_downtrend_ratio": 0.85,
            "ai_prefilter_min_rebound_pct": 0.4,
            "ai_prefilter_min_context_candles": 12,
        },
    )
    assert ok is False
    assert "Falling knife pre-filter" in reason


def test_should_run_ai_analysis_accepts_valid_case():
    ok, reason = should_run_ai_analysis(
        regime="BEAR",
        indicators={
            "bear_downtrend_ratio_8h": 0.5,
            "bear_rebound_from_recent_low_pct_8h": 1.2,
            "bear_volume_recovery_ratio_8h": 1.1,
        },
        market_context_len=24,
        entry_config={
            "ai_prefilter_max_downtrend_ratio": 0.85,
            "ai_prefilter_min_rebound_pct": 0.4,
            "ai_prefilter_min_volume_recovery_ratio": 0.7,
            "ai_prefilter_min_context_candles": 12,
        },
    )
    assert ok is True
    assert reason == ""
