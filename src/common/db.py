import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from dotenv import load_dotenv

# .env 파일 로드 (src/폴더 상위 기준)
load_dotenv()

# 데이터베이스 연결 URL 구성 (asyncpg 사용)
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "coinpilot")
    
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

def get_sync_db_url() -> str:
    """
    LangChain SQLDatabase 등 동기식 연결이 필요한 도구를 위한 URL 반환
    (asyncpg -> psycopg2)
    """
    if not DATABASE_URL:
        # Fallback if env vars not loaded properly, though they should be
        return f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

# 비동기 엔진 생성
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # SQL 로그 출력 여부 (디버깅 시 True)
    future=True,
    pool_size=20,
    max_overflow=10
)

# 비동기 세션 팩토리
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    데이터베이스 비동기 세션을 생성하고 제공하는 컨텍스트 매니저
    의존성 주입 또는 직접 세션이 필요할 때 사용
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# Redis 연결 설정
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

async def get_redis_client():
    """
    Redis 클라이언트를 생성하여 반환합니다. (aioredis 사용 권장 - redis-py 4.2+ 통합됨)
    """
    import redis.asyncio as redis
    client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return client

async def init_db_models():
    """
    (주의) 이 함수는 SQLAlchemy를 통해 테이블을 생성합니다. 
    TimescaleDB 하이퍼테이블 등 고급 설정은 init.sql에서 처리하지만, 
    기본 테이블 구조 정합성을 위해 호출할 수 있습니다.
    """
    from src.common.models import Base
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.create_all)
        pass # 현재는 init.sql을 통해 생성하는 것을 권장
