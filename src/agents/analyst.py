from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from src.agents.state import AgentState
from src.agents.structs import AnalystDecision
from src.agents.prompts import ANALYST_SYSTEM_PROMPT, get_analyst_prompt
from src.agents.factory import get_analyst_llm
import os

async def market_analyst_node(state: AgentState) -> Dict[str, Any]:
    """시장 분석가 노드: 지표 기반 진입 타당성 검토"""
    
    llm = get_analyst_llm()
    structured_llm = llm.with_structured_output(AnalystDecision)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", ANALYST_SYSTEM_PROMPT),
        ("human", "{analyst_prompt}\n\n"
                  "[참고: 원시 입력]\n"
                  "- 심볼: {symbol}\n"
                  "- 현재 지표 (1분봉 기준): {indicators}\n"
                  "- 최근 1시간봉 캔들 (최대 24개): {market_context}")
    ])
    
    chain = prompt | structured_llm
    
    result: AnalystDecision = await chain.ainvoke({
        "symbol": state["symbol"],
        "indicators": state["indicators"],
        "market_context": state["market_context"],
        "analyst_prompt": get_analyst_prompt(state["indicators"])
    })
    
    # 분석 결과 업데이트
    # V1.2 정책: confidence < 60 이면 강제 REJECT
    final_decision = result.decision
    final_reasoning = result.reasoning
    
    if result.decision == "CONFIRM" and result.confidence < 60:
        final_decision = "REJECT"
        final_reasoning = f"[Low Confidence: {result.confidence}] {result.reasoning}"
    
    return {
        "analyst_decision": {
            "decision": final_decision,
            "confidence": result.confidence,
            "reasoning": final_reasoning
        }
    }
