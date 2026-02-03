"""
멀티 코인 지원을 위한 DB 인덱스 최적화 스크립트

목적:
    기존 테이블 구조는 이미 심볼 컬럼을 포함하고 있으나,
    다중 코인 전략 실행 시 '심볼별' 조회 성능을 최적화하기 위해 인덱스를 추가함.
    
실행 방법:
    PYTHONPATH=. python scripts/migrate_multi_coin.py
"""
import asyncio
from sqlalchemy import text
from src.common.db import get_db_session

# 추가할 인덱스 정의
MIGRATIONS = [
    # 1. Trading History 조회 최적화
    # 봇이 특정 코인의 과거 거래 내역을 조회할 때 (심볼 + 시간 역순) 사용됨
    """
    CREATE INDEX IF NOT EXISTS idx_trading_history_symbol_time
    ON trading_history(symbol, created_at DESC);
    """,

    # 2. Agent Decision 조회 최적화
    # AI 에이전트가 특정 코인에 대한 과거 판단을 참조할 때 사용됨
    """
    CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol_time
    ON agent_decisions(symbol, created_at DESC);
    """,
]

async def run_migrations():
    """
    DB 마이그레이션 실행 함수
    정의된 SQL 인덱스 생성 구문을 순차적으로 실행하며, 오류 발생 시 로깅하고 건너뜀.
    (IF NOT EXISTS 구문이 있어 중복 실행 해도 안전함)
    """
    print("[*] Starting DB Migration for Multi-Coin Support...")
    
    async with get_db_session() as session:
        for i, sql in enumerate(MIGRATIONS, 1):
            try:
                # SQL 실행
                await session.execute(text(sql))
                await session.commit()
                print(f"[✓] Index {i}/{len(MIGRATIONS)} 생성 및 적용 완료")
            except Exception as e:
                # 이미 존재하는 등의 이유로 실패 시 로그만 남기고 진행
                print(f"[!] Index {i} 생성 실패 (또는 스킵): {e}")

    print("\n[OK] 모든 인덱스 최적화 작업이 완료되었습니다.")

if __name__ == "__main__":
    asyncio.run(run_migrations())
