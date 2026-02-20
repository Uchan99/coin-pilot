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
