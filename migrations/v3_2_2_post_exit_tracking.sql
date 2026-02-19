ALTER TABLE trading_history
ADD COLUMN IF NOT EXISTS post_exit_prices JSONB;

CREATE INDEX IF NOT EXISTS idx_trading_history_sell_executed_at
ON trading_history (executed_at DESC)
WHERE side = 'SELL' AND status = 'FILLED' AND executed_at IS NOT NULL;
