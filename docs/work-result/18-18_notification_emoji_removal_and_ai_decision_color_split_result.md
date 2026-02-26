# 18-18. 알림 이모지 제거 및 AI Decision CONFIRM/REJECT 색상 분기 구현 결과

작성일: 2026-02-26  
작성자: Codex (GPT-5)  
관련 계획서: `docs/work-plans/18-18_notification_emoji_removal_and_ai_decision_color_split_plan.md`  
상태: Verified  
완료 범위: Phase 1~2  
선반영/추가 구현: 있음(Phase 2: n8n parser 호환 expression 보정)  
관련 트러블슈팅(있다면): `docs/troubleshooting/18-18_notification_style_and_decision_color.md`

---

## 1. 개요
- 구현 범위 요약:
  - Trade/AI Decision Discord 알림에서 이모지 제거
  - AI Decision color를 CONFIRM/REJECT 상태 기반으로 분기
- 목표(요약):
  - 알림 포맷을 텍스트 중심으로 단순화하고 의사결정 상태 가독성 향상
- 이번 구현이 해결한 문제(한 줄):
  - 고정 색상/이모지 기반 알림 스타일을 운영 요구에 맞게 표준화

---

## 2. 구현 내용(핵심 위주)
### 2.1 Trade Notification 이모지 제거
- 파일/모듈: `config/n8n_workflows/trade_notification.json`
- 변경 내용:
  - title의 아이콘 제거: `Trade Executed: <side>`
  - field name 이모지 제거: `Symbol`, `Price`, `Quantity`
  - 기존 payload fallback(`$json.body`/`$json`, `qty/quantity`) 유지
- 효과/의미:
  - 운영 채널 스타일 일관성 확보

### 2.2 AI Decision 색상 분기 + 이모지 제거
- 파일/모듈: `config/n8n_workflows/ai_decision.json`
- 변경 내용:
  - title 이모지 제거: `AI Decision: <decision>`
  - field name 이모지 제거: `Symbol`, `Regime`, `RSI`, `Confidence`
  - color 분기:
    - `CONFIRM` -> `5763719` (green)
    - `REJECT` -> `15548997` (red)
    - 기타 -> `9807270` (gray)
  - 입력 경로 fallback(`$json.body` + `$json`) 보강
- 효과/의미:
  - decision 상태를 색상만으로도 즉시 구분 가능

### 2.3 추적성 문서 반영
- 파일/모듈:
  - `docs/troubleshooting/18-18_notification_style_and_decision_color.md`
  - `docs/PROJECT_CHARTER.md`
- 변경 내용:
  - 18-18 Plan/Result/Troubleshooting 링크 및 changelog 반영
- 효과/의미:
  - 알림 템플릿 정책 변경 이력 추적 가능

### 2.4 n8n parser 호환 표현식 보정 (Phase 2)
- 파일/모듈:
  - `config/n8n_workflows/trade_notification.json`
  - `config/n8n_workflows/ai_decision.json`
- 변경 내용:
  - `(() => {})`, `const`, `??` 기반 표현식을 제거
  - 순수 ternary + `$json[...]` 접근 방식으로 expression 재작성
- 효과/의미:
  - 일부 n8n 버전에서 발생하던 `invalid syntax` 회피

---

## 3. 변경 파일 목록
### 3.1 수정
1) `config/n8n_workflows/trade_notification.json`  
2) `config/n8n_workflows/ai_decision.json`  
3) `docs/PROJECT_CHARTER.md`

### 3.2 신규
1) `docs/work-plans/18-18_notification_emoji_removal_and_ai_decision_color_split_plan.md`  
2) `docs/work-result/18-18_notification_emoji_removal_and_ai_decision_color_split_result.md`  
3) `docs/troubleshooting/18-18_notification_style_and_decision_color.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: JSON expression 이전 버전으로 복원

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `jq . config/n8n_workflows/trade_notification.json >/dev/null`
  - `jq . config/n8n_workflows/ai_decision.json >/dev/null`
- 결과:
  - 두 파일 모두 JSON 문법 통과

### 5.2 테스트 검증
- 실행 명령:
  - 없음 (workflow 템플릿 변경)
- 결과:
  - 해당 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - OCI n8n에서 workflow 반영 후 Trade/AI Decision webhook 테스트
- 결과:
  - 운영 환경 반영 후 확인 필요

---

## 6. 배포/운영 확인 체크리스트(필수)
1) OCI에 최신 코드 pull  
2) n8n `Trade Notification`/`AI Decision Notification` workflow 반영 및 Active ON  
3) 테스트 webhook으로 텍스트/색상 분기 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 알림 스타일 정책을 n8n expression에 직접 반영
- 고려했던 대안:
  1) 현행 유지(이모지 + 고정 색상)
  2) bot payload 단계에서 표현용 필드 생성
  3) n8n 템플릿에서 스타일/색상 처리(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 1은 사용자 요구 불충족
  2) 2는 앱 코드 영향 범위 증가
  3) 3은 변경 범위 최소 + 즉시 반영 가능
- 트레이드오프(단점)와 보완/완화:
  1) expression 길이 증가로 가독성 저하
  2) 호환성 확보를 위해 최신 JS 문법을 쓰지 못함
  3) 공통 템플릿화(후속 과제)로 완화 가능

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) 코드 주석 대상 없음(JSON expression 변경)
  2) 문서에 의도/fallback/색상 정책 명시
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - fallback 불변조건
  - 색상 분기 규칙

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 이모지 제거
  - AI Decision CONFIRM/REJECT 색상 분기
  - 추적 문서 반영
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - Repo 템플릿 기준 알림 스타일/색상 정책 반영 완료
  - n8n parser 호환 expression으로 `invalid syntax` 리스크 완화
- 후속 작업(다음 plan 번호로 넘길 것):
  1) risk/daily workflow에도 동일 스타일 규칙 적용 검토
  2) workflow JSON 반영 자동 점검 스크립트 검토

---

## 12. References
- `docs/work-plans/18-18_notification_emoji_removal_and_ai_decision_color_split_plan.md`
- `docs/troubleshooting/18-18_notification_style_and_decision_color.md`
- `config/n8n_workflows/trade_notification.json`
- `config/n8n_workflows/ai_decision.json`
