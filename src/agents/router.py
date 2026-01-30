from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.agents.config import LLM_MODEL
from src.agents.sql_agent import run_sql_agent
from src.agents.rag_agent import run_rag_agent
import os

# --- State Definition ---
class AgentState(TypedDict):
    """LangGraph 상태 정의: 메시지 기록, 최종 응답, 사용자 의도"""
    messages: list[BaseMessage]
    response: str
    intent: str

# --- Intent Classification Data Model ---
class IntentDecision(BaseModel):
    """LLM 구조적 출력(Structured Output)을 위한 Pydantic 모델"""
    intent: Literal["db_query", "doc_search", "general_chat"] = Field(
        ..., 
        description="User intent classification using 'db_query' for database/market data/financials, 'doc_search' for rules/architecture/concepts, 'general_chat' for geetings/others."
    )

# --- Router Logic ---
def get_classifier_llm():
    """의도 분류를 위한 LLM 인스턴스를 생성하고, 구조적 출력 모드로 설정합니다."""
    if "claude" in LLM_MODEL:
        llm = ChatAnthropic(
            model=LLM_MODEL, # 설정된 모델 사용 (claude-3-haiku)
            temperature=0, 
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    else:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
    return llm.with_structured_output(IntentDecision)

async def classifier_node(state: AgentState):
    """
    사용자 쿼리의 의도(Intent)를 분류하는 노드입니다.
    Fast Path(키워드)와 Slow Path(LLM)를 하이브리드로 사용합니다.
    """
    last_message = state["messages"][-1].content
    
    # 1. Keyword Heuristics (Fast Path)
    # 명확한 키워드가 있으면 LLM 호출 없이 즉시 분류하여 응답 속도를 높입니다.
    sql_keywords = ["수익률", "잔고", "얼마", "가격", "RSI", "포지션", "balance", "price", "pnl"]
    rag_keywords = ["규칙", "설명", "아키텍처", "방법", "왜", "어떻게", "architecture", "rule", "strategy"]
    
    intent = "general_chat"
    
    # Simple check
    if any(k in last_message for k in sql_keywords):
        intent = "db_query"
    elif any(k in last_message for k in rag_keywords):
        intent = "doc_search"
    else:
        # 2. LLM Classification (Slow Path)
        # 키워드로 판단하기 어려운 경우, LLM에게 문맥 파악을 요청합니다.
        try:
            llm = get_classifier_llm()
            decision: IntentDecision = await llm.ainvoke(last_message)
            intent = decision.intent
        except Exception as e:
            # 에러 발생 시 안전하게 일반 대화로 처리 (Fallback)
            print(f"Router Error: {e}")
            intent = "general_chat"
            
    return {"intent": intent}

# --- Agent Nodes ---
async def sql_node(state: AgentState):
    """SQL 에이전트 실행 노드: DB 조회 담당"""
    query = state["messages"][-1].content
    response = await run_sql_agent(query)
    return {"response": response}

async def rag_node(state: AgentState):
    """RAG 에이전트 실행 노드: 문서 검색 담당"""
    query = state["messages"][-1].content
    response = await run_rag_agent(query)
    return {"response": response}

async def general_node(state: AgentState):
    """일반 대화 노드: 안내 메시지 또는 단순 응답"""
    # 현재는 고정 응답을 반환하지만, 추후 스몰 토크 모델을 연동할 수 있습니다.
    return {"response": "안녕하세요! CoinPilot 챗봇입니다. 데이터 분석이나 프로젝트 문서에 대해 물어봐주세요."}

# --- Graph Construction ---
def create_chat_graph():
    """LangGraph 워크플로우 그래프를 구성합니다."""
    workflow = StateGraph(AgentState)
    
    # 노드 등록
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("sql_agent", sql_node)
    workflow.add_node("rag_agent", rag_node)
    workflow.add_node("general_chat", general_node)
    
    # 진입점 설정 (항상 분류부터 시작)
    workflow.set_entry_point("classifier")
    
    # 분류 결과에 따른 조건부 에지 설정
    def route_decision(state: AgentState):
        return state["intent"]
        
    workflow.add_conditional_edges(
        "classifier",
        route_decision,
        {
            "db_query": "sql_agent",
            "doc_search": "rag_agent",
            "general_chat": "general_chat"
        }
    )
    
    # 각 에이전트 실행 후 종료(END)
    workflow.add_edge("sql_agent", END)
    workflow.add_edge("rag_agent", END)
    workflow.add_edge("general_chat", END)
    
    return workflow.compile()

# Entrypoint for the UI
async def process_chat(message: str) -> str:
    """UI에서 호출하는 메인 진입 함수입니다."""
    app = create_chat_graph()
    inputs = {"messages": [HumanMessage(content=message)]}
    
    # 그래프 실행 및 최종 응답 반환
    result = await app.ainvoke(inputs)
    return result["response"]
