import os
import hashlib
from functools import lru_cache
from typing import Any, Dict, Optional, TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

DEV_MODEL = "claude-haiku-4-5-20251001"
PROD_MODEL = "claude-sonnet-4-5-20250929"
PREMIUM_REVIEW_MODEL = PROD_MODEL

SUPPORTED_PROVIDERS = {"anthropic", "openai"}


class AIDecisionRoute(TypedDict):
    """
    Analyst/Guardian에서 공통으로 사용하는 카나리 라우팅 결과입니다.

    왜 필요한가:
    - Analyst/Guardian가 서로 다른 모델을 사용하면 판단 일관성이 깨질 수 있으므로
      신호 단위로 단일 라우팅 결과를 먼저 확정해 두 노드가 공유해야 합니다.
    """

    provider: str
    model: str
    route_label: str
    canary_enabled: bool
    canary_percent: int
    bucket: int
    seed: str


def _normalize_provider(raw: Optional[str]) -> str:
    provider = (raw or "anthropic").strip().lower()
    return provider if provider in SUPPORTED_PROVIDERS else "anthropic"


def _read_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_provider_configured(provider: str) -> bool:
    if provider == "openai":
        return bool((os.getenv("OPENAI_API_KEY") or "").strip())
    return bool((os.getenv("ANTHROPIC_API_KEY") or "").strip())


def _resolve_provider_with_fallback(provider: str) -> str:
    """
    provider 설정은 있어도 API 키가 비어 있을 수 있으므로 안전한 fallback을 적용합니다.
    """
    normalized = _normalize_provider(provider)
    if _is_provider_configured(normalized):
        return normalized

    fallback = "openai" if normalized == "anthropic" else "anthropic"
    if _is_provider_configured(fallback):
        print(f"[LLM Route] provider={normalized} key missing. Fallback to {fallback}.")
        return fallback

    # 양쪽 키가 모두 비어 있어도 런타임에서 원인을 명확히 보기 위해 원래 provider를 유지합니다.
    return normalized


@lru_cache(maxsize=1)
def get_llm_mode() -> str:
    """현재 런타임의 LLM 모드를 반환합니다."""
    return os.getenv("LLM_MODE", "dev").strip().lower()


@lru_cache(maxsize=1)
def get_default_model_name() -> str:
    """LLM_MODE 정책에 따라 기본 모델명을 결정합니다."""
    return PROD_MODEL if get_llm_mode() == "prod" else DEV_MODEL


@lru_cache(maxsize=8)
def _build_anthropic_llm(model_name: str, temperature: float = 0) -> ChatAnthropic:
    """모델/온도 조합별로 Anthropic LLM 인스턴스를 캐시합니다."""
    return ChatAnthropic(
        model=model_name,
        temperature=temperature,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )


@lru_cache(maxsize=8)
def _build_openai_llm(model_name: str, temperature: float = 0) -> ChatOpenAI:
    """모델/온도 조합별로 OpenAI LLM 인스턴스를 캐시합니다."""
    return ChatOpenAI(
        model=model_name,
        temperature=temperature,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
    )


def _build_llm(provider: str, model_name: str, temperature: float = 0):
    normalized = _normalize_provider(provider)
    if normalized == "openai":
        return _build_openai_llm(model_name=model_name, temperature=temperature)
    return _build_anthropic_llm(model_name=model_name, temperature=temperature)


def _extract_signal_marker(market_context: Any, indicators: Any) -> str:
    """
    동일 신호(심볼+전략+최신캔들)에는 같은 라우팅 결과가 나오도록 시그널 마커를 추출합니다.
    """
    if isinstance(market_context, list) and market_context:
        last = market_context[-1]
        if isinstance(last, dict):
            ts = last.get("timestamp")
            if ts:
                return str(ts)
    if isinstance(indicators, dict):
        ts = indicators.get("timestamp")
        if ts:
            return str(ts)
    return "no-signal-timestamp"


def _deterministic_bucket(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 100


def _parse_canary_percent(default_percent: int = 10) -> int:
    raw = os.getenv("AI_CANARY_PERCENT", str(default_percent)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default_percent
    # 운영 가드레일: 카나리는 기본 10%, 최대 20%로 제한한다.
    return max(0, min(20, value))


def get_primary_ai_decision_route() -> AIDecisionRoute:
    primary_provider = _resolve_provider_with_fallback(
        os.getenv("AI_DECISION_PRIMARY_PROVIDER", os.getenv("LLM_PROVIDER", "anthropic"))
    )
    primary_model = os.getenv(
        "AI_DECISION_PRIMARY_MODEL",
        os.getenv("LLM_MODEL", get_default_model_name()),
    )
    return {
        "provider": primary_provider,
        "model": primary_model,
        "route_label": "primary",
        "canary_enabled": False,
        "canary_percent": 0,
        "bucket": 0,
        "seed": "primary-default",
    }


def select_ai_decision_route(
    symbol: str,
    strategy_name: str,
    market_context: Any,
    indicators: Any,
) -> AIDecisionRoute:
    """
    Analyst/Guardian 공용 카나리 라우팅 결과를 결정합니다.

    정책:
    - `AI_CANARY_ENABLED=true`일 때만 카나리 분기
    - 비율은 `AI_CANARY_PERCENT`(0~20, 기본 10)
    - 신호 단위 deterministic hash(심볼+전략+최신 캔들 timestamp) 기반 분기
    """
    primary = get_primary_ai_decision_route()
    canary_enabled = _read_bool_env("AI_CANARY_ENABLED", default=False)
    canary_percent = _parse_canary_percent(default_percent=10)

    marker = _extract_signal_marker(market_context, indicators)
    seed = f"{symbol}|{strategy_name}|{marker}"
    bucket = _deterministic_bucket(seed)

    if not canary_enabled or canary_percent <= 0:
        return {
            **primary,
            "canary_enabled": canary_enabled,
            "canary_percent": canary_percent,
            "bucket": bucket,
            "seed": seed,
        }

    if bucket >= canary_percent:
        return {
            **primary,
            "canary_enabled": True,
            "canary_percent": canary_percent,
            "bucket": bucket,
            "seed": seed,
        }

    # 카나리 실험은 "지정한 provider/model의 품질 비교"가 목적이므로,
    # canary provider 키가 없을 때 다른 provider로 우회하면 실험 의미가 깨집니다.
    # 따라서 canary 경로에서는 provider fallback을 하지 않고 primary로 복귀합니다.
    canary_provider = _normalize_provider(os.getenv("AI_CANARY_PROVIDER", "openai"))
    canary_model = os.getenv("AI_CANARY_MODEL", "gpt-4o-mini")

    if not _is_provider_configured(canary_provider):
        print(
            f"[LLM Canary] canary provider={canary_provider} API key missing. "
            "Fallback to primary route."
        )
        return {
            **primary,
            "route_label": "primary-fallback",
            "canary_enabled": True,
            "canary_percent": canary_percent,
            "bucket": bucket,
            "seed": seed,
        }

    return {
        "provider": canary_provider,
        "model": canary_model,
        "route_label": "canary",
        "canary_enabled": True,
        "canary_percent": canary_percent,
        "bucket": bucket,
        "seed": seed,
    }


def get_llm(model_type: str = "general", temperature: float = 0):
    """
    공통 LLM 팩토리 진입점입니다.

    model_type는 향후 역할별 모델 분기를 위해 유지하며,
    현재는 정책상 동일 기본 모델을 사용합니다.
    """
    if model_type == "premium_review":
        # 전략 리뷰 고난도 질의에 한해 비용-품질 트레이드오프로 상위 모델을 선택합니다.
        model_name = os.getenv("LLM_PREMIUM_MODEL", PREMIUM_REVIEW_MODEL)
    else:
        model_name = os.getenv("LLM_MODEL", get_default_model_name())
    provider = _resolve_provider_with_fallback(os.getenv("LLM_PROVIDER", "anthropic"))
    return _build_llm(provider=provider, model_name=model_name, temperature=temperature)


def get_chat_llm(temperature: float = 0):
    """챗봇/도구 라우팅용 LLM 인스턴스를 반환합니다."""
    return get_llm(model_type="chatbot", temperature=temperature)


def get_analyst_llm(route: Optional[Dict[str, Any]] = None):
    """시장 분석가 노드용 LLM 인스턴스를 반환합니다."""
    if route:
        provider = route.get("provider", "anthropic")
        model_name = route.get("model", os.getenv("LLM_MODEL", get_default_model_name()))
        return _build_llm(provider=provider, model_name=model_name, temperature=0)
    return get_llm(model_type="analyst", temperature=0)


def get_guardian_llm(route: Optional[Dict[str, Any]] = None):
    """리스크 가디언 노드용 LLM 인스턴스를 반환합니다."""
    if route:
        provider = route.get("provider", "anthropic")
        model_name = route.get("model", os.getenv("LLM_MODEL", get_default_model_name()))
        return _build_llm(provider=provider, model_name=model_name, temperature=0)
    return get_llm(model_type="guardian", temperature=0)


def get_premium_review_llm(temperature: float = 0.1):
    """고난도 전략 리뷰 질의에 한해 사용하는 상위 모델 인스턴스를 반환합니다."""
    return get_llm(model_type="premium_review", temperature=temperature)
