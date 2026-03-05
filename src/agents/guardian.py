import time
from typing import Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from src.agents.state import AgentState
from src.agents.structs import GuardianDecision
from src.agents.prompts import GUARDIAN_SYSTEM_PROMPT
from src.agents.factory import get_guardian_llm
from src.common.llm_usage import (
    UsageCaptureCallback,
    build_usage_request_id,
    log_llm_usage_event,
)

async def risk_guardian_node(state: AgentState) -> Dict[str, Any]:
    """위험 관리자 노드: 매매 안전성 및 심리적 요소 검토"""
    
    # Analyst가 이미 거절했다면 실행하지 않음 (LangGraph flow에서 제어할 수도 있지만 여기서도 체크)
    if state["analyst_decision"] and state["analyst_decision"]["decision"] == "REJECT":
        # 'SKIP'은 Pydantic 스키마(SAFE | WARNING)에 없으므로 'WARNING'으로 대체하고 사유에 명시
        return {"guardian_decision": {"decision": "WARNING", "reasoning": "Skipped: Analyst already rejected."}}
    
    llm = get_guardian_llm(state.get("llm_route"))
    structured_llm = llm.with_structured_output(GuardianDecision)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", GUARDIAN_SYSTEM_PROMPT),
        ("human", "현재 리스크 상태를 분석하여 매매 진행 가능 여부를 판단해주세요.\n\n"
                  "심볼: {symbol}\n"
                  "지표: {indicators}")
    ])
    
    chain = prompt | structured_llm
    usage_capture = UsageCaptureCallback()
    started_at = time.perf_counter()
    llm_route = state.get("llm_route") or {}
    provider = str(llm_route.get("provider") or "unknown")
    model = str(llm_route.get("model") or "unknown")

    try:
        invoke_payload = {
            "symbol": state["symbol"],
            "indicators": state["indicators"],
        }
        try:
            result: GuardianDecision = await chain.ainvoke(
                invoke_payload,
                config={"callbacks": [usage_capture]},
            )
        except TypeError:
            result = await chain.ainvoke(invoke_payload)

        await log_llm_usage_event(
            route="ai_decision_guardian",
            feature="ai_decision",
            provider=provider,
            model=model,
            status="success",
            usage=usage_capture.usage,
            request_id=build_usage_request_id("ai_decision_guardian", provider, model),
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            meta={
                "symbol": state.get("symbol"),
                "strategy_name": state.get("strategy_name"),
            },
        )
    except Exception as exc:
        await log_llm_usage_event(
            route="ai_decision_guardian",
            feature="ai_decision",
            provider=provider,
            model=model,
            status="error",
            usage=usage_capture.usage,
            request_id=build_usage_request_id("ai_decision_guardian", provider, model),
            error_type=type(exc).__name__,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            meta={
                "symbol": state.get("symbol"),
                "strategy_name": state.get("strategy_name"),
            },
        )
        raise
    
    return {
        "guardian_decision": {
            "decision": result.decision,
            "reasoning": result.reasoning
        }
    }
