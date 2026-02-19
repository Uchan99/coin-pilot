from src.agents.guardrails import (
    get_reject_cooldown_minutes,
    is_ai_error_reason,
    is_low_credit_error,
)


def test_get_reject_cooldown_minutes_staged():
    cfg = {
        "ai_reject_cooldown_min_1": 5,
        "ai_reject_cooldown_min_2": 10,
        "ai_reject_cooldown_min_3": 15,
    }
    assert get_reject_cooldown_minutes(1, cfg) == 5
    assert get_reject_cooldown_minutes(2, cfg) == 10
    assert get_reject_cooldown_minutes(3, cfg) == 15
    assert get_reject_cooldown_minutes(9, cfg) == 15


def test_is_low_credit_error():
    msg = "AI Error: Error code: 400 - Your credit balance is too low to access the Anthropic API."
    assert is_low_credit_error(msg) is True
    assert is_low_credit_error("normal reject") is False


def test_is_ai_error_reason():
    assert is_ai_error_reason("AI Analysis Error: something bad happened") is True
    assert is_ai_error_reason("Error code: 500 internal server") is True
    assert is_ai_error_reason("Pattern reject") is False
