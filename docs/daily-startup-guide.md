# CoinPilot Daily Startup Guide 🚀

**작성일**: 2026-01-27 (Updated for Week 4 K8s)
**목적**: 컴퓨터 부팅 후 개발/운영 환경을 빠르게 세팅하기 위한 체크리스트

---

## 🛤️ 실행 모드 선택 (Choose Your Mode)

| 모드 | 설명 | 추천 상황 |
| :--- | :--- | :--- |
| **Mode A: Kubernetes (K8s)** | **[권장]** 전체 시스템(Bot, DB, Web)을 Minikube 클러스터에 배포 | **실제 운영 리허설**, 24/7 자동매매 |
| **Mode B: Hybrid (K8s DB + Local App)** | K8s의 DB를 사용하되, **대시보드(Streamlit)**는 로컬에서 실행 | **Test 브랜치 대시보드 개발**, UI 수정 |
| **Mode C: Docker Compose** | 기존 방식의 로컬 컨테이너 실행 | 간단한 DB/Redis 실행 필요 시 (Legacy) |

---

## 1. ☸️ Mode A: Kubernetes 실행 (Main)
시스템 전체를 쿠버네티스 위에서 돌립니다.

### 1.1 Minikube 시작
```bash
# Minikube 클러스터 시작 (Docker 드라이버 사용)
minikube start --driver=docker --cpus 4 --memory 8192
```

### 1.2 배포 스크립트 실행
자동으로 이미지를 빌드하고 K8s 매니페스트를 적용합니다.
```bash
# 프로젝트 루트에서 실행
./deploy/deploy_to_minikube.sh
```

### 1.3 상태 확인
모든 파드(Pod)가 `Running` 상태인지 확인합니다.
```bash
# 상태 모니터링 (watch 모드)
watch kubectl get pods -n coin-pilot-ns
```

### 1.4 접속 주소
- **Dashboard**: [http://localhost:30000](http://localhost:30000)
- **Grafana**: [http://localhost:30001](http://localhost:30001) (ID/PW: admin/admin)
- **Prometheus**: [http://localhost:30090](http://localhost:30090)

---

## 2. 🧪 Mode B: Hybrid (Local Dashboard + K8s DB)
**"대시보드 코드는 Test 브랜치에, DB는 K8s에 있을 때"** 사용하는 방법입니다.

### 2.1 K8s 포트 포워딩 (Port Forwarding)
로컬(Host)에서 K8s 내부 DB에 접속할 수 있도록 길을 뚫어줍니다.
**터미널 탭을 하나 열어서** 다음 명령어를 실행하고 유지하세요.
```bash
# DB & Redis 포트 포워딩 (종료하지 말고 켜두세요!)
kubectl port-forward -n coin-pilot-ns service/db 5432:5432 & \
kubectl port-forward -n coin-pilot-ns service/redis 6379:6379
```

### 2.2 로컬 대시보드 실행
새로운 터미널 탭에서 실행합니다.
```bash
# 1. 가상환경 활성화
source .venv/bin/activate

# 2. 필수 환경변수 확인 (.env)
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/coinpilot

# 3. Streamlit 실행
PYTHONPATH=. .venv/bin/streamlit run src/dashboard/app.py
```
* 접속: [http://localhost:8501](http://localhost:8501) (포트 30000이 아님)

---

## 3. 🐳 Mode C: Docker Compose (Legacy)
K8s 없이 예전 방식으로 실행하고 싶을 때 사용합니다.

### 3.1 컨테이너 실행
```bash
docker-compose -f deploy/docker-compose.yml up -d
```

### 3.2 로컬 스크립트 실행
```bash
# 수집기 (Collector)
PYTHONPATH=. .venv/bin/python src/collector/main.py

# 대시보드 (Dashboard)
PYTHONPATH=. .venv/bin/streamlit run src/dashboard/app.py
```

---

## 4. 🛑 작업 종료 (Shutdown)

### Kubernetes (Minikube) 종료
```bash
# 클러스터 중지 (데이터 유지)
minikube stop

# (선택) 클러스터 삭제 (데이터 초기화됨!)
# minikube delete
```

### Docker Compose 종료
```bash
docker-compose -f deploy/docker-compose.yml stop
```
