import asyncio
import os
from sqlalchemy import text
from src.common.db import engine

async def reinit_database():
    print("[*] Re-initializing database...")
    init_sql_path = "deploy/db/init.sql"
    
    with open(init_sql_path, "r") as f:
        sql_script = f.read()

    # SQL 스크립트를 문장 단위로 분리 (간단한 구현)
    # 실제로는 PG 파서가 필요하지만, 코멘트와 세미콜론 기준으로 분리 시도
    statements = [s.strip() for s in sql_script.split(";") if s.strip()]

    async with engine.connect() as conn:
        for statement in statements:
            try:
                print(f"[*] Executing: {statement[:50]}...")
                await conn.execute(text(statement))
                await conn.commit()
            except Exception as e:
                print(f"[!] Warning (skipping): {e}")
                await conn.rollback()

    print("[+] Database re-initialization finished.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(reinit_database())
