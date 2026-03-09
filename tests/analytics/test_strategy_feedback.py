import pytest

from src.analytics.strategy_feedback import StrategyFeedbackAnalyzer


def _stage(count: int) -> dict:
    return {"count": count, "unique_symbols": 1}


def test_determine_approval_tier_thresholds():
    assert StrategyFeedbackAnalyzer.determine_approval_tier(5) == "hold"
    assert StrategyFeedbackAnalyzer.determine_approval_tier(12) == "reviewable"
    assert StrategyFeedbackAnalyzer.determine_approval_tier(20) == "strong_approval"


def test_build_candidate_changes_skips_ops_bottleneck():
    analyzer = StrategyFeedbackAnalyzer(lambda: None)
    exit_summary = {
        "by_regime": {"SIDEWAYS": {"count": 16}},
        "by_exit_reason": {
            "TAKE_PROFIT": {"avg_post_4h_pct": 3.1},
        },
    }
    funnel_summary = {
        "top_reasons": [
            {"reason_code": "max_per_order", "count": 5},
        ]
    }

    candidates = analyzer._build_candidate_changes(
        exit_summary,
        funnel_summary,
        "reviewable",
    )

    assert candidates == []


@pytest.mark.asyncio
async def test_build_feedback_payload_uses_fallback_window_and_reviewable(monkeypatch):
    analyzer = StrategyFeedbackAnalyzer(lambda: None)
    called_days = []

    class FakeExitAnalyzer:
        def __init__(self, session_factory):
            self.session_factory = session_factory

        async def summarize_period(self, days: int = 7):
            called_days.append(days)
            if days == 7:
                return {
                    "period_days": 7,
                    "period_start": "2026-03-03T00:00:00+00:00",
                    "period_end": "2026-03-10T00:00:00+00:00",
                    "total_sells": 8,
                    "by_exit_reason": {},
                    "by_regime": {"SIDEWAYS": {"count": 8}},
                }
            if days == 14:
                return {
                    "period_days": 14,
                    "period_start": "2026-02-24T00:00:00+00:00",
                    "period_end": "2026-03-10T00:00:00+00:00",
                    "total_sells": 10,
                    "by_exit_reason": {},
                    "by_regime": {"SIDEWAYS": {"count": 10}},
                }
            return {
                "period_days": 30,
                "period_start": "2026-02-09T00:00:00+00:00",
                "period_end": "2026-03-10T00:00:00+00:00",
                "total_sells": 16,
                "by_exit_reason": {
                    "TAKE_PROFIT": {"count": 4, "avg_pnl_pct": 2.0, "avg_post_4h_pct": 3.5},
                },
                "by_regime": {"SIDEWAYS": {"count": 16}},
            }

    class FakeFunnelAnalyzer:
        def __init__(self, session_factory):
            self.session_factory = session_factory

        async def summarize_period(self, days: int = 7):
            assert days == 30
            return {
                "by_regime": {
                    "BULL": {
                        "rule_pass": _stage(6),
                        "risk_reject": _stage(1),
                        "ai_prefilter_reject": _stage(0),
                        "ai_guardrail_block": _stage(0),
                        "ai_confirm": _stage(2),
                        "ai_reject": _stage(1),
                    }
                },
                "top_reasons": [],
            }

        @staticmethod
        def generate_review_suggestions_from_summary(summary, *, target_regime="BULL", min_rule_pass=5):
            return ["funnel-ok"]

    async def fake_sell_sequence_metrics(days: int):
        assert days == 30
        return type(
            "SellMetrics",
            (),
            {
                "total_sells": 16,
                "avg_realized_pnl_pct": 1.2,
                "profit_factor": 1.15,
                "max_drawdown_pct": 1.4,
            },
        )()

    async def fake_ai_metrics(days: int):
        return {
            "total": 24,
            "reject_count": 8,
            "parse_fail_count": 0,
            "timeout_count": 0,
            "reject_rate_pct": 33.3,
            "reject_rate_delta_pct": 1.2,
        }

    async def fake_cost_metrics(days: int):
        return {
            "cost_usd": 0.12,
            "cost_delta_pct": 5.0,
            "provider_snapshot_count": 2,
        }

    monkeypatch.setattr("src.analytics.strategy_feedback.ExitPerformanceAnalyzer", FakeExitAnalyzer)
    monkeypatch.setattr("src.analytics.strategy_feedback.RuleFunnelAnalyzer", FakeFunnelAnalyzer)
    monkeypatch.setattr(analyzer, "_collect_sell_sequence_metrics", fake_sell_sequence_metrics)
    monkeypatch.setattr(analyzer, "_collect_ai_decision_metrics", fake_ai_metrics)
    monkeypatch.setattr(analyzer, "_collect_llm_cost_metrics", fake_cost_metrics)
    monkeypatch.setattr(analyzer, "_strategy_config_hash", lambda: "hash123")

    payload = await analyzer.build_feedback_payload(report_days=7, approval_days=14, fallback_days=30)

    assert called_days == [7, 14, 30]
    assert payload["window"]["approval_days"] == 30
    assert payload["readiness"]["approval_tier"] == "reviewable"
    assert payload["gate_result"] == "recommend"
    assert payload["candidate_changes"][0]["target_param"].endswith("take_profit_pct")
