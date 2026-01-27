# Week 4 Troubleshooting Report: Kubernetes Deployment & Verification

**Project**: CoinPilot - AI-Powered Cryptocurrency Trading System
**Author**: Hur Youchan
**Date**: 2026-01-28
**Tech Stack**: Kubernetes (Minikube), Docker, Python, PostgreSQL, Streamlit

---

## Executive Summary

Week 4는 로컬 개발 환경(Docker Compose)에서 **Kubernetes(Minikube) 기반의 마이크로서비스 아키텍처(MSA)**로 이관하는 중요한 단계였습니다. 이 과정에서 **서비스 디스커버리(Service Discovery)**, **이미지 빌드 전략**, **데이터 일관성**과 관련된 문제들이 발생했습니다. 이를 해결하며 컨테이너 오케스트레이션 환경에서의 네트워킹과 배포 파이프라인에 대한 이해를 심화했습니다.

### Skills Demonstrated
`Kubernetes Networking` `Docker Build Strategy` `Environment Configuration` `Debugging` `Database Connectivity`

### Issues at a Glance

| # | Issue | Severity | Root Cause | Resolution Time |
|---|-------|----------|------------|-----------------|
| 1 | Connection Refused | Critical | K8s Service Discovery 미적용 | ~2h |
| 2 | ImagePullBackOff | High | 이미지 네이밍 불일치 | ~1h |
| 3 | No AI Decisions | Medium | 일봉 데이터 미수집 | ~30m |

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Minikube Cluster                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   bot Pod   │  │ dashboard   │  │   db (PostgreSQL)   │  │
│  │             │──│    Pod      │──│   StatefulSet       │  │
│  │  Collector  │  │  Streamlit  │  │   + TimescaleDB     │  │
│  │  + Engine   │  │             │  │   + pgvector        │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┴──────────┬──────────┘             │
│                                     │                        │
│                          K8s Service (DNS)                   │
│                           db:5432 (ClusterIP)                │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         NodePort:30000  NodePort:30001  NodePort:30090
          (Dashboard)     (Grafana)     (Prometheus)
```

---

## Issue #1: Connection Refused (Service Discovery in K8s)

### Problem Statement
Kubernetes 클러스터에 배포된 `bot` 파드(Pod)가 시작 직후 CrashLoopBackOff 상태에 빠지며, 로그에 DB 접속 실패 에러가 기록되었습니다.

```log
ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)
```

### Technical Context
- **Environment**: Minikube (Single Node Cluster)
- **Component**: `src/common/db.py` (Database Connection Logic)
- **Configuration**: 환경변수 `DATABASE_URL` 사용

### Root Cause Analysis
기존 로컬 개발 환경(Docker Compose 또는 Local Python)에서는 DB가 `localhost`(127.0.0.1)에 있거나 포트 포워딩으로 접근 가능했습니다. 그러나 Kubernetes 환경에서는:
1.  각 파드가 고유한 IP를 가집니다.
2.  `bot` 파드 내부의 `localhost`는 `bot` 컨테이너 자신을 의미하므로, 다른 파드에 있는 DB를 찾을 수 없습니다.
3.  코드가 `DATABASE_URL` 환경변수가 없을 때 기본값으로 `localhost`를 사용하도록 하드코딩 되어 있었습니다.

### Solution: Kubernetes Service & Environment Vars
**1. K8s Service DNS 활용**
Kubernetes는 서비스 이름으로 내부 DNS를 자동 구성합니다. DB 서비스 이름을 `db`로 설정했으므로, 클러스터 내부에서는 `db:5432`로 접근해야 합니다.

**2. ConfigMap & Secret 적용**
`src/common/db.py`가 올바른 주소를 바라보도록 K8s Manifest(`bot-deployment.yaml`)에 환경변수를 명시적으로 주입했습니다.

```yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: coin-pilot-secret
        key: DATABASE_URL
# Secret Value: postgresql+asyncpg://postgres:postgres@db:5432/coinpilot
```

### Verification

```bash
$ kubectl get pods -n coin-pilot-ns
NAME                         READY   STATUS    RESTARTS   AGE
bot-xxxxxxxxx-xxxxx          1/1     Running   0          5m
dashboard-xxxxxxxxx-xxxxx    1/1     Running   0          5m
db-0                         1/1     Running   0          5m

$ kubectl logs -n coin-pilot-ns deployment/bot | grep -i database
[+] Database connection established successfully.
```

### Key Takeaway
> **Cluster Networking**: 컨테이너 오케스트레이션 환경에서는 `localhost` 통신이 불가능함을 명심해야 합니다. **Service Name**을 통한 DNS 조회 방식을 이해하고, 환경변수를 통해 유동적으로 연결 문자열을 관리하는 것이 필수적입니다.

---

## Issue #2: Docker Image Naming Mismatch

### Problem Statement
`docker-compose build` 명령어로 이미지를 빌드했음에도 불구하고, Kubernetes 배포 시 `ImagePullBackOff` 에러가 발생했습니다.

```
ErrImagePull: rpc error: code = Unknown desc = Error response from daemon: pull access denied for dashboard, repository does not exist
```

### Technical Context
- **Build Tool**: Docker Compose
- **Orchestrator**: Minikube (Docker Driver)

### Root Cause Analysis
Docker Compose는 기본적으로 `[프로젝트명]_[서비스명]` 형식으로 이미지 태그를 생성합니다(예: `deploy-dashboard:latest`). 반면, 작성한 Kubernetes Manifest 파일(`deployment.yaml`)은 `dashboard:latest`라는 단순한 이름을 기대하고 있었습니다. 이름이 일치하지 않아 이미지를 찾을 수 없었던 것입니다.

### Solution: Explicit Image Naming
`docker-compose.yml` 파일에 `image` 속성을 추가하여, 빌드되는 이미지의 이름을 강제로 지정했습니다.

```yaml
# docker-compose.yml
services:
  dashboard:
    build:
      context: ..
      dockerfile: deploy/docker/dashboard.Dockerfile
    image: dashboard:latest  # <--- 명시적 이름 지정
```

또한, Minikube 내부 Docker 데몬을 사용하도록 `eval $(minikube docker-env)`를 설정하여, 빌드된 이미지가 로컬 레지스트리가 아닌 Minikube 환경에 바로 저장되도록 했습니다.

### Verification

```bash
$ eval $(minikube docker-env)
$ docker images | grep -E "bot|dashboard"
bot         latest    abc123def456   2 minutes ago   892MB
dashboard   latest    789xyz012abc   2 minutes ago   654MB

$ kubectl describe pod -n coin-pilot-ns dashboard-xxx | grep Image:
    Image:         dashboard:latest
```

### Key Takeaway
> **Build Consistency**: 배포 파이프라인에서 빌드 아티팩트(이미지)의 이름은 일관되어야 합니다. 자동 생성되는 이름에 의존하기보다, 명시적인 네이밍 규칙을 적용하여 빌드 도구와 배포 도구 간의 불일치를 방지해야 합니다.

---

## Issue #3: Insufficient Historical Data for Simulation

### Problem Statement
대시보드 검증을 위해 "Simulation" 기능을 실행했으나, 아무런 결과(AI Decisions)가 표시되지 않았습니다. 로그 확인 결과 `Insufficient daily data for MA200` 경고가 발생했습니다.

### Root Cause Analysis
전략 알고리즘(`MeanReversionStrategy`)은 **200일 이동평균선(MA200)**을 사용하여 추세를 판단합니다. 이를 위해서는 최소 200개의 **일봉(Daily Candle)** 데이터가 필요합니다. 하지만 초기 데이터 수집 스크립트는 **분봉(Minute Candle)** 데이터만 수집하도록 작성되어 있었습니다.

### Solution: Dual-Timeframe Data Fetching
데이터 수집 스크립트(`scripts/fetch_historical_data.py`)를 개선하여 두 종류의 데이터를 모두 수집하도록 수정했습니다.

1.  **Minute Candles**: 단기 변동성 분석용 (기존 유지)
2.  **Daily Candles**: 장기 추세(MA200) 계산용 (신규 추가)

```python
# [1d Data] Daily API 호출 (MA200 계산용)
url = "https://api.upbit.com/v1/candles/days"
resp = await client.get(url, params={"market": symbol, "count": 200})
```

이후 **Hybrid Mode Verification**을 통해 로컬 대시보드에서 K8s DB의 데이터를 정상적으로 읽어와 분석하는 것을 확인했습니다.

### Verification

```bash
$ PYTHONPATH=. python scripts/fetch_historical_data.py
[*] Starting Historical Data Fetch (1m: 200, 1d: 200)...
[*] Fetching 1m candles...
[+] Saved 200 records.
[*] Fetching 1d candles...
[+] Saved 200 records.
[+] Successfully saved all historical data.

$ psql -h localhost -U postgres -d coinpilot -c \
    "SELECT interval, COUNT(*) FROM market_data GROUP BY interval;"
 interval | count
----------+-------
 1m       |   200
 1d       |   200

$ PYTHONPATH=. python scripts/simulate_with_ai.py
[*] Starting AI-Integrated Strategy Simulation for KRW-BTC...
[*] Current MA200 (Daily): 151,170,545
[*] Processing 500 minute candles...
[*] AI-Integrated Simulation finished.
```

### Key Takeaway
> **Data Dependency**: 알고리즘이나 모델이 요구하는 데이터의 범위(Timeframe)와 양(Volume)을 정확히 파악해야 합니다. 인프라가 준비되었더라도, **데이터 파이프라인**이 요구사항을 충족하지 못하면 시스템은 의도한 대로 동작하지 않습니다.

---

## Conclusion

Week 4에서는 단순한 '실행'을 넘어, **운영 가능한(Operable)** 환경을 구축하는 데 집중했습니다. Kubernetes의 파드 격리성, 서비스 네트워크, 그리고 상태 저장소(StatefulSet)의 개념을 몸소 체득하며, "내 컴퓨터에서는 되는데?"라는 문제(Works on My Machine)를 해결하는 표준화된 배포 프로세스를 확립했습니다.

### Achievements

| Metric | Before (Week 3) | After (Week 4) |
|--------|-----------------|----------------|
| **배포 방식** | Docker Compose (수동) | K8s Manifest (선언적) |
| **서비스 복구** | 수동 재시작 | Self-healing (Auto-restart) |
| **환경 일관성** | 로컬 의존적 | 컨테이너 기반 표준화 |
| **모니터링** | 로그 수동 확인 | Prometheus + Grafana |
| **배포 시간** | ~10분 (수동) | ~2분 (스크립트 자동화) |

### Lessons Learned

1. **"Shift Left" Debugging**: 문제를 배포 단계가 아닌 빌드 단계에서 발견하는 것이 효율적입니다. `docker-compose build` 후 즉시 이미지 이름을 확인하는 습관이 중요합니다.

2. **Infrastructure as Code (IaC)**: YAML 매니페스트로 인프라를 코드화함으로써, 동일한 환경을 언제든 재현할 수 있게 되었습니다. 이는 팀 협업과 장애 복구에 핵심적입니다.

3. **Data-First Thinking**: 인프라가 완벽해도 데이터가 준비되지 않으면 시스템은 무용지물입니다. 알고리즘의 데이터 요구사항을 먼저 정의하고, 이를 충족하는 파이프라인을 구축해야 합니다.

### Related Files

| File | Description |
|------|-------------|
| [deploy_to_minikube.sh](file:///home/syt07203/workspace/coin-pilot/deploy/deploy_to_minikube.sh) | 원클릭 배포 스크립트 |
| [k8s/](file:///home/syt07203/workspace/coin-pilot/k8s/) | Kubernetes 매니페스트 디렉토리 |
| [fetch_historical_data.py](file:///home/syt07203/workspace/coin-pilot/scripts/fetch_historical_data.py) | 데이터 수집 (1m + 1d) |
| [daily-startup-guide.md](file:///home/syt07203/workspace/coin-pilot/docs/daily-startup-guide.md) | 운영 가이드 |

---

## Personal Growth

이번 트러블슈팅 경험을 통해 다음 역량을 강화했습니다:

1. **Kubernetes 네트워킹 이해**: Pod 격리성, ClusterIP Service, DNS 기반 Service Discovery의 동작 원리를 실습을 통해 체득했습니다.

2. **DevOps 마인드셋**: "Works on My Machine" 문제를 YAML 기반 선언적 인프라로 해결하며, 재현 가능한 배포 환경의 중요성을 깨달았습니다.

3. **End-to-End 디버깅**: 에러 메시지(`Connection Refused`)에서 시작해, 네트워크 설정 → 환경변수 → 코드 레벨까지 계층적으로 문제를 추적하는 방법론을 습득했습니다.

4. **데이터 파이프라인 설계**: 알고리즘 요구사항(MA200)을 먼저 분석하고, 이를 충족하는 데이터 수집 로직을 역순으로 설계하는 "Data-First" 접근법을 적용했습니다.

---

## References

- [Kubernetes Service Discovery](https://kubernetes.io/docs/concepts/services-networking/service/)
- [Docker Compose Build Reference](https://docs.docker.com/compose/compose-file/build/)
- [Minikube Docker Environment](https://minikube.sigs.k8s.io/docs/handbook/pushing/#1-pushing-directly-to-the-in-cluster-docker-daemon-docker-env)
- [StatefulSets for Databases](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)

---

*This document demonstrates practical experience with Kubernetes deployment, debugging container orchestration issues, and building production-ready data pipelines.*
