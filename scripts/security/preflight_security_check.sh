#!/usr/bin/env bash
set -euo pipefail

# 목적:
# - OCI 운영 배포 전에 "실수로 인한 보안 취약 설정"을 빠르게 탐지한다.
# - .env 필수값/권한, compose 하드닝 옵션, n8n webhook secret 검증 구성 여부를 점검한다.
#
# 사용:
#   ./scripts/security/preflight_security_check.sh
#   ./scripts/security/preflight_security_check.sh /opt/coin-pilot/deploy/cloud/oci/.env

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/deploy/cloud/oci/.env}"
COMPOSE_FILE="$ROOT_DIR/deploy/cloud/oci/docker-compose.prod.yml"
WORKFLOW_DIR="$ROOT_DIR/config/n8n_workflows"

fail_count=0

ok() {
  echo "[OK] $1"
}

warn() {
  echo "[WARN] $1"
}

fail() {
  echo "[FAIL] $1"
  fail_count=$((fail_count + 1))
}

require_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    fail "file not found: $file"
    return 1
  fi
  ok "file exists: $file"
}

check_env_permission() {
  local perm
  perm="$(stat -c '%a' "$ENV_FILE")"
  # 운영 시크릿 파일은 그룹/타인 읽기 권한이 없어야 한다.
  if [[ "$perm" != "600" ]]; then
    fail "env permission must be 600 (current: $perm): $ENV_FILE"
  else
    ok "env permission is 600: $ENV_FILE"
  fi
}

read_env_value() {
  local key="$1"
  local line
  line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    echo ""
    return 0
  fi
  echo "${line#*=}"
}

check_required_env() {
  local required_keys=(
    DB_PASSWORD
    UPBIT_ACCESS_KEY
    UPBIT_SECRET_KEY
    ANTHROPIC_API_KEY
    OPENAI_API_KEY
    N8N_WEBHOOK_SECRET
    N8N_BASIC_AUTH_USER
    N8N_BASIC_AUTH_PASSWORD
    DASHBOARD_ACCESS_PASSWORD
    GRAFANA_ADMIN_USER
    GRAFANA_ADMIN_PASSWORD
  )

  local key value
  for key in "${required_keys[@]}"; do
    value="$(read_env_value "$key")"
    if [[ -z "$value" ]]; then
      fail "required env is missing or empty: $key"
      continue
    fi

    # 플레이스홀더/약한 기본값이 남아 있으면 운영 배포를 막는다.
    if echo "$value" | grep -Eqi 'change_me|^admin$|^postgres$'; then
      fail "unsafe placeholder/default detected: $key"
      continue
    fi

    ok "required env looks set: $key"
  done
}

check_compose_hardening() {
  require_file "$COMPOSE_FILE" || return

  if grep -q 'N8N_BLOCK_ENV_ACCESS_IN_NODE: "true"' "$COMPOSE_FILE"; then
    ok "n8n env access block is enabled"
  else
    fail "N8N_BLOCK_ENV_ACCESS_IN_NODE must be true"
  fi

  # 외부(0.0.0.0)로 바로 바인딩된 포트가 있으면 운영 위험도가 급격히 높아진다.
  # 허용 정책: loopback 바인딩("127.0.0.1:host:container") 또는 포트 미바인딩.
  local direct_bind_lines
  direct_bind_lines="$(grep -En '^[[:space:]]*-[[:space:]]*"[0-9]+:[0-9]+"' "$COMPOSE_FILE" || true)"
  if [[ -n "$direct_bind_lines" ]]; then
    fail "direct host port binding detected (must use 127.0.0.1 bind): $direct_bind_lines"
  else
    ok "no direct host port binding found"
  fi
}

check_compose_image_tags() {
  require_file "$COMPOSE_FILE" || return

  local image_lines line image
  image_lines="$(grep -E '^[[:space:]]*image:[[:space:]]*' "$COMPOSE_FILE" || true)"
  if [[ -z "$image_lines" ]]; then
    warn "no image entries found in compose file: $COMPOSE_FILE"
    return
  fi

  while IFS= read -r line; do
    image="$(echo "$line" | sed -E 's/^[[:space:]]*image:[[:space:]]*//; s/[[:space:]]+#.*$//')"
    [[ -z "$image" ]] && continue

    # 로컬 빌드 이미지는 태그 정책에서 제외한다.
    case "$image" in
      collector:latest|bot:latest|dashboard:latest)
        ok "local build image allowed: $image"
        continue
        ;;
    esac

    if [[ "$image" == *"@sha256:"* ]]; then
      ok "immutable image digest detected: $image"
      continue
    fi

    # latest/부동 태그는 재현성과 보안 검증 일관성을 깨므로 배포 전 차단한다.
    if [[ "$image" =~ :latest($|-) ]]; then
      fail "mutable image tag is not allowed: $image"
      continue
    fi

    if [[ "$image" =~ :alpine$ ]]; then
      fail "floating alpine tag is not allowed (use versioned alpine tag): $image"
      continue
    fi

    if [[ "$image" != *:* ]]; then
      fail "image tag is missing: $image"
      continue
    fi

    ok "versioned image tag detected: $image"
  done <<< "$image_lines"
}

check_n8n_workflow_guards() {
  require_file "$WORKFLOW_DIR/trade_notification.json" || return
  require_file "$WORKFLOW_DIR/risk_alert.json" || return
  require_file "$WORKFLOW_DIR/daily_report.json" || return
  require_file "$WORKFLOW_DIR/ai_decision.json" || return
  require_file "$WORKFLOW_DIR/weekly-exit-report-workflow.json" || return

  local f
  for f in \
    "$WORKFLOW_DIR/trade_notification.json" \
    "$WORKFLOW_DIR/risk_alert.json" \
    "$WORKFLOW_DIR/daily_report.json" \
    "$WORKFLOW_DIR/ai_decision.json" \
    "$WORKFLOW_DIR/weekly-exit-report-workflow.json"; do
    if grep -q '"Validate Webhook Secret"' "$f"; then
      ok "webhook secret validation node found: $(basename "$f")"
    else
      fail "missing webhook secret validation node: $(basename "$f")"
    fi
  done
}

main() {
  require_file "$ENV_FILE" || true
  require_file "$COMPOSE_FILE" || true

  if [[ -f "$ENV_FILE" ]]; then
    check_env_permission
    check_required_env
  fi

  check_compose_hardening
  check_compose_image_tags
  check_n8n_workflow_guards

  echo
  if [[ "$fail_count" -gt 0 ]]; then
    echo "[RESULT] FAILED ($fail_count issues)"
    exit 1
  fi
  echo "[RESULT] PASSED"
}

main "$@"
