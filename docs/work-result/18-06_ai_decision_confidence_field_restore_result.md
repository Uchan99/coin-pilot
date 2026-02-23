# 18-06. AI Decision Confidence 필드 복구 구현 결과

작성일: 2026-02-23
작성자: Codex (GPT-5)
관련 계획서: `docs/work-plans/18-06_ai_decision_confidence_field_restore_plan.md`
상태: Verified
완료 범위: Phase 1
선반영/추가 구현: 없음
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - n8n AI Decision 알림 embed fields에 Confidence 항목 복구.
- 목표(요약):
  - Discord 메시지에서 AI 판단 신뢰도 가시성 회복.
- 이번 구현이 해결한 문제(한 줄):
  - 누락된 Confidence 표시를 복원했다.

---

## 2. 구현 내용(핵심 위주)
### 2.1 AI Decision 워크플로우 필드 복구
- 파일/모듈:
  - `config/n8n_workflows/ai_decision.json`
- 변경 내용:
  - `embeds.fields`에 `🎯 Confidence` 항목 추가
  - null/undefined 대응 표현식 적용
- 효과/의미:
  - REJECT/CONFIRM 알림에서 confidence를 다시 확인 가능

---

## 3. 변경 파일 목록
### 3.1 수정
1) `config/n8n_workflows/ai_decision.json`

### 3.2 신규
1) `docs/work-plans/18-06_ai_decision_confidence_field_restore_plan.md`
2) `docs/work-result/18-06_ai_decision_confidence_field_restore_result.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `jq . config/n8n_workflows/ai_decision.json >/dev/null`
- 결과:
  - JSON 유효성 통과

### 5.2 테스트 검증
- 실행 명령:
  - 없음 (워크플로우 템플릿 변경)
- 결과:
  - N/A

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - n8n에서 `AI Decision Notification` 워크플로우에 동일 표현식 반영 후 테스트 실행
- 결과:
  - 사용자 환경에서 확인 필요

---

## 6. 배포/운영 확인 체크리스트(필수)
1) n8n `Discord Webhook` 노드의 `embeds`에 Confidence field 포함 여부 확인
2) 테스트 실행 시 Discord 메시지에 `Confidence` 라인 표시 확인
3) confidence 누락 payload에서도 `-`로 안전 표시 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 알림 템플릿만 최소 변경하여 가시성 복구
- 고려했던 대안:
  1) 백엔드 payload에 별도 문자열 필드 추가
  2) Discord plain text 포맷으로 전환
  3) 현재 템플릿 유지
- 대안 대비 실제 이점(근거/관측 포함):
  1) 기존 UI/노드 구조와 호환
  2) 영향 범위 최소
  3) 즉시 적용 가능
- 트레이드오프(단점)와 보완/완화:
  1) n8n UI에 수동 반영 필요 가능성 -> import/update 절차로 완화

---

## 8. 한국어 주석 반영 결과(필수)
- 코드 로직 변경이 아닌 워크플로우 템플릿 변경이라 주석 추가 없음

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 누락 필드 복구 및 JSON 검증 완료
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 저장소 템플릿 기준 Confidence 표시가 복구됨
- 후속 작업:
  1) n8n UI 워크플로우 동기화 후 테스트 실행

---

## 12. References
- `docs/work-plans/18-06_ai_decision_confidence_field_restore_plan.md`
- `config/n8n_workflows/ai_decision.json`
