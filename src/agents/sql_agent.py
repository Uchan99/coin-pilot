from typing import Any, Dict
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from src.common.db import get_sync_db_url
from src.agents.config import LLM_MODEL
import os

# System Prompt for SQL Agent
SQL_PREFIX = """당신은 PostgreSQL 데이터베이스와 상호작용하는 에이전트입니다.
사용자의 질문을 받으면, 올바른 PostgreSQL 쿼리를 생성하여 실행하고, 결과를 바탕으로 답변하세요.
특별히 지정하지 않으면 결과는 최대 5개로 제한하세요.

**절대 DML 문(INSERT, UPDATE, DELETE, DROP 등)을 실행하지 마세요.**

테이블 정보:
- market_data: 암호화폐 OHLCV 데이터 (timestamp, symbol, open, high, low, close, volume)
- trading_history: 체결된 거래 내역 (timestamp, symbol, side, price, amount, pnl)
- account_state: 잔고 이력 (timestamp, total_balance_krw, cash_krw, locked_krw)
- daily_risk_state: 일별 리스크 지표 (date, daily_loss_rate, trade_count)
"""

# Suffix: 최종 답변 생성 직전에 적용되는 지시
SQL_SUFFIX = """**중요: 최종 답변은 반드시 한국어로 자연스럽게 작성하세요.**
- 영어로 답변하지 마세요.
- "한국어로:" 같은 접두사 없이 바로 한국어 문장으로 답변하세요.
- 예시: "현재 비트코인 가격은 117,218,000원입니다."""

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

# Singleton instance for caching the agent executor
_agent_executor = None

def get_or_create_agent_executor():
    """
    SQL 에이전트 실행기(Executor)를 싱글톤 패턴으로 관리합니다.
    매 요청마다 DB 연결/초기화를 반복하지 않아 성능을 최적화합니다.
    """
    global _agent_executor
    
    if _agent_executor is None:
        db_url = get_sync_db_url()
        
        # sample_rows_in_table_info=2: 테이블 스키마 조회 시 샘플 데이터를 2건만 포함하여 토큰 절약
        db = SQLDatabase.from_uri(db_url, sample_rows_in_table_info=2)
        
        llm = get_llm()
        
        # tool-calling: 최신 모델의 Function Calling 기능을 사용하여 SQL 생성의 정확도 향상
        _agent_executor = create_sql_agent(
            llm=llm,
            toolkit=None,
            db=db,
            verbose=True,
            agent_type="tool-calling",
            prefix=SQL_PREFIX,
            suffix=SQL_SUFFIX
        )
        
    return _agent_executor

async def run_sql_agent(query: str) -> str:
    """
    SQL 에이전트를 비동기적으로 실행하는 진입점입니다.
    사용자의 자연어 질문을 입력받아, DB 조회 결과를 반환합니다.
    """
    try:
        agent_executor = get_or_create_agent_executor()
        
        # ainvoke를 사용하여 비동기 실행 (내부적으로는 별도 스레드풀 등에서 DB 접근)
        result = await agent_executor.ainvoke({"input": query})
        
        # Output Parsing Logic:
        # tool-calling 에이전트(Anthropic)가 경우에 따라 Text Block List를 반환할 수 있음.
        # 예: [{'text': 'Balance is ...', 'type': 'text', ...}]
        output = result.get("output", "")
        
        if isinstance(output, list):
            # 모든 텍스트 블록을 추출하여 결합 (다중 반환 대응)
            texts = [
                item.get("text", str(item)) if isinstance(item, dict) else str(item) 
                for item in output
            ]
            return "\n".join(texts)
            
        return str(output)
    except Exception as e:
        return f"Error executing SQL Agent: {str(e)}"
