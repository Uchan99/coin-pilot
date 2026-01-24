import pytest_asyncio
import asyncio
from datetime import datetime, timezone
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from src.common.models import Base

# 테스팅을 위한 비동기 SQLite 인메모리 엔진 설정 명시
# 테스팅을 위한 PostgreSQL 테스트용 DB 설정
# 테스팅을 위한 PostgreSQL 테스트용 DB 설정
# (docker exec로 생성한 coinpilot_test DB 사용)
TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot_test"

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """테스트용 DB 엔진 생성 및 스키마 초기화"""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=pool.NullPool)
    
    # 테스트 시작 전 기존 테이블 모두 삭제 (완전한 격리)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture
async def test_db(test_engine) -> AsyncSession:
    """각 테스트마다 독립된 세션을 제공하는 피스처"""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session
        await session.rollback()
