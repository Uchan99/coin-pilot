#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - OCI A1.Flex(2 OCPU/12GB) 인스턴스 생성이 "Out of capacity"로 실패할 때 자동 재시도한다.
# - 현재 이미 만들어 둔 VCN/Subnet/Security Rule을 재사용하고, 인스턴스만 생성한다.
# - SSH 개인키는 로컬에서 생성/보관하여 "다시 다운로드 불가" 문제를 피한다.

# ===== 사용자 설정(환경변수) =====
OCI_PROFILE="${OCI_PROFILE:-DEFAULT}"
COMPARTMENT_OCID="${COMPARTMENT_OCID:-}"
SUBNET_OCID="${SUBNET_OCID:-}"
AVAILABILITY_DOMAIN="${AVAILABILITY_DOMAIN:-}"
IMAGE_OCID="${IMAGE_OCID:-}"
IMAGE_COMPARTMENT_OCID="${IMAGE_COMPARTMENT_OCID:-$COMPARTMENT_OCID}"
IMAGE_OS_NAME="${IMAGE_OS_NAME:-Canonical Ubuntu}"
IMAGE_OS_VERSION="${IMAGE_OS_VERSION:-22.04}"
IMAGE_NAME_FILTER_1="${IMAGE_NAME_FILTER_1:-Minimal}"
IMAGE_NAME_FILTER_2="${IMAGE_NAME_FILTER_2:-aarch64}"

INSTANCE_NAME="${INSTANCE_NAME:-coinpilot-ins}"
SHAPE="${SHAPE:-VM.Standard.A1.Flex}"
OCPUS="${OCPUS:-2}"
MEMORY_GBS="${MEMORY_GBS:-12}"
BOOT_VOLUME_SIZE_GBS="${BOOT_VOLUME_SIZE_GBS:-50}"
ASSIGN_PUBLIC_IP="${ASSIGN_PUBLIC_IP:-true}"

# 재시도 정책
RETRY_INTERVAL_SECONDS="${RETRY_INTERVAL_SECONDS:-600}"  # 기본 10분
MAX_ATTEMPTS="${MAX_ATTEMPTS:-0}"                        # 0이면 무한 재시도

# Discord 알림(선택)
DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
DISCORD_NOTIFY_EVERY_N_ATTEMPTS="${DISCORD_NOTIFY_EVERY_N_ATTEMPTS:-10}"

# 키/로그 저장 경로
KEY_DIR="${KEY_DIR:-$HOME/.ssh/coinpilot-oci}"
KEY_BASENAME="${KEY_BASENAME:-${INSTANCE_NAME}_a1_flex}"
ARTIFACT_DIR="${ARTIFACT_DIR:-$PWD/artifacts/oci-a1-flex-retry}"

PRIVATE_KEY_PATH="${PRIVATE_KEY_PATH:-$KEY_DIR/$KEY_BASENAME}"
PUBLIC_KEY_PATH="${PUBLIC_KEY_PATH:-${PRIVATE_KEY_PATH}.pub}"

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] command not found: $1"
    exit 1
  fi
}

validate_required() {
  local missing=0
  for v in COMPARTMENT_OCID SUBNET_OCID AVAILABILITY_DOMAIN; do
    if [[ -z "${!v}" ]]; then
      echo "[ERROR] required variable is empty: $v"
      missing=1
    fi
  done
  if [[ "$missing" -ne 0 ]]; then
    exit 1
  fi
}

resolve_image_ocid_if_needed() {
  if [[ -n "$IMAGE_OCID" ]]; then
    echo "[INFO] IMAGE_OCID is explicitly provided: $IMAGE_OCID"
    return
  fi

  echo "[INFO] IMAGE_OCID is empty; resolving image automatically..."
  echo "[INFO] image lookup compartment: $IMAGE_COMPARTMENT_OCID"
  local images_json resolved

  images_json="$(oci compute image list \
    --profile "$OCI_PROFILE" \
    --compartment-id "$IMAGE_COMPARTMENT_OCID" \
    --all \
    --shape "$SHAPE" \
    --output json 2>/dev/null || true)"

  if [[ -z "$images_json" || "$images_json" == "null" ]]; then
    echo "[ERROR] failed to query images from OCI API."
    exit 1
  fi

  # 1차: Ubuntu 22.04 + Minimal + Arm/aarch64
  resolved="$(echo "$images_json" | jq -r '
    .data
    | map(select(."lifecycle-state"=="AVAILABLE"))
    | map(select((."operating-system" // "" | ascii_downcase | contains("ubuntu"))))
    | map(select((."operating-system-version" // "" | startswith("22.04"))))
    | map(select((."display-name" // "" | ascii_downcase | contains("minimal"))))
    | map(select((."display-name" // "" | ascii_downcase | contains("aarch64") or contains("arm"))))
    | sort_by(."time-created")
    | last
    | .id // empty
  ')"

  # 2차: Ubuntu 22.04 + Arm/aarch64
  if [[ -z "$resolved" || "$resolved" == "null" ]]; then
    resolved="$(echo "$images_json" | jq -r '
      .data
      | map(select(."lifecycle-state"=="AVAILABLE"))
      | map(select((."operating-system" // "" | ascii_downcase | contains("ubuntu"))))
      | map(select((."operating-system-version" // "" | startswith("22.04"))))
      | map(select((."display-name" // "" | ascii_downcase | contains("aarch64") or contains("arm"))))
      | sort_by(."time-created")
      | last
      | .id // empty
    ')"
  fi

  # 3차: Ubuntu 22.04 최신
  if [[ -z "$resolved" || "$resolved" == "null" ]]; then
    resolved="$(echo "$images_json" | jq -r '
      .data
      | map(select(."lifecycle-state"=="AVAILABLE"))
      | map(select((."operating-system" // "" | ascii_downcase | contains("ubuntu"))))
      | map(select((."operating-system-version" // "" | startswith("22.04"))))
      | sort_by(."time-created")
      | last
      | .id // empty
    ')"
  fi

  if [[ -z "$resolved" || "$resolved" == "null" ]]; then
    echo "[ERROR] failed to resolve IMAGE_OCID automatically."
    echo "[INFO] candidate images for shape=$SHAPE:"
    echo "$images_json" | jq -r '
      .data
      | map(select(."lifecycle-state"=="AVAILABLE"))
      | map({id: .id, name: ."display-name", os: ."operating-system", os_ver: ."operating-system-version", created: ."time-created"})
      | sort_by(.created)
      | reverse
      | .[:15]
      | .[]
      | "- \(.name) | \(.os) \(.os_ver) | \(.id)"
    '
    echo "        provide IMAGE_OCID explicitly or adjust IMAGE_* filters."
    exit 1
  fi

  IMAGE_OCID="$resolved"
  echo "[INFO] resolved IMAGE_OCID: $IMAGE_OCID"
}

prepare_ssh_key() {
  mkdir -p "$KEY_DIR"
  chmod 700 "$KEY_DIR"

  if [[ -f "$PRIVATE_KEY_PATH" && -f "$PUBLIC_KEY_PATH" ]]; then
    echo "[INFO] existing key pair found: $PRIVATE_KEY_PATH"
  else
    echo "[INFO] generating new SSH key pair: $PRIVATE_KEY_PATH"
    ssh-keygen -t rsa -b 4096 -N "" -f "$PRIVATE_KEY_PATH" -C "${INSTANCE_NAME}-$(date +%F)" >/dev/null
  fi

  chmod 600 "$PRIVATE_KEY_PATH"
  chmod 644 "$PUBLIC_KEY_PATH"
}

get_public_ip() {
  local instance_id="$1"
  local vnic_id

  vnic_id="$(oci compute vnic-attachment list \
    --profile "$OCI_PROFILE" \
    --compartment-id "$COMPARTMENT_OCID" \
    --instance-id "$instance_id" \
    --query 'data[0]."vnic-id"' \
    --raw-output)"

  oci network vnic get \
    --profile "$OCI_PROFILE" \
    --vnic-id "$vnic_id" \
    --query 'data."public-ip"' \
    --raw-output
}

is_retryable_capacity_error() {
  local msg="$1"
  # OCI가 capacity 부족 상황에서 반환하는 대표 메시지들을 재시도 대상으로 본다.
  if echo "$msg" | grep -Eqi \
    "Out of capacity for shape|Out of host capacity|code\"[[:space:]]*:[[:space:]]*\"InternalError\""; then
    return 0
  fi
  return 1
}

notify_discord() {
  local title="$1"
  local body="$2"

  if [[ -z "$DISCORD_WEBHOOK_URL" ]]; then
    return 0
  fi

  # Discord webhook payload는 content 문자열만 사용해 단순/안정적으로 유지한다.
  local payload
  payload="$(jq -n --arg content "**${title}**\n${body}" '{content: $content}')"

  curl -sS -X POST "$DISCORD_WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null || true
}

main() {
  need_cmd oci
  need_cmd jq
  need_cmd ssh-keygen
  if [[ -n "$DISCORD_WEBHOOK_URL" ]]; then
    need_cmd curl
  fi
  validate_required
  resolve_image_ocid_if_needed
  prepare_ssh_key

  mkdir -p "$ARTIFACT_DIR"
  local timestamp
  timestamp="$(date +%Y%m%d_%H%M%S)"
  local log_file="$ARTIFACT_DIR/retry_${timestamp}.log"
  local result_file="$ARTIFACT_DIR/result_${timestamp}.json"

  echo "[INFO] starting retry loop for A1.Flex launch" | tee -a "$log_file"
  echo "[INFO] instance_name=$INSTANCE_NAME shape=$SHAPE ocpus=$OCPUS memory_gb=$MEMORY_GBS" | tee -a "$log_file"
  notify_discord "OCI A1 Retry Started" "name=${INSTANCE_NAME}\nshape=${SHAPE}\nocpus=${OCPUS}\nmemory=${MEMORY_GBS}GB\ninterval=${RETRY_INTERVAL_SECONDS}s"

  local attempt=1
  while true; do
    if [[ "$MAX_ATTEMPTS" -gt 0 && "$attempt" -gt "$MAX_ATTEMPTS" ]]; then
      echo "[ERROR] reached max attempts: $MAX_ATTEMPTS" | tee -a "$log_file"
      notify_discord "OCI A1 Retry Stopped" "reached max attempts: ${MAX_ATTEMPTS}\nlog=${log_file}"
      exit 1
    fi

    echo "[INFO] attempt #$attempt" | tee -a "$log_file"
    if [[ "$attempt" -eq 1 || $((attempt % DISCORD_NOTIFY_EVERY_N_ATTEMPTS)) -eq 0 ]]; then
      notify_discord "OCI A1 Retry Progress" "attempt=${attempt}\nstatus=launching"
    fi

    local launch_output
    if launch_output="$(oci compute instance launch \
      --profile "$OCI_PROFILE" \
      --compartment-id "$COMPARTMENT_OCID" \
      --availability-domain "$AVAILABILITY_DOMAIN" \
      --display-name "$INSTANCE_NAME" \
      --shape "$SHAPE" \
      --shape-config "{\"ocpus\":${OCPUS},\"memoryInGBs\":${MEMORY_GBS}}" \
      --subnet-id "$SUBNET_OCID" \
      --assign-public-ip "$ASSIGN_PUBLIC_IP" \
      --image-id "$IMAGE_OCID" \
      --ssh-authorized-keys-file "$PUBLIC_KEY_PATH" \
      --boot-volume-size-in-gbs "$BOOT_VOLUME_SIZE_GBS" \
      --output json 2>&1)"; then

      echo "$launch_output" > "$result_file"
      local instance_id
      instance_id="$(echo "$launch_output" | jq -r '.data.id')"

      echo "[INFO] launch request accepted: instance_id=$instance_id" | tee -a "$log_file"
      echo "[INFO] waiting until RUNNING" | tee -a "$log_file"

      oci compute instance get \
        --profile "$OCI_PROFILE" \
        --instance-id "$instance_id" \
        --wait-for-state RUNNING \
        --max-wait-seconds 1800 >/dev/null

      local public_ip
      public_ip="$(get_public_ip "$instance_id")"

      cat <<EOM | tee -a "$log_file"
[SUCCESS] instance created
- instance_id: $instance_id
- public_ip: $public_ip
- private_key: $PRIVATE_KEY_PATH
- public_key: $PUBLIC_KEY_PATH
- launch_result_json: $result_file
SSH example:
ssh -i "$PRIVATE_KEY_PATH" ubuntu@$public_ip
EOM
      notify_discord "OCI A1 Instance Created" "instance_id=${instance_id}\npublic_ip=${public_ip}\nname=${INSTANCE_NAME}"
      exit 0
    fi

    echo "$launch_output" | tee -a "$log_file"

    # A1 무료 용량 부족 상황은 운영적으로 흔하므로 재시도 루프를 유지한다.
    if is_retryable_capacity_error "$launch_output"; then
      echo "[WARN] retryable capacity error detected; sleeping ${RETRY_INTERVAL_SECONDS}s" | tee -a "$log_file"
      if [[ "$attempt" -eq 1 || $((attempt % DISCORD_NOTIFY_EVERY_N_ATTEMPTS)) -eq 0 ]]; then
        notify_discord "OCI A1 Capacity Retry" "attempt=${attempt}\nreason=capacity\nsleep=${RETRY_INTERVAL_SECONDS}s"
      fi
      sleep "$RETRY_INTERVAL_SECONDS"
      attempt=$((attempt + 1))
      continue
    fi

    echo "[ERROR] non-retryable launch failure" | tee -a "$log_file"
    notify_discord "OCI A1 Retry Failed" "attempt=${attempt}\nreason=non-retryable\nlog=${log_file}"
    exit 1
  done
}

main "$@"
