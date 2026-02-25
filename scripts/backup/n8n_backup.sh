#!/usr/bin/env bash
set -euo pipefail

# 운영 정책: 일간 7일 + 주간 4주 보관
# n8n은 SQLite + binaryData를 volume에 저장하므로 volume 전체를 tar.gz로 보관한다.

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/coinpilot/n8n}"
CONTAINER_NAME="${N8N_CONTAINER_NAME:-coinpilot-n8n}"
VOLUME_NAME="${N8N_VOLUME_NAME:-}"
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
DOW="$(date +'%u')"
DAILY_DIR="${BACKUP_ROOT}/daily"
WEEKLY_DIR="${BACKUP_ROOT}/weekly"

mkdir -p "${DAILY_DIR}" "${WEEKLY_DIR}"

if [[ -z "${VOLUME_NAME}" ]]; then
  # N8N_VOLUME_NAME을 강제하지 않은 경우, 현재 실행 중인 n8n 컨테이너 mount를 조회한다.
  VOLUME_NAME="$(
    docker inspect "${CONTAINER_NAME}" \
      --format '{{ range .Mounts }}{{ if eq .Destination "/home/node/.n8n" }}{{ .Name }}{{ end }}{{ end }}'
  )"
fi

if [[ -z "${VOLUME_NAME}" ]]; then
  echo "[ERROR] could not resolve n8n volume name. set N8N_VOLUME_NAME or check container ${CONTAINER_NAME}" >&2
  exit 1
fi

DAILY_FILE="${DAILY_DIR}/coinpilot_n8n_${TIMESTAMP}.tar.gz"
WEEKLY_FILE="${WEEKLY_DIR}/coinpilot_n8n_weekly_${TIMESTAMP}.tar.gz"

# 실행 중 SQLite는 WAL/SHM 파일을 함께 백업해야 복구 정합성이 높다.
# volume 전체를 압축해 workflow/credential/execution 메타까지 같이 보존한다.
docker run --rm \
  -v "${VOLUME_NAME}:/v:ro" \
  -v "${DAILY_DIR}:/out" \
  alpine sh -c "tar -czf /out/coinpilot_n8n_${TIMESTAMP}.tar.gz -C /v ."

sha256sum "${DAILY_FILE}" > "${DAILY_FILE}.sha256"

if [[ "${DOW}" == "7" ]]; then
  cp "${DAILY_FILE}" "${WEEKLY_FILE}"
  sha256sum "${WEEKLY_FILE}" > "${WEEKLY_FILE}.sha256"
fi

find "${DAILY_DIR}" -type f -name 'coinpilot_n8n_*.tar.gz*' -mtime +7 -delete
find "${WEEKLY_DIR}" -type f -name 'coinpilot_n8n_weekly_*.tar.gz*' -mtime +28 -delete

echo "[OK] n8n backup created: ${DAILY_FILE} (volume=${VOLUME_NAME})"
