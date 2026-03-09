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
    echo "[FAIL] days 인자는 정수여야 합니다. 예: scripts/ops/strategy_feedback_report.sh 7 14 30"
    exit 2
  fi
done

echo "[INFO] Strategy Feedback Report"
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

# 전략 피드백 분석기는 sqlalchemy 등 bot 이미지 의존성을 사용하므로,
# 호스트 셸이 아니라 운영 bot 컨테이너 안에서 항상 동일한 런타임으로 실행한다.
run_compose exec -T \
  -e REPORT_DAYS="${REPORT_DAYS}" \
  -e APPROVAL_DAYS="${APPROVAL_DAYS}" \
  -e FALLBACK_DAYS="${FALLBACK_DAYS}" \
  -e PYTHONPATH=/app \
  bot python - <<'PY'
import asyncio
import json
import os

from src.analytics.strategy_feedback import StrategyFeedbackAnalyzer
from src.common.db import get_db_session


async def main() -> None:
    analyzer = StrategyFeedbackAnalyzer(get_db_session)
    payload = await analyzer.build_feedback_payload(
        report_days=int(os.environ["REPORT_DAYS"]),
        approval_days=int(os.environ["APPROVAL_DAYS"]),
        fallback_days=int(os.environ["FALLBACK_DAYS"]),
    )

    readiness = payload["readiness"]
    scoreboard = payload["scoreboard"]
    print("[INFO] gate_result:", payload["gate_result"])
    print("[INFO] approval_tier:", readiness["approval_tier"])
    print(
        "[INFO] samples:",
        f"sell={readiness['sell_samples']},",
        f"ai={readiness['ai_decisions']},",
        f"bull_rule_pass={readiness['bull_rule_pass']}",
    )
    print(
        "[INFO] scoreboard:",
        f"avg_realized_pnl_pct={scoreboard['avg_realized_pnl_pct']},",
        f"profit_factor={scoreboard['profit_factor']},",
        f"max_drawdown_pct={scoreboard['max_drawdown_pct']},",
        f"ai_reject_rate_pct={scoreboard['ai_reject_rate_pct']},",
        f"llm_cost_delta_pct={scoreboard['llm_cost_delta_pct']}",
    )

    print("\n[INFO] hold_reasons")
    for reason in readiness["hold_reasons"]:
        print("-", reason)

    print("\n[INFO] discard_reasons")
    for reason in readiness["discard_reasons"]:
        print("-", reason)

    print("\n[INFO] bottlenecks")
    for item in payload["bottlenecks"]:
        print("-", item)

    print("\n[INFO] candidate_changes")
    for item in payload["candidate_changes"]:
        print(
            "-",
            f"{item['candidate_id']}: {item['target_param']} "
            f"{item['current_value']} -> {item['proposed_value']} "
            f"({item['approval_tier']})",
        )

    print("\n[INFO] json")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


asyncio.run(main())
PY
