-- v3.1 REJECT 검증용 필드 추가
-- 실행: kubectl exec -it -n coin-pilot-ns db-0 -- psql -U postgres -d coinpilot -f - < migrations/v3_1_reject_tracking.sql

BEGIN;

-- agent_decisions 테이블에 REJECT 검증용 필드 추가
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS price_at_decision DECIMAL(20,8);
ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS regime VARCHAR(10);

-- 인덱스 추가 (REJECT 분석용)
CREATE INDEX IF NOT EXISTS idx_agent_decisions_decision ON agent_decisions(decision);
CREATE INDEX IF NOT EXISTS idx_agent_decisions_regime ON agent_decisions(regime);

COMMIT;

-- 확인 쿼리
-- SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'agent_decisions';
