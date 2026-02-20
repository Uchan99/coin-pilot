import os
from functools import lru_cache

from langchain_anthropic import ChatAnthropic

# from langchain_openai import ChatOpenAI  # OpenAI 사용 시 주석 해제

DEV_MODEL = "claude-haiku-4-5-20251001"
PROD_MODEL = "claude-sonnet-4-5-20250929"
PREMIUM_REVIEW_MODEL = PROD_MODEL


@lru_cache(maxsize=1)
def get_llm_mode() -> str:
    """현재 런타임의 LLM 모드를 반환합니다."""
    return os.getenv("LLM_MODE", "dev").strip().lower()


@lru_cache(maxsize=1)
def get_default_model_name() -> str:
    """LLM_MODE 정책에 따라 기본 모델명을 결정합니다."""
    return PROD_MODEL if get_llm_mode() == "prod" else DEV_MODEL


@lru_cache(maxsize=4)
def _build_anthropic_llm(model_name: str, temperature: float = 0) -> ChatAnthropic:
    """모델/온도 조합별로 Anthropic LLM 인스턴스를 캐시합니다."""
    return ChatAnthropic(
        model=model_name,
        temperature=temperature,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )


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
    return _build_anthropic_llm(model_name=model_name, temperature=temperature)


def get_chat_llm(temperature: float = 0):
    """챗봇/도구 라우팅용 LLM 인스턴스를 반환합니다."""
    return get_llm(model_type="chatbot", temperature=temperature)


def get_analyst_llm():
    """시장 분석가 노드용 LLM 인스턴스를 반환합니다."""
    return get_llm(model_type="analyst", temperature=0)


def get_guardian_llm():
    """리스크 가디언 노드용 LLM 인스턴스를 반환합니다."""
    return get_llm(model_type="guardian", temperature=0)


def get_premium_review_llm(temperature: float = 0.1):
    """고난도 전략 리뷰 질의에 한해 사용하는 상위 모델 인스턴스를 반환합니다."""
    return get_llm(model_type="premium_review", temperature=temperature)
