import json
import os
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional

from langchain_core.callbacks.base import BaseCallbackHandler


@dataclass
class TokenUsage:
    """
    LLM 호출 1회(또는 집계 1건)의 토큰 사용량.

    필드 의미:
    - input_tokens: 프롬프트/입력 토큰
    - output_tokens: 생성/출력 토큰
    - total_tokens: 입력+출력(벤더가 직접 주면 우선 사용)
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class UsageCaptureCallback(BaseCallbackHandler):
    """
    LangChain 콜백으로 LLM usage를 수집하는 핸들러.

    왜 callback을 쓰는가:
    - structured output(chain.with_structured_output) 경로에서는
      최종 반환값이 Pydantic 객체라 usage 메타데이터가 사라질 수 있다.
    - on_llm_end 단계에서 LLMResult를 직접 읽으면 모델별 메타데이터 누락을 줄일 수 있다.
    """

    def __init__(self) -> None:
        self.usage = TokenUsage()

    def on_llm_end(self, response, **kwargs: Any) -> None:  # type: ignore[override]
        usage = extract_usage_from_llm_result(response)
        if usage is None:
            return
        self.usage = TokenUsage(
            input_tokens=max(0, int(self.usage.input_tokens + usage.input_tokens)),
            output_tokens=max(0, int(self.usage.output_tokens + usage.output_tokens)),
            total_tokens=max(0, int(self.usage.total_tokens + usage.total_tokens)),
        )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _pick_first_int(mapping: Dict[str, Any], keys: list[str]) -> Optional[int]:
    for key in keys:
        if key in mapping:
            parsed = _to_int(mapping.get(key))
            if parsed is not None:
                return parsed
    return None


def _normalize_usage(input_tokens: Optional[int], output_tokens: Optional[int], total_tokens: Optional[int]) -> Optional[TokenUsage]:
    in_tok = max(0, int(input_tokens or 0))
    out_tok = max(0, int(output_tokens or 0))

    if total_tokens is None:
        total = in_tok + out_tok
    else:
        total = max(0, int(total_tokens))
        if total == 0 and (in_tok > 0 or out_tok > 0):
            total = in_tok + out_tok

    if in_tok == 0 and out_tok == 0 and total == 0:
        return None

    return TokenUsage(input_tokens=in_tok, output_tokens=out_tok, total_tokens=total)


def extract_usage_from_response_message(message: Any) -> Optional[TokenUsage]:
    """
    AIMessage/유사 객체에서 usage 메타데이터를 추출한다.

    지원 포맷:
    - message.usage_metadata (langchain-core 공통)
    - message.response_metadata.usage / token_usage (provider별)
    """
    if message is None:
        return None

    usage_metadata = getattr(message, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        usage = _normalize_usage(
            input_tokens=_pick_first_int(usage_metadata, ["input_tokens", "prompt_tokens"]),
            output_tokens=_pick_first_int(usage_metadata, ["output_tokens", "completion_tokens"]),
            total_tokens=_pick_first_int(usage_metadata, ["total_tokens"]),
        )
        if usage is not None:
            return usage

    response_metadata = getattr(message, "response_metadata", None)
    if not isinstance(response_metadata, dict):
        return None

    usage_block = response_metadata.get("usage")
    if isinstance(usage_block, dict):
        usage = _normalize_usage(
            input_tokens=_pick_first_int(usage_block, ["input_tokens", "prompt_tokens"]),
            output_tokens=_pick_first_int(usage_block, ["output_tokens", "completion_tokens"]),
            total_tokens=_pick_first_int(usage_block, ["total_tokens"]),
        )
        if usage is not None:
            return usage

    token_usage = response_metadata.get("token_usage")
    if isinstance(token_usage, dict):
        usage = _normalize_usage(
            input_tokens=_pick_first_int(token_usage, ["input_tokens", "prompt_tokens"]),
            output_tokens=_pick_first_int(token_usage, ["output_tokens", "completion_tokens"]),
            total_tokens=_pick_first_int(token_usage, ["total_tokens"]),
        )
        if usage is not None:
            return usage

    return None


def extract_usage_from_llm_result(result: Any) -> Optional[TokenUsage]:
    """
    LangChain LLMResult에서 usage를 집계 추출한다.
    """
    if result is None:
        return None

    total_in = 0
    total_out = 0
    total_sum = 0

    generations = getattr(result, "generations", None)
    if isinstance(generations, list):
        for row in generations:
            if not isinstance(row, list):
                continue
            for generation in row:
                message = getattr(generation, "message", None)
                usage = extract_usage_from_response_message(message)
                if usage is None:
                    continue
                total_in += usage.input_tokens
                total_out += usage.output_tokens
                total_sum += usage.total_tokens

    if total_in > 0 or total_out > 0 or total_sum > 0:
        if total_sum == 0:
            total_sum = total_in + total_out
        return TokenUsage(input_tokens=total_in, output_tokens=total_out, total_tokens=total_sum)

    llm_output = getattr(result, "llm_output", None)
    if not isinstance(llm_output, dict):
        return None

    usage_block = llm_output.get("token_usage") or llm_output.get("usage")
    if not isinstance(usage_block, dict):
        return None

    return _normalize_usage(
        input_tokens=_pick_first_int(usage_block, ["input_tokens", "prompt_tokens"]),
        output_tokens=_pick_first_int(usage_block, ["output_tokens", "completion_tokens"]),
        total_tokens=_pick_first_int(usage_block, ["total_tokens"]),
    )


def estimate_tokens_from_text(text: str) -> int:
    """
    메타데이터가 없는 경로(예: 일부 embedding wrapper)용 토큰 근사치.

    기준:
    - 운영용 빠른 추정으로 1 token ~= 4 chars를 사용
    - billing 정산값이 아니라 route별 상대 비교/추이 관측 용도
    """
    if not text:
        return 0
    return max(1, int(round(len(text) / 4)))


def _default_price_table() -> Dict[str, Dict[str, Decimal]]:
    """
    모델별 1M token 기준 단가(USD).

    주의:
    - 벤더 정책 변경 가능성이 있으므로 환경변수 override를 우선한다.
    - 가격은 추정치 용도이며, 실제 청구서와 차이가 날 수 있다.
    """
    return {
        "anthropic:claude-haiku-4-5-20251001": {
            "input_per_1m": Decimal("0.80"),
            "output_per_1m": Decimal("4.00"),
        },
        "openai:gpt-4o-mini": {
            "input_per_1m": Decimal("0.15"),
            "output_per_1m": Decimal("0.60"),
        },
        "openai:text-embedding-3-small": {
            "input_per_1m": Decimal("0.02"),
            "output_per_1m": Decimal("0.00"),
        },
        "openai:text-embedding-3-large": {
            "input_per_1m": Decimal("0.13"),
            "output_per_1m": Decimal("0.00"),
        },
    }


def _load_price_table() -> Dict[str, Dict[str, Decimal]]:
    table = _default_price_table()
    raw = os.getenv("LLM_USAGE_PRICE_TABLE_JSON", "").strip()
    if not raw:
        return table

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return table

    if not isinstance(payload, dict):
        return table

    for key, value in payload.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        input_price = value.get("input_per_1m")
        output_price = value.get("output_per_1m")
        try:
            if input_price is None or output_price is None:
                continue
            table[key.lower()] = {
                "input_per_1m": Decimal(str(input_price)),
                "output_per_1m": Decimal(str(output_price)),
            }
        except Exception:
            continue

    return table


def estimate_cost_usd(
    provider: str,
    model: str,
    usage: Optional[TokenUsage],
) -> Optional[Decimal]:
    if usage is None:
        return None

    table = _load_price_table()
    key = f"{(provider or 'unknown').strip().lower()}:{(model or 'unknown').strip()}".lower()
    pricing = table.get(key)
    if pricing is None:
        return None

    input_cost = (Decimal(usage.input_tokens) / Decimal(1_000_000)) * pricing["input_per_1m"]
    output_cost = (Decimal(usage.output_tokens) / Decimal(1_000_000)) * pricing["output_per_1m"]
    total = input_cost + output_cost
    return total.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def is_llm_usage_enabled() -> bool:
    return _env_bool("LLM_USAGE_ENABLED", default=True)


def build_usage_request_id(route: str, provider: str, model: str) -> str:
    seed = f"{route}:{provider}:{model}:{uuid.uuid4().hex}"
    return seed[:120]


async def log_llm_usage_event(
    *,
    route: str,
    feature: str,
    provider: str,
    model: str,
    status: str,
    usage: Optional[TokenUsage] = None,
    request_id: Optional[str] = None,
    error_type: Optional[str] = None,
    latency_ms: Optional[int] = None,
    meta: Optional[Dict[str, Any]] = None,
    price_version: str = "v1",
) -> None:
    """
    usage 이벤트를 DB에 저장한다.

    운영 원칙:
    - 이 함수는 soft-fail이다. 저장 실패가 본 기능 실패로 전파되면 안 된다.
    """
    if not is_llm_usage_enabled():
        return

    try:
        from src.common.db import get_db_session
        from src.common.models import LlmUsageEvent

        usage_for_store = usage
        if usage_for_store is not None and int(usage_for_store.total_tokens) <= 0:
            usage_for_store = None

        estimated_cost = estimate_cost_usd(provider=provider, model=model, usage=usage_for_store)

        async with get_db_session() as session:
            row = LlmUsageEvent(
                request_id=request_id,
                route=route,
                feature=feature,
                provider=(provider or "unknown").strip().lower(),
                model=(model or "unknown").strip(),
                status=(status or "unknown").strip().lower(),
                error_type=(error_type or "").strip() or None,
                input_tokens=usage_for_store.input_tokens if usage_for_store else None,
                output_tokens=usage_for_store.output_tokens if usage_for_store else None,
                total_tokens=usage_for_store.total_tokens if usage_for_store else None,
                estimated_cost_usd=estimated_cost,
                price_version=price_version,
                latency_ms=latency_ms,
                meta=meta,
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        print(f"[LLM Usage] failed to persist event: {exc}")
