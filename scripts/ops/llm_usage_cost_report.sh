#!/usr/bin/env bash
set -euo pipefail

HOURS="${1:-24}"
DB_CONTAINER="${DB_CONTAINER:-coinpilot-db}"
DB_NAME="${DB_NAME:-coinpilot}"
DB_USER="${DB_USER:-postgres}"

if ! [[ "$HOURS" =~ ^[0-9]+$ ]]; then
  echo "[ERROR] hours must be an integer. ex) scripts/ops/llm_usage_cost_report.sh 24" >&2
  exit 1
fi

echo "[INFO] LLM Usage Cost Report"
echo "[INFO] window: last ${HOURS} hours"
echo "[INFO] db: container=${DB_CONTAINER}, database=${DB_NAME}"

SQL_SUMMARY=$(cat <<SQL
WITH base AS (
  SELECT *
  FROM llm_usage_events
  WHERE created_at >= now() - interval '${HOURS} hours'
)
SELECT
  feature,
  route,
  provider,
  model,
  COUNT(*) AS total_calls,
  SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_calls,
  SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error_calls,
  SUM(CASE WHEN status = 'estimated' THEN 1 ELSE 0 END) AS estimated_calls,
  COALESCE(SUM(input_tokens), 0) AS input_tokens,
  COALESCE(SUM(output_tokens), 0) AS output_tokens,
  COALESCE(SUM(total_tokens), 0) AS total_tokens,
  ROUND(COALESCE(SUM(estimated_cost_usd), 0)::numeric, 6) AS cost_usd,
  ROUND(
    CASE WHEN COUNT(*) > 0
      THEN COALESCE(SUM(estimated_cost_usd), 0)::numeric / COUNT(*)
      ELSE 0
    END,
    6
  ) AS avg_cost_usd_per_call
FROM base
GROUP BY feature, route, provider, model
ORDER BY cost_usd DESC, total_calls DESC, feature, route, provider, model;
SQL
)

SQL_DAILY=$(cat <<SQL
WITH base AS (
  SELECT *
  FROM llm_usage_events
  WHERE created_at >= now() - interval '${HOURS} hours'
)
SELECT
  date_trunc('hour', created_at) AS hour_utc,
  feature,
  provider,
  model,
  COUNT(*) AS calls,
  COALESCE(SUM(total_tokens), 0) AS total_tokens,
  ROUND(COALESCE(SUM(estimated_cost_usd), 0)::numeric, 6) AS cost_usd
FROM base
GROUP BY hour_utc, feature, provider, model
ORDER BY hour_utc DESC, feature, provider, model;
SQL
)

SQL_RECON=$(cat <<SQL
WITH usage_cost AS (
  SELECT
    provider,
    ROUND(COALESCE(SUM(estimated_cost_usd), 0)::numeric, 6) AS ledger_cost_usd
  FROM llm_usage_events
  WHERE created_at >= now() - interval '${HOURS} hours'
  GROUP BY provider
),
credit_delta AS (
  SELECT
    provider,
    ROUND((MAX(balance_usd) - MIN(balance_usd))::numeric, 6) AS credit_delta_usd
  FROM llm_credit_snapshots
  WHERE created_at >= now() - interval '${HOURS} hours'
  GROUP BY provider
)
SELECT
  COALESCE(u.provider, c.provider) AS provider,
  COALESCE(u.ledger_cost_usd, 0) AS ledger_cost_usd,
  COALESCE(c.credit_delta_usd, 0) AS credit_delta_usd,
  ROUND((COALESCE(u.ledger_cost_usd, 0) - ABS(COALESCE(c.credit_delta_usd, 0)))::numeric, 6) AS delta_usd
FROM usage_cost u
FULL OUTER JOIN credit_delta c ON u.provider = c.provider
ORDER BY provider;
SQL
)

docker exec -u "$DB_USER" "$DB_CONTAINER" psql -d "$DB_NAME" -c "$SQL_SUMMARY"
echo

echo "[INFO] hourly breakdown"
docker exec -u "$DB_USER" "$DB_CONTAINER" psql -d "$DB_NAME" -c "$SQL_DAILY"
echo

echo "[INFO] reconciliation (ledger sum vs credit snapshot delta)"
docker exec -u "$DB_USER" "$DB_CONTAINER" psql -d "$DB_NAME" -c "$SQL_RECON"
