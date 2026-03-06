#!/bin/sh
set -eu

# Promtail이 docker API를 직접 호출하지 않고 파일 경로만 읽도록
# coinpilot-* 컨테이너 로그 경로를 symlink 타깃 목록으로 생성한다.
# (Docker API 최소 버전 불일치 환경 대응)

OUT_DIR="${PROMTAIL_TARGET_DIR:-/targets/logs}"
INTERVAL_SEC="${PROMTAIL_TARGET_INTERVAL_SEC:-30}"

mkdir -p "${OUT_DIR}"

while true; do
  # 이전 타깃 제거 후 최신 컨테이너 목록으로 재생성한다.
  find "${OUT_DIR}" -mindepth 1 -maxdepth 1 -type l -delete 2>/dev/null || true

  docker ps -a --format '{{.ID}} {{.Names}}' | while read -r cid cname; do
    case "${cname}" in
      coinpilot-*)
        full_id="$(docker inspect --format '{{.Id}}' "${cid}" 2>/dev/null || true)"
        if [ -z "${full_id}" ]; then
          continue
        fi

        log_path="/var/lib/docker/containers/${full_id}/${full_id}-json.log"
        if [ ! -f "${log_path}" ]; then
          continue
        fi

        ln -sf "${log_path}" "${OUT_DIR}/${cname}.log"
        ;;
    esac
  done

  sleep "${INTERVAL_SEC}"
done

