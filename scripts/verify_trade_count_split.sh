#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="coin-pilot-ns"
DB_POD="db-0"
FOLLOW_BUY=0
FOLLOW_SELL=0
FOLLOW_MINUTES=60

usage() {
  cat <<USAGE
Usage: $(basename "$0") [options]

Options:
  -n, --namespace <ns>      Kubernetes namespace (default: coin-pilot-ns)
  -d, --db-pod <pod>        DB pod name (default: db-0)
      --follow-buy          Follow bot logs for BUY-related events
      --follow-sell         Follow bot logs for SELL-related events
      --follow-min <min>    Log history minutes for follow mode (default: 60)
  -h, --help                Show this help

Examples:
  bash scripts/verify_trade_count_split.sh
  bash scripts/verify_trade_count_split.sh --follow-buy
  bash scripts/verify_trade_count_split.sh --follow-sell --follow-min 120
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    -d|--db-pod)
      DB_POD="$2"
      shift 2
      ;;
    --follow-buy)
      FOLLOW_BUY=1
      shift
      ;;
    --follow-sell)
      FOLLOW_SELL=1
      shift
      ;;
    --follow-min)
      FOLLOW_MINUTES="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      usage
      exit 1
      ;;
  esac
done

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command not found: $1"
    exit 1
  fi
}

need_cmd kubectl

echo "== Verify 14 Trade Count Split =="
echo "Namespace: $NAMESPACE"
echo "DB Pod:    $DB_POD"
echo

# 0) Sanity: DB pod exists
kubectl get pod "$DB_POD" -n "$NAMESPACE" >/dev/null

# 1) Schema check
cat <<'SQL' | kubectl exec -i -n "$NAMESPACE" "$DB_POD" -- psql -U postgres -d coinpilot
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'daily_risk_state'
  AND column_name IN ('buy_count','sell_count','trade_count')
ORDER BY column_name;
SQL

echo

# 2) Latest daily risk state
cat <<'SQL' | kubectl exec -i -n "$NAMESPACE" "$DB_POD" -- psql -U postgres -d coinpilot
SELECT now() AS checked_at, date, buy_count, sell_count, trade_count, total_pnl,
       (buy_count + sell_count) AS calculated_total,
       (trade_count - (buy_count + sell_count)) AS mismatch
FROM daily_risk_state
ORDER BY date DESC
LIMIT 3;
SQL

echo

# 3) Recent filled trades
cat <<'SQL' | kubectl exec -i -n "$NAMESPACE" "$DB_POD" -- psql -U postgres -d coinpilot
SELECT created_at, symbol, side, price, quantity, status
FROM trading_history
WHERE status = 'FILLED'
ORDER BY created_at DESC
LIMIT 10;
SQL

echo

# 4) Daily integrity (recent 7 rows)
cat <<'SQL' | kubectl exec -i -n "$NAMESPACE" "$DB_POD" -- psql -U postgres -d coinpilot
SELECT date, buy_count, sell_count, trade_count,
       (buy_count + sell_count) AS calculated_total,
       (trade_count - (buy_count + sell_count)) AS mismatch
FROM daily_risk_state
ORDER BY date DESC
LIMIT 7;
SQL

echo

# 5) Summary counts for today
cat <<'SQL' | kubectl exec -i -n "$NAMESPACE" "$DB_POD" -- psql -U postgres -d coinpilot
WITH t AS (
  SELECT side, COUNT(*) AS cnt
  FROM trading_history
  WHERE status = 'FILLED'
    AND created_at >= date_trunc('day', now())
  GROUP BY side
)
SELECT
  COALESCE(MAX(CASE WHEN side='BUY' THEN cnt END), 0)  AS filled_buys_today,
  COALESCE(MAX(CASE WHEN side='SELL' THEN cnt END), 0) AS filled_sells_today
FROM t;
SQL

echo
echo "[OK] Base verification queries completed."

if [[ "$FOLLOW_BUY" -eq 1 ]]; then
  echo
  echo "== Follow BUY logs (Ctrl+C to stop) =="
  kubectl logs -n "$NAMESPACE" -l app=bot --since="${FOLLOW_MINUTES}m" -f --prefix=true \
    | grep -E "Entry Signal Detected|Trade Executed|BUY|AI CONFIRM|AI REJECT"
fi

if [[ "$FOLLOW_SELL" -eq 1 ]]; then
  echo
  echo "== Follow SELL logs (Ctrl+C to stop) =="
  kubectl logs -n "$NAMESPACE" -l app=bot --since="${FOLLOW_MINUTES}m" -f --prefix=true \
    | grep -E "Exit Triggered|Trade Closed|SELL|PnL"
fi
