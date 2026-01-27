# Week 4 Implementation Plan: Kubernetes Deployment & Architecture Evolution

**작성일**: 2026-01-27
**목표**: 로컬 개발 환경(Docker Compose)을 넘어, **Kubernetes(Minikube)** 환경에서 자율 운영되는 프로덕션 레벨의 인프라 구축.
**상태**: ⚠️ 조건부 승인 반영 (v1.1)

---

## 1. 개요 (Overview)
현재 시스템은 `src/collector`와 `src/dashboard`가 개별적으로 실행되며, 매매 로직은 스크립트(`scripts/`)를 통해 수동 또는 단발성으로만 실행되고 있습니다.
Week 4에서는 시스템을 **24/7 자율 주행** 상태로 전환하기 위해 **자동 매매 봇(Trading Bot)** 서비스를 구현하고, 모든 컴포넌트를 **MSA(Microservices Architecture)** 형태로 K8s에 배포합니다.

---

## 2. 목표 아키텍처 (Target Architecture)

| 서비스 명 | 역할 | 타입 | K8s Resource | 비고 |
| :--- | :--- | :--- | :--- | :--- |
| **Collector** | 1분마다 시세 수집 및 DB 저장 | Daemon | Deployment (1 replica) | Backfill 기능 포함 |
| **Trading Bot** | (New) 매 분마다 시장 상태 분석 및 매매 실행 | Daemon | Deployment (1 replica) | **Real-time Loop** |
| **Dashboard** | 사용자를 위한 Web UI | Web App | Deployment + Service (NodePort) | |
| **PostgreSQL** | 시장 데이터 및 거래 기록 저장 (TimescaleDB) | Stateful | StatefulSet + PVC | Resource Limit 필수 |
| **Redis** | AI 에이전트 메모리 및 캐시 | Stateful | StatefulSet | |
| **Monitoring** | 시스템 상태 감시 | Infra | Prometheus + Grafana | **New** |

---

## 3. 결정된 사항 (Decisions Made)

| 항목 | 결정 | 근거 |
|------|------|------|
| **Bot Loop 방식** | **Simple Infinite Loop** | `while True` + `sleep(60)` 방식. APScheduler 등 복잡성 제거. |
| **Resource Limits** | **필수 적용** | Minikube 로컬 환경 리소스 보호 및 OOM 방지. |
| **비용 승인** | **Dev: ~$1.5/월, Prod: ~$15/월** | Anthropic API 예상 비용 승인 완료. |
| **Secret 관리** | **Git Ignore + Template** | `k8s/base/secret.yaml`은 커밋 제외, `secret.yaml.example` 제공. |

---

## 4. 상세 작업 계획 (Detailed Tasks)

### Phase 0: Prerequisites (선행 작업)
K8s 배포 전 데이터 무결성과 보안 설정을 완료합니다.
- [ ] **DB Migration**: `scripts/add_market_data_constraint.py` 실행하여 UNIQUE 제약 조건 적용.
- [ ] **Data Integrity**: 중복 데이터 정리 확인.
- [ ] **Git Config**: `.gitignore`에 `k8s/base/secret.yaml` 포함 여부 재확인.

### Phase 1: Core Refactoring (Trading Bot Implementation)
실시간 매매를 위한 데몬 서비스를 구현합니다. (백테스팅 로직 아님)
- [ ] **Create `src/bot/main.py`**:
    - **Logic**: Infinite Loop (`while True`).
    - **Step 1**: DB에서 최신 N개(예: 200개) 캔들 조회 (`timestamp < now()` 확정 데이터만 사용).
    - **Step 2**: [Rule Engine] -> [AI Confirm] -> [Execute] 파이프라인 실행.
    - **Step 3**: `time.sleep`을 사용하여 정확히 1분 간격 유지 (`max(0, 60 - elapsed)` 보정).
    - **Shutdown**: `signal` 핸들링으로 Graceful Shutdown 구현.

### Phase 2: Dockerization (Container Packaging)
각 서비스를 독립적인 컨테이너 이미지로 빌드합니다.
- [ ] **Write `Dockerfile`s**:
    - `deploy/docker/collector.Dockerfile`
    - `deploy/docker/bot.Dockerfile`
    - `deploy/docker/dashboard.Dockerfile` (필요 시 `requirements-dashboard.txt` 분리 검토)
- [ ] **Optimization**: Multi-stage build 적용.
- [ ] **Docker Compose Update**: 로컬 통합 테스트용 `docker-compose.yml` 업데이트.

### Phase 3: Kubernetes Manifests (IaC)
안정성과 모니터링을 고려한 Manifest 작성.
- [ ] **Namespace & Config**:
    - `k8s/base/namespace.yaml`
    - `k8s/base/configmap.yaml`
    - `k8s/base/secret.yaml.example` (**Template**)
- [ ] **Data Layer (StatefulSet)**:
    - `k8s/db/postgres-statefulset.yaml` (Resource Limits 포함)
    - `k8s/db/redis-statefulset.yaml`
- [ ] **Application Layer (Deployment)**:
    - `k8s/apps/collector-deployment.yaml`
        - **Probes**: Liveness(Fail 시 재시작), Readiness(DB 연결 확인 전 트래픽 차단).
        - **Resources**: Requests/Limits 설정.
    - `k8s/apps/bot-deployment.yaml`
        - **Probes**: Liveness (`python -c exit(0)` or file check).
    - `k8s/apps/dashboard-deployment.yaml`
        - **Probes**: Liveness (`/_stcore/health` HTTP check).
- [ ] **Monitoring (New)**:
    - `k8s/monitoring/prometheus.yaml` (Optional or Minikube addon)
    - `k8s/monitoring/grafana.yaml`

### Phase 4: Deployment & Verification
- [ ] **Minikube Setup**:
    - `minikube start --cpus 4 --memory 8192` (리소스 확보).
    - `minikube addons enable metrics-server`.
    - `eval $(minikube docker-env)`.
- [ ] **Deploy**: `kubectl apply -f k8s/`.
- [ ] **Verify**:
    - `kubectl get pods` (All Running).
    - **Self-healing Test**: `kubectl delete pod -l app=bot` 후 자동 재생성 확인.
    - **Bot Logic Test**: 로그에서 "Analyzing..." 메시지 1분 간격 확인.

---

## 5. 최종 검토 (Final Verification)

> **Claude Code Verify**: 위 계획이 수정된 요구사항과 기술적 제약을 모두 만족하는지 최종 확인합니다.

- [x] Critical 2.1 (Bot Logic): 실시간 루프 반영 완료.
- [x] Critical 2.2 (DB Migration): Phase 0에 추가 완료.
- [x] Critical 2.3 (Concurrency): 확정된 데이터(`timestamp < now`) 조회 원칙 반영.
- [x] Required 3.1 (Probes): Phase 3 Manifest 작업에 추가 완료.
- [x] Required 3.2 (Monitoring): Phase 3에 모니터링 섹션 추가 완료.
- [x] Required 3.4 (Limits): Resource Limits 설정 명시.

---

## 6. Claude Code 최종 승인

**검토일**: 2026-01-27
**검토자**: Claude Code (Operator & Reviewer)
**상태**: ✅ **최종 승인 (APPROVED)**

---

### 검증 완료 사항

| 카테고리 | 항목 | 상태 |
|----------|------|------|
| **Critical** | Bot Logic (실시간 루프) | ✅ Phase 1 반영 |
| **Critical** | DB Migration (UNIQUE 제약) | ✅ Phase 0 반영 |
| **Critical** | Concurrency (확정 데이터 조회) | ✅ Phase 1 Step 1 반영 |
| **Required** | Health Probes | ✅ Phase 3 반영 |
| **Required** | Monitoring (Prometheus/Grafana) | ✅ Phase 3 + 아키텍처 반영 |
| **Required** | Resource Limits | ✅ 다수 위치 반영 |
| **Required** | Secret 관리 | ✅ Section 3 + Phase 3 반영 |
| **Decision** | Bot Loop 방식 | ✅ Simple Loop 확정 |
| **Decision** | 비용 승인 | ✅ ~$1.5~15/월 |

---

### 추가 권장사항 (Optional)

#### 1. Dashboard Probe 추가 검토
`dashboard-deployment.yaml`에도 Liveness/Readiness Probe 추가 권장:
```yaml
livenessProbe:
  httpGet:
    path: /_stcore/health  # Streamlit health endpoint
    port: 8501
  initialDelaySeconds: 30
```

#### 2. Future Consideration
> **Celery + Redis**: 다중 심볼 병렬 처리 등 확장 필요 시 도입 검토. (이전 프로젝트 경험 있음)

---

### 승인 결론

| 구분 | 내용 |
|------|------|
| **계획 품질** | ✅ 우수 - 모든 Critical/Required 항목 반영 |
| **실현 가능성** | ✅ 높음 - 단계별 검증 포인트 명확 |
| **리스크** | ✅ 낮음 - 선행 작업(Phase 0) 포함 |

**✅ Week 4 개발 시작 승인**

---

**다음 단계**: Phase 0 (Prerequisites) 실행 → Phase 1 (Bot 구현) 시작
