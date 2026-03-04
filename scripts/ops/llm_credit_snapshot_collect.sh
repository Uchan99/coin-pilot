#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - provider API 잔여 크레딧 스냅샷 수집을 1회 강제 실행한다.
# - 스케줄러 반영 전/후 동작 검증 및 운영 트러블슈팅에 사용한다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ENV_FILE="${COINPILOT_ENV_FILE:-${REPO_ROOT}/deploy/cloud/oci/.env}"
COMPOSE_FILE="${COINPILOT_COMPOSE_FILE:-${REPO_ROOT}/deploy/cloud/oci/docker-compose.prod.yml}"
DB_CONTAINER="${COINPILOT_DB_CONTAINER:-coinpilot-db}"
DB_NAME="${COINPILOT_DB_NAME:-coinpilot}"

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

echo "[INFO] LLM credit snapshot collect (one-shot)"
echo "[INFO] env=${ENV_FILE}"
echo "[INFO] compose=${COMPOSE_FILE}"

run_compose exec -T bot python - <<'PY'
import asyncio
import json
from src.common.llm_usage import collect_llm_credit_snapshots_once

summary = asyncio.run(collect_llm_credit_snapshots_once())
print("[INFO] collect summary")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY

echo
echo "[INFO] recent llm_credit_snapshots"
docker exec -u postgres "${DB_CONTAINER}" psql -d "${DB_NAME}" -c "
SELECT created_at, provider, balance_usd, balance_unit, source
FROM llm_credit_snapshots
ORDER BY created_at DESC
LIMIT 20;
"
