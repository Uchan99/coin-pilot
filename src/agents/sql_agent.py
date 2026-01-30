from typing import Any, Dict
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from src.common.db import get_sync_db_url
from src.agents.config import LLM_MODEL
import os

# System Prompt for SQL Agent
SQL_PREFIX = """You are an agent designed to interact with a PostgreSQL database.
Given an input question, create a syntactically correct PostgreSQL query to run, then look at the results of the query and return the answer.
Unless the user specifies a specific number of examples they wish to obtain, always limit your query to at most 5 results.
You can order the results by a relevant column to return the most interesting examples in the database.
Never query for all the columns from a specific table, only ask for the relevant columns given the question.
You have access to tools for interacting with the database.
Only use the below tools. Only use the information returned by the below tools to construct your final answer.
You MUST double check your query before executing it. If you get an error while executing a query, rewrite the query and try again.

DO NOT make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.
If the question does not seem related to the database, just return "I don't know" as the answer.

Table Information:
- market_data: OHLCV data for cryptocurrencies (timestamp, symbol, open, high, low, close, volume)
- trading_history: Executed trades (timestamp, symbol, side, price, amount, pnl)
- account_state: Balance history (timestamp, total_balance_krw, cash_krw, locked_krw)
- daily_risk_state: Daily risk metrics (date, daily_loss_rate, trade_count)

Example:
User: "What is the current balance?"
Query: SELECT total_balance_krw FROM account_state ORDER BY timestamp DESC LIMIT 1;
"""

def get_llm():
    """
    LLM 인스턴스를 생성하여 반환합니다.
    설정 파일(config.py)의 모델명을 사용하며, Claude(Anthropic)를 기본으로 합니다.
    """
    if "claude" in LLM_MODEL:
        return ChatAnthropic(
            model=LLM_MODEL, 
            temperature=0, 
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    else:
        # Fallback: OpenAI (설정에 따라 선택적 사용)
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)

def create_agent_executor():
    """
    SQL 에이전트 실행기(Executor)를 생성합니다.
    1. 동기식 DB URL을 가져옵니다 (LangChain SQLDatabase는 동기 드라이버 필요).
    2. SQLDatabase 객체를 초기화합니다 (스키마 정보 로드).
    3. LangChain의 create_sql_agent 팩토리를 사용하여 에이전트를 구성합니다.
    """
    db_url = get_sync_db_url()
    
    # sample_rows_in_table_info=2: 테이블 스키마 조회 시 샘플 데이터를 2건만 포함하여 토큰 절약
    db = SQLDatabase.from_uri(db_url, sample_rows_in_table_info=2)
    
    llm = get_llm()
    
    # tool-calling: 최신 모델의 Function Calling 기능을 사용하여 SQL 생성의 정확도 향상
    return create_sql_agent(
        llm=llm,
        toolkit=None, 
        db=db,
        verbose=True,
        agent_type="tool-calling",
        prefix=SQL_PREFIX
    )

async def run_sql_agent(query: str) -> str:
    """
    SQL 에이전트를 비동기적으로 실행하는 진입점입니다.
    사용자의 자연어 질문을 입력받아, DB 조회 결과를 반환합니다.
    """
    agent_executor = create_agent_executor()
    
    try:
        # ainvoke를 사용하여 비동기 실행 (내부적으로는 별도 스레드풀 등에서 DB 접근)
        result = await agent_executor.ainvoke({"input": query})
        return result["output"]
    except Exception as e:
        return f"Error executing SQL Agent: {str(e)}"
