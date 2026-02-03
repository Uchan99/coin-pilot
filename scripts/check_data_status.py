
import asyncio
from sqlalchemy import text
from src.common.db import get_db_session

async def check_data():
    async with get_db_session() as session:
        result = await session.execute(text('''
            SELECT symbol, COUNT(*) as cnt, MAX(timestamp) as latest
            FROM market_data
            GROUP BY symbol
            ORDER BY symbol
        '''))
        for row in result:
            print(f'{row.symbol}: {row.cnt}건, 최신: {row.latest}')

if __name__ == "__main__":
    asyncio.run(check_data())
