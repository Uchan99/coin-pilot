#!/bin/sh
set -eu

# Promtail이 docker API를 직접 호출하지 않고 파일 경로만 읽도록
# coinpilot-* 컨테이너 로그 경로를 symlink 타깃 목록으로 생성한다.
# (Docker API 최소 버전 불일치 환경 대응)
# 주의: 기존 타깃을 매 주기마다 전부 삭제/재생성하면 promtail tailer가
# "moved/deleted file" 이벤트를 반복으로 받아 offset/재오픈 비용이 커진다.
# 그래서 "변경된 타깃만" 갱신하는 증분 방식으로 유지한다.

OUT_DIR="${PROMTAIL_TARGET_DIR:-/targets/logs}"
INTERVAL_SEC="${PROMTAIL_TARGET_INTERVAL_SEC:-30}"

mkdir -p "${OUT_DIR}"

while true; do
  # 이번 루프에서 확인된 타깃 목록을 임시 파일에 기록해 stale 링크만 정리한다.
  seen_file="$(mktemp)"

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

        link_path="${OUT_DIR}/${cname}.log"
        printf '%s\n' "${link_path}" >> "${seen_file}"

        # 동일 경로를 가리키는 기존 symlink는 건드리지 않아 tailer 재시작을 방지한다.
        if [ -L "${link_path}" ]; then
          current_target="$(readlink "${link_path}" || true)"
          if [ "${current_target}" = "${log_path}" ]; then
            continue
          fi
        fi

        ln -sfn "${log_path}" "${link_path}"
        ;;
    esac
  done

  # 더 이상 운영 대상이 아닌 stale symlink만 제거한다.
  find "${OUT_DIR}" -mindepth 1 -maxdepth 1 -type l | while read -r existing; do
    if ! grep -Fxq "${existing}" "${seen_file}"; then
      rm -f "${existing}"
    fi
  done
  rm -f "${seen_file}"

  sleep "${INTERVAL_SEC}"
done
