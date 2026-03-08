import pytest

import src.analytics.exit_performance as exit_performance_module
from src.analytics.exit_performance import ExitPerformanceAnalyzer
from src.analytics.rule_funnel import RuleFunnelAnalyzer


@pytest.mark.asyncio
async def test_build_weekly_report_payload_includes_rule_funnel(monkeypatch):
    class DummyLLM:
        pass

    monkeypatch.setattr(exit_performance_module, "ChatOpenAI", lambda *args, **kwargs: DummyLLM())

    analyzer = ExitPerformanceAnalyzer(lambda: None)

    async def fake_summarize_period(days: int = 7):
        return {
            "period_days": days,
            "period_start": "2026-03-01T00:00:00+00:00",
            "period_end": "2026-03-08T00:00:00+00:00",
            "total_sells": 24,
            "by_exit_reason": {"TIME_LIMIT": {"count": 10, "avg_pnl_pct": -1.2, "avg_post_24h_pct": -0.4}},
            "by_regime": {"BULL": {"count": 12}},
        }

    async def fake_funnel_summarize(self, days: int = 7):
        return {
            "period_days": days,
            "period_start": "2026-03-01T00:00:00+00:00",
            "period_end": "2026-03-08T00:00:00+00:00",
            "by_regime": {
                "BULL": {
                    "rule_pass": {"count": 8, "unique_symbols": 2},
                    "risk_reject": {"count": 3, "unique_symbols": 2},
                    "ai_prefilter_reject": {"count": 2, "unique_symbols": 1},
                    "ai_guardrail_block": {"count": 1, "unique_symbols": 1},
                    "ai_confirm": {"count": 1, "unique_symbols": 1},
                    "ai_reject": {"count": 2, "unique_symbols": 1},
                }
            },
            "totals_by_stage": {},
            "ratios_by_regime": {},
            "top_reasons": [],
        }

    async def fake_llm_summary(summary, suggestions, *, funnel_summary=None, funnel_suggestions=None):
        assert funnel_summary is not None
        assert funnel_summary["by_regime"]["BULL"]["rule_pass"]["count"] == 8
        assert funnel_suggestions == ["funnel suggestion"]
        return "weekly summary"

    monkeypatch.setattr(analyzer, "summarize_period", fake_summarize_period)
    monkeypatch.setattr(RuleFunnelAnalyzer, "summarize_period", fake_funnel_summarize)
    monkeypatch.setattr(
        RuleFunnelAnalyzer,
        "generate_review_suggestions_from_summary",
        staticmethod(lambda *args, **kwargs: ["funnel suggestion"]),
    )
    monkeypatch.setattr(analyzer, "_generate_llm_summary", fake_llm_summary)

    payload = await analyzer.build_weekly_report_payload(days=7, min_samples=20)

    assert payload["rule_funnel"]["by_regime"]["BULL"]["ai_confirm"]["count"] == 1
    assert payload["rule_funnel_suggestions"] == ["funnel suggestion"]
    assert payload["summary"] == "weekly summary"
