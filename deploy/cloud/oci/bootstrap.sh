#!/usr/bin/env bash
set -euo pipefail

# 이 스크립트는 Ubuntu 기반 OCI VM에서 CoinPilot 실행 최소 환경을 준비한다.
# 운영 중인 시스템을 과도하게 변경하지 않도록, 설치 대상은 docker/compose/git/기본 유틸로 제한한다.

if [[ "${EUID}" -ne 0 ]]; then
  echo "[ERROR] root 권한으로 실행해야 합니다. (sudo 사용)"
  exit 1
fi

TARGET_USER="${SUDO_USER:-ubuntu}"
PROJECT_ROOT="/opt/coin-pilot"

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  git \
  jq \
  unzip \
  gnupg \
  lsb-release

if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update
  apt-get install -y --no-install-recommends \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin
fi

usermod -aG docker "$TARGET_USER"

mkdir -p "$PROJECT_ROOT"
chown -R "$TARGET_USER":"$TARGET_USER" "$PROJECT_ROOT"

cat <<'EOM'
[OK] Bootstrap 완료
다음 단계:
1) sudo -iu <user> 로 재로그인(또는 SSH 재접속) 후 docker 그룹 권한 반영
2) git clone <repo> /opt/coin-pilot
3) cp /opt/coin-pilot/deploy/cloud/oci/.env.example /opt/coin-pilot/deploy/cloud/oci/.env
4) chmod 600 /opt/coin-pilot/deploy/cloud/oci/.env
5) cd /opt/coin-pilot/deploy/cloud/oci && docker compose -f docker-compose.prod.yml up -d --build
EOM
