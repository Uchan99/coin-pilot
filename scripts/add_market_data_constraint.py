import asyncio
import os
from sqlalchemy import text
from src.common.db import get_db_session

async def migrate():
    """Add Unique Constraint to market_data table"""
    print("[*] Adding Unique Constraint to market_data...")
    
    async with get_db_session() as session:
        # 중복 데이터 제거 (Constraint 추가 전 정제)
        # symbol, interval, timestamp가 같은 데이터 중 id가 가장 큰 것만 남기고 삭제
        # TimescaleDB 하이퍼테이블에서는 DELETE가 비용이 클 수 있으나, 중복 제거는 필수
        
        print("[*] Cleaning up duplicate data...")
        cleanup_sql = """
        DELETE FROM market_data a USING (
            SELECT min(id) as id, symbol, interval, timestamp 
            FROM market_data 
            GROUP BY symbol, interval, timestamp 
            HAVING count(*) > 1
        ) b 
        WHERE a.symbol = b.symbol 
          AND a.interval = b.interval 
          AND a.timestamp = b.timestamp 
          AND a.id <> b.id;
        """
        # Note: TimescaleDB might have restrictions on DELETE. 
        # If this fails, we might need a different approach, but standard PG delete works on chunks.
        try:
            await session.execute(text(cleanup_sql))
            print("[+] Duplicates cleaned up.")
        except Exception as e:
            print(f"[!] Warning cleaning duplicates: {e}")

        print("[*] Creating Unique Index/Constraint...")
        # TimescaleDB에서 unique constraint는 partition key(timestamp)를 포함해야 함 (이미 포함됨)
        # ADD CONSTRAINT
        commands = [
            """
            ALTER TABLE market_data 
            ADD CONSTRAINT uq_market_data_symbol_interval_ts 
            UNIQUE (symbol, interval, timestamp);
            """
        ]
        
        for cmd in commands:
            try:
                await session.execute(text(cmd))
                print("[+] Constraint added successfully.")
            except Exception as e:
                if "already exists" in str(e):
                    print("[!] Constraint already exists.")
                else:
                    print(f"[!] Error adding constraint: {e}")
                    
        await session.commit()
    
    print("[OK] Migration Completed.")

if __name__ == "__main__":
    asyncio.run(migrate())
