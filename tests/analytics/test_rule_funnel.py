from src.analytics.rule_funnel import RuleFunnelAnalyzer


def _stage(count: int) -> dict:
    return {"count": count, "unique_symbols": 1}


def test_generate_review_suggestions_data_shortage():
    summary = {
        "by_regime": {
            "BULL": {
                "rule_pass": _stage(3),
                "risk_reject": _stage(0),
                "ai_prefilter_reject": _stage(0),
                "ai_guardrail_block": _stage(0),
                "ai_confirm": _stage(0),
                "ai_reject": _stage(0),
            }
        }
    }

    suggestions = RuleFunnelAnalyzer.generate_review_suggestions_from_summary(
        summary,
        target_regime="BULL",
        min_rule_pass=5,
    )

    assert len(suggestions) == 1
    assert "데이터 부족" in suggestions[0]


def test_generate_review_suggestions_detects_bull_bottlenecks():
    summary = {
        "by_regime": {
            "BULL": {
                "rule_pass": _stage(20),
                "risk_reject": _stage(11),
                "ai_prefilter_reject": _stage(9),
                "ai_guardrail_block": _stage(7),
                "ai_confirm": _stage(4),
                "ai_reject": _stage(10),
            },
            "SIDEWAYS": {
                "rule_pass": _stage(20),
                "risk_reject": _stage(2),
                "ai_prefilter_reject": _stage(2),
                "ai_guardrail_block": _stage(1),
                "ai_confirm": _stage(12),
                "ai_reject": _stage(4),
            },
        }
    }

    suggestions = RuleFunnelAnalyzer.generate_review_suggestions_from_summary(
        summary,
        target_regime="BULL",
        min_rule_pass=5,
    )
    joined = "\n".join(suggestions)

    assert "Risk reject 비중이 높음" in joined
    assert "AI prefilter reject 비중이 높음" in joined
    assert "AI guardrail block 비중이 높음" in joined
    assert "AI reject가 confirm보다 많음" in joined
    assert "SIDEWAYS" in joined
