#!/usr/bin/env bash
set -euo pipefail

HOURS="${1:-72}"
DB_CONTAINER="${COINPILOT_DB_CONTAINER:-coinpilot-db}"
DB_NAME="${COINPILOT_DB_NAME:-coinpilot}"

if ! [[ "${HOURS}" =~ ^[0-9]+$ ]]; then
  echo "[FAIL] hours는 정수여야 합니다. 예: scripts/ops/rule_funnel_regime_report.sh 72"
  exit 2
fi

echo "[INFO] Rule Funnel Regime Report"
echo "[INFO] window: last ${HOURS} hours"
echo "[INFO] db: container=${DB_CONTAINER}, database=${DB_NAME}"

docker exec -u postgres "${DB_CONTAINER}" psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -c "
WITH scoped AS (
  SELECT
    COALESCE(regime, 'UNKNOWN') AS regime,
    stage,
    result,
    reason_code,
    symbol,
    created_at
  FROM rule_funnel_events
  WHERE created_at >= now() - interval '${HOURS} hours'
)
SELECT
  regime,
  stage,
  result,
  COUNT(*) AS event_count,
  COUNT(DISTINCT symbol) AS unique_symbols
FROM scoped
GROUP BY regime, stage, result
ORDER BY regime, stage, result;
"

echo
echo "[INFO] regime conversion summary"
docker exec -u postgres "${DB_CONTAINER}" psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -c "
WITH stage_counts AS (
  SELECT
    COALESCE(regime, 'UNKNOWN') AS regime,
    stage,
    COUNT(*) AS cnt
  FROM rule_funnel_events
  WHERE created_at >= now() - interval '${HOURS} hours'
  GROUP BY 1, 2
),
pivoted AS (
  SELECT
    regime,
    COALESCE(MAX(CASE WHEN stage = 'rule_pass' THEN cnt END), 0) AS rule_pass,
    COALESCE(MAX(CASE WHEN stage = 'risk_reject' THEN cnt END), 0) AS risk_reject,
    COALESCE(MAX(CASE WHEN stage = 'ai_prefilter_reject' THEN cnt END), 0) AS ai_prefilter_reject,
    COALESCE(MAX(CASE WHEN stage = 'ai_guardrail_block' THEN cnt END), 0) AS ai_guardrail_block,
    COALESCE(MAX(CASE WHEN stage = 'ai_confirm' THEN cnt END), 0) AS ai_confirm,
    COALESCE(MAX(CASE WHEN stage = 'ai_reject' THEN cnt END), 0) AS ai_reject
  FROM stage_counts
  GROUP BY regime
)
SELECT
  regime,
  rule_pass,
  risk_reject,
  ai_prefilter_reject,
  ai_guardrail_block,
  ai_confirm,
  ai_reject,
  ROUND(ai_confirm::numeric / NULLIF(rule_pass, 0), 4) AS confirm_per_rule_pass,
  ROUND(ai_reject::numeric / NULLIF(rule_pass, 0), 4) AS reject_per_rule_pass
FROM pivoted
ORDER BY regime;
"

echo
echo "[INFO] top reason codes"
docker exec -u postgres "${DB_CONTAINER}" psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -c "
WITH scoped AS (
  SELECT
    COALESCE(regime, 'UNKNOWN') AS regime,
    stage,
    COALESCE(reason_code, 'unknown') AS reason_code
  FROM rule_funnel_events
  WHERE created_at >= now() - interval '${HOURS} hours'
)
SELECT
  regime,
  stage,
  reason_code,
  COUNT(*) AS event_count
FROM scoped
GROUP BY regime, stage, reason_code
ORDER BY event_count DESC, regime, stage, reason_code
LIMIT 15;
"
