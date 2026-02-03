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
봇이 5개 코인(BTC, ETH, XRP, SOL, DOGE)에 대해 시작되었는지 로그를 확인합니다.

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

### 3.2 대시보드 확인
대시보드 사이드바의 "Select Symbol" 드롭다운에 5개 코인이 모두 표시되는지 확인합니다.
- 접속: http://localhost:8501 (포트포워딩 필요)

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

## Claude Code Review

> **검토일**: 2026-02-04
> **검토자**: Claude Code (Operator & Reviewer)
> **상태**: ✅ 승인 (보완 권장 사항 포함)

### ✅ 잘 작성된 부분

| 항목 | 평가 |
|------|------|
| 배포 절차 단계별 정리 | ✅ 명확함 |
| 명령어 복사-붙여넣기 가능 | ✅ 편리함 |
| 예상 출력 예시 | ✅ 검증 용이 |
| 트러블슈팅 포함 | ✅ 실용적 |
| `./minikube` 경로 | ✅ deploy 스크립트와 일치 |

---

### 📝 보완 권장 사항

#### 1. Collector 로그 확인 추가
멀티 코인 수집이 정상 동작하는지 확인하는 명령어가 없습니다.

```bash
# 섹션 3.1에 추가 권장
kubectl logs -f deployment/collector -n coin-pilot-ns
```
**예상 출력**:
```text
[*] Starting Upbit Collector for 5 symbols...
[*] Target Symbols: ['KRW-BTC', 'KRW-ETH', 'KRW-XRP', 'KRW-SOL', 'KRW-DOGE']
```

#### 2. 대시보드 포트포워딩 명령어 명시
섹션 3.2에서 "포트포워딩 필요"라고 언급만 하고 명령어가 없습니다.

```bash
# 추가 권장
kubectl port-forward -n coin-pilot-ns service/dashboard 8501:8501
```

#### 3. Redis 포트포워딩 (Bot Brain용)
대시보드의 Bot Brain 기능이 Redis를 사용하므로 포트포워딩이 필요합니다.

```bash
# 추가 권장
kubectl port-forward -n coin-pilot-ns service/redis 6379:6379
```

#### 4. 롤백 절차 섹션 추가
문제 발생 시 즉시 롤백할 수 있는 방법이 없습니다.

```markdown
## 5. 롤백 (Rollback)
문제 발생 시 보수적 모드로 즉시 전환:

1. `src/config/strategy.py` 수정:
   ```python
   USE_CONSERVATIVE_MODE = True  # False → True
   ```

2. 재배포:
   ```bash
   ./deploy/deploy_to_minikube.sh
   kubectl rollout restart deployment/bot -n coin-pilot-ns
   kubectl rollout restart deployment/collector -n coin-pilot-ns
   ```
```

---

### ✅ 결론

**승인** - 기본 배포 절차가 명확하게 문서화되어 있습니다. 위 보완 사항은 선택적으로 추가하면 더 완성도 높은 가이드가 됩니다.

---

*Review by Claude Code - CoinPilot Operator & Reviewer*
