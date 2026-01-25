from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from src.agents.state import AgentState
from src.agents.structs import GuardianDecision
from src.agents.prompts import GUARDIAN_SYSTEM_PROMPT
from src.agents.factory import get_guardian_llm
import os

async def risk_guardian_node(state: AgentState) -> Dict[str, Any]:
    """위험 관리자 노드: 매매 안전성 및 심리적 요소 검토"""
    
    # Analyst가 이미 거절했다면 실행하지 않음 (LangGraph flow에서 제어할 수도 있지만 여기서도 체크)
    if state["analyst_decision"] and state["analyst_decision"]["decision"] == "REJECT":
        # 'SKIP'은 Pydantic 스키마(SAFE | WARNING)에 없으므로 'WARNING'으로 대체하고 사유에 명시
        return {"guardian_decision": {"decision": "WARNING", "reasoning": "Skipped: Analyst already rejected."}}
    
    llm = get_guardian_llm()
    structured_llm = llm.with_structured_output(GuardianDecision)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", GUARDIAN_SYSTEM_PROMPT),
        ("human", "현재 리스크 상태를 분석하여 매매 진행 가능 여부를 판단해주세요.\n\n"
                  "심볼: {symbol}\n"
                  "지표: {indicators}")
    ])
    
    chain = prompt | structured_llm
    
    result: GuardianDecision = await chain.ainvoke({
        "symbol": state["symbol"],
        "indicators": state["indicators"]
    })
    
    return {
        "guardian_decision": {
            "decision": result.decision,
            "reasoning": result.reasoning
        }
    }
