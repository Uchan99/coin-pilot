import asyncio
import os
from sqlalchemy import text
from src.common.db import get_db_session

async def migrate():
    """Week 3: AI Agent Integration을 위한 DB 마이그레이션"""
    print("[*] Starting Week 3 Migration...")
    
    async with get_db_session() as session:
        # AgentDecision 테이블 생성
        commands = [
            """
            CREATE TABLE IF NOT EXISTS agent_decisions (
                id BIGSERIAL PRIMARY KEY,
                symbol VARCHAR(20) NOT NULL,
                strategy_name VARCHAR(50) NOT NULL,
                decision VARCHAR(20) NOT NULL,
                reasoning TEXT,
                confidence INTEGER,
                model_used VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol ON agent_decisions(symbol)",
            "CREATE INDEX IF NOT EXISTS idx_agent_decisions_strategy ON agent_decisions(strategy_name)",
            "CREATE INDEX IF NOT EXISTS idx_agent_decisions_created_at ON agent_decisions(created_at)"
        ]
        for cmd in commands:
            await session.execute(text(cmd))
        await session.commit()
    
    print("[OK] Week 3 Migration Completed (agent_decisions table created).")

if __name__ == "__main__":
    asyncio.run(migrate())
