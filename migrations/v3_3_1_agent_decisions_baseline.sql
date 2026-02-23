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
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_symbol
ON agent_decisions (symbol);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_created
ON agent_decisions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision
ON agent_decisions (decision);

CREATE INDEX IF NOT EXISTS idx_agent_decisions_regime
ON agent_decisions (regime);
