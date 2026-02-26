# 18-17. Trade Notification payload fallback + BUY/SELL 색상 분기 구현 결과

작성일: 2026-02-26  
작성자: Codex (GPT-5)  
관련 계획서: `docs/work-plans/18-17_trade_notification_payload_fallback_and_color_split_plan.md`  
상태: Verified  
완료 범위: Phase 1  
선반영/추가 구현: 없음  
관련 트러블슈팅(있다면): `docs/troubleshooting/18-17_trade_notification_quantity_blank.md`

---

## 1. 개요
- 구현 범위 요약:
  - n8n Trade Notification expression에서 payload fallback 보강 및 color 분기 추가
- 목표(요약):
  - Discord 체결 알림에서 `Quantity` 누락을 방지하고 BUY/SELL 가시성 강화
- 이번 구현이 해결한 문제(한 줄):
  - `$json`/`$json.body` 경로 차이로 발생하던 Quantity 공백 표시 문제 완화

---

## 2. 구현 내용(핵심 위주)
### 2.1 Trade Notification expression 강건화
- 파일/모듈: `config/n8n_workflows/trade_notification.json`
- 변경 내용:
  - 기존 단순 참조(`$json.side`, `$json.quantity`) 기반 expression을 IIFE 기반 안전 파서로 교체
  - 필드 fallback:
    - `side`: `body.side -> $json.side -> body.action -> $json.action -> "-" `
    - `quantity`: `body.qty -> body.quantity -> $json.qty -> $json.quantity -> "-" `
    - `price/symbol/timestamp/reason`도 동일한 안전 fallback 적용
- 효과/의미:
  - 실행 컨텍스트별 payload 경로 차이에도 값 누락 가능성 감소

### 2.2 BUY/SELL 색상 분기 반영
- 파일/모듈: `config/n8n_workflows/trade_notification.json`
- 변경 내용:
  - BUY: green(`5763719`), SELL: red(`15548997`), 기타: gray(`9807270`)
  - title icon도 BUY/SELL/기타에 맞춰 `🟢/🔴/⚪` 분기
- 효과/의미:
  - 체결 방향을 Discord에서 즉시 식별 가능

---

## 3. 변경 파일 목록
### 3.1 수정
1) `config/n8n_workflows/trade_notification.json`  
2) `docs/PROJECT_CHARTER.md`

### 3.2 신규
1) `docs/work-plans/18-17_trade_notification_payload_fallback_and_color_split_plan.md`  
2) `docs/work-result/18-17_trade_notification_payload_fallback_and_color_split_result.md`  
3) `docs/troubleshooting/18-17_trade_notification_quantity_blank.md`

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: workflow expression을 이전 값으로 복원

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `jq . config/n8n_workflows/trade_notification.json >/dev/null`
- 결과:
  - JSON 문법 검증 통과

### 5.2 테스트 검증
- 실행 명령:
  - 없음 (n8n workflow 템플릿 변경)
- 결과:
  - 해당 없음

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법(healthcheck, curl, kubectl 등):
  - OCI n8n UI에서 workflow expression 반영 후 webhook 테스트
- 결과:
  - 사용자 운영 환경에서 확인 필요

---

## 6. 배포/운영 확인 체크리스트(필수)
1) OCI에 최신 코드 pull  
2) n8n `Trade Notification` workflow에 JSON 반영(Import/수동 반영)  
3) BUY/SELL webhook 테스트 후 Discord `Price/Quantity` 표시 확인

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - n8n expression 내부에서 payload 경로 fallback + 표시 분기 처리
- 고려했던 대안:
  1) bot payload를 단일 schema로 강제(앱 코드 수정)
  2) n8n 중간 Set/Code 노드로 normalize 후 Discord 전송
  3) Discord node expression 자체를 강건화(채택)
- 대안 대비 실제 이점(근거/관측 포함):
  1) 1은 봇 배포/검증 범위가 커짐
  2) 2는 n8n 워크플로우 복잡도 증가
  3) 3은 변경 범위가 가장 작고 즉시 반영 가능
- 트레이드오프(단점)와 보완/완화:
  1) expression 길이가 길어져 가독성 저하
  2) 추후 공통 표현식 템플릿화 필요

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) 코드 주석 대상 없음(JSON expression 변경 작업)
  2) 대신 plan/result/troubleshooting 문서에 fallback 의도와 실패 모드 명시
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 엣지 케이스(`qty`/`quantity`, `$json`/`$json.body`)
  - 실패 시 기본값 처리(`"-"`)

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - payload fallback 보강
  - BUY/SELL 색상 분기 반영
  - 추적 문서(Plan/Result/Troubleshooting) 작성
- 변경/추가된 부분(왜 바뀌었는지):
  - 없음
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - Repo workflow 템플릿 기준으로 Quantity 공백 리스크를 줄이는 패치 완료
- 후속 작업(다음 plan 번호로 넘길 것):
  1) ai/risk/daily workflow도 동일 fallback 표준 적용 검토
  2) webhook payload contract 회귀 테스트 자동화 검토

---

## 12. References
- `docs/work-plans/18-17_trade_notification_payload_fallback_and_color_split_plan.md`
- `docs/troubleshooting/18-17_trade_notification_quantity_blank.md`
- `config/n8n_workflows/trade_notification.json`
