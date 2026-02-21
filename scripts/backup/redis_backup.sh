#!/usr/bin/env bash
set -euo pipefail

# 운영 정책: 일간 7일 + 주간 4주 보관
# Redis는 RDB/AOF 파일이 /data에 공존할 수 있어, /data 전체를 tar.gz로 보관한다.

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/coinpilot/redis}"
CONTAINER_NAME="${REDIS_CONTAINER_NAME:-coinpilot-redis}"
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
DOW="$(date +'%u')"
DAILY_DIR="${BACKUP_ROOT}/daily"
WEEKLY_DIR="${BACKUP_ROOT}/weekly"

mkdir -p "${DAILY_DIR}" "${WEEKLY_DIR}"

DAILY_FILE="${DAILY_DIR}/coinpilot_redis_${TIMESTAMP}.tar.gz"
WEEKLY_FILE="${WEEKLY_DIR}/coinpilot_redis_weekly_${TIMESTAMP}.tar.gz"

# BGSAVE를 먼저 요청해 최신 스냅샷 반영을 유도한다.
docker exec "${CONTAINER_NAME}" redis-cli BGSAVE >/dev/null || true
sleep 2

# /data 전체 보관으로 Redis 버전별 AOF 디렉터리 구조 차이를 흡수한다.
docker exec "${CONTAINER_NAME}" sh -c 'tar -czf /tmp/redis-backup.tar.gz -C /data .'
docker cp "${CONTAINER_NAME}:/tmp/redis-backup.tar.gz" "${DAILY_FILE}"
docker exec "${CONTAINER_NAME}" rm -f /tmp/redis-backup.tar.gz

sha256sum "${DAILY_FILE}" > "${DAILY_FILE}.sha256"

if [[ "${DOW}" == "7" ]]; then
  cp "${DAILY_FILE}" "${WEEKLY_FILE}"
  sha256sum "${WEEKLY_FILE}" > "${WEEKLY_FILE}.sha256"
fi

find "${DAILY_DIR}" -type f -name 'coinpilot_redis_*.tar.gz*' -mtime +7 -delete
find "${WEEKLY_DIR}" -type f -name 'coinpilot_redis_weekly_*.tar.gz*' -mtime +28 -delete

echo "[OK] Redis backup created: ${DAILY_FILE}"
