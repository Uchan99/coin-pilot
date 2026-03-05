#!/usr/bin/env sh
set -eu

# 목적:
# - OCI 환경에서 cAdvisor 라벨/시계열이 불안정할 때도
#   컨테이너별 서비스명/CPU/메모리/재시작 지표를 안정적으로 수집한다.
# - 수집 결과를 node-exporter textfile collector로 노출해 Grafana가 직접 사용한다.
#
# 설계 포인트:
# 1) docker ps(실행 중 컨테이너)로 기준 집합을 만든다.
# 2) docker stats --no-stream으로 실시간 CPU/메모리 값을 가져온다.
# 3) docker inspect로 restart_count/running 상태를 보강한다.
# 4) 매 주기마다 .prom 파일을 원자적으로 교체한다.

OUT_DIR="${OUT_DIR:-/textfile}"
OUT_FILE="${OUT_FILE:-${OUT_DIR}/coinpilot_container_display_map.prom}"
MAP_INTERVAL_SEC="${MAP_INTERVAL_SEC:-30}"
TMP_STATE_DIR="${TMP_STATE_DIR:-/tmp/coinpilot_container_map}"

mkdir -p "${OUT_DIR}" "${TMP_STATE_DIR}"

# 메모리 문자열(예: 56.2MiB)을 byte 정수로 변환.
# 주의:
# - 운영 컨테이너(docker:cli)에서는 busybox awk를 쓰는 경우가 있어
#   gawk 전용 문법(match(..., arr))을 피하고 POSIX 호환 방식으로 파싱한다.
# - docker stats 단위는 KiB/MiB/GiB 또는 KB/MB/GB가 섞일 수 있어 둘 다 처리한다.
to_bytes() {
  val="$1"
  printf '%s\n' "${val}" | awk '
    BEGIN { OFS="" }
    {
      gsub(/,/,"",$0)
      gsub(/[[:space:]\r]/,"",$0)
      if ($0 !~ /^[0-9]+([.][0-9]+)?[A-Za-z]+$/) { print 0; next }

      v = $0
      sub(/[A-Za-z]+$/, "", v)
      v = v + 0

      u = $0
      sub(/^[0-9]+([.][0-9]+)?/, "", u)

      if (u == "B") mult = 1
      else if (u == "KB") mult = 1000
      else if (u == "MB") mult = 1000*1000
      else if (u == "GB") mult = 1000*1000*1000
      else if (u == "TB") mult = 1000*1000*1000*1000
      else if (u == "KiB") mult = 1024
      else if (u == "MiB") mult = 1024*1024
      else if (u == "GiB") mult = 1024*1024*1024
      else if (u == "TiB") mult = 1024*1024*1024*1024
      else mult = 1
      printf "%.0f\n", v * mult
    }
  '
}

while true; do
  map_file="${TMP_STATE_DIR}/container_map.tsv"
  stats_file="${TMP_STATE_DIR}/container_stats.tsv"
  inspect_file="${TMP_STATE_DIR}/container_inspect.tsv"
  tmp_file="${OUT_FILE}.$$"

  # 실행 중 컨테이너만 대상으로 수집해, 과거 중지 컨테이너 노이즈를 제거한다.
  docker ps --format '{{.ID}}|{{.Names}}' > "${map_file}" || true

  # docker stats는 실행 중 컨테이너에 한해 CPU/메모리를 즉시 제공한다.
  docker stats --no-stream --format '{{.ID}}|{{.CPUPerc}}|{{.MemUsage}}' > "${stats_file}" || true

  container_ids="$(cut -d'|' -f1 "${map_file}" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  if [ -n "${container_ids}" ]; then
    # restart_count는 운영 중 누적 증가치를 보여주므로 24h 변화량 패널에 활용 가능하다.
    docker inspect --format '{{.Id}}|{{.RestartCount}}|{{.State.Running}}' ${container_ids} > "${inspect_file}" || true
  else
    : > "${inspect_file}"
  fi

  {
    echo "# HELP coinpilot_container_display_info Static mapping from container short id to container display name."
    echo "# TYPE coinpilot_container_display_info gauge"
    echo "# HELP coinpilot_container_cpu_percent Instant CPU usage percent from docker stats."
    echo "# TYPE coinpilot_container_cpu_percent gauge"
    echo "# HELP coinpilot_container_memory_working_set_bytes Instant memory usage bytes from docker stats."
    echo "# TYPE coinpilot_container_memory_working_set_bytes gauge"
    echo "# HELP coinpilot_container_restart_count Restart count from docker inspect."
    echo "# TYPE coinpilot_container_restart_count gauge"
    echo "# HELP coinpilot_container_running Running state from docker inspect (1=true,0=false)."
    echo "# TYPE coinpilot_container_running gauge"

    while IFS='|' read -r full_id display_name; do
      if [ -z "${full_id}" ] || [ -z "${display_name}" ]; then
        continue
      fi

      cid="$(printf '%s' "${full_id}" | cut -c1-12)"
      esc_display="$(printf '%s' "${display_name}" | sed 's/\\/\\\\/g; s/"/\\"/g')"

      # 매핑 메트릭(조인 키)
      printf 'coinpilot_container_display_info{cid="%s",display="%s"} 1\n' "${cid}" "${esc_display}"

      # CPU/메모리 메트릭: stats 행이 없으면 0으로 기록해 시계열 끊김을 줄인다.
      stats_line="$(awk -F'|' -v id="${cid}" '$1==id || index($1,id)==1 { print; exit }' "${stats_file}" 2>/dev/null || true)"
      if [ -n "${stats_line}" ]; then
        cpu_raw="$(printf '%s' "${stats_line}" | cut -d'|' -f2 | tr -d '%' | tr -d ' ')"
        mem_raw_full="$(printf '%s' "${stats_line}" | cut -d'|' -f3)"
        mem_used="$(printf '%s' "${mem_raw_full}" | awk -F'/' '{gsub(/ /,"",$1); print $1}')"
        mem_bytes="$(to_bytes "${mem_used}")"
      else
        cpu_raw="0"
        mem_bytes="0"
      fi
      printf 'coinpilot_container_cpu_percent{cid="%s",display="%s"} %s\n' "${cid}" "${esc_display}" "${cpu_raw:-0}"
      printf 'coinpilot_container_memory_working_set_bytes{cid="%s",display="%s"} %s\n' "${cid}" "${esc_display}" "${mem_bytes:-0}"

      # restart/running 메트릭
      inspect_line="$(awk -F'|' -v id="${full_id}" '$1==id || index($1,id)==1 { print; exit }' "${inspect_file}" 2>/dev/null || true)"
      if [ -n "${inspect_line}" ]; then
        restart_count="$(printf '%s' "${inspect_line}" | cut -d'|' -f2)"
        running_raw="$(printf '%s' "${inspect_line}" | cut -d'|' -f3)"
      else
        restart_count="0"
        running_raw="false"
      fi
      if [ "${running_raw}" = "true" ]; then
        running_val="1"
      else
        running_val="0"
      fi
      printf 'coinpilot_container_restart_count{cid="%s",display="%s"} %s\n' "${cid}" "${esc_display}" "${restart_count:-0}"
      printf 'coinpilot_container_running{cid="%s",display="%s"} %s\n' "${cid}" "${esc_display}" "${running_val}"
    done < "${map_file}"
  } > "${tmp_file}"

  mv "${tmp_file}" "${OUT_FILE}"
  sleep "${MAP_INTERVAL_SEC}"
done
