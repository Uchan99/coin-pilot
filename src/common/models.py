from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, JSON, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class MarketData(Base):
    """
    시장 데이터 (OHLCV) 테이블 - TimescaleDB 하이퍼테이블로 사용됨
    - AI SQL Agent가 기술 지표 계산 시 주로 참조
    """
    __tablename__ = "market_data"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    interval = Column(String(10), nullable=False, index=True)
    open_price = Column(Numeric(20, 8), nullable=False)
    high_price = Column(Numeric(20, 8), nullable=False)
    low_price = Column(Numeric(20, 8), nullable=False)
    close_price = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(20, 8), nullable=False)
    timestamp = Column(DateTime(timezone=True), primary_key=True, nullable=False, index=True)

class TradingHistory(Base):
    """
    거래 이력 (주문/체결) 테이블
    - 실제 매매 결과 및 성과 분석 데이터 저장
    """
    __tablename__ = "trading_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)  # BUY, SELL
    order_type = Column(String(10), nullable=False)  # LIMIT, MARKET
    price = Column(Numeric(20, 8), nullable=False)
    quantity = Column(Numeric(20, 8), nullable=False)
    fee = Column(Numeric(20, 8), default=0)
    status = Column(String(20), nullable=False)  # FILLED, CANCELLED, PENDING
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    # RiskAudit과의 관계 (1:N)
    risk_audits = relationship("RiskAudit", back_populates="related_order")

class RiskAudit(Base):
    """
    리스크 관리 위반 및 감사 기록 테이블
    - 리스크 엔진에 의해 차단된 활동이나 경고 기록
    """
    __tablename__ = "risk_audit"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    violation_type = Column(String(50), nullable=False)
    description = Column(Text)
    related_order_id = Column(UUID(as_uuid=True), ForeignKey("trading_history.id"), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow)

    # TradingHistory와의 관계
    related_order = relationship("TradingHistory", back_populates="risk_audits")

class AgentMemory(Base):
    """
    AI 에이전트 기억장치 (벡터 저장소 포함)
    - pgvector를 사용하여 성공/실패 패턴 및 당시 상황(context) 저장
    """
    __tablename__ = "agent_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    agent_type = Column(String(20), nullable=False, index=True) # SQL_AGENT, RAG_AGENT
    context = Column(JSONB)
    decision = Column(Text)
    outcome = Column(String(20)) # SUCCESS, FAILURE
    embedding = Column(Vector(1536)) # OpenAI/Claude Embedding Dimension
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
