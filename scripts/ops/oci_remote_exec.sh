#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - WSL/로컬 셸에서 CoinPilot 운영 source of truth(OCI)로 명령을 프록시한다.
# - 로컬에 docker가 없어도, OCI에서 동일한 스크립트/SQL/compose 명령을 재사용하게 만든다.
#
# 설계 원칙:
# - 기본 작업 디렉토리는 /opt/coin-pilot로 고정해 runbook/결과 문서와 동일한 경로를 사용한다.
# - SSH 대상/키/포트는 env 파일에서만 읽고, 저장소에는 example만 커밋한다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEFAULT_ENV_FILE="${REPO_ROOT}/deploy/cloud/oci/ops/oci_access.env"

ENV_FILE="${OCI_REMOTE_ACCESS_ENV_FILE:-${DEFAULT_ENV_FILE}}"
RAW_MODE=false
RAW_COMMAND=""

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/oci_remote_exec.sh [--env-file <path>] <command> [args...]
  scripts/ops/oci_remote_exec.sh [--env-file <path>] --raw '<shell command>'

Examples:
  scripts/ops/oci_remote_exec.sh pwd
  scripts/ops/oci_remote_exec.sh scripts/ops/ai_decision_canary_report.sh 24
  scripts/ops/oci_remote_exec.sh --raw 'docker exec -u postgres coinpilot-db psql -d coinpilot -c "SELECT now();"'

Env file preparation:
  cp deploy/cloud/oci/ops/oci_access.env.example deploy/cloud/oci/ops/oci_access.env
  chmod 600 deploy/cloud/oci/ops/oci_access.env

Supported env keys:
  OCI_REMOTE_SSH_TARGET=coinpilot-oci            # optional, ssh config alias or user@host
  OCI_REMOTE_HOST=168.107.40.180                 # used when OCI_REMOTE_SSH_TARGET is empty
  OCI_REMOTE_USER=ubuntu
  OCI_REMOTE_SSH_KEY_PATH=~/.ssh/coinpilot-oci/coinpilot-ins_a1_flex
  OCI_REMOTE_SSH_PORT=22
  OCI_REMOTE_REPO_ROOT=/opt/coin-pilot
  OCI_REMOTE_CONNECT_TIMEOUT_SEC=10
  OCI_REMOTE_STRICT_HOST_KEY_CHECKING=accept-new
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

quote_args() {
  local quoted=()
  local arg
  for arg in "$@"; do
    quoted+=("$(printf '%q' "${arg}")")
  done
  printf '%s ' "${quoted[@]}"
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
      --raw)
        if [[ $# -lt 2 ]]; then
          echo "[FAIL] --raw requires a shell command string" >&2
          usage
          exit 2
        fi
        RAW_MODE=true
        RAW_COMMAND="$2"
        shift 2
        ;;
      -h|--help|help)
        usage
        exit 0
        ;;
      --)
        shift
        break
        ;;
      -*)
        echo "[FAIL] unknown option: $1" >&2
        usage
        exit 2
        ;;
      *)
        break
        ;;
    esac
  done

  REMAINING_ARGS=("$@")
}

parse_args "$@"
load_env_file

if ! command -v ssh >/dev/null 2>&1; then
  echo "[FAIL] ssh 명령을 찾을 수 없습니다." >&2
  exit 2
fi

SSH_TARGET="$(build_ssh_target)"
REMOTE_REPO_ROOT="${OCI_REMOTE_REPO_ROOT:-/opt/coin-pilot}"
SSH_KEY_PATH="$(expand_path "${OCI_REMOTE_SSH_KEY_PATH:-}")"
SSH_PORT="${OCI_REMOTE_SSH_PORT:-22}"
CONNECT_TIMEOUT_SEC="${OCI_REMOTE_CONNECT_TIMEOUT_SEC:-10}"
STRICT_HOST_KEY_CHECKING="${OCI_REMOTE_STRICT_HOST_KEY_CHECKING:-accept-new}"

if [[ "${RAW_MODE}" == true ]]; then
  if [[ -z "${RAW_COMMAND}" ]]; then
    echo "[FAIL] --raw command is empty" >&2
    exit 2
  fi
  REMOTE_COMMAND_BODY="${RAW_COMMAND}"
else
  if [[ ${#REMAINING_ARGS[@]} -eq 0 ]]; then
    usage
    exit 2
  fi
  REMOTE_COMMAND_BODY="$(quote_args "${REMAINING_ARGS[@]}")"
fi

# 원격 셸에서는 항상 /opt/coin-pilot 기준으로 실행해 상대경로 혼선을 제거한다.
REMOTE_PAYLOAD="cd $(printf '%q' "${REMOTE_REPO_ROOT}") && ${REMOTE_COMMAND_BODY}"

SSH_ARGS=(
  -o "BatchMode=yes"
  -o "ConnectTimeout=${CONNECT_TIMEOUT_SEC}"
  -o "ServerAliveInterval=30"
  -o "ServerAliveCountMax=3"
  -o "StrictHostKeyChecking=${STRICT_HOST_KEY_CHECKING}"
  -p "${SSH_PORT}"
)

if [[ -n "${SSH_KEY_PATH}" ]]; then
  SSH_ARGS+=(-i "${SSH_KEY_PATH}")
fi

echo "[INFO] OCI remote exec"
echo "[INFO] env_file=${ENV_FILE}"
echo "[INFO] ssh_target=${SSH_TARGET}"
echo "[INFO] remote_repo_root=${REMOTE_REPO_ROOT}"
if [[ "${RAW_MODE}" == true ]]; then
  echo "[INFO] mode=raw"
else
  echo "[INFO] mode=argv"
fi

exec ssh "${SSH_ARGS[@]}" "${SSH_TARGET}" "bash -lc $(printf '%q' "${REMOTE_PAYLOAD}")"
