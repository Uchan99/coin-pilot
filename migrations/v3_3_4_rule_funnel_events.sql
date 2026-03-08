-- v3.3.4: Rule/Risk/AI 퍼널 이벤트 테이블 추가
-- 목적:
-- 1) BULL/SIDEWAYS/BEAR 레짐별 진입 병목 지점을 DB에서 직접 분해
-- 2) weekly_exit_report에 퍼널 요약을 증분 통합할 수 있는 근거 데이터 확보

CREATE TABLE IF NOT EXISTS rule_funnel_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    symbol VARCHAR(20) NOT NULL,
    strategy_name VARCHAR(50),
    regime VARCHAR(10),
    stage VARCHAR(40) NOT NULL,
    result VARCHAR(20) NOT NULL,
    reason_code VARCHAR(80),
    reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_rule_funnel_events_created
ON rule_funnel_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_rule_funnel_events_regime_stage_created
ON rule_funnel_events (regime, stage, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_rule_funnel_events_symbol_created
ON rule_funnel_events (symbol, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_rule_funnel_events_reason_code_created
ON rule_funnel_events (reason_code, created_at DESC);
