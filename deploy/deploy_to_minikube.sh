#!/bin/bash
set -e

echo "[*] Configuring Docker environment for Minikube..."
eval $(./minikube -p minikube docker-env)

echo "[*] Building Docker images inside Minikube..."
docker-compose -f deploy/docker-compose.yml build

echo "[*] Applying Kubernetes Manifests..."

# Base
echo "[-] Applying Base..."
./minikube kubectl -- apply -f k8s/base/namespace.yaml
./minikube kubectl -- apply -f k8s/base/secret.yaml
./minikube kubectl -- apply -f k8s/base/configmap.yaml

# DB
echo "[-] Applying DB..."
./minikube kubectl -- apply -f k8s/db/init-sql-configmap.yaml
./minikube kubectl -- apply -f k8s/db/postgres-statefulset.yaml
./minikube kubectl -- apply -f k8s/db/redis-statefulset.yaml

# Wait for DB to be ready (Optional, but good practice)
# echo "[-] Waiting for DB..."
# ./minikube kubectl -- -n coin-pilot-ns rollout status statefulset/db

# Apps
echo "[-] Applying Apps..."
./minikube kubectl -- apply -f k8s/apps/collector-deployment.yaml
./minikube kubectl -- apply -f k8s/apps/bot-deployment.yaml
./minikube kubectl -- apply -f k8s/apps/dashboard-deployment.yaml

# Monitoring
echo "[-] Applying Monitoring..."
./minikube kubectl -- apply -f k8s/monitoring/prometheus.yaml
./minikube kubectl -- apply -f k8s/monitoring/grafana.yaml

echo "[*] Deployment Complete!"
echo "[*] Use './minikube dashboard' or './minikube service list -n coin-pilot-ns' to check services."
