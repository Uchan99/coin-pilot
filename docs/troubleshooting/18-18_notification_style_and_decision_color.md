# 18-18. 알림 스타일(이모지 제거) 및 AI Decision 색상 분기 트러블슈팅 / 핫픽스

작성일: 2026-02-26  
상태: Fixed  
우선순위: P2  
관련 문서:
- Plan: `docs/work-plans/18-18_notification_emoji_removal_and_ai_decision_color_split_plan.md`
- Result: `docs/work-result/18-18_notification_emoji_removal_and_ai_decision_color_split_result.md`
- Charter update 필요: YES

---

## 1. 트리거(왜 시작했나)
- 운영 채널에서 알림 스타일 단순화 요구가 발생했다.
- Trade/AI Decision 메시지의 이모지를 제거하고, AI Decision은 CONFIRM/REJECT를 색상으로 구분하라는 요청이 있었다.

---

## 2. 증상/영향
- 증상:
  - 알림에 이모지가 포함되어 운영 채널 톤과 불일치
  - AI Decision이 상태와 관계없이 고정 색상으로 표시됨
- 영향(리스크/데이터/비용/운영):
  - 가독성/일관성 저하
  - 이벤트 우선순위 판단 속도 저하
- 발생 조건/재현 조건:
  - 기본 workflow 템플릿 사용 시 반복 발생

---

## 3. 재현/관측 정보
- 재현 절차:
  1) Trade webhook 이벤트 송신
  2) AI Decision webhook 이벤트 송신
  3) Discord 메시지 title/field의 이모지 및 색상 확인
- 입력/데이터:
  - webhook payload: trade(`side`, `price`, `quantity`), ai(`decision`, `confidence`, `reason`)
- 핵심 로그/에러 메시지:
  - 예외/오류 없음(표현 포맷 개선 이슈)
- 관련 지표/대시보드(있다면):
  - 없음

---

## 4. 원인 분석
- 가설 목록:
  1) 템플릿이 초기 UI 스타일(이모지 중심)로 고정
  2) AI Decision expression이 decision 상태를 color 매핑하지 않음
  3) n8n payload 경로 차이로 필드 누락 가능성
- 조사 과정(무엇을 확인했는지):
  - `config/n8n_workflows/trade_notification.json` expression 점검
  - `config/n8n_workflows/ai_decision.json` expression 점검
- Root cause(결론):
  - 템플릿 표현식의 스타일/색상 정책이 최신 운영 요구사항을 반영하지 않음

---

## 5. 해결 전략
- 단기 핫픽스:
  - 이모지 제거(Title/Field Name)
  - AI Decision color를 decision 기반으로 분기
- 근본 해결:
  - 텍스트 중심 스타일 표준 유지
  - `$json.body`/`$json` fallback 유지로 실행 컨텍스트 차이 대응
- 안전장치(feature flag, rate limit, timeout/cooldown, circuit breaker 등):
  - 미존재 필드는 `"-"` 기본값
  - 알 수 없는 decision은 중립 색상 사용

---

## 6. 수정 내용
- 변경 요약:
  - Trade/AI Decision 알림 템플릿 스타일 정리 및 color 분기 반영
- 변경 파일:
  - `config/n8n_workflows/trade_notification.json`
  - `config/n8n_workflows/ai_decision.json`
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  - 해당 JSON value expression을 이전 버전으로 복원

---

## 7. 검증
- 실행 명령/절차:
  - `jq . config/n8n_workflows/trade_notification.json >/dev/null`
  - `jq . config/n8n_workflows/ai_decision.json >/dev/null`
- 결과:
  - JSON 문법 유효성 통과

- 운영 확인 체크:
  1) Trade 알림에서 이모지 제거 및 BUY/SELL 색상 확인
  2) AI Decision 알림에서 CONFIRM(녹색)/REJECT(적색) 분기 확인

---

## 8. 재발 방지
- 가드레일(테스트/알림/검증 스크립트/권한/필터/타임아웃 등):
  - n8n workflow 템플릿 스타일 정책 문서화 검토
- 문서 반영:
  - plan/result 업데이트 여부: YES
  - troubleshooting 링크 추가 여부: YES
  - PROJECT_CHARTER.md 변경(있다면): 8.5 목록/8.9 변경 이력 반영

---

## 9. References
- `docs/work-plans/18-18_notification_emoji_removal_and_ai_decision_color_split_plan.md`
- `docs/work-result/18-18_notification_emoji_removal_and_ai_decision_color_split_result.md`
- `config/n8n_workflows/trade_notification.json`
- `config/n8n_workflows/ai_decision.json`

## 10. 배운점
- 알림은 정보 정확성뿐 아니라 운영 채널의 일관된 시각 규칙이 중요하다.
- 트러블슈팅 관점에서 "기능 오류가 아닌 표시 정책 불일치"도 운영 품질 문제로 관리해야 한다.
- JSON 템플릿을 repo source-of-truth로 유지하면 환경 간 드리프트를 줄일 수 있다.
