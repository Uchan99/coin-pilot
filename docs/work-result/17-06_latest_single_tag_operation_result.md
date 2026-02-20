# 17-06. Latest 단일 태그 운영 전환 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17-06_latest_single_tag_operation_plan.md`

---

## 1. 구현 요약

사용자 요청에 따라 Bot 운영 태그를 `bot:rss-v1`에서 `bot:latest` 단일 태그 방식으로 복원했다.

추가로, minikube CLI가 없는 환경에서도 `latest` 빌드/배포를 반복할 수 있도록 자동화 스크립트를 제공했다.

---

## 2. 변경 파일

1. `k8s/apps/bot-deployment.yaml`
- `image: bot:rss-v1` -> `image: bot:latest`

2. `k8s/jobs/backfill-regime-job.yaml`
- `image: bot:rss-v1` -> `image: bot:latest`

3. `scripts/redeploy_latest_minikube.sh` (신규)
- 기능:
  1. `docker-compose` 또는 `docker compose` 자동 감지
  2. `bot:latest` 빌드
  3. `docker exec minikube docker load`로 노드 런타임에 이미지 주입
  4. `kubectl set image` + `rollout status` 수행

---

## 3. 아키텍처 결정 기록

### 선택안
- 개발 단계에서 `latest` 단일 태그 운영

### 대안 비교
1. 버전 태그 고정 운영
- 장점: 재현성/롤백 우수
- 단점: 개발 반복 시 태그 관리 오버헤드

2. `latest` 단일 태그 운영 (채택)
- 장점: 반복 배포 간단, 운영 부담 감소
- 단점: 재현성 상대적 약화

### 트레이드오프 완화
- 안정 릴리즈 시점에만 버전 태그를 별도 발급하는 하이브리드 운영 권장

---

## 4. 검증

실행:
```bash
rg -n "image:\s*bot:" k8s -g '*.yaml'
```

결과:
- `k8s/apps/bot-deployment.yaml` -> `bot:latest`
- `k8s/jobs/backfill-regime-job.yaml` -> `bot:latest`

실행:
```bash
bash -n scripts/redeploy_latest_minikube.sh
```

결과:
- 문법 통과

---

## 5. 사용 방법

```bash
./scripts/redeploy_latest_minikube.sh
```

실행 후 `deployment/bot`가 `bot:latest`로 롤아웃된다.
