from src.analytics.exit_performance import ExitPerformanceAnalyzer


def test_generate_tuning_suggestions_data_shortage():
    summary = {
        "total_sells": 7,
        "by_exit_reason": {},
        "by_regime": {},
    }
    suggestions = ExitPerformanceAnalyzer.generate_tuning_suggestions_from_summary(
        summary, min_samples=20
    )
    assert len(suggestions) == 1
    assert "데이터 부족" in suggestions[0]


def test_generate_tuning_suggestions_rule_hits():
    summary = {
        "total_sells": 40,
        "by_exit_reason": {
            "TRAILING_STOP": {"avg_post_24h_pct": 3.4, "avg_post_4h_pct": 0.2},
            "STOP_LOSS": {"avg_post_4h_pct": 1.3},
            "TAKE_PROFIT": {"avg_post_4h_pct": 2.4},
            "TIME_LIMIT": {"avg_post_24h_pct": -2.6},
        },
        "by_regime": {
            "SIDEWAYS": {"early_exit_rate": 0.46},
            "BEAR": {"early_exit_rate": 0.12},
        },
    }
    suggestions = ExitPerformanceAnalyzer.generate_tuning_suggestions_from_summary(
        summary, min_samples=20
    )
    joined = "\n".join(suggestions)

    assert "trailing_stop_pct" in joined
    assert "stop_loss_pct" in joined
    assert "take_profit_pct" in joined
    assert "TIME_LIMIT" in joined
    assert "SIDEWAYS" in joined


def test_generate_tuning_suggestions_no_signal():
    summary = {
        "total_sells": 30,
        "by_exit_reason": {
            "TRAILING_STOP": {"avg_post_24h_pct": 1.2},
            "STOP_LOSS": {"avg_post_4h_pct": 0.5},
        },
        "by_regime": {
            "SIDEWAYS": {"early_exit_rate": 0.1},
        },
    }
    suggestions = ExitPerformanceAnalyzer.generate_tuning_suggestions_from_summary(
        summary, min_samples=20
    )
    assert len(suggestions) == 1
    assert "현행 파라미터 유지" in suggestions[0]
