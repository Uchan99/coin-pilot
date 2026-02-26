from src.agents.analyst import (
    build_rule_boundary_audit_note,
    detect_rule_revalidation_terms,
    contains_rule_revalidation_reasoning,
    extract_candle_pattern_features,
    sanitize_market_context_for_analyst,
)
from src.agents.prompts import get_analyst_prompt


def test_get_analyst_prompt_excludes_rule_engine_threshold_fields():
    prompt = get_analyst_prompt(
        {
            "regime": "SIDEWAYS",
            "symbol": "KRW-BTC",
            "close": 100000000,
            "ai_context_candles": 24,
            "pattern_direction": "DOWN",
            "net_change_pct_6h": -1.2,
            "bearish_streak_6h": 3,
            "bullish_streak_6h": 0,
            "last_body_to_range_ratio": 0.7,
            "last_upper_wick_ratio": 0.1,
            "last_lower_wick_ratio": 0.2,
            "range_expansion_ratio_6h": 1.5,
            "rsi": 42,
            "rsi_short": 38,
            "ma_trend": 99999999,
            "vol_ratio": 0.8,
        }
    )

    assert "RSI(14)" not in prompt
    assert "RSI(7)" not in prompt
    assert "MA(20)" not in prompt
    assert "거래량 비율" not in prompt
    assert "캔들 패턴 보조 피처" in prompt


def test_contains_rule_revalidation_reasoning_detects_rule_terms():
    assert contains_rule_revalidation_reasoning("RSI가 48로 과매도 미도달이라 진입 부적절")
    assert contains_rule_revalidation_reasoning("거래량 부족 + MA20 하회로 반등 신뢰도 낮음")
    assert not contains_rule_revalidation_reasoning(
        "최근 3개 음봉 연속 후 긴 윗꼬리가 출현해 상승 지속성이 약합니다."
    )


def test_detect_rule_revalidation_terms_returns_canonical_names():
    terms = detect_rule_revalidation_terms("RSI와 MA20, 거래량, 볼린저밴드 하단을 다시 점검했습니다.")
    assert "rsi" in terms
    assert "ma20" in terms
    assert "volume" in terms
    assert "bollinger" in terms


def test_build_rule_boundary_audit_note_keeps_original_preview():
    original = (
        "RSI가 낮고 MA20 하회 구간이라 신호를 재검증했습니다. "
        "최근 4개 캔들의 꼬리 패턴과 거래량 변화를 함께 고려하면 변동성 확대 가능성이 큽니다."
    )
    merged = build_rule_boundary_audit_note(original, matched_terms=["rsi", "ma20"], preview_len=500)

    assert "[BoundaryAudit]" in merged
    assert "terms=rsi,ma20" in merged
    assert "최근 4개 캔들" in merged


def test_build_rule_boundary_audit_note_truncates_long_text():
    long_text = "A" * 2000
    merged = build_rule_boundary_audit_note(long_text, matched_terms=["rsi"], preview_len=100)

    assert "...(후략)" in merged
    assert len(merged) < 500


def test_sanitize_market_context_for_analyst_drops_volume_and_limits_count():
    market_context = [
        {
            "timestamp": f"2026-02-21T{hour:02d}:00:00+00:00",
            "open": 100 + hour,
            "high": 101 + hour,
            "low": 99 + hour,
            "close": 100.5 + hour,
            "volume": 1000 + hour,
        }
        for hour in range(30)
    ]
    sanitized = sanitize_market_context_for_analyst(market_context, limit=24)

    assert len(sanitized) == 24
    assert "volume" not in sanitized[-1]
    assert sanitized[0]["timestamp"] == "2026-02-21T06:00:00+00:00"


def test_extract_candle_pattern_features_returns_expected_direction_and_keys():
    context = [
        {"timestamp": "t1", "open": 100, "high": 103, "low": 99, "close": 102},
        {"timestamp": "t2", "open": 102, "high": 104, "low": 101, "close": 103},
        {"timestamp": "t3", "open": 103, "high": 106, "low": 102, "close": 105},
        {"timestamp": "t4", "open": 105, "high": 107, "low": 104, "close": 106},
        {"timestamp": "t5", "open": 106, "high": 108, "low": 105, "close": 107},
        {"timestamp": "t6", "open": 107, "high": 109, "low": 106, "close": 108},
    ]
    features = extract_candle_pattern_features(context)

    assert features["pattern_direction"] == "UP"
    assert features["bullish_streak_6h"] >= 1
    assert 0.0 <= features["last_body_to_range_ratio"] <= 1.0
    assert 0.0 <= features["last_upper_wick_ratio"] <= 1.0
    assert 0.0 <= features["last_lower_wick_ratio"] <= 1.0
