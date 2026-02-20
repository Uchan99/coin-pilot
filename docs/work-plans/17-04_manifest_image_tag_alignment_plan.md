# 17-04. Bot 이미지 태그 정렬 계획

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P0

---

## 1. 배경

현재 실제 배포는 `bot:rss-v1`로 교체되었지만, Kubernetes 매니페스트(`k8s/apps/bot-deployment.yaml`, `k8s/jobs/backfill-regime-job.yaml`)는 여전히 `bot:latest`를 참조한다.

이 상태에서 `kubectl apply -f k8s/...`를 다시 실행하면 이미지가 `latest`로 되돌아가 코드 불일치가 재발할 수 있다.

---

## 2. 목표

1. 매니페스트의 Bot 이미지 참조를 `bot:rss-v1`로 정렬
2. 재적용 시 현재 동작 코드와 매니페스트 상태가 일치하도록 보장

---

## 3. 아키텍처/선택 근거

### 선택안
- 이미지 태그를 명시 버전(`bot:rss-v1`)으로 고정

### 대안
1. `bot:latest` 유지
- 장점: 태그 관리 단순
- 단점: 재현성 낮고 롤백/추적 어려움

2. SHA digest 고정 (`bot@sha256:...`)
- 장점: 가장 강한 재현성
- 단점: 운영 절차 복잡도 증가

### 트레이드오프
- 버전 태그는 digest보다는 약하지만 `latest` 대비 재현성과 추적성이 크게 향상된다.

---

## 4. 구현 범위

1. `k8s/apps/bot-deployment.yaml`
- `image: bot:latest` -> `image: bot:rss-v1`

2. `k8s/jobs/backfill-regime-job.yaml`
- `image: bot:latest` -> `image: bot:rss-v1`

---

## 5. 검증

```bash
rg -n "image:\s*bot:" k8s -g '*.yaml'
```

기대:
- 관련 매니페스트가 `bot:rss-v1`로 표시됨

---

## 6. 산출물

1. 수정된 매니페스트 2개
2. 결과 문서: `docs/work-result/17-04_manifest_image_tag_alignment_result.md`

---

## 7. 변경 이력

### 2026-02-20

1. `k8s/apps/bot-deployment.yaml` 이미지 태그를 `bot:rss-v1`로 변경
2. `k8s/jobs/backfill-regime-job.yaml` 이미지 태그를 `bot:rss-v1`로 변경
