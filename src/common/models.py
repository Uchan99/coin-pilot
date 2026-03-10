from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, JSON, Text, ForeignKey, Integer, Date, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import declarative_base, relationship
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class MarketData(Base):
    """
    시장 데이터 (OHLCV) 테이블 - TimescaleDB 하이퍼테이블로 사용됨
    - AI SQL Agent가 기술 지표 계산 시 주로 참조
    """
    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint('symbol', 'interval', 'timestamp', name='uq_market_data_symbol_interval_ts'),
    )

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
    regime = Column(String(10), nullable=True)  # 진입 시 레짐
    high_water_mark = Column(Numeric(20, 8), nullable=True)  # 청산 시점 최고가
    exit_reason = Column(String(30), nullable=True)  # 청산 사유
    post_exit_prices = Column(JSONB, nullable=True)  # 매도 후 1h/4h/12h/24h 추적 가격
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
    buy_count = Column(Integer, default=0, nullable=False)
    sell_count = Column(Integer, default=0, nullable=False)
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
    regime = Column(String(10), nullable=True)  # 진입 시 레짐
    high_water_mark = Column(Numeric(20, 8), nullable=True)  # 보유 중 최고가 (실시간 갱신)
    opened_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class RegimeHistory(Base):
    """
    마켓 레짐 감지 이력 테이블
    """
    __tablename__ = "regime_history"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    regime = Column(String(10), nullable=False)  # BULL, SIDEWAYS, BEAR, UNKNOWN
    ma50 = Column(Numeric(20, 8), nullable=True)
    ma200 = Column(Numeric(20, 8), nullable=True)
    diff_pct = Column(Numeric(10, 4), nullable=True)
    coin_symbol = Column(String(10), nullable=False, default='BTC', index=True)

class AgentDecision(Base):
    """
    AI 에이전트의 의사결정 이력 및 근거 저장 테이블
    """
    __tablename__ = "agent_decisions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    strategy_name = Column(String(50), nullable=False, index=True)
    decision = Column(String(20), nullable=False)  # CONFIRM, REJECT, SAFE, WARNING
    reasoning = Column(Text, nullable=True)        # AI의 분석 근거
    confidence = Column(Integer, nullable=True)     # 확신도 (0-100)
    model_used = Column(String(50), nullable=True) # 사용된 LLM 모델명
    # v3.0 추가: REJECT 검증용 필드
    price_at_decision = Column(Numeric(20, 8), nullable=True)  # 결정 시점 가격
    regime = Column(String(10), nullable=True)     # 결정 시점 레짐
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


class RuleFunnelEvent(Base):
    """
    Rule -> Risk -> AI 퍼널 단계를 레짐별로 계측하는 이벤트 테이블.

    설계 의도:
    - agent_decisions만으로는 "AI가 적게 호출된 원인"을 분리할 수 없으므로,
      Rule pass / Risk reject / AI guardrail block / AI final decision을
      동일 스키마로 누적해 병목 지점을 직접 SQL로 확인한다.
    - 주문 로직을 바꾸지 않고 관측만 추가하는 목적이므로, 최소 필드만 저장한다.
    """
    __tablename__ = "rule_funnel_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    strategy_name = Column(String(50), nullable=True, index=True)
    regime = Column(String(10), nullable=True, index=True)
    stage = Column(String(40), nullable=False, index=True)
    result = Column(String(20), nullable=False, index=True)
    reason_code = Column(String(80), nullable=True, index=True)
    reason = Column(Text, nullable=True)


class LlmUsageEvent(Base):
    """
    LLM 호출 단위 usage/cost 원장 테이블.

    설계 의도:
    - 계정 잔여 크레딧 감소량만으로는 원인 분리가 불가능하므로,
      "어떤 경로(route)가 어떤 모델을 얼마나 사용했는지"를 이벤트 단위로 저장한다.
    - 저장 실패 시 본 기능(매매/챗봇/리포트)을 중단하면 운영 리스크가 커지므로
      호출부에서 soft-fail로 기록한다.
    """
    __tablename__ = "llm_usage_events"
    __table_args__ = (
        UniqueConstraint("request_id", name="uq_llm_usage_events_request_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    request_id = Column(String(128), nullable=True)

    route = Column(String(64), nullable=False, index=True)
    feature = Column(String(64), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    model = Column(String(128), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="success", index=True)
    error_type = Column(String(80), nullable=True, index=True)

    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Numeric(20, 8), nullable=True)
    price_version = Column(String(32), nullable=False, default="v1")
    latency_ms = Column(Integer, nullable=True)

    meta = Column(JSONB, nullable=True)


class LlmCreditSnapshot(Base):
    """
    LLM 계정 잔여 크레딧 스냅샷 테이블.

    목적:
    - usage 원장 합계와 계정 단위 변화를 대조(reconciliation)하기 위한 보조 지표.
    """
    __tablename__ = "llm_credit_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    balance_usd = Column(Numeric(20, 8), nullable=False)
    balance_unit = Column(String(20), nullable=False, default="usd")
    source = Column(String(40), nullable=False, default="manual")
    note = Column(Text, nullable=True)


class LlmProviderCostSnapshot(Base):
    """
    provider 비용 스냅샷 테이블.

    목적:
    - provider의 공식 비용 API(기간 비용)를 저장해
      내부 usage 원장 합계와 외부 비용 합계를 대조(reconciliation)한다.
    - "잔여 크레딧(balance)"가 아닌 "구간 비용(cost)" 기반이므로
      route 분리 원장과 함께 해석해야 정확한 운영 판단이 가능하다.
    """
    __tablename__ = "llm_provider_cost_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    provider = Column(String(32), nullable=False, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False, index=True)
    window_end = Column(DateTime(timezone=True), nullable=False, index=True)
    cost_usd = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(10), nullable=False, default="usd")
    source = Column(String(40), nullable=False, default="provider_cost_api")
    note = Column(Text, nullable=True)


class ExchangeAccountSnapshot(Base):
    """
    거래소 계좌 스냅샷 테이블.

    왜 별도 테이블이 필요한가:
    - 기존 `account_state`는 paper 잔고 1개 row만 표현하므로,
      실거래의 "KRW + 코인 잔고 + 주문 잠금(locked) + 평균매수가"를 담을 수 없다.
    - 실거래 전환 시 Dashboard/정산은 paper 장부가 아니라 거래소 스냅샷을
      기준으로 canonical portfolio를 만들어야 하므로, 원장(raw snapshot)을 먼저 보존한다.
    """
    __tablename__ = "exchange_account_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    exchange = Column(String(32), nullable=False, default="upbit", index=True)
    asset_symbol = Column(String(20), nullable=False, index=True)
    balance = Column(Numeric(20, 8), nullable=False)
    locked = Column(Numeric(20, 8), nullable=False, default=0)
    avg_buy_price = Column(Numeric(20, 8), nullable=True)
    unit_currency = Column(String(10), nullable=True)
    source = Column(String(40), nullable=False, default="exchange_api")
    raw_payload = Column(JSONB, nullable=True)


class ExchangeOrder(Base):
    """
    거래소 주문 원장 테이블.

    설계 의도:
    - `trading_history`는 전략 관점 trade log로 유지하고,
      실제 거래소의 주문 상태(pending/partial/filled/cancelled)는 별도 원장으로 보존한다.
    - 추후 live executor/reconciliation/job이 같은 표준 필드를 쓰도록
      상태/수량/수수료/원본 payload를 최소 단위로 저장한다.
    """
    __tablename__ = "exchange_orders"
    __table_args__ = (
        UniqueConstraint("exchange_order_id", name="uq_exchange_orders_exchange_order_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    exchange = Column(String(32), nullable=False, default="upbit", index=True)
    exchange_order_id = Column(String(128), nullable=False)
    client_order_id = Column(String(128), nullable=True, index=True)
    market = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    ord_type = Column(String(20), nullable=False)
    state = Column(String(20), nullable=False, index=True)
    requested_price = Column(Numeric(20, 8), nullable=True)
    requested_volume = Column(Numeric(20, 8), nullable=True)
    remaining_volume = Column(Numeric(20, 8), nullable=True)
    executed_volume = Column(Numeric(20, 8), nullable=True)
    avg_fill_price = Column(Numeric(20, 8), nullable=True)
    paid_fee = Column(Numeric(20, 8), nullable=True)
    reserved_fee = Column(Numeric(20, 8), nullable=True)
    remaining_fee = Column(Numeric(20, 8), nullable=True)
    locked = Column(Numeric(20, 8), nullable=True)
    time_in_force = Column(String(20), nullable=True)
    source = Column(String(20), nullable=False, default="live")
    strategy_name = Column(String(50), nullable=True, index=True)
    signal_info = Column(JSONB, nullable=True)
    raw_payload = Column(JSONB, nullable=True)


class ExchangeFill(Base):
    """
    거래소 체결 원장 테이블.

    실패 모드/엣지케이스:
    - 실거래는 한 주문이 여러 fill로 나뉠 수 있으므로, order row 1개만으로는
      실제 체결 평균가/수량/수수료를 정확히 재구성할 수 없다.
    - 따라서 fill 단위를 별도 테이블로 저장해 이후 realized PnL과 history audit을 계산한다.
    """
    __tablename__ = "exchange_fills"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    exchange = Column(String(32), nullable=False, default="upbit", index=True)
    exchange_order_id = Column(String(128), nullable=False, index=True)
    exchange_trade_id = Column(String(128), nullable=True, index=True)
    market = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False)
    fill_price = Column(Numeric(20, 8), nullable=False)
    fill_volume = Column(Numeric(20, 8), nullable=False)
    fee = Column(Numeric(20, 8), nullable=True)
    liquidity = Column(String(20), nullable=True)
    filled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    source = Column(String(20), nullable=False, default="exchange_fill")
    raw_payload = Column(JSONB, nullable=True)


class ReconciliationRun(Base):
    """
    거래소-DB 정산 실행 이력 테이블.

    왜 필요한가:
    - 실거래 전환의 핵심 리스크는 전략보다 정산 불일치다.
    - 매 실행마다 mismatch 건수와 세부 details를 남겨야,
      신규 BUY 차단/kill switch/운영 보고의 근거를 수치로 설명할 수 있다.
    """
    __tablename__ = "reconciliation_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    exchange = Column(String(32), nullable=False, default="upbit", index=True)
    mode = Column(String(20), nullable=False, default="dry_run")
    status = Column(String(20), nullable=False, index=True)
    snapshot_started_at = Column(DateTime(timezone=True), nullable=True)
    snapshot_finished_at = Column(DateTime(timezone=True), nullable=True)
    account_mismatch_count = Column(Integer, nullable=False, default=0)
    order_mismatch_count = Column(Integer, nullable=False, default=0)
    fill_mismatch_count = Column(Integer, nullable=False, default=0)
    portfolio_mismatch_count = Column(Integer, nullable=False, default=0)
    note = Column(Text, nullable=True)
    details = Column(JSONB, nullable=True)


class NewsArticle(Base):
    """
    RSS에서 수집한 뉴스 원본/정규화 데이터를 저장하는 테이블.
    - content_hash unique로 중복 기사 재적재를 방지
    - symbols 배열은 심볼 기반 조회 성능을 위해 GIN 인덱스 사용 예정
    """
    __tablename__ = "news_articles"
    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_news_articles_content_hash"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False)
    feed_url = Column(Text, nullable=False)
    article_url = Column(Text, nullable=True)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=False, index=True)
    symbols = Column(ARRAY(String(20)), nullable=False, default=list)
    risk_signal_score = Column(Numeric(6, 2), nullable=False, default=0)
    risk_drivers = Column(JSONB, nullable=True)
    content_hash = Column(String(64), nullable=False)
    ingested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class NewsSummary(Base):
    """
    일정 시간창(window) 기준으로 심볼별 뉴스 요약을 저장하는 테이블.
    """
    __tablename__ = "news_summaries"
    __table_args__ = (
        UniqueConstraint("symbol", "window_start", "window_end", name="uq_news_summaries_symbol_window"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    summary_text = Column(Text, nullable=False)
    key_points = Column(JSONB, nullable=True)
    article_count = Column(Integer, nullable=False, default=0)
    model_used = Column(String(50), nullable=False, default="rss-rule-v1")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class NewsRiskScore(Base):
    """
    심볼별 뉴스 위험 점수(0~100)와 등급을 저장하는 테이블.
    챗봇/리스크 진단에서 최신 점수를 조회해 사용한다.
    """
    __tablename__ = "news_risk_scores"
    __table_args__ = (
        UniqueConstraint("symbol", "window_start", "window_end", name="uq_news_risk_scores_symbol_window"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    risk_score = Column(Numeric(6, 2), nullable=False)
    risk_level = Column(String(10), nullable=False)
    drivers = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
