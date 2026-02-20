# 17-09. 문서 번호 충돌(18번) 정리 계획

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P0

---

## 1. 배경

기존에 `18_cloud_migration_cost_optimized_deployment_plan.md`가 존재하는 상태에서,
별개 작업 문서가 `18_chatbot_consultant_intent_sell_strategy_*`로 생성되어 번호 충돌이 발생했다.

이로 인해 문서 탐색/추적 시 18번 의미가 중복되어 혼선을 유발한다.

---

## 2. 목표

1. 기존 18번 클라우드 마이그레이션 문서 번호를 보존
2. 충돌난 챗봇 문서를 새로운 번호로 이동
3. 이동된 문서의 내부 제목/링크를 모두 정합성 있게 갱신

---

## 3. 아키텍처 선택 및 대안

### 선택안 (채택)
- 충돌 문서(챗봇 의도 분리)만 새 번호로 이동
- 기존 클라우드 마이그레이션 18번 유지

### 대안 1
- 클라우드 문서를 다른 번호로 이동
- 단점: 기존 문맥/참조 훼손 가능성 높음

### 대안 2
- 파일명은 유지하고 제목만 변경
- 단점: 파일 탐색 시 충돌이 계속 남음

### 트레이드오프
- 이동 시 히스토리 상 번호 불연속은 생길 수 있으나,
  중복 번호 제거가 우선이며 운영 추적성은 개선된다.

---

## 4. 구현 범위

1. 파일 이동
- `docs/work-plans/18_chatbot_consultant_intent_sell_strategy_plan.md` -> `docs/work-plans/17-01_chatbot_consultant_intent_sell_strategy_plan.md`
- `docs/work-result/18_chatbot_consultant_intent_sell_strategy_result.md` -> `docs/work-result/17-01_chatbot_consultant_intent_sell_strategy_result.md`

2. 내부 내용 정리
- 문서 제목의 번호를 에픽-서브태스크 형식(`17-01.`)으로 정규화
- 결과 문서의 관련 계획서 링크를 `17-01` 경로로 변경
- 계획서의 산출물 링크를 `17-01` 결과 경로로 변경

3. 참조 검색 검증
- `18_chatbot_consultant_intent_sell_strategy` 문자열이 남지 않는지 확인

---

## 5. 검증

```bash
ls -1 docs/work-plans | sort -V
ls -1 docs/work-result | sort -V
rg -n "18_chatbot_consultant_intent_sell_strategy" docs -g '*.md'
```

---

## 6. 변경 이력

### 2026-02-20

1. 계획서 작성
2. 18번 충돌 문서를 에픽-서브태스크 체계(`17-01`)로 이동하고 내부 링크 정리 완료
