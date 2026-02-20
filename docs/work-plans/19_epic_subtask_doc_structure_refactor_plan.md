# 19. 에픽-서브태스크 문서 체계 개편 계획 (17 중심)

**작성일**: 2026-02-20  
**상태**: Completed (2026-02-20)  
**우선순위**: P0

---

## 1. 배경

17번 메인 계획 수행 과정에서 파생 작업이 19~27 번호로 분산되어,
메인 에픽(17) 추적성과 독립 작업 번호 체계가 혼재됐다.

요구사항:
1. 메인 계획과 서브 계획/결과를 분리
2. 문서 규칙(AGENTS/CHARTER)에 에픽-서브태스크 체계 반영
3. 기존 문서를 신규 체계로 리네이밍 및 링크 정합성 복구

---

## 2. 목표

1. 네이밍 정책 확정
- 독립 작업: `<NN>_<topic>_...`
- 에픽 하위 작업: `<EPIC>-<subNN>_<topic>_...`

2. 정책 문서 반영
- `docs/PROJECT_CHARTER.md`
- `AGENTS.md`
- `docs/AGENTS.md`
- 필요 시 `docs/templates/*` 경로 예시

3. 17 관련 파생 문서 리네이밍
- 기존 `19~27` 중 17 관련 문서를 `17-xx`로 이동
- plan/result 간 상호 링크, 17 마스터 문서 링크 갱신

4. 인덱스 가시화
- `17` 메인 plan/result에 하위 작업 인덱스 추가

---

## 3. 아키텍처 선택 및 대안

### 선택안 (채택)
- 파일명에서 계층을 바로 드러내는 `17-xx` 네이밍
- 17 문서에 하위 작업 인덱스를 유지하는 허브 구조

### 대안 1
- 기존 번호(19~27) 유지 + 17 문서에 링크만 추가
- 장점: 파일 이동 최소
- 단점: 번호 체계 혼선 지속

### 대안 2
- 상위 폴더 분리(`docs/work-plans/17/*`)
- 장점: 물리적 분리 명확
- 단점: 기존 규칙/툴링/탐색 습관 변경 부담

### 대안 3
- 태그/메타데이터 기반 분류만 사용
- 장점: 파일명 유지
- 단점: CLI 탐색성과 직관성 낮음

### 트레이드오프
- 리네이밍 시 기존 참조 링크 수정 비용이 들지만,
  이후 추적성과 확장성(17-01, 17-02...)이 크게 개선된다.

---

## 4. 구현 범위

1. 정책 문서 수정
- `docs/PROJECT_CHARTER.md` (운영 규칙 + changelog)
- `AGENTS.md`
- `docs/AGENTS.md`
- `docs/templates/work-plan.template.md`
- `docs/templates/work-result.template.md`
- `docs/templates/troubleshooting.template.md`

2. 파일 리네이밍 (17 파생 작업)
- Plan/Result를 `17-01`~`17-08` 체계로 이동

3. 링크 정합성 수정
- plan <-> result 링크
- 17 메인 plan/result의 후속 링크
- 전역 참조 검색 후 잔여 경로 제거

4. 인덱스 추가
- `docs/work-plans/17_chatbot_trading_assistant_upgrade_plan.md`
- `docs/work-result/17_chatbot_trading_assistant_upgrade_result.md`

---

## 5. 검증

```bash
ls -1 docs/work-plans | sort -V
ls -1 docs/work-result | sort -V
rg -n "docs/work-(plans|result)/(19_|20_|21_|22_|23_|24_|26_|27_)" docs -g '*.md'
```

---

## 6. 산출물

1. 에픽-서브태스크 네이밍 정책 반영 문서
2. 17 파생 문서 리네이밍 완료본
3. 17 마스터 문서 하위 인덱스
4. 결과 문서: `docs/work-result/19_epic_subtask_doc_structure_refactor_result.md`

---

## 7. 변경 이력

### 2026-02-20

1. 계획서 작성
2. 정책 문서(CHARTER/AGENTS/templates) 에픽-서브태스크 규칙 반영 완료
3. 17 파생 문서를 `17-01`~`17-09` 체계로 리네이밍 완료
4. 17 메인 plan/result에 하위 인덱스 추가 및 링크 정합성 검증 완료
