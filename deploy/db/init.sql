-- CoinPilot v3.0 Database Initialization Script
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

CREATE EXTENSION IF NOT EXISTS vector;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS market_data (
    id BIGSERIAL,
    symbol VARCHAR(20) NOT NULL,
    interval VARCHAR(10) NOT NULL,
    open_price NUMERIC(20, 8) NOT NULL,
    high_price NUMERIC(20, 8) NOT NULL,
    low_price NUMERIC(20, 8) NOT NULL,
    close_price NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    PRIMARY KEY (timestamp, id)
);

SELECT create_hypertable (
        'market_data', 'timestamp', if_not_exists => TRUE
    );

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_interval_time ON market_data (
    symbol,
    interval,
    timestamp DESC
);

ALTER TABLE market_data
SET (
        timescaledb.compress,
        timescaledb.compress_segmentby = 'symbol, interval'
    );

SELECT add_compression_policy (
        'market_data', INTERVAL '7 days', if_not_exists => TRUE
    );

ALTER TABLE market_data
ADD CONSTRAINT uq_market_data_symbol_interval_ts UNIQUE (symbol, interval, timestamp);

CREATE TABLE IF NOT EXISTS trading_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(10) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    fee NUMERIC(20, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(50),
    signal_info JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_trading_history_strategy ON trading_history (strategy_name);

CREATE INDEX IF NOT EXISTS idx_trading_history_symbol_created ON trading_history (symbol, created_at DESC);

CREATE TABLE IF NOT EXISTS risk_audit (
    id SERIAL PRIMARY KEY,
    violation_type VARCHAR(50) NOT NULL,
    description TEXT,
    related_order_id UUID REFERENCES trading_history (id),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4 (),
    agent_type VARCHAR(20) NOT NULL,
    context JSONB,
    decision TEXT,
    outcome VARCHAR(20),
    embedding vector (1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_type ON agent_memory (agent_type);

CREATE INDEX IF NOT EXISTS idx_agent_memory_embedding ON agent_memory USING hnsw (embedding vector_cosine_ops);

-- AI Agent 의사결정 이력 (System 페이지 및 분석 리포트에서 사용)
-- 참고: 기존 K8s init SQL에는 존재했지만 Compose init SQL에는 누락되어
-- 운영 전환 시 조회 오류가 발생할 수 있어 baseline 스키마에 포함한다.
CREATE TABLE IF NOT EXISTS agent_decisions (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(50) NOT NULL,
    decision VARCHAR(20) NOT NULL,
    reasoning TEXT,
    confidence INTEGER,
    model_used VARCHAR(50),
    price_at_decision NUMERIC(20, 8),
    regime VARCHAR(10),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol ON agent_decisions (symbol);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_created ON agent_decisions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision ON agent_decisions (decision);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_regime ON agent_decisions (regime);

-- LLM usage/cost observability (21-04)
CREATE TABLE IF NOT EXISTS llm_usage_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    request_id VARCHAR(128),
    route VARCHAR(64) NOT NULL,
    feature VARCHAR(64) NOT NULL,
    provider VARCHAR(32) NOT NULL,
    model VARCHAR(128) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'success',
    error_type VARCHAR(80),
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_usd NUMERIC(20, 8),
    price_version VARCHAR(32) NOT NULL DEFAULT 'v1',
    latency_ms INTEGER,
    meta JSONB,
    CONSTRAINT uq_llm_usage_events_request_id UNIQUE (request_id)
);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_created ON llm_usage_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_events_route_created ON llm_usage_events (route, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_events_provider_model_created ON llm_usage_events (provider, model, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_usage_events_status_created ON llm_usage_events (status, created_at DESC);

CREATE TABLE IF NOT EXISTS llm_credit_snapshots (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    provider VARCHAR(32) NOT NULL,
    balance_usd NUMERIC(20, 8) NOT NULL,
    balance_unit VARCHAR(20) NOT NULL DEFAULT 'usd',
    source VARCHAR(40) NOT NULL DEFAULT 'manual',
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_credit_snapshots_provider_created ON llm_credit_snapshots (provider, created_at DESC);

-- Provider Cost Snapshot (21-04 Phase 2.1)
-- 참고:
-- - 공식 API에서 "잔여 크레딧" 대신 "구간 비용"을 제공하는 경우가 있어
--   reconciliation 기준을 balance delta가 아닌 cost sum으로 확장한다.
CREATE TABLE IF NOT EXISTS llm_provider_cost_snapshots (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    provider VARCHAR(32) NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    cost_usd NUMERIC(20, 8) NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'usd',
    source VARCHAR(40) NOT NULL DEFAULT 'provider_cost_api',
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_provider_cost_snapshots_provider_created
ON llm_provider_cost_snapshots (provider, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_provider_cost_snapshots_window
ON llm_provider_cost_snapshots (window_start, window_end, created_at DESC);

-- Week 2: Additional Tables
CREATE TABLE IF NOT EXISTS daily_risk_state (
    date DATE PRIMARY KEY,
    total_pnl NUMERIC(20, 8) DEFAULT 0 NOT NULL,
    trade_count INTEGER DEFAULT 0 NOT NULL,
    consecutive_losses INTEGER DEFAULT 0 NOT NULL,
    cooldown_until TIMESTAMP WITH TIME ZONE,
    is_trading_halted BOOLEAN DEFAULT FALSE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS account_state (
    id SERIAL PRIMARY KEY,
    balance NUMERIC(20, 8) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Initialize default balance (10,000,000 KRW)
INSERT INTO
    account_state (id, balance)
VALUES (1, 10000000.0)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS positions (
    symbol VARCHAR(20) PRIMARY KEY,
    quantity NUMERIC(20, 8) NOT NULL,
    avg_price NUMERIC(20, 8) NOT NULL,
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
