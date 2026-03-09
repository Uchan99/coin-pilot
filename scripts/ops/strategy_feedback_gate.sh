#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

REPORT_DAYS="${1:-7}"
APPROVAL_DAYS="${2:-14}"
FALLBACK_DAYS="${3:-30}"
ENV_FILE="${COINPILOT_ENV_FILE:-${REPO_ROOT}/deploy/cloud/oci/.env}"
COMPOSE_FILE="${COINPILOT_COMPOSE_FILE:-${REPO_ROOT}/deploy/cloud/oci/docker-compose.prod.yml}"

for value in "${REPORT_DAYS}" "${APPROVAL_DAYS}" "${FALLBACK_DAYS}"; do
  if ! [[ "${value}" =~ ^[0-9]+$ ]]; then
    echo "[FAIL] days 인자는 정수여야 합니다. 예: scripts/ops/strategy_feedback_gate.sh 7 14 30"
    exit 2
  fi
done

echo "[INFO] Strategy Feedback Gate"
echo "[INFO] report_days=${REPORT_DAYS}, approval_days=${APPROVAL_DAYS}, fallback_days=${FALLBACK_DAYS}"
echo "[INFO] env=${ENV_FILE}"
echo "[INFO] compose=${COMPOSE_FILE}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[FAIL] env file not found: ${ENV_FILE}"
  exit 2
fi
if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "[FAIL] compose file not found: ${COMPOSE_FILE}"
  exit 2
fi

run_compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

# gate 스크립트도 host python/venv 상태에 의존하지 않고 bot 컨테이너 기준으로 고정한다.
run_compose exec -T \
  -e REPORT_DAYS="${REPORT_DAYS}" \
  -e APPROVAL_DAYS="${APPROVAL_DAYS}" \
  -e FALLBACK_DAYS="${FALLBACK_DAYS}" \
  -e PYTHONPATH=/app \
  bot python - <<'PY'
import asyncio
import os
import sys

from src.analytics.strategy_feedback import StrategyFeedbackAnalyzer
from src.common.db import get_db_session


async def main() -> int:
    analyzer = StrategyFeedbackAnalyzer(get_db_session)
    payload = await analyzer.build_feedback_payload(
        report_days=int(os.environ["REPORT_DAYS"]),
        approval_days=int(os.environ["APPROVAL_DAYS"]),
        fallback_days=int(os.environ["FALLBACK_DAYS"]),
    )
    readiness = payload["readiness"]
    print(
        f"gate_result={payload['gate_result']} "
        f"approval_tier={readiness['approval_tier']} "
        f"sell_samples={readiness['sell_samples']} "
        f"ai_decisions={readiness['ai_decisions']}"
    )
    if readiness["hold_reasons"]:
        print("hold_reasons=" + " | ".join(readiness["hold_reasons"]))
    if readiness["discard_reasons"]:
        print("discard_reasons=" + " | ".join(readiness["discard_reasons"]))
    return 0 if payload["gate_result"] == "recommend" else 1


sys.exit(asyncio.run(main()))
PY
