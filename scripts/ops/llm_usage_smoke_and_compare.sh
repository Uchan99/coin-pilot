#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - LLM usage 계측이 실제로 기록되는지 운영 환경에서 빠르게 검증한다.
# - chat/rag/sql + ai_decision(analyst/guardian) 경로를 강제 호출한 뒤
#   usage/canary 리포트를 연속 출력해 모델/경로 분포를 즉시 확인한다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

HOURS="${1:-1}"
ENV_FILE="${COINPILOT_ENV_FILE:-${REPO_ROOT}/deploy/cloud/oci/.env}"
COMPOSE_FILE="${COINPILOT_COMPOSE_FILE:-${REPO_ROOT}/deploy/cloud/oci/docker-compose.prod.yml}"

if ! [[ "${HOURS}" =~ ^[0-9]+$ ]]; then
  echo "[FAIL] hours는 정수여야 합니다. 예: scripts/ops/llm_usage_smoke_and_compare.sh 1"
  exit 2
fi

run_compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

echo "[INFO] LLM usage smoke start"
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

# 0) 계측 플래그/모듈 확인
# 주의: python -c 문자열은 셸/파이썬 따옴표 충돌이 잦아 f-string 대신 단순 문자열 결합을 사용한다.
run_compose exec -T bot python -c 'import os; print("LLM_USAGE_ENABLED=" + os.getenv("LLM_USAGE_ENABLED", "unset"))'
run_compose exec -T bot python -c 'import src.common.llm_usage as _m; print("llm_usage module ok")'
run_compose exec -T bot python -c 'import os; print("LLM_COST_SNAPSHOT_ENABLED=" + os.getenv("LLM_COST_SNAPSHOT_ENABLED", "unset"))'

# 0-1) cost snapshot 1회 강제 실행 (비활성 상태여도 summary 출력)
run_compose exec -T bot python - <<'PY'
import asyncio
import json
from src.common.llm_usage import collect_llm_cost_snapshots_once

summary = asyncio.run(collect_llm_cost_snapshots_once())
print("[COST][SNAPSHOT]", json.dumps(summary, ensure_ascii=False))
PY

# 1) 챗봇 경로 강제 호출 (classifier/rag/sql/premium_review)
run_compose exec -T bot python - <<'PY'
import asyncio
from src.agents.router import process_chat

async def main() -> None:
    queries = [
        ("usage-smoke-clf", "오늘 답변 톤을 한 줄로 설명해줘"),
        ("usage-smoke-rag", "프로젝트 아키텍처 문서 기준으로 리스크 한도 핵심만 알려줘"),
        ("usage-smoke-sql", "SQL로 trading_history 최근 1건 symbol, side, price 보여줘"),
        ("usage-smoke-review", "최근 전략 장단점 원인 근거 리스크 개선안을 구체적으로 리뷰해줘"),
    ]

    for session_id, query in queries:
        try:
            answer = await process_chat(query, session_id=session_id)
            print(f"[CHAT][OK] {session_id} len={len(answer)}")
        except Exception as exc:  # noqa: BLE001
            print(f"[CHAT][FAIL] {session_id} error={type(exc).__name__}: {exc}")

asyncio.run(main())
PY

# 2) AI Decision 경로 강제 호출 (실거래 시그널과 무관하게 analyst/guardian usage 검증)
run_compose exec -T bot python - <<'PY'
import asyncio
from src.agents.analyst import market_analyst_node
from src.agents.factory import get_primary_ai_decision_route
from src.agents.guardian import risk_guardian_node

async def main() -> None:
    route = get_primary_ai_decision_route()

    base_state = {
        "messages": [],
        "symbol": "KRW-BTC",
        "strategy_name": "UsageSmoke",
        "market_context": [
            {"timestamp": "2026-03-04T00:00:00Z", "open": 100000000, "high": 100200000, "low": 99900000, "close": 100100000},
            {"timestamp": "2026-03-04T01:00:00Z", "open": 100100000, "high": 100300000, "low": 100000000, "close": 100250000},
            {"timestamp": "2026-03-04T02:00:00Z", "open": 100250000, "high": 100350000, "low": 100100000, "close": 100280000},
        ],
        "indicators": {
            "symbol": "KRW-BTC",
            "close": 100280000,
            "regime": "SIDEWAYS",
            "regime_diff_pct": 0.2,
            "ai_context_candles": 24,
            "pattern_direction": "UP",
            "net_change_pct_6h": 0.31,
            "bearish_streak_6h": 0,
            "bullish_streak_6h": 2,
            "last_body_to_range_ratio": 0.45,
            "last_upper_wick_ratio": 0.15,
            "last_lower_wick_ratio": 0.12,
            "range_expansion_ratio_6h": 1.08,
        },
        "llm_route": route,
        "analyst_decision": None,
        "guardian_decision": None,
        "final_decision": "REJECT",
        "final_reasoning": "usage smoke",
    }

    analyst_result = await market_analyst_node(base_state)
    print(f"[AI][ANALYST] decision={analyst_result.get('analyst_decision', {}).get('decision')}")

    guardian_state = {
        **base_state,
        "analyst_decision": {"decision": "CONFIRM", "confidence": 70, "reasoning": "usage smoke confirm"},
    }
    guardian_result = await risk_guardian_node(guardian_state)
    print(f"[AI][GUARDIAN] decision={guardian_result.get('guardian_decision', {}).get('decision')}")

asyncio.run(main())
PY

# 3) 집계 리포트 출력
cd "${REPO_ROOT}"

scripts/ops/llm_usage_cost_report.sh "${HOURS}"
echo
scripts/ops/ai_decision_canary_report.sh "${HOURS}"

echo

echo "[INFO] recent route coverage"
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT route, provider, model, count(*) AS calls
FROM llm_usage_events
WHERE created_at >= now() - interval '${HOURS} hours'
GROUP BY route, provider, model
ORDER BY calls DESC, route;
"

echo "[PASS] smoke + compare completed"
