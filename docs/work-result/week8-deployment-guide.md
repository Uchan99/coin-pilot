# Week 8 Strategy Expansion Deployment Guide

**작성일**: 2026-02-04
**버전**: v1.0 (Strategy Expansion Update)

## 1. 개요
Week 8 전략 확장(멀티 코인 + 리스크 관리) 코드가 구현되었습니다.
변경된 코드를 Kubernetes 클러스터에 배포하기 위한 절차를 안내합니다.

## 2. 배포 절차 (Deployment Steps)

### Step 1. 배포 스크립트 실행
이미지를 새로 빌드하고 K8s 설정을 업데이트합니다.
(Minikube 환경에서 실행)

```bash
# 프로젝트 루트 디렉토리에서 실행
./deploy/deploy_to_minikube.sh
```

> **💡 Secret 관리**: 스크립트가 `.env` 파일에서 API 키(ANTHROPIC, OPENAI, UPBIT 등)를 읽어 K8s Secret을 자동 생성합니다.
> - `.env` 파일이 프로젝트 루트에 존재해야 함
> - `.env`는 `.gitignore`에 포함되어 git에 업로드되지 않음
> - `k8s/base/secret.yaml`은 플레이스홀더만 포함 (실제 키 없음)

### Step 2. 파드 재시작 (Rollout Restart)
`latest` 태그를 사용하는 경우, 이미지가 갱신되어도 파드가 즉시 재시작되지 않을 수 있습니다.
확실한 적용을 위해 강제 재시작을 수행합니다.

```bash
# Bot, Collector, Dashboard 재시작
kubectl rollout restart deployment/bot -n coin-pilot-ns
kubectl rollout restart deployment/collector -n coin-pilot-ns
kubectl rollout restart deployment/dashboard -n coin-pilot-ns
```

### Step 3. 배포 확인
모든 파드가 정상적으로 `Running` 상태가 되는지 확인합니다.

```bash
watch kubectl get pods -n coin-pilot-ns
```

---

## 3. 검증 (Verification)

### 3.1 로그 확인
봇과 수집기가 5개 코인(BTC, ETH, XRP, SOL, DOGE)에 대해 시작되었는지 로그를 확인합니다.

```bash
# Bot 로그 확인
kubectl logs -f deployment/bot -n coin-pilot-ns
```
**예상 출력**:
```text
[*] CoinPilot Trading Bot Started for 5 symbols
[*] Strategy: MeanReversion
[*] Target Symbols: ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-DOGE']
```

```bash
# Collector 로그 확인
kubectl logs -f deployment/collector -n coin-pilot-ns
```
**예상 출력**:
```text
[*] Starting Upbit Collector for 5 symbols...
[*] Target Symbols: ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-DOGE']
[*] Backfill completed. Entering main loop...
```

### 3.2 대시보드 확인
대시보드 사이드바의 "Select Symbol" 드롭다운에 5개 코인이 모두 표시되는지 확인합니다.

**포트포워딩 (필수)**:
```bash
# 대시보드 접속용
kubectl port-forward -n coin-pilot-ns service/dashboard 8501:8501 &

# Bot Brain(Redis) 작동용
kubectl port-forward -n coin-pilot-ns service/redis 6379:6379
```
- 접속: http://localhost:8501

---

## 4. 트러블슈팅

**Q. 파드가 ImagePullBackOff 상태입니다.**
A. Minikube Docker 환경 설정이 풀렸을 수 있습니다. 다음 명령어로 환경을 다시 로드하고 스크립트를 재실행하세요.
```bash
eval $(./minikube -p minikube docker-env)
./deploy/deploy_to_minikube.sh
```

**Q. DB 에러가 발생합니다.**
A. 설정 변경으로 인한 일시적 현상일 수 있습니다. DB가 완전히 준비될 때까지 기다리거나 DB 파드도 재시작해 보세요.
```bash
kubectl rollout restart statefulset/db -n coin-pilot-ns
```

---

## 5. 롤백 (Rollback)

문제 발생 시 보수적 모드(BTC only, 엄격한 조건)로 즉시 전환할 수 있습니다.

### 5.1 롤백 트리거 조건
- 24시간 내 -10% 이상 손실
- API Rate Limit 지속 초과
- 시스템 에러 연속 발생

### 5.2 롤백 방법

**Step 1.** `src/config/strategy.py` 수정:
```python
# 이 값만 True로 변경
USE_CONSERVATIVE_MODE = True  # False → True
```

**Step 2.** 재배포:
```bash
./deploy/deploy_to_minikube.sh
kubectl rollout restart deployment/bot -n coin-pilot-ns
kubectl rollout restart deployment/collector -n coin-pilot-ns
```

**Step 3.** 로그 확인:
```bash
kubectl logs -f deployment/bot -n coin-pilot-ns
```
**예상 출력** (롤백 모드):
```text
[*] CoinPilot Trading Bot Started for 1 symbols
[*] Target Symbols: ['KRW-BTC']
```

---

## Claude Code Review

> **검토일**: 2026-02-04
> **검토자**: Claude Code (Operator & Reviewer)
> **상태**: ✅ 승인 (모든 보완 사항 반영 완료)

### ✅ 잘 작성된 부분

| 항목 | 평가 |
|------|------|
| 배포 절차 단계별 정리 | ✅ 명확함 |
| 명령어 복사-붙여넣기 가능 | ✅ 편리함 |
| 예상 출력 예시 | ✅ 검증 용이 |
| 트러블슈팅 포함 | ✅ 실용적 |
| `./minikube` 경로 | ✅ deploy 스크립트와 일치 |

---

### ✅ 반영 완료 사항

| 항목 | 상태 |
|------|------|
| Collector 로그 확인 추가 | ✅ 섹션 3.1에 반영 |
| 대시보드 포트포워딩 명령어 | ✅ 섹션 3.2에 반영 |
| Redis 포트포워딩 (Bot Brain용) | ✅ 섹션 3.2에 반영 |
| 롤백 절차 섹션 | ✅ 섹션 5에 신규 추가 |

---

### ✅ 결론

**승인** - 모든 보완 사항이 반영되어 완성도 높은 배포 가이드가 되었습니다.

---

*Review by Claude Code - CoinPilot Operator & Reviewer*
