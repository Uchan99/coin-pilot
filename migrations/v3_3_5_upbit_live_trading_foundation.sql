-- v3.3.5: Upbit 실거래 전환 Stage A 기초 스키마
-- 목적:
-- 1) paper 장부와 거래소 원장을 분리해 실거래 audit trail을 저장
-- 2) 주문/체결/계좌 스냅샷/정산 결과를 별도 테이블로 보존
-- 3) 추후 Dashboard/History/Mobile API가 canonical portfolio view를 만들 근거 데이터 확보

CREATE TABLE IF NOT EXISTS exchange_account_snapshots (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    exchange VARCHAR(32) NOT NULL DEFAULT 'upbit',
    asset_symbol VARCHAR(20) NOT NULL,
    balance NUMERIC(20, 8) NOT NULL,
    locked NUMERIC(20, 8) NOT NULL DEFAULT 0,
    avg_buy_price NUMERIC(20, 8),
    unit_currency VARCHAR(10),
    source VARCHAR(40) NOT NULL DEFAULT 'exchange_api',
    raw_payload JSONB
);

CREATE INDEX IF NOT EXISTS idx_exchange_account_snapshots_created
ON exchange_account_snapshots (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_exchange_account_snapshots_exchange_asset_created
ON exchange_account_snapshots (exchange, asset_symbol, created_at DESC);

CREATE TABLE IF NOT EXISTS exchange_orders (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    exchange VARCHAR(32) NOT NULL DEFAULT 'upbit',
    exchange_order_id VARCHAR(128) NOT NULL,
    client_order_id VARCHAR(128),
    market VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    ord_type VARCHAR(20) NOT NULL,
    state VARCHAR(20) NOT NULL,
    requested_price NUMERIC(20, 8),
    requested_volume NUMERIC(20, 8),
    remaining_volume NUMERIC(20, 8),
    executed_volume NUMERIC(20, 8),
    avg_fill_price NUMERIC(20, 8),
    paid_fee NUMERIC(20, 8),
    reserved_fee NUMERIC(20, 8),
    remaining_fee NUMERIC(20, 8),
    locked NUMERIC(20, 8),
    time_in_force VARCHAR(20),
    source VARCHAR(20) NOT NULL DEFAULT 'live',
    strategy_name VARCHAR(50),
    signal_info JSONB,
    raw_payload JSONB,
    CONSTRAINT uq_exchange_orders_exchange_order_id UNIQUE (exchange_order_id)
);

CREATE INDEX IF NOT EXISTS idx_exchange_orders_market_created
ON exchange_orders (market, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_exchange_orders_state_created
ON exchange_orders (state, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_exchange_orders_client_order_id
ON exchange_orders (client_order_id);

CREATE TABLE IF NOT EXISTS exchange_fills (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    exchange VARCHAR(32) NOT NULL DEFAULT 'upbit',
    exchange_order_id VARCHAR(128) NOT NULL,
    exchange_trade_id VARCHAR(128),
    market VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    fill_price NUMERIC(20, 8) NOT NULL,
    fill_volume NUMERIC(20, 8) NOT NULL,
    fee NUMERIC(20, 8),
    liquidity VARCHAR(20),
    filled_at TIMESTAMPTZ,
    source VARCHAR(20) NOT NULL DEFAULT 'exchange_fill',
    raw_payload JSONB
);

CREATE INDEX IF NOT EXISTS idx_exchange_fills_order_created
ON exchange_fills (exchange_order_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_exchange_fills_market_filled_at
ON exchange_fills (market, filled_at DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_exchange_fills_trade_id
ON exchange_fills (exchange_trade_id);

CREATE TABLE IF NOT EXISTS reconciliation_runs (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    exchange VARCHAR(32) NOT NULL DEFAULT 'upbit',
    mode VARCHAR(20) NOT NULL DEFAULT 'dry_run',
    status VARCHAR(20) NOT NULL,
    snapshot_started_at TIMESTAMPTZ,
    snapshot_finished_at TIMESTAMPTZ,
    account_mismatch_count INTEGER NOT NULL DEFAULT 0,
    order_mismatch_count INTEGER NOT NULL DEFAULT 0,
    fill_mismatch_count INTEGER NOT NULL DEFAULT 0,
    portfolio_mismatch_count INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_reconciliation_runs_created
ON reconciliation_runs (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_reconciliation_runs_status_created
ON reconciliation_runs (status, created_at DESC);
