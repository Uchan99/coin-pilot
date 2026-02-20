import os
import re
from typing import Any, Dict
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities import SQLDatabase

from src.agents.factory import get_chat_llm
from src.common.db import get_sync_db_url

# System Prompt for SQL Agent
SQL_PREFIX = """당신은 PostgreSQL 데이터베이스와 상호작용하는 에이전트입니다.
사용자의 질문을 받으면, 올바른 PostgreSQL 쿼리를 생성하여 실행하고, 결과를 바탕으로 답변하세요.
특별히 지정하지 않으면 결과는 최대 5개로 제한하세요.

**절대 DML/DDL 문(INSERT, UPDATE, DELETE, DROP, ALTER 등)을 실행하지 마세요.**

테이블 정보:
- market_data: 암호화폐 OHLCV 데이터 (timestamp, symbol, interval, open_price, high_price, low_price, close_price, volume)
- trading_history: 체결된 거래 내역 (created_at, executed_at, symbol, side, price, quantity, status, regime, exit_reason)
- account_state: 잔고 이력 (balance, updated_at)
- daily_risk_state: 일별 리스크 지표 (date, total_pnl, buy_count, sell_count, trade_count)
"""

# Suffix: 최종 답변 생성 직전에 적용되는 지시
SQL_SUFFIX = """**중요: 최종 답변은 반드시 한국어로 자연스럽게 작성하세요.**
- 영어로 답변하지 마세요.
- "한국어로:" 같은 접두사 없이 바로 한국어 문장으로 답변하세요.
- 예시: "현재 비트코인 가격은 117,218,000원입니다."""

# SQL 실행 직전 차단 정규식
# 주의: WITH ... DELETE 같은 패턴도 막기 위해 단어 경계로 검사합니다.
BLOCKED_SQL_PATTERN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REINDEX|GRANT|REVOKE|MERGE|CALL|COPY|COMMENT)\b",
    re.IGNORECASE,
)


# Singleton instance for caching the agent executor
_agent_executor = None


def build_readonly_db_url(db_url: str) -> str:
    """psycopg2 연결 URL에 read-only 세션 옵션을 주입합니다."""
    parsed = urlparse(db_url)
    query_items = dict(parse_qsl(parsed.query, keep_blank_values=True))

    read_only_option = "-c default_transaction_read_only=on"
    existing_options = query_items.get("options", "").strip()

    if read_only_option not in existing_options:
        query_items["options"] = (
            f"{existing_options} {read_only_option}".strip()
            if existing_options
            else read_only_option
        )

    new_query = urlencode(query_items)
    return urlunparse(parsed._replace(query=new_query))


def contains_blocked_sql(sql: str) -> bool:
    """DML/DDL 키워드 포함 여부를 판정합니다."""
    if not sql:
        return False
    compact_sql = " ".join(str(sql).strip().split())
    return bool(BLOCKED_SQL_PATTERN.search(compact_sql))


def _guard_sql_or_raise(command: Any) -> None:
    """쿼리 실행 직전 안전성 검사를 수행하고 위반 시 예외를 발생시킵니다."""
    sql = str(command)
    if contains_blocked_sql(sql):
        raise ValueError("안전 정책에 의해 DML/DDL 쿼리가 차단되었습니다.")


def _build_safe_database() -> SQLDatabase:
    """
    SQLDatabase 인스턴스에 실행 가드(정규식 차단)를 주입합니다.

    1) read-only 트랜잭션 세션 강제
    2) 실행 직전 DML/DDL 정규식 차단

    두 가지를 동시에 걸어 방어 심층(Defense in Depth)을 구성합니다.
    """
    db_url = build_readonly_db_url(get_sync_db_url())
    db = SQLDatabase.from_uri(db_url, sample_rows_in_table_info=2)

    raw_run = db.run
    raw_run_no_throw = db.run_no_throw

    def safe_run(command: Any, *args: Any, **kwargs: Any):
        _guard_sql_or_raise(command)
        return raw_run(command, *args, **kwargs)

    def safe_run_no_throw(command: Any, *args: Any, **kwargs: Any):
        try:
            _guard_sql_or_raise(command)
        except ValueError as exc:
            return f"[SQL 안전 차단] {exc}"
        return raw_run_no_throw(command, *args, **kwargs)

    db.run = safe_run  # type: ignore[assignment]
    db.run_no_throw = safe_run_no_throw  # type: ignore[assignment]
    return db


def get_or_create_agent_executor():
    """
    SQL 에이전트 실행기(Executor)를 싱글톤 패턴으로 관리합니다.
    매 요청마다 DB 연결/초기화를 반복하지 않아 성능을 최적화합니다.
    """
    global _agent_executor

    if _agent_executor is None:
        db = _build_safe_database()
        llm = get_chat_llm(temperature=0)

        # tool-calling: 최신 모델의 Function Calling 기능을 사용하여 SQL 생성의 정확도 향상
        _agent_executor = create_sql_agent(
            llm=llm,
            toolkit=None,
            db=db,
            verbose=(os.getenv("SQL_AGENT_VERBOSE", "false").lower() == "true"),
            agent_type="tool-calling",
            prefix=SQL_PREFIX,
            suffix=SQL_SUFFIX,
        )

    return _agent_executor


async def run_sql_agent(query: str) -> str:
    """
    SQL 에이전트를 비동기적으로 실행하는 진입점입니다.
    사용자의 자연어 질문을 입력받아, DB 조회 결과를 반환합니다.
    """
    try:
        # 사용자가 SQL 문을 직접 입력한 경우를 대비해 1차 차단
        if contains_blocked_sql(query):
            return "안전 정책상 데이터 변경 쿼리(DML/DDL)는 허용되지 않습니다. 조회(SELECT) 질문으로 요청해주세요."

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
    except Exception as exc:
        return f"SQL Agent 실행 중 오류가 발생했습니다: {str(exc)}"
