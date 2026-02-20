# 17-07. latest 단일 태그 Bot+Dashboard 동시 재배포 스크립트 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/17-07_latest_dual_redeploy_script_plan.md`

---

## 1. 구현 요약

`latest` 단일 운영을 유지하면서, 기존 `bot` 전용 재배포 스크립트를 `bot + dashboard` 동시 재빌드/재배포 방식으로 확장했다.

---

## 2. 변경 파일

1. `scripts/redeploy_latest_minikube.sh`
- 기존: `bot`만 빌드/load/롤아웃
- 변경: `bot`과 `dashboard`를 함께 빌드/load/롤아웃

---

## 3. 아키텍처 결정 기록

### 선택안
- 기존 스크립트 확장 방식 채택 (동일 명령 흐름 유지)

### 대안 비교
1. 스크립트 분리
- 장점: 단일 책임
- 단점: 명령 반복 증가

2. 전체 매니페스트 재적용(`kubectl apply -f ...`)
- 장점: 선언형 전체 동기화
- 단점: 빠른 반복 재배포 요구 대비 범위 과다

### 트레이드오프
- 이번 스크립트는 "이미 존재하는 배포의 이미지 교체"에 최적화되어 있다.
- 반면 매니페스트 신규/변경 리소스 반영은 별도 apply 절차가 필요하다.

---

## 4. 검증

실행:
```bash
bash -n scripts/redeploy_latest_minikube.sh
```

결과:
- 문법 검사 통과

---

## 5. 사용 방법

```bash
./scripts/redeploy_latest_minikube.sh
```

수행 항목:
1. `docker-compose build bot dashboard`
2. `bot:latest`, `dashboard:latest`를 minikube docker runtime으로 load
3. `deployment/bot`, `deployment/dashboard` 이미지 갱신
4. 두 deployment rollout 완료 대기
5. 이미지/파드 상태 출력
