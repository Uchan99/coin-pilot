#!/usr/bin/env bash
set -euo pipefail

# 한국어 안내:
# - minikube CLI가 없어도 동작하도록 docker exec 기반 load를 사용합니다.
# - bot:latest + dashboard:latest 단일 태그를 빌드/노드 로드/롤아웃까지 일괄 수행합니다.

NS="coin-pilot-ns"
BOT_DEPLOYMENT="bot"
DASHBOARD_DEPLOYMENT="dashboard"
COMPOSE_FILE="deploy/docker-compose.yml"
MINIKUBE_CONTAINER="minikube"
COMPOSE_CMD=""
TMP_DOCKER_CONFIG=""

cleanup_tmp_docker_config() {
  if [[ -n "${TMP_DOCKER_CONFIG}" && -d "${TMP_DOCKER_CONFIG}" ]]; then
    rm -rf "${TMP_DOCKER_CONFIG}"
  fi
}

configure_docker_creds_fallback() {
  local user_docker_config="${HOME}/.docker/config.json"

  # 의도:
  # - WSL/Linux에서 Docker Desktop helper(desktop.exe) 호출이 불안정할 때
  #   공용 이미지 pull조차 credential helper 오류로 실패하는 케이스를 우회합니다.
  # 불변조건:
  # - 사용자가 명시적으로 DOCKER_CONFIG를 지정했다면 절대 덮어쓰지 않습니다.
  # - 사용자가 COINPILOT_KEEP_DOCKER_CREDS=1을 설정하면 fallback을 비활성화합니다.
  # 실패/엣지 케이스:
  # - private registry 인증이 필요한 환경에서는 최소 config(auths 비어있음)로 pull 실패 가능성이 있어
  #   이 경우 사용자가 DOCKER_CONFIG 또는 COINPILOT_KEEP_DOCKER_CREDS로 원래 동작을 강제해야 합니다.
  if [[ -n "${COINPILOT_KEEP_DOCKER_CREDS:-}" ]]; then
    echo "[INFO] COINPILOT_KEEP_DOCKER_CREDS is set. Skipping Docker credential fallback."
    return
  fi

  if [[ -n "${DOCKER_CONFIG:-}" ]]; then
    return
  fi

  if [[ ! -f "${user_docker_config}" ]]; then
    return
  fi

  if grep -Eq '"credsStore"\s*:\s*"desktop(\.exe)?"' "${user_docker_config}"; then
    TMP_DOCKER_CONFIG="$(mktemp -d /tmp/coinpilot-docker-config.XXXXXX)"
    printf '{\n  "auths": {}\n}\n' > "${TMP_DOCKER_CONFIG}/config.json"
    export DOCKER_CONFIG="${TMP_DOCKER_CONFIG}"
    echo "[INFO] Docker Desktop credsStore detected. Using temporary DOCKER_CONFIG fallback."
  fi
}

trap cleanup_tmp_docker_config EXIT

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] docker command not found"
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "[ERROR] kubectl command not found"
  exit 1
fi

if command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
elif docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
else
  echo "[ERROR] docker-compose or docker compose is required"
  exit 1
fi

configure_docker_creds_fallback

if ! docker ps --format '{{.Names}}' | grep -qx "${MINIKUBE_CONTAINER}"; then
  echo "[ERROR] minikube node container '${MINIKUBE_CONTAINER}' not found"
  echo "        (docker ps로 컨테이너 이름을 확인하세요)"
  exit 1
fi

echo "[1/5] Building bot:latest and dashboard:latest via docker-compose..."
${COMPOSE_CMD} -f "${COMPOSE_FILE}" build bot dashboard

echo "[2/5] Loading images into minikube docker runtime..."
docker save bot:latest | docker exec -i "${MINIKUBE_CONTAINER}" docker load
docker save dashboard:latest | docker exec -i "${MINIKUBE_CONTAINER}" docker load

echo "[3/5] Updating deployment images..."
kubectl set image deployment/${BOT_DEPLOYMENT} ${BOT_DEPLOYMENT}=bot:latest -n "${NS}"
kubectl set image deployment/${DASHBOARD_DEPLOYMENT} ${DASHBOARD_DEPLOYMENT}=dashboard:latest -n "${NS}"

echo "[4/5] Waiting for rollouts..."
kubectl rollout status deployment/${BOT_DEPLOYMENT} -n "${NS}"
kubectl rollout status deployment/${DASHBOARD_DEPLOYMENT} -n "${NS}"

echo "[5/5] Verifying images and pods..."
kubectl get deployment ${BOT_DEPLOYMENT} -n "${NS}" -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl get deployment ${DASHBOARD_DEPLOYMENT} -n "${NS}" -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl get pods -n "${NS}" -l app=${BOT_DEPLOYMENT}
kubectl get pods -n "${NS}" -l app=${DASHBOARD_DEPLOYMENT}

echo "[DONE] bot:latest + dashboard:latest redeploy completed."
