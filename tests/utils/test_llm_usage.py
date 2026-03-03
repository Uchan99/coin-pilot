from types import SimpleNamespace

from src.common.llm_usage import (
    TokenUsage,
    estimate_cost_usd,
    estimate_tokens_from_text,
    extract_usage_from_llm_result,
    extract_usage_from_response_message,
)


class _FakeMessage:
    def __init__(self, usage_metadata=None, response_metadata=None):
        self.usage_metadata = usage_metadata
        self.response_metadata = response_metadata


class _FakeGeneration:
    def __init__(self, message):
        self.message = message


def test_extract_usage_from_usage_metadata():
    msg = _FakeMessage(usage_metadata={"input_tokens": 12, "output_tokens": 8, "total_tokens": 20})
    usage = extract_usage_from_response_message(msg)

    assert usage is not None
    assert usage.input_tokens == 12
    assert usage.output_tokens == 8
    assert usage.total_tokens == 20


def test_extract_usage_from_response_metadata_usage_block():
    msg = _FakeMessage(
        response_metadata={
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
        }
    )
    usage = extract_usage_from_response_message(msg)

    assert usage is not None
    assert usage.input_tokens == 10
    assert usage.output_tokens == 5
    assert usage.total_tokens == 15


def test_extract_usage_from_llm_result_llm_output_token_usage():
    result = SimpleNamespace(
        generations=[],
        llm_output={"token_usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10}},
    )

    usage = extract_usage_from_llm_result(result)

    assert usage is not None
    assert usage.input_tokens == 7
    assert usage.output_tokens == 3
    assert usage.total_tokens == 10


def test_extract_usage_from_llm_result_generations_sum():
    result = SimpleNamespace(
        generations=[
            [_FakeGeneration(_FakeMessage(usage_metadata={"input_tokens": 4, "output_tokens": 6, "total_tokens": 10}))],
            [_FakeGeneration(_FakeMessage(usage_metadata={"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}))],
        ],
        llm_output={},
    )

    usage = extract_usage_from_llm_result(result)

    assert usage is not None
    assert usage.input_tokens == 7
    assert usage.output_tokens == 8
    assert usage.total_tokens == 15


def test_estimate_tokens_from_text():
    assert estimate_tokens_from_text("") == 0
    assert estimate_tokens_from_text("abcd") == 1
    assert estimate_tokens_from_text("abcdefgh") == 2


def test_estimate_cost_usd_known_model():
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000, total_tokens=2_000_000)
    cost = estimate_cost_usd(
        provider="openai",
        model="gpt-4o-mini",
        usage=usage,
    )

    assert cost is not None
    # 0.15 + 0.60 = 0.75
    assert float(cost) == 0.75
