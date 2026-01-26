import os
from langchain_anthropic import ChatAnthropic
# from langchain_openai import ChatOpenAI  # OpenAI 사용 시 주석 해제

# 싱글톤 인스턴스 캐싱
_analyst_llm = None
_guardian_llm = None

def get_llm(model_type="analyst"):
    """
    LLM 인스턴스를 생성하거나 캐시된 인스턴스를 반환합니다.
    Provider 확장을 고려하여 설계.
    """
    # 현재는 Claude만 사용하지만, 향후 provider 분기 가능
    # provider = os.getenv("LLM_PROVIDER", "anthropic")
    
    return ChatAnthropic(
        # model="claude-3-haiku-20240307",    # Development (Low Cost, Fast)
        model="claude-sonnet-4-5-20250929",   # Production (High Reasoning)
        temperature=0,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )

def get_analyst_llm():
    """시장 분석용 LLM 인스턴스 반환 (Singleton)"""
    global _analyst_llm
    if _analyst_llm is None:
        _analyst_llm = get_llm("analyst")
    return _analyst_llm

def get_guardian_llm():
    """위험 관리용 LLM 인스턴스 반환 (Singleton)"""
    global _guardian_llm
    if _guardian_llm is None:
        _guardian_llm = get_llm("guardian")
    return _guardian_llm
