import asyncio
import os
from sqlalchemy import text
from src.common.db import engine

async def run_migration():
    migration_file = "migrations/004_add_pgvector.sql"
    
    print(f"Reading migration file: {migration_file}")
    with open(migration_file, "r") as f:
        sql_content = f.read()

    print("Executing migration...")
    async with engine.begin() as conn:
        # Split statements by semicolon
        statements = sql_content.split(';')
        for stmt in statements:
            if stmt.strip():
                print(f"Executing: {stmt[:50]}...")
                await conn.execute(text(stmt))
    
    print("Migration completed successfully.")

if __name__ == "__main__":
    asyncio.run(run_migration())
