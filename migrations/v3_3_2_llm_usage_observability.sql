-- v3.3.2: LLM usage/cost observability baseline
-- 목적:
-- 1) 호출 단위 usage/cost 원장 저장 (route/provider/model 분리)
-- 2) 계정 잔여 크레딧 스냅샷 저장 (원장 합계와 대조)

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

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_created
ON llm_usage_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_route_created
ON llm_usage_events (route, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_provider_model_created
ON llm_usage_events (provider, model, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_llm_usage_events_status_created
ON llm_usage_events (status, created_at DESC);


CREATE TABLE IF NOT EXISTS llm_credit_snapshots (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    provider VARCHAR(32) NOT NULL,
    balance_usd NUMERIC(20, 8) NOT NULL,
    balance_unit VARCHAR(20) NOT NULL DEFAULT 'usd',
    source VARCHAR(40) NOT NULL DEFAULT 'manual',
    note TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_credit_snapshots_provider_created
ON llm_credit_snapshots (provider, created_at DESC);
