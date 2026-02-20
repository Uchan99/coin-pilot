# 17-06. Latest 단일 태그 운영 전환 계획

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P0

---

## 1. 배경

현재 Bot 매니페스트가 `bot:rss-v1`를 참조하고 있어, 개발 중 반복 배포 시 태그를 계속 증가시키는 운영 부담이 발생한다.

사용자 요구:
1. `latest` 단일 태그 운영으로 회귀
2. minikube CLI 없이도 `latest` 빌드/반영이 가능해야 함

---

## 2. 목표

1. Bot 관련 Kubernetes 매니페스트를 `bot:latest`로 복원
2. `latest` 단일 태그 빌드/로드/롤아웃 자동화 스크립트 제공

---

## 3. 아키텍처 선택 및 대안

### 선택안 (채택)
- 매니페스트: `bot:latest` 참조
- 배포: 로컬 Docker 빌드 -> `docker exec minikube docker load` -> `kubectl rollout`

### 대안 1
- 버전 태그 운영(`bot:rss-v2`, `v3`...)
- 장점: 롤백/재현성 우수
- 단점: 개발 반복 시 관리 비용 증가

### 대안 2
- minikube CLI 설치 후 `minikube docker-env` 기반 운영
- 장점: 표준 절차
- 단점: 현재 환경에서 CLI 부재

### 트레이드오프
- `latest` 단일 태그는 재현성은 낮지만 개발 속도/운영 단순성이 높다.
- 안정 릴리즈 시점에만 버전 태그 전략으로 전환하는 하이브리드 운영을 권장한다.

---

## 4. 구현 범위

1. `k8s/apps/bot-deployment.yaml`
- `image: bot:rss-v1` -> `image: bot:latest`

2. `k8s/jobs/backfill-regime-job.yaml`
- `image: bot:rss-v1` -> `image: bot:latest`

3. `scripts/redeploy_latest_minikube.sh` (신규)
- `docker-compose build bot`
- `docker save bot:latest | docker exec -i minikube docker load`
- `kubectl set image ... bot:latest`
- `rollout status`

---

## 5. 검증

```bash
rg -n "image:\s*bot:" k8s -g '*.yaml'
./scripts/redeploy_latest_minikube.sh
```

---

## 6. 산출물

1. Bot 매니페스트 latest 복원
2. Latest 단일 태그 재배포 스크립트
3. 결과 문서: `docs/work-result/17-06_latest_single_tag_operation_result.md`

---

## 7. 변경 이력

### 2026-02-20

1. `k8s/apps/bot-deployment.yaml` 이미지를 `bot:latest`로 복원
2. `k8s/jobs/backfill-regime-job.yaml` 이미지를 `bot:latest`로 복원
3. `scripts/redeploy_latest_minikube.sh` 신규 추가
