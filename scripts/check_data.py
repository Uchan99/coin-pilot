import asyncio
from sqlalchemy import text
from src.common.db import engine

async def check_data():
    print("[*] Queries latest market data...")
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM market_data ORDER BY timestamp DESC LIMIT 5;"))
        rows = result.fetchall()
        
        if not rows:
            print("[-] No data found in market_data.")
            return

        print(f"[+] Found {len(rows)} records:")
        for row in rows:
            # row indices based on init.sql: id, symbol, interval, open, high, low, close, volume, timestamp
            print(f"  {row.timestamp} | {row.symbol} | Close: {row.close_price} | Vol: {row.volume}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_data())
