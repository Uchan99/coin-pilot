#!/usr/bin/env bash
set -euo pipefail

REPORT_DAYS="${1:-7}"
APPROVAL_DAYS="${2:-14}"
FALLBACK_DAYS="${3:-30}"

for value in "${REPORT_DAYS}" "${APPROVAL_DAYS}" "${FALLBACK_DAYS}"; do
  if ! [[ "${value}" =~ ^[0-9]+$ ]]; then
    echo "[FAIL] days 인자는 정수여야 합니다. 예: scripts/ops/strategy_feedback_gate.sh 7 14 30"
    exit 2
  fi
done

PYTHONPATH=. python - <<'PY'
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
