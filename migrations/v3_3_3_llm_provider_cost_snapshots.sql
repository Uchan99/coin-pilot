-- v3.3.3: provider 비용 스냅샷 테이블 추가
-- 목적:
-- 1) provider 공식 비용 API 결과(구간 비용)를 저장
-- 2) 내부 usage 원장 합계와 외부 비용 합계를 대조(reconciliation)

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
