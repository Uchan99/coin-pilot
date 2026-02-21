#!/usr/bin/env bash
set -euo pipefail

# 운영 정책: 일간 7일 + 주간 4주 보관
# 주간 백업은 일요일(7)에 일간 백업을 추가 보관하는 방식으로 구현한다.

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/coinpilot/postgres}"
CONTAINER_NAME="${DB_CONTAINER_NAME:-coinpilot-db}"
POSTGRES_DB="${POSTGRES_DB:-coinpilot}"
TIMESTAMP="$(date +'%Y%m%d_%H%M%S')"
DOW="$(date +'%u')"
DAILY_DIR="${BACKUP_ROOT}/daily"
WEEKLY_DIR="${BACKUP_ROOT}/weekly"

mkdir -p "${DAILY_DIR}" "${WEEKLY_DIR}"

DAILY_FILE="${DAILY_DIR}/coinpilot_${TIMESTAMP}.sql.gz"
WEEKLY_FILE="${WEEKLY_DIR}/coinpilot_weekly_${TIMESTAMP}.sql.gz"

# 컨테이너 내부의 POSTGRES_PASSWORD를 그대로 사용해 인증 실패를 줄인다.
docker exec "${CONTAINER_NAME}" sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -U postgres -d "$POSTGRES_DB"' | gzip > "${DAILY_FILE}"
sha256sum "${DAILY_FILE}" > "${DAILY_FILE}.sha256"

if [[ "${DOW}" == "7" ]]; then
  cp "${DAILY_FILE}" "${WEEKLY_FILE}"
  sha256sum "${WEEKLY_FILE}" > "${WEEKLY_FILE}.sha256"
fi

# mtime +7 은 8일 이상 지난 파일을 의미한다.
find "${DAILY_DIR}" -type f -name 'coinpilot_*.sql.gz*' -mtime +7 -delete
find "${WEEKLY_DIR}" -type f -name 'coinpilot_weekly_*.sql.gz*' -mtime +28 -delete

echo "[OK] Postgres backup created: ${DAILY_FILE}"
