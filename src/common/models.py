from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, JSON, Text, ForeignKey, Integer, Date, Boolean
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
    strategy_name = Column(String(50), nullable=True, index=True)  # 전략 이름
    signal_info = Column(JSONB, nullable=True)  # 진입 당시 지표 정보 (RSI, BB 등)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
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
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class DailyRiskState(Base):
    """
    일일 리스크 관리 상태를 저장하는 테이블
    - 컨테이너 재시작 시에도 당일 손실액, 거래 횟수 등을 유지하기 위함
    """
    __tablename__ = "daily_risk_state"

    date = Column(Date, primary_key=True, default=lambda: datetime.now(timezone.utc).date())
    total_pnl = Column(Numeric(20, 8), default=0, nullable=False)
    trade_count = Column(Integer, default=0, nullable=False)
    consecutive_losses = Column(Integer, default=0, nullable=False)
    cooldown_until = Column(DateTime(timezone=True), nullable=True)
    is_trading_halted = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class AccountState(Base):
    """
    계좌 잔고 보관 테이블 (Paper Trading용)
    """
    __tablename__ = "account_state"

    id = Column(Integer, primary_key=True)
    balance = Column(Numeric(20, 8), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class Position(Base):
    """
    현재 보유 중인 포지션 정보 (Stateless Pod 지원을 위해 DB 저장)
    """
    __tablename__ = "positions"

    symbol = Column(String(20), primary_key=True)
    quantity = Column(Numeric(20, 8), nullable=False)
    avg_price = Column(Numeric(20, 8), nullable=False)
    opened_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
