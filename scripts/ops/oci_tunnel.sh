#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - WSL/로컬에서 OCI 운영 UI(dashboard/grafana/n8n/prometheus/next-dashboard)에 접근할 때
#   SSH -L 옵션을 매번 수동으로 치지 않도록 표준 프로파일을 제공한다.
# - CLI 접근(oci_remote_exec.sh)과 브라우저 접근(oci_tunnel.sh)의 env 파일을 동일하게 맞춘다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEFAULT_ENV_FILE="${REPO_ROOT}/deploy/cloud/oci/ops/oci_access.env"

ENV_FILE="${OCI_REMOTE_ACCESS_ENV_FILE:-${DEFAULT_ENV_FILE}}"

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/oci_tunnel.sh [--env-file <path>] [all|dashboard|n8n|grafana|next-dashboard|prometheus]...

Examples:
  scripts/ops/oci_tunnel.sh all
  scripts/ops/oci_tunnel.sh dashboard grafana

Default local ports:
  dashboard  -> localhost:18501 -> OCI 127.0.0.1:8501
  n8n        -> localhost:15678 -> OCI 127.0.0.1:5678
  grafana    -> localhost:13000 -> OCI 127.0.0.1:3000
  next-dashboard -> localhost:13001 -> OCI 127.0.0.1:3001
  prometheus -> localhost:19090 -> OCI 127.0.0.1:9090
EOF
}

expand_path() {
  local raw="${1:-}"
  if [[ -z "${raw}" ]]; then
    return 0
  fi
  if [[ "${raw}" == "~" ]]; then
    printf '%s\n' "${HOME}"
    return 0
  fi
  if [[ "${raw}" == ~/* ]]; then
    printf '%s/%s\n' "${HOME}" "${raw#~/}"
    return 0
  fi
  printf '%s\n' "${raw}"
}

load_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    cat <<EOF
[FAIL] OCI access env file not found: ${ENV_FILE}
준비 순서:
1) cp ${REPO_ROOT}/deploy/cloud/oci/ops/oci_access.env.example ${DEFAULT_ENV_FILE}
2) ${DEFAULT_ENV_FILE} 에 실제 OCI host/key 값을 입력
3) chmod 600 ${DEFAULT_ENV_FILE}
EOF
    exit 2
  fi

  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
}

build_ssh_target() {
  if [[ -n "${OCI_REMOTE_SSH_TARGET:-}" ]]; then
    printf '%s\n' "${OCI_REMOTE_SSH_TARGET}"
    return 0
  fi
  if [[ -z "${OCI_REMOTE_HOST:-}" || -z "${OCI_REMOTE_USER:-}" ]]; then
    echo "[FAIL] OCI_REMOTE_SSH_TARGET 또는 OCI_REMOTE_HOST/OCI_REMOTE_USER가 필요합니다." >&2
    exit 2
  fi
  printf '%s@%s\n' "${OCI_REMOTE_USER}" "${OCI_REMOTE_HOST}"
}

add_profile() {
  local profile="$1"
  case "${profile}" in
    all)
      add_profile dashboard
      add_profile n8n
      add_profile grafana
      add_profile next-dashboard
      add_profile prometheus
      ;;
    dashboard)
      FORWARDS+=(-L "${OCI_TUNNEL_LOCAL_DASHBOARD_PORT:-18501}:127.0.0.1:${OCI_TUNNEL_REMOTE_DASHBOARD_PORT:-8501}")
      PROFILE_LABELS+=("dashboard:${OCI_TUNNEL_LOCAL_DASHBOARD_PORT:-18501}->8501")
      ;;
    n8n)
      FORWARDS+=(-L "${OCI_TUNNEL_LOCAL_N8N_PORT:-15678}:127.0.0.1:${OCI_TUNNEL_REMOTE_N8N_PORT:-5678}")
      PROFILE_LABELS+=("n8n:${OCI_TUNNEL_LOCAL_N8N_PORT:-15678}->5678")
      ;;
    grafana)
      FORWARDS+=(-L "${OCI_TUNNEL_LOCAL_GRAFANA_PORT:-13000}:127.0.0.1:${OCI_TUNNEL_REMOTE_GRAFANA_PORT:-3000}")
      PROFILE_LABELS+=("grafana:${OCI_TUNNEL_LOCAL_GRAFANA_PORT:-13000}->3000")
      ;;
    next-dashboard)
      FORWARDS+=(-L "${OCI_TUNNEL_LOCAL_NEXT_DASHBOARD_PORT:-13001}:127.0.0.1:${OCI_TUNNEL_REMOTE_NEXT_DASHBOARD_PORT:-3001}")
      PROFILE_LABELS+=("next-dashboard:${OCI_TUNNEL_LOCAL_NEXT_DASHBOARD_PORT:-13001}->3001")
      ;;
    prometheus)
      FORWARDS+=(-L "${OCI_TUNNEL_LOCAL_PROMETHEUS_PORT:-19090}:127.0.0.1:${OCI_TUNNEL_REMOTE_PROMETHEUS_PORT:-9090}")
      PROFILE_LABELS+=("prometheus:${OCI_TUNNEL_LOCAL_PROMETHEUS_PORT:-19090}->9090")
      ;;
    *)
      echo "[FAIL] unknown tunnel profile: ${profile}" >&2
      usage
      exit 2
      ;;
  esac
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --env-file)
        if [[ $# -lt 2 ]]; then
          echo "[FAIL] --env-file requires a path" >&2
          usage
          exit 2
        fi
        ENV_FILE="$2"
        shift 2
        ;;
      -h|--help|help)
        usage
        exit 0
        ;;
      *)
        PROFILES+=("$1")
        shift
        ;;
    esac
  done
}

PROFILES=()
FORWARDS=()
PROFILE_LABELS=()

parse_args "$@"
load_env_file

if ! command -v ssh >/dev/null 2>&1; then
  echo "[FAIL] ssh 명령을 찾을 수 없습니다." >&2
  exit 2
fi

if [[ ${#PROFILES[@]} -eq 0 ]]; then
  PROFILES=(all)
fi

for profile in "${PROFILES[@]}"; do
  add_profile "${profile}"
done

SSH_TARGET="$(build_ssh_target)"
SSH_KEY_PATH="$(expand_path "${OCI_REMOTE_SSH_KEY_PATH:-}")"
SSH_PORT="${OCI_REMOTE_SSH_PORT:-22}"
CONNECT_TIMEOUT_SEC="${OCI_REMOTE_CONNECT_TIMEOUT_SEC:-10}"
STRICT_HOST_KEY_CHECKING="${OCI_REMOTE_STRICT_HOST_KEY_CHECKING:-accept-new}"

SSH_ARGS=(
  -N
  -o "BatchMode=yes"
  -o "ConnectTimeout=${CONNECT_TIMEOUT_SEC}"
  -o "ServerAliveInterval=30"
  -o "ServerAliveCountMax=3"
  -o "ExitOnForwardFailure=yes"
  -o "StrictHostKeyChecking=${STRICT_HOST_KEY_CHECKING}"
  -p "${SSH_PORT}"
)

if [[ -n "${SSH_KEY_PATH}" ]]; then
  SSH_ARGS+=(-i "${SSH_KEY_PATH}")
fi

echo "[INFO] OCI tunnel"
echo "[INFO] env_file=${ENV_FILE}"
echo "[INFO] ssh_target=${SSH_TARGET}"
echo "[INFO] profiles=${PROFILE_LABELS[*]}"
echo "[INFO] Ctrl+C 로 종료합니다."

exec ssh "${SSH_ARGS[@]}" "${FORWARDS[@]}" "${SSH_TARGET}"
