#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - cron/systemd 등 스케줄러에서 CoinPilot 운영 점검 스크립트를 표준 방식으로 실행한다.
# - 중복 실행을 flock으로 방지하고, timeout/로그 경로/실행 메타를 일관되게 남긴다.
#
# 왜 별도 래퍼가 필요한가:
# - 개별 스크립트마다 flock/timeout/로그 리다이렉션을 반복하면 cron 라인이 길고 실수하기 쉽다.
# - 운영 중 실패 원인 분석을 위해 "언제 시작했고, 얼마나 걸렸고, 어떤 코드로 끝났는지"를
#   동일 형식으로 남길 필요가 있다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

LOG_ROOT="${COINPILOT_OPS_LOG_ROOT:-/var/log/coinpilot/ops}"
LOCK_ROOT="${COINPILOT_OPS_LOCK_ROOT:-/tmp/coinpilot-ops-locks}"
TIMEOUT_SEC="${COINPILOT_OPS_TIMEOUT_SEC:-900}"

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/run_scheduled_monitoring.sh <job_name> <command> [args...]

Examples:
  scripts/ops/run_scheduled_monitoring.sh monitoring-t1h \
    scripts/ops/check_24h_monitoring.sh t1h --automation-mode

  scripts/ops/run_scheduled_monitoring.sh llm-usage-24h \
    scripts/ops/llm_usage_cost_report.sh 24

Optional env overrides:
  COINPILOT_OPS_LOG_ROOT=/var/log/coinpilot/ops
  COINPILOT_OPS_LOCK_ROOT=/tmp/coinpilot-ops-locks
  COINPILOT_OPS_TIMEOUT_SEC=900
EOF
}

if [[ $# -lt 2 ]]; then
  usage
  exit 2
fi

JOB_NAME="$1"
shift

mkdir -p "${LOG_ROOT}" "${LOCK_ROOT}"

DATE_UTC="$(date -u +%Y%m%d)"
LOG_FILE="${LOG_ROOT}/${JOB_NAME}-${DATE_UTC}.log"
LOCK_FILE="${LOCK_ROOT}/${JOB_NAME}.lock"
STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
START_TS="$(date +%s)"

# 로그는 stdout/stderr를 모두 모아서 남긴다. cron에서는 메일 대신 파일을 표준 증빙으로 삼는다.
exec >>"${LOG_FILE}" 2>&1

echo "[INFO] run_scheduled_monitoring started_at=${STARTED_AT} job=${JOB_NAME}"
echo "[INFO] cwd=${REPO_ROOT}"
echo "[INFO] timeout_sec=${TIMEOUT_SEC}"
echo "[INFO] command=$*"

cd "${REPO_ROOT}"

if ! command -v flock >/dev/null 2>&1; then
  echo "[FAIL] flock 명령을 찾을 수 없음"
  exit 2
fi

if ! command -v timeout >/dev/null 2>&1; then
  echo "[FAIL] timeout 명령을 찾을 수 없음"
  exit 2
fi

run_with_guard() {
  flock -n 9 || {
    echo "[WARN] 중복 실행 감지: ${JOB_NAME}"
    return 99
  }

  # timeout은 hung process가 다음 주기까지 락을 오래 쥐고 있지 않도록 하는 최후 안전장치다.
  timeout "${TIMEOUT_SEC}" "$@"
}

set +e
run_with_guard 9>"${LOCK_FILE}" "$@"
EXIT_CODE=$?
set -e

ENDED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
ELAPSED_SEC="$(( $(date +%s) - START_TS ))"
echo "[INFO] run_scheduled_monitoring ended_at=${ENDED_AT} job=${JOB_NAME} exit_code=${EXIT_CODE} elapsed_sec=${ELAPSED_SEC}"

exit "${EXIT_CODE}"
