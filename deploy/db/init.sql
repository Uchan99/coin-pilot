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

SELECT create_hypertable('market_data', 'timestamp', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_market_data_symbol_interval_time ON market_data (symbol, interval, timestamp DESC);

ALTER TABLE market_data SET (timescaledb.compress, timescaledb.compress_segmentby = 'symbol, interval');

SELECT add_compression_policy('market_data', INTERVAL '7 days', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS trading_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    order_type VARCHAR(10) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    fee NUMERIC(20, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_trading_history_symbol_created ON trading_history (symbol, created_at DESC);

CREATE TABLE IF NOT EXISTS risk_audit (
    id SERIAL PRIMARY KEY,
    violation_type VARCHAR(50) NOT NULL,
    description TEXT,
    related_order_id UUID REFERENCES trading_history(id),
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_type VARCHAR(20) NOT NULL,
    context JSONB,
    decision TEXT,
    outcome VARCHAR(20),
    embedding vector(1536),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_memory_type ON agent_memory (agent_type);
CREATE INDEX IF NOT EXISTS idx_agent_memory_embedding ON agent_memory USING hnsw (embedding vector_cosine_ops);
