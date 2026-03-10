#!/usr/bin/env bash
set -uo pipefail

# 24시간 운영 점검은 "일부 실패가 있어도 다음 점검을 계속 수행"해야 전체 상태를 한 번에 파악할 수 있다.
# 그래서 set -e를 사용하지 않고, 실패 카운트를 누적해 마지막에 종료코드로 반환한다.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

ENV_FILE="${COINPILOT_ENV_FILE:-${REPO_ROOT}/deploy/cloud/oci/.env}"
COMPOSE_FILE="${COINPILOT_COMPOSE_FILE:-${REPO_ROOT}/deploy/cloud/oci/docker-compose.prod.yml}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://127.0.0.1:9090}"
LOKI_URL="${LOKI_URL:-http://127.0.0.1:3100}"
OPS_LOG_ROOT="${COINPILOT_OPS_LOG_ROOT:-/var/log/coinpilot/ops}"
LLM_SNAPSHOT_MAX_LAG_MINUTES="${LLM_SNAPSHOT_MAX_LAG_MINUTES:-180}"
AI_DECISION_INACTIVITY_HOURS="${AI_DECISION_INACTIVITY_HOURS:-6}"

FAIL_COUNT=0
WARN_COUNT=0
MODE="all"
OUTPUT_FILE=""
AUTOMATION_MODE=false

SERVICES=(bot collector dashboard db grafana n8n prometheus redis node-exporter cadvisor container-map loki promtail-targets promtail)
OPTIONAL_SERVICES=(discord-bot)

usage() {
  cat <<'EOF'
Usage:
  scripts/ops/check_24h_monitoring.sh [all|t0|t1h|t6h|t12h|t24h] [--output <file>] [--automation-mode]

Examples:
  scripts/ops/check_24h_monitoring.sh all
  scripts/ops/check_24h_monitoring.sh t0
  scripts/ops/check_24h_monitoring.sh all --output /var/log/coinpilot/monitoring-24h.log
  scripts/ops/check_24h_monitoring.sh t1h --automation-mode

Optional env overrides:
  COINPILOT_ENV_FILE=/opt/coin-pilot/deploy/cloud/oci/.env
  COINPILOT_COMPOSE_FILE=/opt/coin-pilot/deploy/cloud/oci/docker-compose.prod.yml
  PROMETHEUS_URL=http://127.0.0.1:9090
  LOKI_URL=http://127.0.0.1:3100
  COINPILOT_OPS_LOG_ROOT=/var/log/coinpilot/ops
  LLM_SNAPSHOT_MAX_LAG_MINUTES=180
  AI_DECISION_INACTIVITY_HOURS=6
EOF
}

info() { echo "[INFO] $*"; }
pass() { echo "[PASS] $*"; }
warn() { echo "[WARN] $*"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "[FAIL] $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

run_compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

read_env_value() {
  local key="$1"
  awk -F= -v key="$key" '
    /^[[:space:]]*#/ { next }
    $1 == key {
      sub(/^[^=]*=/, "", $0)
      gsub(/\r$/, "", $0)
      print $0
      exit
    }
  ' "${ENV_FILE}" 2>/dev/null || true
}

normalize_bool() {
  local raw="${1:-}"
  raw="${raw%\"}"
  raw="${raw#\"}"
  echo "${raw}" | tr '[:upper:]' '[:lower:]'
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
      --automation-mode)
        AUTOMATION_MODE=true
        shift
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

  # 선택 서비스는 배포 정책/환경변수에 따라 비활성일 수 있으므로 "존재할 때만" 상태를 강제 점검한다.
  local optional_name optional_svc
  for optional_svc in "${OPTIONAL_SERVICES[@]}"; do
    optional_name="coinpilot-${optional_svc}"
    if ! grep -Eq "${optional_name}[[:space:]]" <<<"${ps_output}"; then
      info "${optional_name} 서비스는 비활성(또는 미배포) 상태로 간주하고 점검에서 제외"
      continue
    fi
    if grep -E "${optional_name}.*(Up|running|healthy)" <<<"${ps_output}" >/dev/null 2>&1; then
      pass "${optional_name} 상태 정상"
    else
      fail "${optional_name}가 Up 상태가 아님"
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

check_prometheus_infra_targets_up() {
  info "T+1h: Prometheus infra target(node-exporter/cadvisor) UP 점검"
  if ! command -v curl >/dev/null 2>&1; then
    fail "curl 명령을 찾을 수 없음"
    return
  fi

  # 문자열 비교 오탐을 줄이기 위해 대상 job을 각각 분리 조회한다.
  # 두 exporter는 인프라 지표의 소스이므로 하나라도 DOWN이면 운영 관측 공백이 생긴다.
  local jobs=(node-exporter cadvisor)
  local job response
  for job in "${jobs[@]}"; do
    response="$(
      curl -fsSG "${PROMETHEUS_URL}/api/v1/query" \
        --data-urlencode "query=up{job=\"${job}\"}" 2>/dev/null || true
    )"

    if [[ -z "${response}" ]]; then
      fail "${job} target 조회 응답 없음 (${PROMETHEUS_URL})"
      continue
    fi
    if ! grep -q '"status":"success"' <<<"${response}"; then
      fail "${job} target 조회 실패 응답: ${response}"
      continue
    fi
    if grep -Eq '"value":[[][^]]*,"1"' <<<"${response}"; then
      pass "${job} target이 UP(1)"
    else
      fail "${job} target이 UP(1) 아님: ${response}"
    fi
  done
}

check_prometheus_container_display_map() {
  info "T+1h: Prometheus container display map 메트릭 점검"
  if ! command -v curl >/dev/null 2>&1; then
    fail "curl 명령을 찾을 수 없음"
    return
  fi

  # cAdvisor가 라벨을 제공하지 않는 환경에서는 이 매핑 메트릭이
  # Grafana 범례의 서비스명 표기를 담당한다.
  local response
  response="$(
    curl -fsSG "${PROMETHEUS_URL}/api/v1/query" \
      --data-urlencode 'query=count(coinpilot_container_display_info{job="node-exporter"})' 2>/dev/null || true
  )"

  if [[ -z "${response}" ]]; then
    fail "container display map 메트릭 조회 응답 없음 (${PROMETHEUS_URL})"
    return
  fi
  if ! grep -q '"status":"success"' <<<"${response}"; then
    fail "container display map 메트릭 조회 실패 응답: ${response}"
    return
  fi
  if grep -Eq '"value":[[][^]]*,"[1-9][0-9]*"' <<<"${response}"; then
    pass "container display map 메트릭 존재 확인"
  else
    warn "container display map 메트릭이 비어 있음(범례 fallback ID 동작 예상): ${response}"
  fi

  # display map만 존재하고 stats가 비면 CPU/Memory 패널은 No data가 될 수 있다.
  local stats_response
  stats_response="$(
    curl -fsSG "${PROMETHEUS_URL}/api/v1/query" \
      --data-urlencode 'query=count(coinpilot_container_cpu_percent{job="node-exporter"})' 2>/dev/null || true
  )"
  if [[ -z "${stats_response}" ]]; then
    warn "container cpu metric 조회 응답 없음 (${PROMETHEUS_URL})"
    return
  fi
  if ! grep -q '"status":"success"' <<<"${stats_response}"; then
    warn "container cpu metric 조회 실패 응답: ${stats_response}"
    return
  fi
  if grep -Eq '"value":[[][^]]*,"[1-9][0-9]*"' <<<"${stats_response}"; then
    pass "container cpu metric 존재 확인"
  else
    warn "container cpu metric이 비어 있음(CPU 패널 No data 가능): ${stats_response}"
  fi
}

check_loki_log_pipeline() {
  info "T+1h: Loki/Promtail 로그 수집 파이프라인 점검"
  if ! command -v curl >/dev/null 2>&1; then
    fail "curl 명령을 찾을 수 없음"
    return
  fi

  local ready_response
  ready_response="$(curl -fsS "${LOKI_URL}/ready" 2>/dev/null || true)"
  if [[ "${ready_response}" == "ready" ]]; then
    pass "Loki readiness 확인(ready)"
  fi

  local labels_response
  labels_response="$(
    curl -fsSG "${LOKI_URL}/loki/api/v1/label/service/values" 2>/dev/null || true
  )"
  if [[ "${ready_response}" != "ready" ]]; then
    # 일부 Loki 버전/프록시 조합에서는 /ready 응답 본문이 비거나 curl이 실패해도
    # 실제 query API는 정상인 경우가 있다. 이런 경우 readiness만으로 FAIL 처리하면
    # 운영 false fail이 되므로 query API 성공을 readiness fallback으로 인정한다.
    if [[ -n "${labels_response}" ]] && grep -q '"status":"success"' <<<"${labels_response}"; then
      pass "Loki readiness fallback 확인(query API success, /ready body=${ready_response:-empty})"
    else
      fail "Loki readiness 실패 (${LOKI_URL}/ready): ${ready_response:-empty response}"
    fi
  fi

  if [[ -z "${labels_response}" ]]; then
    warn "Loki service 라벨 조회 응답 없음 (${LOKI_URL})"
  elif ! grep -q '"status":"success"' <<<"${labels_response}"; then
    warn "Loki service 라벨 조회 실패 응답: ${labels_response}"
  elif grep -Eq 'coinpilot-' <<<"${labels_response}"; then
    pass "Loki service 라벨에서 coinpilot-* 로그 스트림 확인"
  else
    # 파일 타깃 수집 구조에서는 service 라벨 추출 지연/누락이 있을 수 있으므로
    # filename 라벨(실제 파일 경로)에서 coinpilot-* 유입을 2차 확인한다.
    local filename_labels_response
    filename_labels_response="$(
      curl -fsSG "${LOKI_URL}/loki/api/v1/label/filename/values" 2>/dev/null || true
    )"
    if [[ -n "${filename_labels_response}" ]] \
      && grep -q '"status":"success"' <<<"${filename_labels_response}" \
      && grep -Eq '/targets/logs/coinpilot-' <<<"${filename_labels_response}"; then
      pass "Loki filename 라벨에서 coinpilot-* 로그 스트림 확인(service 라벨 fallback)"
    else
      warn "Loki service/filename 라벨에서 coinpilot-* 로그 스트림 미검출(초기 구간일 수 있음): service=${labels_response} filename=${filename_labels_response:-empty}"
    fi
  fi

  local promtail_logs
  if ! promtail_logs="$(run_compose logs --since=15m promtail 2>&1)"; then
    fail "promtail logs 조회 실패: ${promtail_logs}"
    return
  fi

  if grep -Eiq "client version .* too old|unable to refresh target groups" <<<"${promtail_logs}"; then
    fail "promtail 로그에 Docker API/대상 탐색 오류 키워드 감지"
  elif grep -Eiq "timestamp too old|entry too far behind" <<<"${promtail_logs}"; then
    # 최초 구간 백로그를 Loki가 드롭하는 케이스는 일시적일 수 있어 경고로 분류한다.
    warn "promtail 로그에 과거 타임스탬프 드롭 경고 감지(positions 안정화 후 재확인 권장)"
  elif grep -Eiq "error sending batch|server returned HTTP status 4|server returned HTTP status 5" <<<"${promtail_logs}"; then
    fail "promtail 로그에 전송 배치 오류 키워드 감지"
  else
    pass "promtail 전송 오류 키워드 미검출"
  fi

  # 파일 타깃 생성 사이드카가 실패하면 promtail 자체는 정상이어도 로그 유입이 0이 될 수 있다.
  local promtail_targets_logs
  if ! promtail_targets_logs="$(run_compose logs --since=15m promtail-targets 2>&1)"; then
    fail "promtail-targets logs 조회 실패: ${promtail_targets_logs}"
    return
  fi

  if grep -Eiq "client version .* too old|cannot connect to the docker daemon|permission denied|error response from daemon|no such file or directory|read-only file system" <<<"${promtail_targets_logs}"; then
    fail "promtail-targets 로그에 타깃 생성 오류 키워드 감지"
  else
    pass "promtail-targets 타깃 생성 오류 키워드 미검출"
  fi
}

check_manual_alert_routing_notice() {
  info "T+1h: Grafana/Discord 라우팅 확인 안내"
  # 자동 실행(cron)에서는 이 항목이 항상 미확인 상태이므로 WARN으로 누적되면
  # 실제 장애 신호 대비 노이즈가 된다. 수동 점검에서만 WARN을 유지하고,
  # 자동화 모드에서는 "별도 UI 확인 필요"라는 안내만 INFO로 남긴다.
  if [[ "${AUTOMATION_MODE}" == "true" ]]; then
    info "automation mode: Grafana/Discord 라우팅 수동 확인 항목은 WARN 집계에서 제외"
    echo "  - 수동 점검 시 Grafana Alert rules / Contact points Test / Discord 수신 확인 필요"
    return
  fi

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

  # "failed_feeds=0" 같은 정상 통계 필드명은 제외하고,
  # 실제 실패 문맥(예: "... job failed:" / "scheduler...failed:")만 감지한다.
  if grep -Eiq "traceback|critical|rss (ingest|summarize) job failed:|daily report .*failed|scheduler.*failed:" <<<"${bot_logs}"; then
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

check_llm_snapshot_freshness_24h() {
  info "T+24h: LLM provider cost snapshot freshness 점검"

  # 개인 계정 fallback 운영에서는 snapshot 수집을 의도적으로 끈다.
  # 이 경우 0건은 장애가 아니라 정책된 상태이므로 FAIL/WARN으로 올리지 않고 INFO만 남긴다.
  local snapshot_enabled
  snapshot_enabled="$(normalize_bool "$(read_env_value "LLM_COST_SNAPSHOT_ENABLED")")"
  if [[ "${snapshot_enabled}" != "true" ]]; then
    info "LLM cost snapshot 비활성(개인 계정 fallback 또는 운영 정책): freshness 점검 제외"
    return
  fi

  local providers_raw providers_sql
  providers_raw="$(read_env_value "LLM_COST_SNAPSHOT_PROVIDERS")"
  providers_raw="${providers_raw:-anthropic,openai}"
  providers_sql="$(echo "${providers_raw}" | sed "s/,/' , '/g; s/^/'/; s/$/'/")"

  local rows
  rows="$(
    docker exec -u postgres coinpilot-db psql -d coinpilot -At -F '|' -c "
    WITH configured(provider) AS (
      SELECT unnest(ARRAY[${providers_sql}])
    ),
    latest AS (
      SELECT
        provider,
        COUNT(*) AS snapshots,
        MAX(created_at) AS last_snapshot_at,
        ROUND(EXTRACT(EPOCH FROM (now() - MAX(created_at))) / 60.0, 2) AS lag_minutes
      FROM llm_provider_cost_snapshots
      GROUP BY provider
    )
    SELECT
      c.provider,
      COALESCE(l.snapshots, 0),
      COALESCE(to_char(l.last_snapshot_at, 'YYYY-MM-DD\"T\"HH24:MI:SSOF'), ''),
      COALESCE(l.lag_minutes::text, '')
    FROM configured c
    LEFT JOIN latest l ON l.provider = c.provider
    ORDER BY c.provider;
    " 2>/dev/null || true
  )"

  if [[ -z "${rows}" ]]; then
    warn "LLM snapshot freshness 조회 결과가 비어 있음(설정/권한/테이블 상태 확인 필요)"
    return
  fi

  local row provider snapshots last_snapshot_at lag_minutes
  while IFS='|' read -r provider snapshots last_snapshot_at lag_minutes; do
    if [[ -z "${provider}" ]]; then
      continue
    fi
    if [[ "${snapshots}" == "0" ]]; then
      warn "${provider} snapshot 0건: provider reconciliation 공백"
      continue
    fi
    if [[ -z "${lag_minutes}" ]]; then
      warn "${provider} snapshot 최신 시각 계산 실패"
      continue
    fi

    if awk "BEGIN { exit !(${lag_minutes} <= ${LLM_SNAPSHOT_MAX_LAG_MINUTES}) }"; then
      pass "${provider} snapshot freshness 정상(lag=${lag_minutes}m, latest=${last_snapshot_at})"
    else
      warn "${provider} snapshot stale(lag=${lag_minutes}m > ${LLM_SNAPSHOT_MAX_LAG_MINUTES}m, latest=${last_snapshot_at})"
    fi
  done <<< "${rows}"
}

check_ai_decision_inactivity_6h() {
  info "T+6h: AI decision inactivity 점검 (${AI_DECISION_INACTIVITY_HOURS}h)"

  local decision_count
  decision_count="$(
    docker exec -u postgres coinpilot-db psql -d coinpilot -At -c "
    SELECT COUNT(*)
    FROM agent_decisions
    WHERE created_at >= now() - interval '${AI_DECISION_INACTIVITY_HOURS} hours';
    " 2>/dev/null || true
  )"
  decision_count="${decision_count//[[:space:]]/}"

  if [[ -z "${decision_count}" ]]; then
    warn "AI decision inactivity 조회 실패"
    return
  fi

  if (( decision_count > 0 )); then
    pass "최근 ${AI_DECISION_INACTIVITY_HOURS}h agent_decisions 존재: ${decision_count}건"
    return
  fi

  # 신규 의사결정이 0건이면 bot 장애와 시장 한산을 구분해야 한다.
  # bot 컨테이너가 Up이면 즉시 FAIL보다 WARN으로 두고, 추가 원인 분석(시장/가드레일/데이터)을 유도한다.
  local ps_output
  if ! ps_output="$(run_compose ps bot 2>&1)"; then
    fail "bot 상태 조회 실패: ${ps_output}"
    return
  fi

  if grep -E "coinpilot-bot.*(Up|running|healthy)" <<<"${ps_output}" >/dev/null 2>&1; then
    warn "최근 ${AI_DECISION_INACTIVITY_HOURS}h agent_decisions 0건(bot은 Up, 시장/가드레일/입력 공백 확인 필요)"
  else
    fail "최근 ${AI_DECISION_INACTIVITY_HOURS}h agent_decisions 0건이며 bot도 Up 상태가 아님"
  fi
}

check_log_heartbeat_minutes() {
  local pattern="$1"
  local label="$2"
  local max_age_minutes="$3"

  local latest
  latest="$(ls -1t ${pattern} 2>/dev/null | head -n 1 || true)"
  if [[ -z "${latest}" ]]; then
    warn "${label} heartbeat 로그 없음 (${pattern})"
    return
  fi

  local now_ts file_ts age_minutes
  now_ts="$(date +%s)"
  file_ts="$(stat -c %Y "${latest}" 2>/dev/null || true)"
  if [[ -z "${file_ts}" ]]; then
    warn "${label} heartbeat timestamp 조회 실패: ${latest}"
    return
  fi

  age_minutes="$(( (now_ts - file_ts) / 60 ))"
  if (( age_minutes <= max_age_minutes )); then
    pass "${label} heartbeat 정상(${age_minutes}m 전): ${latest}"
  else
    warn "${label} heartbeat stale(${age_minutes}m > ${max_age_minutes}m): ${latest}"
  fi
}

check_cron_heartbeat_24h() {
  info "T+24h: scheduled monitoring heartbeat 점검"

  # cron heartbeat는 '파일이 최근 주기 안에 갱신됐는가'만 보는 얕은 점검이다.
  # 내용 파싱까지 하면 경로/형식 변경에 취약해지므로, 먼저 로그 갱신 시각만 기준으로 공백을 찾는다.
  check_log_heartbeat_minutes "${OPS_LOG_ROOT}/monitoring-t1h-*.log" "monitoring-t1h" 130
  check_log_heartbeat_minutes "${OPS_LOG_ROOT}/monitoring-t6h-*.log" "monitoring-t6h" 420
  check_log_heartbeat_minutes "${OPS_LOG_ROOT}/monitoring-t12h-*.log" "monitoring-t12h" 780
  check_log_heartbeat_minutes "${OPS_LOG_ROOT}/monitoring-t24h-*.log" "monitoring-t24h" 1560
  check_log_heartbeat_minutes "${OPS_LOG_ROOT}/ai-canary-24h-*.log" "ai-canary-24h" 1560
  check_log_heartbeat_minutes "${OPS_LOG_ROOT}/llm-usage-24h-*.log" "llm-usage-24h" 1560
}

run_t0() {
  check_compose_services_up
  check_bot_critical_logs "10m"
}

run_t1h() {
  check_prometheus_up
  check_prometheus_infra_targets_up
  check_prometheus_container_display_map
  check_loki_log_pipeline
  check_manual_alert_routing_notice
}

run_t6h() {
  check_ai_risk_flow_logs "6h"
  check_ai_decision_inactivity_6h
}

run_t12h() {
  check_batch_jobs_12h "12h"
}

run_t24h() {
  check_backups_24h
  check_llm_snapshot_freshness_24h
  check_cron_heartbeat_24h
}

main() {
  parse_args "$@"
  setup_output_redirection

  info "automation_mode=${AUTOMATION_MODE}"
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
