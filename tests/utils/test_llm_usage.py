from types import SimpleNamespace

from src.common.llm_usage import (
    TokenUsage,
    _build_cost_snapshot_url,
    _expand_env_placeholders,
    _extract_json_path,
    _parse_headers_json,
    estimate_cost_usd,
    estimate_tokens_from_text,
    extract_usage_from_llm_result,
    extract_usage_from_response_message,
    load_llm_credit_snapshot_configs,
    load_llm_cost_snapshot_configs,
)
from datetime import datetime, timezone


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


def test_expand_env_placeholders(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    raw = "Bearer ${OPENAI_API_KEY}"
    assert _expand_env_placeholders(raw) == "Bearer test-openai-key"


def test_extract_json_path_nested():
    payload = {
        "data": {
            "credits": [
                {"provider": "openai", "balance": 12.34},
            ]
        }
    }
    value = _extract_json_path(payload, "data.credits.0.balance")
    assert value == 12.34


def test_parse_headers_json_with_placeholder(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    raw = '{"x-api-key":"${ANTHROPIC_API_KEY}","x-version":"2026-01-01"}'
    headers = _parse_headers_json(raw)
    assert headers["x-api-key"] == "test-anthropic-key"
    assert headers["x-version"] == "2026-01-01"


def test_load_llm_credit_snapshot_configs(monkeypatch):
    monkeypatch.setenv("LLM_CREDIT_SNAPSHOT_PROVIDERS", "openai")
    monkeypatch.setenv("LLM_CREDIT_SNAPSHOT_OPENAI_URL", "https://example.test/openai/credits")
    monkeypatch.setenv("LLM_CREDIT_SNAPSHOT_OPENAI_BALANCE_JSON_PATH", "credits.balance_usd")
    monkeypatch.setenv("LLM_CREDIT_SNAPSHOT_OPENAI_HEADERS_JSON", '{"Authorization":"Bearer ${OPENAI_API_KEY}"}')
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    configs = load_llm_credit_snapshot_configs()

    assert len(configs) == 1
    assert configs[0].provider == "openai"
    assert configs[0].url == "https://example.test/openai/credits"
    assert configs[0].balance_json_path == "credits.balance_usd"
    assert configs[0].headers["Authorization"] == "Bearer test-openai-key"


def test_build_cost_snapshot_url_with_runtime_and_env(monkeypatch):
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "test-admin-key")
    template = (
        "https://api.example.test/costs?"
        "start=${START_UNIX}&end=${END_UNIX}&token=${OPENAI_ADMIN_KEY}"
    )
    url = _build_cost_snapshot_url(
        url_template=template,
        window_start=datetime(2026, 3, 5, 9, 0, tzinfo=timezone.utc),
        window_end=datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc),
    )
    assert "start=1772701200" in url
    assert "end=1772704800" in url
    assert "token=test-admin-key" in url


def test_load_llm_cost_snapshot_configs(monkeypatch):
    monkeypatch.setenv("LLM_COST_SNAPSHOT_PROVIDERS", "openai")
    monkeypatch.setenv(
        "LLM_COST_SNAPSHOT_OPENAI_URL_TEMPLATE",
        "https://api.example.test/costs?start=${START_UNIX}&end=${END_UNIX}",
    )
    monkeypatch.setenv("LLM_COST_SNAPSHOT_OPENAI_VALUE_JSON_PATH", "data.0.amount.usd")
    monkeypatch.setenv(
        "LLM_COST_SNAPSHOT_OPENAI_HEADERS_JSON",
        '{"Authorization":"Bearer ${OPENAI_ADMIN_KEY}"}',
    )
    monkeypatch.setenv("OPENAI_ADMIN_KEY", "test-admin-key")

    configs = load_llm_cost_snapshot_configs()

    assert len(configs) == 1
    assert configs[0].provider == "openai"
    assert configs[0].value_json_path == "data.0.amount.usd"
    assert "START_UNIX" in configs[0].url_template
    assert configs[0].headers["Authorization"] == "Bearer test-admin-key"
