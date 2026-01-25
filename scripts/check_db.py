import asyncio
from sqlalchemy import select
from src.common.db import get_db_session
from src.common.models import AgentDecision

async def check():
    async with get_db_session() as session:
        result = await session.execute(select(AgentDecision))
        rows = result.scalars().all()
        print(f"Total decisions found: {len(rows)}")
        for r in rows:
            print(f"- {r.decision} ({r.symbol}): {r.reasoning}")

if __name__ == "__main__":
    asyncio.run(check())
