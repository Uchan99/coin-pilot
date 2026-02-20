# 17-04. Bot 이미지 태그 정렬 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17-04_manifest_image_tag_alignment_plan.md`

---

## 1. 변경 요약

매니페스트와 실제 배포 이미지 불일치 문제를 해결하기 위해 Bot 관련 YAML 2개의 이미지 태그를 `bot:rss-v1`로 정렬했다.

---

## 2. 변경 파일

1. `k8s/apps/bot-deployment.yaml`
- `image: bot:latest` -> `image: bot:rss-v1`

2. `k8s/jobs/backfill-regime-job.yaml`
- `image: bot:latest` -> `image: bot:rss-v1`

---

## 3. 검증

실행:
```bash
rg -n "image:\s*bot:" k8s -g '*.yaml'
```

결과:
- `k8s/apps/bot-deployment.yaml: image: bot:rss-v1`
- `k8s/jobs/backfill-regime-job.yaml: image: bot:rss-v1`

---

## 4. 효과

1. `kubectl apply -f k8s/...` 재적용 시 이미지가 `latest`로 되돌아가는 위험 감소
2. 운영 중인 코드와 매니페스트 상태의 정합성 확보
