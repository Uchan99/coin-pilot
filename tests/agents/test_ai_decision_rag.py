from datetime import datetime, timezone

from src.agents.ai_decision_rag import (
    build_strategy_reference_lines,
    render_ai_decision_rag_text,
)
from src.agents.ai_decision_replay import build_replay_sample_from_signal_info
from src.agents.analyst import build_analyst_rag_reference_block


def test_build_strategy_reference_lines_returns_regime_specific_context():
    lines = build_strategy_reference_lines("SIDEWAYS")

    assert len(lines) >= 3
    assert len(lines) <= 4
    joined = "\n".join(lines)
    assert "Rule Engine" in joined
    assert "SIDEWAYS" in joined
    assert "단일 포지션 한도" not in joined


def test_render_ai_decision_rag_text_places_cases_before_strategy():
    text = render_ai_decision_rag_text(
        strategy_lines=["전략 1", "전략 2"],
        case_lines=["사례 1", "사례 2"],
    )

    assert text.index("[과거 사례 요약]") < text.index("[전략 문서 핵심]")
    assert "사례 1" in text
    assert "전략 1" in text


def test_build_analyst_rag_reference_block_includes_source_summary():
    block = build_analyst_rag_reference_block(
        {
            "text": "[과거 사례 요약]\n- test case\n\n[전략 문서 핵심]\n- test line",
            "source_summary": ["strategy:4", "cases:2"],
        }
    )

    assert "전략/과거사례 RAG" in block
    assert "strategy:4" in block
    assert "test line" in block
    assert "Rule Engine을 뒤집기 위한 근거가 아니라" in block
    assert "RSI, 거래량, MA, 볼린저밴드 임계치" in block


def test_build_replay_sample_from_signal_info_restores_market_context():
    sample = build_replay_sample_from_signal_info(
        sample_id="sample-1",
        symbol="KRW-BTC",
        strategy_name="AdaptiveMeanReversion",
        regime="SIDEWAYS",
        created_at=datetime.now(timezone.utc),
        signal_info={
            "close": 100,
            "regime": "SIDEWAYS",
            "market_context": [
                {"timestamp": "2026-03-01T00:00:00+00:00", "open": 1, "high": 2, "low": 0.5, "close": 1.5}
            ],
        },
    )

    assert sample is not None
    assert sample.symbol == "KRW-BTC"
    assert sample.indicators["close"] == 100
    assert sample.market_context[0]["timestamp"] == "2026-03-01T00:00:00+00:00"


def test_build_replay_sample_from_signal_info_skips_missing_context():
    sample = build_replay_sample_from_signal_info(
        sample_id="sample-2",
        symbol="KRW-BTC",
        strategy_name="AdaptiveMeanReversion",
        regime="SIDEWAYS",
        created_at=datetime.now(timezone.utc),
        signal_info={"close": 100},
    )

    assert sample is None
