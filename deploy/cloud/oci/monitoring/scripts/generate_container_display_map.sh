#!/usr/bin/env sh
set -eu

# 목적:
# - cAdvisor 라벨(name/container_label_*)이 비어 있는 환경에서도
#   Grafana에서 컨테이너 ID를 서비스명으로 해석할 수 있도록
#   docker ps 결과를 Prometheus textfile 메트릭으로 주기적으로 내보낸다.
#
# 핵심 불변조건:
# - metric 라벨 cid는 항상 12자리 short id를 사용한다(대시보드 fallback과 동일 기준).
# - metric 값은 1(gauge) 고정이며, 시계열 존재 여부/라벨 조인에만 사용한다.

OUT_DIR="${OUT_DIR:-/textfile}"
OUT_FILE="${OUT_FILE:-${OUT_DIR}/coinpilot_container_display_map.prom}"
MAP_INTERVAL_SEC="${MAP_INTERVAL_SEC:-30}"

mkdir -p "${OUT_DIR}"

while true; do
  # 원자적 교체를 위해 임시 파일에 완성본을 쓰고 마지막에 mv 한다.
  tmp_file="${OUT_FILE}.$$"
  {
    echo "# HELP coinpilot_container_display_info Static mapping from container short id to container display name."
    echo "# TYPE coinpilot_container_display_info gauge"

    docker ps -a --format '{{.ID}} {{.Names}}' | while IFS=' ' read -r full_id display_name; do
      # docker ps 출력 이상/빈 행 방어: cid 또는 name이 비면 해당 행은 스킵한다.
      if [ -z "${full_id}" ] || [ -z "${display_name}" ]; then
        continue
      fi

      cid="$(printf '%s' "${full_id}" | cut -c1-12)"
      esc_display="$(printf '%s' "${display_name}" | sed 's/\\/\\\\/g; s/"/\\"/g')"
      printf 'coinpilot_container_display_info{cid="%s",display="%s"} 1\n' "${cid}" "${esc_display}"
    done
  } > "${tmp_file}"

  mv "${tmp_file}" "${OUT_FILE}"
  sleep "${MAP_INTERVAL_SEC}"
done
