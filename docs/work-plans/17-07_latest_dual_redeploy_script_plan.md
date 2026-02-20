# 17-07. latest 단일 태그 Bot+Dashboard 동시 재배포 스크립트 계획

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P0

---

## 1. 배경

현재 `scripts/redeploy_latest_minikube.sh`는 `bot`만 대상으로 동작한다.
사용자 요구는 `latest` 단일 태그 운영을 유지하면서 `bot`과 `dashboard`를 함께 재빌드/재배포하는 것이다.

---

## 2. 목표

1. `bot:latest`, `dashboard:latest`를 한 번에 빌드
2. minikube 노드 런타임으로 두 이미지를 한 번에 로드
3. `deployment/bot`, `deployment/dashboard`를 한 번에 롤아웃
4. 배포 결과를 한 번에 검증 출력

---

## 3. 아키텍처 선택 및 대안

### 선택안 (채택)
- 기존 스크립트를 확장해 `bot`+`dashboard` 동시 처리
- 기존 명령 흐름(빌드 -> load -> set image -> rollout)을 유지

### 대안 1
- 스크립트를 2개로 분리 (`redeploy_bot`, `redeploy_dashboard`)
- 장점: 단일 책임
- 단점: 반복 명령 증가, 사용성 저하

### 대안 2
- `kubectl apply -f deploy/` 스타일로 전체 재적용
- 장점: 선언형 전체 동기화
- 단점: 이번 요구(빠른 latest 반복 배포) 대비 범위 과다

### 트레이드오프
- 스크립트 확장 방식은 빠른 반복 배포에 유리하지만,
  매니페스트 변경 자체를 반영하는 작업(`kubectl apply`)과는 목적이 다르다.

---

## 4. 구현 범위

1. `scripts/redeploy_latest_minikube.sh`
- 빌드 대상을 `bot dashboard`로 확장
- minikube load를 두 이미지 모두 수행
- `kubectl set image`를 bot/dashboard 모두 수행
- rollout 상태 확인을 bot/dashboard 모두 수행
- 배포 후 이미지/파드 확인을 bot/dashboard 모두 출력

2. 결과 문서 작성
- `docs/work-result/17-07_latest_dual_redeploy_script_result.md`

---

## 5. 검증

```bash
bash -n scripts/redeploy_latest_minikube.sh
```

실운영 검증(사용자 환경):

```bash
./scripts/redeploy_latest_minikube.sh
kubectl get deploy -n coin-pilot-ns bot dashboard
kubectl get pods -n coin-pilot-ns -l app=bot
kubectl get pods -n coin-pilot-ns -l app=dashboard
```

---

## 6. 변경 이력

### 2026-02-20

1. 계획서 초안 작성
2. `scripts/redeploy_latest_minikube.sh`를 bot+dashboard 동시 재배포 방식으로 확장
