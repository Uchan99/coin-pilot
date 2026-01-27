# Week 4: Kubernetes Migration & Trading Bot Implementation

**작성일**: 2026-01-27
**상태**: Phase 1~3 완료 (Deployment Ready)

비동기 수집기(Collector)와 대시보드만 있던 기존 구조에서, 실제 자동 매매를 수행하는 **Trading Bot(Daemon)**을 구현하고, 전체 시스템을 **Kubernetes(Minikube)** 환경으로 이관하기 위한 준비를 마쳤습니다.

---

## 1. 주요 변경 사항 (Key Changes)

### 1️⃣ 실시간 트레이딩 봇 구현 (`src/bot/main.py`)
기존의 단발성 스크립트 실행 방식에서 벗어나, 24/7 중단 없이 돌아가는 **무한 루프(Daemon)** 형태의 봇을 구현했습니다.

- **프로세스 흐름**:
  1. **Data Fetch**: 수집기가 DB에 적재한 최신 1분봉 데이터 조회
  2. **Analyze**: 보조지표(RSI, BB, MA 등) 계산 (pandas-ta 활용)
  3. **Signal Check**:
     - **진입(Entry)**: RSI < 30 등 과매도 구간 포착 시
     - **청산(Exit)**: 익절(+5%), 손절(-3%), 시간 만료 등
  4. **Risk Management**:
     - `AccountState` 잔고 조회 후 자산의 5%만 투입 (Position Sizing)
     - 연패 시 쿨다운, 일일 손실 한도 체크
  5. **Execution (with AI)**:
     - 최종 주문 전 **AI Agent(LLM)**에게 시장 상황 브리핑 & 검증 요청

> **[Note]** `src/bot/main.py`에는 코드의 동작 원리와 철학("Reaction over Prediction")을 설명하는 상세한 한국어 주석이 포함되어 있습니다.

### 2️⃣ Dockerization (컨테이너화)
모든 컴포넌트를 독립된 컨테이너로 패키징했습니다.
- **Base Image Upgrade**: `python:3.10-slim` -> **`python:3.12-slim`**
  - *이유: `pandas-ta` 라이브러리의 의존성 충돌 문제 해결*
- **Dockerfiles**:
  - `deploy/docker/collector.Dockerfile`
  - `deploy/docker/bot.Dockerfile`
  - `deploy/docker/dashboard.Dockerfile`

### 3️⃣ Kubernetes Manifests (k8s/)
Minikube환경 배포를 위한 매니페스트를 구조화하여 작성했습니다.

| 구분 | 파일 경로 | 설명 |
| :--- | :--- | :--- |
| **Base** | `k8s/base/namespace.yaml` | `coin-pilot-ns` 네임스페이스 정의 |
| | `k8s/base/secret.yaml.example` | API Key, DB Password 등 보안 설정 |
| **DB** | `k8s/db/init-sql-configmap.yaml` | DB 초기화 스크립트 (`market_data` 테이블 등) |
| | `k8s/db/postgres-statefulset.yaml` | TimescaleDB (StatefulSet + Volume Claim) |
| | `k8s/db/redis-statefulset.yaml` | Redis 캐시 (StatefulSet) |
| **Apps** | `k8s/apps/collector-deployment.yaml` | 데이터 수집기 (Liveness/Readiness Probe 포함) |
| | `k8s/apps/bot-deployment.yaml` | 트레이딩 봇 (Daemon) |
| | `k8s/apps/dashboard-deployment.yaml` | Streamlit 대시보드 (NodePort 30000) |
| **Monitoring** | `k8s/monitoring/prometheus.yaml` | 메트릭 수집 서버 |
| | `k8s/monitoring/grafana.yaml` | 메트릭 시각화 (NodePort 30001) |

---

## 2. 검증 결과 (Verification)

### ✅ Local Test (Bot Logic)
- **명령어**: `PYTHONPATH=. .venv/bin/python src/bot/main.py`
- **결과**:
  - DB 연결 성공 (`[*] CoinPilot Trading Bot Started for KRW-BTC`)
  - 전략 초기화 및 Infinite Loop 진입 확인
  - 데이터 부족(`Not enough data`) 시 대기 로직 정상 동작 확인

### ✅ Docker Build Test
- **명령어**: `docker-compose -f deploy/docker-compose.yml build`
- **결과**: `collector`, `bot`, `dashboard` 3개 서비스 모두 빌드 성공 (Python 3.12 기반)
- **해결된 이슈**: `pandas-ta` 설치 시 `git clone` 오류 -> PyPI 정식 버전 사용 및 Python 버전 업그레이드로 해결

---

## 3. 다음 단계 (Next Steps)
이제 **Phase 4: Deployment & Verification**을 진행할 차례입니다.

1. **Minikube Start**: 로컬 K8s 클러스터 구동
2. **Apply Manifests**: `kubectl apply -f k8s/...` 순차 적용
3. **Smoke Test**: 파드(Pod) 상태 확인 및 로그 모니터링 (`kubectl logs -f ...`)
4. **Dashboard Access**: `http://localhost:30000` 접속 확인

이 보고서를 검토하시고 승인해주시면, 즉시 배포를 시작하겠습니다.

---

## Claude Code Review

**검토일**: 2026-01-27
**검토자**: Claude Code (Operator & Reviewer)
**상태**: ✅ **승인 (APPROVED)**

> Phase 1~3 구현이 완료되었으며, 발견된 Critical 이슈들도 모두 수정되었습니다. Phase 4 배포 준비가 완료되었습니다.

---

### 1. 검증 결과 요약

| 구분 | 파일/항목 | 상태 |
|------|----------|------|
| **Bot 구현** | `src/bot/main.py` | ✅ 우수 |
| **Dockerfiles** | 3개 (collector, bot, dashboard) | ✅ 정상 |
| **K8s Manifests** | 10개 YAML | ✅ 수정 완료 |
| **docker-compose.yml** | 업데이트 | ✅ 정상 |
| **Secret 관리** | .gitignore + template | ✅ 정상 |

---

### 2. 조치된 수정사항 (Resolved Issues)

#### 2.1 `agent_decisions` 테이블 추가
- **위치**: `k8s/db/init-sql-configmap.yaml`
- **조치**: AI 판단 결과를 저장할 `agent_decisions` 테이블 생성 SQL을 추가했습니다.

#### 2.2 Dashboard 의존성 추가
- **위치**: `requirements.txt`
- **조치**: `streamlit`, `plotly` 라이브러리를 추가하여 Dashboard 실행 오류를 방지했습니다.

#### 2.3 Deployment Manifest 정리
- **위치**: `k8s/apps/collector-deployment.yaml`
- **조치**: `DATABASE_URL` 환경 변수 설정을 `bot-deployment.yaml`과 통일하고 불필요한 주석을 제거했습니다.

---

### 3. ✅ 우수 구현 사항

| 항목 | 평가 |
|------|------|
| **Bot 로직 (`src/bot/main.py`)** | ✅ 상세한 한국어 주석, Graceful Shutdown, 1분 간격 보정 로직 우수 |
| **Dockerfile Python 버전** | ✅ 3.12-slim 통일 (pandas-ta 호환성 해결) |
| **K8s Resource Limits** | ✅ 모든 주요 서비스에 적용 |
| **Liveness/Readiness Probes** | ✅ collector, bot, dashboard 모두 적용 |
| **UNIQUE Constraint** | ✅ init-sql에 포함 (line 46) |
| **Secret 관리** | ✅ .gitignore에 포함 (line 208) |
| **docker-compose.yml** | ✅ 5개 서비스 정의 완료 |

---

### 4. 코드 품질 평가

#### `src/bot/main.py` 상세 검토

| 검증 항목 | 결과 |
|----------|------|
| Graceful Shutdown (SIGTERM/SIGINT) | ✅ Line 22-32 |
| 1분 간격 보정 로직 | ✅ Line 223-228 (`max(0, 60 - elapsed)`) |
| 데이터 신선도 체크 | ✅ Line 123 (`> timedelta(minutes=2)`) |
| AI Agent 연동 | ✅ Line 202-208 (executor 내부 호출) |
| 예외 처리 | ✅ Line 210-213 (traceback 출력) |
| 코드 주석 | ✅ 상세한 한국어 설명 포함 |

---

### 5. Phase별 완료 상태

| Phase | 작업 내용 | 상태 |
|-------|----------|------|
| Phase 0 | DB Migration (UNIQUE 제약) | ✅ init-sql에 포함 |
| Phase 1 | Trading Bot 구현 | ✅ 완료 |
| Phase 2 | Dockerization | ✅ 완료 |
| Phase 3 | K8s Manifests | ✅ 수정 완료 |
| Phase 4 | Deployment | ⏳ 대기 |

---

### 6. 최종 결론

| 구분 | 내용 |
|------|------|
| **승인 상태** | ✅ **승인 (APPROVED)** |
| **배포 가능 여부** | **가능 (Ready to Deploy)** |

**수정 체크리스트 (완료)**:
- [x] `k8s/db/init-sql-configmap.yaml`에 `agent_decisions` 테이블 추가
- [x] `requirements.txt`에 `streamlit`, `plotly` 추가
- [x] (Optional) `k8s/apps/collector-deployment.yaml` 주석 정리

---

**다음 단계**: **Phase 4 (Deployment)** 진행 승인 요청

---

## 최종 검증 (Final Verification)

**검토일**: 2026-01-27
**검토자**: Claude Code (Operator & Reviewer)

### 수정사항 적용 확인

| 항목 | 파일 | 검증 결과 |
|------|------|----------|
| `agent_decisions` 테이블 | `k8s/db/init-sql-configmap.yaml:87-99` | ✅ 테이블 + 인덱스 2개 추가 확인 |
| Dashboard 의존성 | `requirements.txt` | ✅ `streamlit`, `plotly` 추가 확인 |
| DATABASE_URL 패턴 | `k8s/apps/collector-deployment.yaml:28-29` | ✅ `value` 방식으로 수정 확인 |

### ✅ 최종 승인 (FINAL APPROVED)

모든 Critical 이슈가 해결되었으며, Phase 1~3 구현이 완료되었습니다.

| 구분 | 상태 |
|------|------|
| **Phase 0** (Prerequisites) | ✅ 완료 |
| **Phase 1** (Bot 구현) | ✅ 완료 |
| **Phase 2** (Dockerization) | ✅ 완료 |
| **Phase 3** (K8s Manifests) | ✅ 완료 |
| **Phase 4** (Deployment) | 🚀 **진행 가능** |

---

**Phase 4 배포 명령어 참고**:
```bash
# 1. Minikube 시작
minikube start --cpus 4 --memory 8192

# 2. Docker 환경 연결
eval $(minikube docker-env)

# 3. 이미지 빌드
docker-compose -f deploy/docker-compose.yml build

# 4. Secret 생성 (secret.yaml.example 복사 후 수정)
cp k8s/base/secret.yaml.example k8s/base/secret.yaml
# secret.yaml 편집 후...
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/secret.yaml

# 5. 순차 배포
kubectl apply -f k8s/db/
kubectl apply -f k8s/apps/
kubectl apply -f k8s/monitoring/

# 6. 상태 확인
kubectl get pods -n coin-pilot-ns
```

