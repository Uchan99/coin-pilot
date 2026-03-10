#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - AI Decision 전략/사례 RAG replay를 가능한 한 bot 컨테이너와 동일한 런타임에서 실행한다.
# - 단, WSL 로컬처럼 docker가 없는 개발 환경에서도 replay smoke test를 막지 않기 위해
#   `.venv/bin/python` 또는 `python3`로 자동 폴백한다.
# - 즉, "운영 재현성 우선 + 로컬 개발 차단 방지"를 동시에 만족시키는 래퍼다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ENV_FILE="${COINPILOT_ENV_FILE:-${REPO_ROOT}/deploy/cloud/oci/.env}"
COMPOSE_FILE="${COINPILOT_COMPOSE_FILE:-${REPO_ROOT}/deploy/cloud/oci/docker-compose.prod.yml}"

run_compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

run_local() {
  local local_python=""

  if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    local_python="${REPO_ROOT}/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    local_python="python3"
  else
    echo "[FAIL] docker가 없고 로컬 python 실행기도 찾지 못했습니다."
    exit 2
  fi

  echo "[INFO] replay runtime: local (${local_python})"
  (
    cd "${REPO_ROOT}"
    PYTHONPATH="${REPO_ROOT}" "${local_python}" "${REPO_ROOT}/scripts/replay_ai_decision_rag.py" "$@"
  )
}

if command -v docker >/dev/null 2>&1 && [[ -f "${ENV_FILE}" ]] && [[ -f "${COMPOSE_FILE}" ]]; then
  echo "[INFO] replay runtime: bot container"
  if run_compose exec -T -e PYTHONPATH=/app bot python /app/scripts/replay_ai_decision_rag.py "$@"; then
    exit 0
  fi
  echo "[WARN] bot 컨테이너 replay 실행에 실패해 로컬 python으로 폴백합니다."
fi

echo "[INFO] docker/compose 런타임을 사용할 수 없어 로컬 python으로 폴백합니다."
run_local "$@"
