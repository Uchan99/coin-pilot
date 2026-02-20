from functools import lru_cache
from typing import Any, Dict, List

from sqlalchemy import create_engine, text

from src.common.db import get_sync_db_url


@lru_cache(maxsize=1)
def get_tool_engine():
    """Tool 계층 공용 동기 Engine (읽기 전용 조회 용도)."""
    return create_engine(get_sync_db_url(), pool_pre_ping=True, pool_size=5, max_overflow=5)


def fetch_all(query: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    """SELECT 결과를 dict 리스트로 반환합니다."""
    engine = get_tool_engine()
    with engine.connect() as conn:
        rows = conn.execute(text(query), params or {}).fetchall()
    return [dict(row._mapping) for row in rows]


def fetch_one(query: str, params: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    """단일 행 조회 결과를 dict로 반환합니다."""
    rows = fetch_all(query, params=params)
    return rows[0] if rows else None
