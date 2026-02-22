#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - 매번 export를 다시 치지 않고, 고정 환경파일을 불러와 재시도 스크립트를 실행한다.
# - 데스크톱 재부팅/터미널 재시작 이후에도 동일 명령 1줄로 재개할 수 있게 한다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ENV_FILE:-$SCRIPT_DIR/oci_retry.env}"
TARGET_SCRIPT="$SCRIPT_DIR/oci_retry_launch_a1_flex.sh"

if [[ ! -x "$TARGET_SCRIPT" ]]; then
  echo "[ERROR] target script not executable: $TARGET_SCRIPT"
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cat <<EOM
[ERROR] env file not found: $ENV_FILE
다음 순서로 준비하세요:
1) cp $SCRIPT_DIR/oci_retry.env.example $SCRIPT_DIR/oci_retry.env
2) 편집기로 oci_retry.env 값을 실제 OCID/옵션으로 수정
3) chmod 600 $SCRIPT_DIR/oci_retry.env
EOM
  exit 1
fi

# 환경파일의 모든 키를 export해 하위 스크립트에서 바로 읽을 수 있게 한다.
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# 사용자가 OCI 설정파일 경로를 별도 관리하는 경우를 대비한 호환 옵션.
if [[ -n "${OCI_CONFIG_FILE:-}" ]]; then
  export OCI_CLI_CONFIG_FILE="$OCI_CONFIG_FILE"
fi

exec "$TARGET_SCRIPT"
