from typing import Annotated, TypedDict, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage
from src.agents.langgraph_compat import add_messages
import operator

class AgentState(TypedDict):
    """LangGraph 기반 에이전트 워크플로우 상태 정의"""
    # 대화 기록 (자동 병합)
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 입력 데이터
    symbol: str
    strategy_name: str
    market_context: List[Dict[str, Any]] # OHLCV Summary
    indicators: Dict[str, Any]    # RSI, BB, MA 등
    # 카나리 실험 시 Analyst/Guardian가 동일 모델 경로를 사용하도록 공유하는 라우팅 메타데이터
    llm_route: Optional[Dict[str, Any]]
    
    # 분석 결과
    analyst_decision: Optional[Dict[str, Any]]
    guardian_decision: Optional[Dict[str, Any]]
    
    # 최종 결과
    final_decision: str  # CONFIRM, REJECT
    final_reasoning: str
