#!/usr/bin/env bash
set -euo pipefail

# 카나리 실험 리포트는 "최근 N시간" 구간의 모델별 의사결정 분포를 빠르게 확인하는 용도다.
# 기본은 24시간이며, 운영자가 즉시 비교할 수 있도록 CONFIRM/REJECT/실패 지표를 함께 보여준다.

HOURS="${1:-24}"
DB_CONTAINER="${COINPILOT_DB_CONTAINER:-coinpilot-db}"
DB_NAME="${COINPILOT_DB_NAME:-coinpilot}"

if ! [[ "${HOURS}" =~ ^[0-9]+$ ]]; then
  echo "[FAIL] hours는 정수여야 합니다. 예: scripts/ops/ai_decision_canary_report.sh 24"
  exit 2
fi

echo "[INFO] AI Decision Canary Report"
echo "[INFO] window: last ${HOURS} hours"
echo "[INFO] db: container=${DB_CONTAINER}, database=${DB_NAME}"

docker exec -u postgres "${DB_CONTAINER}" psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -c "
WITH scoped AS (
  SELECT
    created_at,
    symbol,
    decision,
    confidence,
    COALESCE(model_used, 'unknown') AS model_used,
    CASE WHEN reasoning LIKE '분석가 출력 검증 실패:%' THEN 1 ELSE 0 END AS parse_fail,
    CASE WHEN reasoning ILIKE '%timed out%' THEN 1 ELSE 0 END AS timeout_fail
  FROM agent_decisions
  WHERE created_at >= now() - interval '${HOURS} hours'
)
SELECT
  model_used,
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE decision = 'CONFIRM') AS confirm_count,
  COUNT(*) FILTER (WHERE decision = 'REJECT') AS reject_count,
  ROUND(100.0 * COUNT(*) FILTER (WHERE decision = 'CONFIRM') / NULLIF(COUNT(*), 0), 2) AS confirm_rate_pct,
  ROUND(AVG(confidence)::numeric, 2) AS avg_confidence,
  SUM(parse_fail) AS parse_fail_count,
  SUM(timeout_fail) AS timeout_count
FROM scoped
GROUP BY model_used
ORDER BY total DESC, model_used;
"

echo
echo "[INFO] model + symbol breakdown"
docker exec -u postgres "${DB_CONTAINER}" psql -d "${DB_NAME}" -v ON_ERROR_STOP=1 -c "
WITH scoped AS (
  SELECT
    symbol,
    decision,
    COALESCE(model_used, 'unknown') AS model_used
  FROM agent_decisions
  WHERE created_at >= now() - interval '${HOURS} hours'
)
SELECT
  model_used,
  symbol,
  COUNT(*) AS total,
  COUNT(*) FILTER (WHERE decision = 'CONFIRM') AS confirm_count,
  COUNT(*) FILTER (WHERE decision = 'REJECT') AS reject_count
FROM scoped
GROUP BY model_used, symbol
ORDER BY model_used, total DESC, symbol;
"
