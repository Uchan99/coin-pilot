import asyncio
import os
from sqlalchemy import text
from src.common.db import engine

async def verify_database():
    print("[*] Connecting to database...")
    try:
        async with engine.connect() as conn:
            # 1. Check Extensions
            print("[*] Checking extensions...")
            result = await conn.execute(text("SELECT extname FROM pg_extension;"))
            extensions = [row[0] for row in result]
            print(f"[+] Extensions found: {extensions}")
            
            required_extensions = ['timescaledb', 'vector', 'uuid-ossp']
            for ext in required_extensions:
                if ext in extensions:
                    print(f"  [✓] {ext} is installed.")
                else:
                    print(f"  [✗] {ext} is MISSING.")

            # 2. Check Tables
            print("[*] Checking tables...")
            result = await conn.execute(text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public';"))
            tables = [row[0] for row in result]
            print(f"[+] Tables found: {tables}")
            
            required_tables = ['market_data', 'trading_history', 'risk_audit', 'agent_memory']
            for table in required_tables:
                if table in tables:
                    print(f"  [✓] {table} is created.")
                else:
                    print(f"  [✗] {table} is MISSING.")
            
            # 3. Check Hypertable
            print("[*] Checking if market_data is a hypertable...")
            result = await conn.execute(text("SELECT * FROM timescaledb_information.hypertables WHERE hypertable_name = 'market_data';"))
            row = result.fetchone()
            if row:
                print("  [✓] market_data is a hypertable.")
            else:
                print("  [✗] market_data is NOT a hypertable.")

    except Exception as e:
        print(f"[!] Verification failed: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify_database())
