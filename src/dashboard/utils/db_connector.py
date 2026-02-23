import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# .env 로드
load_dotenv()

def _build_sync_db_url() -> str:
    # 운영 환경에서 약한 기본 비밀번호 폴백(postgres)을 막기 위해
    # DATABASE_URL이 없으면 DB_PASSWORD를 필수로 요구한다.
    async_url = os.getenv("DATABASE_URL")
    if async_url and "asyncpg" in async_url:
        return async_url.replace("+asyncpg", "")
    if async_url:
        return async_url

    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "coinpilot")

    if not db_password:
        raise RuntimeError(
            "DB_PASSWORD is required when DATABASE_URL is not set."
        )

    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"


# 동기식 DB 연결 (Sync Engine)
# Streamlit은 멀티스레드 환경이므로 Async Engine을 억지로 쓰기보다
# 별도의 Sync Engine을 만드는 것이 훨씬 안정적입니다.
def get_sync_db_url():
    return _build_sync_db_url()

# 전역 엔진 생성 (Connection Pool 공유)
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        db_url = get_sync_db_url()
        # DB 재기동 후 죽은 커넥션(stale socket)을 재사용하면
        # OperationalError(server closed connection)가 간헐적으로 발생할 수 있다.
        # pool_pre_ping으로 커넥션 체크 후 필요 시 자동 재연결해 복원력을 높인다.
        _engine = create_engine(
            db_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=10,
            pool_use_lifo=True,
        )
    return _engine

@st.cache_data(ttl=30)
def get_data_as_dataframe(query: str, params: dict = None) -> pd.DataFrame:
    """
    [동기 방식] SQL 쿼리를 실행하여 Pandas DataFrame으로 반환합니다.
    psycopg2 드라이버를 사용하여 Async Loop 이슈를 원천 차단합니다.
    """
    try:
        engine = get_engine()
        # Pandas의 read_sql은 params를 dict로 받지 않고 리스트나 튜플로 받는 경우가 많아,
        # SQLAlchemy Connection을 직접 사용하여 실행
        with engine.connect() as conn:
            # text()로 감싸서 실행
            result = conn.execute(text(query), params or {})
            # 컬럼명 가져오기
            columns = result.keys()
            # 데이터 가져오기
            data = result.fetchall()
            
            if not data:
                return pd.DataFrame(columns=columns)
                
            return pd.DataFrame(data, columns=columns)
            
    except Exception as e:
        # 에러 메시지를 좀 더 명확하게 표시
        st.error(f"DB Error: {str(e)}")
        # 빈 값 반환하여 UI 깨짐 방지
        return pd.DataFrame()

def check_db_connection() -> bool:
    """
    DB 연결 상태를 확인합니다.
    """
    try:
        df = get_data_as_dataframe("SELECT 1 as connected")
        return not df.empty and df.iloc[0]['connected'] == 1
    except Exception:
        return False
