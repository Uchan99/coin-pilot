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
# ./minikube kubectl -- apply -f k8s/base/secret.yaml
# Dynamic Secret Creation from .env
if [ -f .env ]; then
  echo "[-] Creating Secret from .env..."
  # Load .env variables
  set -a
  source .env
  set +a
  
  # Check if keys exist
  if [ -z "$ANTHROPIC_API_KEY" ] || [ -z "$OPENAI_API_KEY" ]; then
    echo "[!] Warning: API Keys missing in .env"
  fi

  # Create secret using envsubst to replace placeholders in a temp file
  # Note: This requires gettext-base package for envsubst, or we can use sed for simplicity.
  # Let's use a simpler approach: kubectl create secret generic --from-literal
  
  # Delete existing secret first to allow update
  ./minikube kubectl -- delete secret coin-pilot-secret -n coin-pilot-ns --ignore-not-found
  
  ./minikube kubectl -- create secret generic coin-pilot-secret -n coin-pilot-ns \
    --from-literal=ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    --from-literal=OPENAI_API_KEY="$OPENAI_API_KEY" \
    --from-literal=UPBIT_ACCESS_KEY="$UPBIT_ACCESS_KEY" \
    --from-literal=UPBIT_SECRET_KEY="$UPBIT_SECRET_KEY" \
    --from-literal=DB_PASSWORD="$DB_PASSWORD" \
    --from-literal=REDIS_URL="redis://redis:6379/0" \
    --from-literal=N8N_WEBHOOK_SECRET="${N8N_WEBHOOK_SECRET:-coinpilot-n8n-secret}" \
    --from-literal=DISCORD_WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"
    
else
  echo "[!] .env file not found! Skipping Secret creation."
fi

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
./minikube kubectl -- apply -f k8s/apps/n8n-deployment.yaml

# Monitoring
echo "[-] Applying Monitoring ConfigMaps..."
./minikube kubectl -- apply -f k8s/monitoring/prometheus-config-cm.yaml
./minikube kubectl -- apply -f k8s/monitoring/grafana-datasources-cm.yaml
./minikube kubectl -- apply -f k8s/monitoring/grafana-dashboards-cm.yaml

echo "[-] Applying Monitoring Apps..."
./minikube kubectl -- apply -f k8s/monitoring/prometheus.yaml
./minikube kubectl -- apply -f k8s/monitoring/grafana.yaml

# Jobs (Backfill) - Optional, run with --backfill flag
if [[ "$*" == *"--backfill"* ]]; then
  echo "[-] Applying Backfill Job for Regime Detection..."
  # Delete existing job first (job names are immutable)
  ./minikube kubectl -- delete job backfill-regime -n coin-pilot-ns --ignore-not-found
  # Wait for DB to be ready before running backfill
  echo "[-] Waiting for DB to be ready..."
  ./minikube kubectl -- -n coin-pilot-ns wait --for=condition=ready pod -l app=db --timeout=120s || true
  # Apply backfill job
  ./minikube kubectl -- apply -f k8s/jobs/backfill-regime-job.yaml
  echo "[*] Backfill job started. Check progress with:"
  echo "    ./minikube kubectl -- logs -f job/backfill-regime -n coin-pilot-ns"
fi

echo "[*] Deployment Complete!"
echo "[*] Use './minikube dashboard' or './minikube service list -n coin-pilot-ns' to check services."
echo ""
echo "[TIP] To run backfill for regime detection (first deploy only):"
echo "    ./deploy/deploy_to_minikube.sh --backfill"
