-- migrations/v3_0_regime_trading.sql

BEGIN;

-- 1. regime_history 테이블 생성
CREATE TABLE IF NOT EXISTS regime_history (
    id SERIAL PRIMARY KEY,
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    regime VARCHAR(10) NOT NULL,
    ma50 DECIMAL(20, 8),
    ma200 DECIMAL(20, 8),
    diff_pct DECIMAL(10, 4),
    coin_symbol VARCHAR(10) NOT NULL DEFAULT 'BTC'
);

CREATE INDEX IF NOT EXISTS idx_regime_history_symbol_time
    ON regime_history (coin_symbol, detected_at DESC);

-- 2. trading_history 테이블 컬럼 추가
ALTER TABLE trading_history ADD COLUMN IF NOT EXISTS regime VARCHAR(10);
ALTER TABLE trading_history ADD COLUMN IF NOT EXISTS high_water_mark DECIMAL(20, 8);
ALTER TABLE trading_history ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(30);

-- 3. positions 테이블 컬럼 추가
ALTER TABLE positions ADD COLUMN IF NOT EXISTS regime VARCHAR(10);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS high_water_mark DECIMAL(20, 8);

COMMIT;
