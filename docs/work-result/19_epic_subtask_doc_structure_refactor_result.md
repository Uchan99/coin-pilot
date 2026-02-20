# 19. 에픽-서브태스크 문서 체계 개편 결과

**작성일**: 2026-02-20  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/19_epic_subtask_doc_structure_refactor_plan.md`

---

## 1. 구현 요약

17번 메인 에픽과 파생 작업 문서를 분리하기 위해 문서 번호 정책을 개편하고,
기존 17 관련 파생 문서를 `17-xx` 체계로 일괄 정리했다.

---

## 2. 아키텍처 결정 기록

### 선택안
- 메인 에픽은 `17_*` 유지
- 하위 작업은 `17-01_*`, `17-02_*` 형태로 분리
- 독립 스트림은 기존처럼 `<NN>_*` 유지

### 대안 비교
1. 기존 19~27 번호 유지 + 링크만 보강
- 장점: 파일 이동 없음
- 단점: 번호 체계 혼선 지속

2. 폴더 분리(`docs/work-plans/17/*`)
- 장점: 물리적 분리 명확
- 단점: 기존 규칙/탐색 흐름 변경 부담

3. 파일명은 유지하고 메타데이터만 보강
- 장점: 최소 변경
- 단점: CLI 탐색 시 계층이 드러나지 않음

### 트레이드오프
- 리네이밍/링크 수정 비용은 발생했지만,
  이후 에픽 진행 추적성과 번호 충돌 방지 효과가 더 크다.

---

## 3. 변경 내용

### 3.1 정책 문서
1. `docs/PROJECT_CHARTER.md`
- 문서 네이밍 규칙에 에픽-서브태스크 형식(`<EPIC>-<subNN>`) 추가
- 8.9 변경 이력에 정책 변경 기록 추가

2. `AGENTS.md`
- Required workflow에 independent/epic-subtask 네이밍 규칙 추가
- Numbering policy 섹션 추가

3. `docs/AGENTS.md`
- 문서 생성 규칙 및 numbering policy 확장

4. 템플릿
- `docs/templates/work-plan.template.md`
- `docs/templates/work-result.template.md`
- `docs/templates/troubleshooting.template.md`
- `<NN>` + `<EPIC>-<subNN>` 예시 경로로 갱신

### 3.2 파일 리네이밍 (17 파생 작업)
- Plan
  - `17-01_chatbot_consultant_intent_sell_strategy_plan.md`
  - `17-02_chatbot_buy_action_intent_fix_plan.md`
  - `17-03_news_rag_rss_only_implementation_plan.md`
  - `17-04_manifest_image_tag_alignment_plan.md`
  - `17-05_news_summary_readability_improvement_plan.md`
  - `17-06_latest_single_tag_operation_plan.md`
  - `17-07_latest_dual_redeploy_script_plan.md`
  - `17-08_phase5_chat_guardrails_and_model_tiering_plan.md`
  - `17-09_doc_numbering_conflict_fix_plan.md`
- Result
  - `17-01_chatbot_consultant_intent_sell_strategy_result.md`
  - `17-02_chatbot_buy_action_intent_fix_result.md`
  - `17-03_news_rag_rss_only_implementation_result.md`
  - `17-04_manifest_image_tag_alignment_result.md`
  - `17-05_news_summary_readability_improvement_result.md`
  - `17-06_latest_single_tag_operation_result.md`
  - `17-07_latest_dual_redeploy_script_result.md`
  - `17-08_phase5_chat_guardrails_and_model_tiering_result.md`
  - `17-09_doc_numbering_conflict_fix_result.md`

### 3.3 메인 문서 인덱스 추가
1. `docs/work-plans/17_chatbot_trading_assistant_upgrade_plan.md`
- `10.1 하위 작업 인덱스` 추가

2. `docs/work-result/17_chatbot_trading_assistant_upgrade_result.md`
- `1.1 하위 결과 인덱스` 추가

---

## 4. 검증

실행:
```bash
ls -1 docs/work-plans | sort -V
ls -1 docs/work-result | sort -V
rg -n "docs/work-(plans|result)/(19_|20_|21_|22_|23_|24_|25_|26_|27_)" docs -g '*.md'
```

결과:
- `docs/work-plans`/`docs/work-result`에서 17 파생 문서는 `17-01`~`17-09`로 정렬됨
- 구 경로(`19_`~`27_`) 참조 0건 확인

---

## 5. 영향

1. 17 메인 에픽의 진행 추적성이 개선됨
2. 독립 작업 번호(예: 18번 cloud migration)와 파생 작업 번호 충돌 위험 감소
3. 향후 17 후속 작업은 `17-10`, `17-11` 형태로 일관 확장 가능
