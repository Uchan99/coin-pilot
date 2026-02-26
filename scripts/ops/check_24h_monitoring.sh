#!/usr/bin/env bash
set -uo pipefail

# 24시간 운영 점검은 "일부 실패가 있어도 다음 점검을 계속 수행"해야 전체 상태를 한 번에 파악할 수 있다.
# 그래서 set -e를 사용하지 않고, 실패 카운트를 누적해 마지막에 종료코드로 반환한다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ENV_FILE="${COINPILOT_ENV_FILE:-${REPO_ROOT}/deploy/cloud/oci/.env}"
COMPOSE_FILE="${COINPILOT_COMPOSE_FILE:-${REPO_ROOT}/deploy/cloud/oci/docker-compose.prod.yml}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"

FAIL_COUNT=0
WARN_COUNT=0
MODE="all"
OUTPUT_FILE=""

SERVICES=(bot collector dashboard db grafana n8n prometheus redis)

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/check_24h_monitoring.sh [all|t0|t1h|t6h|t12h|t24h] [--output <file>]

Examples:
  scripts/ops/check_24h_monitoring.sh all
  scripts/ops/check_24h_monitoring.sh t0
  scripts/ops/check_24h_monitoring.sh all --output /var/log/coinpilot/monitoring-24h.log

Optional env overrides:
  COINPILOT_ENV_FILE=/opt/coin-pilot/deploy/cloud/oci/.env
  COINPILOT_COMPOSE_FILE=/opt/coin-pilot/deploy/cloud/oci/docker-compose.prod.yml
  PROMETHEUS_URL=http://127.0.0.1:9090
EOF
}

info() { echo "[INFO] $*"; }
pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "[FAIL] $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

run_compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      all|t0|t1h|t6h|t12h|t24h)
        MODE="$1"
        shift
        ;;
      --output)
        if [[ $# -lt 2 ]]; then
          echo "[FAIL] --output requires a file path"
          usage
          exit 2
        fi
        OUTPUT_FILE="$2"
        shift 2
        ;;
      -h|--help|help)
        usage
        exit 0
        ;;
      *)
        echo "[FAIL] unknown argument: $1"
        usage
        exit 2
        ;;
    esac
  done
}

setup_output_redirection() {
  if [[ -z "${OUTPUT_FILE}" ]]; then
    return
  fi

  local output_dir
  output_dir="$(dirname "${OUTPUT_FILE}")"
  if [[ ! -d "${output_dir}" ]]; then
    mkdir -p "${output_dir}" 2>/dev/null || {
      echo "[FAIL] output directory 생성 실패: ${output_dir}"
      exit 2
    }
  fi

  # 운영 점검 로그를 화면 + 파일에 동시에 남겨, 사후 분석과 운영보고 증적을 확보한다.
  exec > >(tee -a "${OUTPUT_FILE}") 2>&1
  info "output log file: ${OUTPUT_FILE}"
}

check_prerequisites() {
  info "사전 조건 점검"
  if [[ ! -f "${ENV_FILE}" ]]; then
    fail "환경파일 없음: ${ENV_FILE}"
  else
    pass "환경파일 확인: ${ENV_FILE}"
  fi

  if [[ ! -f "${COMPOSE_FILE}" ]]; then
    fail "Compose 파일 없음: ${COMPOSE_FILE}"
  else
    pass "Compose 파일 확인: ${COMPOSE_FILE}"
  fi

  if ! command -v docker >/dev/null 2>&1; then
    fail "docker 명령을 찾을 수 없음"
  else
    pass "docker 명령 확인"
  fi
}

check_compose_services_up() {
  info "T+0m: compose 서비스 상태 점검"
  local ps_output
  if ! ps_output="$(run_compose ps 2>&1)"; then
    fail "compose ps 실패: ${ps_output}"
    return
  fi

  for svc in "${SERVICES[@]}"; do
    local name="coinpilot-${svc}"
    if ! grep -Eq "${name}[[:space:]]" <<<"${ps_output}"; then
      fail "${name} 서비스가 목록에 없음"
      continue
    fi
    if grep -E "${name}.*(Up|running|healthy)" <<<"${ps_output}" >/dev/null 2>&1; then
      pass "${name} 상태 정상"
    else
      fail "${name}가 Up 상태가 아님"
    fi
  done
}

check_bot_critical_logs() {
  local since="${1:-10m}"
  info "T+0m: bot 치명 오류 키워드 점검 (${since})"
  local logs
  if ! logs="$(run_compose logs --since="${since}" bot 2>&1)"; then
    fail "bot logs 조회 실패: ${logs}"
    return
  fi

  if grep -Eiq "critical|traceback|undefinedtable|undefinedcolumn|critical bot loop error" <<<"${logs}"; then
    fail "bot 로그에서 치명 키워드 감지"
    echo "------ bot log tail ------"
    echo "${logs}" | tail -n 40
    echo "--------------------------"
  else
    pass "bot 로그 치명 키워드 없음"
  fi
}

check_prometheus_up() {
  info "T+1h: Prometheus coinpilot-core UP 점검"
  if ! command -v curl >/dev/null 2>&1; then
    fail "curl 명령을 찾을 수 없음"
    return
  fi

  local response
  response="$(
    curl -fsSG "${PROMETHEUS_URL}/api/v1/query" \
      --data-urlencode 'query=up{job="coinpilot-core"}' 2>/dev/null || true
  )"

  if [[ -z "${response}" ]]; then
    fail "Prometheus API 응답 없음 (${PROMETHEUS_URL})"
    return
  fi

  if ! grep -q '"status":"success"' <<<"${response}"; then
    fail "Prometheus API 호출 실패 응답: ${response}"
    return
  fi

  if grep -Eq '"value":[[][^]]*,"1"' <<<"${response}"; then
    pass "coinpilot-core target이 UP(1)"
  else
    fail "coinpilot-core target이 UP(1) 아님: ${response}"
  fi
}

check_manual_alert_routing_notice() {
  info "T+1h: Grafana/Discord 라우팅 확인 안내"
  warn "Grafana Alert Rule/Notification Policy와 Discord 수신은 UI에서 수동 확인 필요"
  echo "  - Grafana: Alerting > Alert rules 상태 확인"
  echo "  - Grafana: Contact points(coinpilot) Test 실행 후 Discord 수신 확인"
}

check_ai_risk_flow_logs() {
  local since="${1:-6h}"
  info "T+6h: Entry/AI/Risk 흐름 로그 연속성 점검 (${since})"

  local logs
  if ! logs="$(run_compose logs --since="${since}" bot 2>&1)"; then
    fail "bot logs 조회 실패: ${logs}"
    return
  fi

  if grep -Eiq "critical|traceback|undefinedtable|undefinedcolumn|critical bot loop error" <<<"${logs}"; then
    fail "bot 로그에서 치명 키워드 감지"
  else
    pass "bot 로그 치명 키워드 없음"
  fi

  local flow_count
  flow_count="$(
    grep -Ec "Entry Signal Detected|AI PreFilter Rejected|AI Guardrail Blocked|Trade Rejected by AI Agent|Trade Approved by AI Agent|Risk Rejected" <<<"${logs}" || true
  )"

  if [[ "${flow_count}" -gt 0 ]]; then
    pass "Entry/AI/Risk 이벤트 로그 감지: ${flow_count}건"
  else
    warn "Entry/AI/Risk 이벤트 로그가 없음(시장 상황/시간대 영향 가능)"
  fi
}

check_batch_jobs_12h() {
  local since="${1:-12h}"
  info "T+12h: RSS/Daily 배치 실패 누적 점검 (${since})"

  local bot_logs n8n_logs
  if ! bot_logs="$(run_compose logs --since="${since}" bot 2>&1)"; then
    fail "bot logs 조회 실패: ${bot_logs}"
    return
  fi
  if ! n8n_logs="$(run_compose logs --since="${since}" n8n 2>&1)"; then
    warn "n8n logs 조회 실패: ${n8n_logs}"
    n8n_logs=""
  fi

  if grep -Eiq "traceback|critical|rss .*failed|daily report .*failed|scheduler.*failed" <<<"${bot_logs}"; then
    fail "bot 배치 로그에서 실패 키워드 감지"
  else
    pass "bot 배치 실패 키워드 없음"
  fi

  if grep -q "RSS ingest done" <<<"${bot_logs}"; then
    pass "RSS ingest 완료 로그 확인"
  else
    warn "RSS ingest 완료 로그 미검출"
  fi

  if grep -Eiq "error|failed|exception" <<<"${n8n_logs}"; then
    warn "n8n 로그에 error/failed/exception 존재(수동 확인 권장)"
  else
    pass "n8n 로그 주요 에러 키워드 미검출"
  fi
}

check_latest_file_age_hours() {
  local pattern="$1"
  local label="$2"
  local max_age_hours="$3"

  local latest
  latest="$(ls -1t ${pattern} 2>/dev/null | head -n 1 || true)"
  if [[ -z "${latest}" ]]; then
    fail "${label} 백업 파일 없음 (${pattern})"
    return
  fi

  local now_ts file_ts age_hours
  now_ts="$(date +%s)"
  file_ts="$(stat -c %Y "${latest}" 2>/dev/null || true)"
  if [[ -z "${file_ts}" ]]; then
    fail "${label} 백업 파일 timestamp 조회 실패: ${latest}"
    return
  fi

  age_hours="$(( (now_ts - file_ts) / 3600 ))"
  if (( age_hours <= max_age_hours )); then
    pass "${label} 최신 백업 확인 (${age_hours}h 전): ${latest}"
  else
    fail "${label} 최신 백업이 오래됨 (${age_hours}h 전): ${latest}"
  fi
}

check_backups_24h() {
  info "T+24h: Postgres/Redis/n8n 백업 생성 점검"

  check_latest_file_age_hours "/var/backups/coinpilot/postgres/daily/*.sql.gz" "Postgres" 36
  check_latest_file_age_hours "/var/backups/coinpilot/redis/daily/*.tar.gz" "Redis" 36
  check_latest_file_age_hours "/var/backups/coinpilot/n8n/daily/*.tar.gz" "n8n" 36

  if command -v systemctl >/dev/null 2>&1; then
    local cron_state
    cron_state="$(systemctl is-active cron 2>/dev/null || true)"
    if [[ "${cron_state}" == "active" ]]; then
      pass "cron 서비스 active"
    else
      warn "cron 서비스 상태 확인 필요: ${cron_state:-unknown}"
    fi
  fi
}

run_t0() {
  check_compose_services_up
  check_bot_critical_logs "10m"
}

run_t1h() {
  check_prometheus_up
  check_manual_alert_routing_notice
}

run_t6h() {
  check_ai_risk_flow_logs "6h"
}

run_t12h() {
  check_batch_jobs_12h "12h"
}

run_t24h() {
  check_backups_24h
}

main() {
  parse_args "$@"
  setup_output_redirection

  check_prerequisites

  case "${MODE}" in
    all)
      run_t0
      run_t1h
      run_t6h
      run_t12h
      run_t24h
      ;;
    t0) run_t0 ;;
    t1h) run_t1h ;;
    t6h) run_t6h ;;
    t12h) run_t12h ;;
    t24h) run_t24h ;;
  esac

  echo
  echo "========== SUMMARY =========="
  echo "FAIL: ${FAIL_COUNT}"
  echo "WARN: ${WARN_COUNT}"

  if (( FAIL_COUNT > 0 )); then
    exit 1
  fi
  exit 0
}

main "$@"
