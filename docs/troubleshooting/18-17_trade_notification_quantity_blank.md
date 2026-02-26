# 18-17. Trade Notification Quantity 공백 표시 트러블슈팅 / 핫픽스

작성일: 2026-02-26  
상태: Fixed  
우선순위: P1  
관련 문서:
- Plan: `docs/work-plans/18-17_trade_notification_payload_fallback_and_color_split_plan.md`
- Result: `docs/work-result/18-17_trade_notification_payload_fallback_and_color_split_result.md`
- Charter update 필요: YES

---

## 1. 트리거(왜 시작했나)
- Discord 체결 알림에서 BUY 이벤트의 `Quantity`가 `-`로 표시되는 사례가 보고됐다.
- 운영자가 실제 체결 여부를 오판할 수 있어 즉시 보정이 필요했다.

---

## 2. 증상/영향
- 증상:
  - `Trade Executed: BUY` 메시지에서 `Quantity` 필드가 비어 보임
  - 알림 템플릿에 따라 가격/수량 표기 일관성이 떨어짐
- 영향(리스크/데이터/비용/운영):
  - 운영 모니터링 신뢰도 저하
  - 실제 체결 확인을 DB/로그로 역추적해야 하는 운영비용 증가
- 발생 조건/재현 조건:
  - n8n webhook 입력 경로가 `$json.body.*` 또는 `$json.*` 중 한쪽으로만 들어오는 실행 컨텍스트

---

## 3. 재현/관측 정보
- 재현 절차:
  1) BUY 체결 이벤트 발생
  2) Discord Trade Notification 확인
  3) Quantity 값이 `-` 표시되는지 확인
- 입력/데이터:
  - bot payload: `{symbol, side, price, quantity, ...}`
  - n8n expression: `$json` 기준 참조(기존)
- 핵심 로그/에러 메시지:
  - expression 오류는 없으나 값 경로 불일치로 `-` 노출
- 관련 지표/대시보드(있다면):
  - 없음

---

## 4. 원인 분석
- 가설 목록:
  1) bot가 `quantity`를 보내지 않는다
  2) n8n이 `$json.body.quantity`로만 값을 전달한다
  3) n8n expression이 payload 경로 변화를 흡수하지 못한다
- 조사 과정(무엇을 확인했는지):
  - `src/engine/executor.py`에서 webhook 전송 필드 확인
  - `config/n8n_workflows/trade_notification.json`에서 Discord expression 확인
- Root cause(결론):
  - n8n expression의 필드 참조가 단일 경로 중심이라 실행 컨텍스트 차이에서 값 누락 발생

---

## 5. 해결 전략
- 단기 핫픽스:
  - Discord expression을 다중 fallback(`$json.body` + `$json`)으로 보강
- 근본 해결:
  - `side/action`, `qty/quantity`, `timestamp`를 모두 안전 fallback 처리
  - BUY/SELL/기타 상태별 색상 분기 적용
- 안전장치(feature flag, rate limit, timeout/cooldown, circuit breaker 등):
  - 값 누락 시 expression 실패 대신 `"-"` 기본값 노출

---

## 6. 수정 내용
- 변경 요약:
  - Trade Notification expression을 IIFE 기반 안전 파싱으로 교체
  - BUY/SELL/기타 색상 분기 추가
- 변경 파일:
  - `config/n8n_workflows/trade_notification.json`
- DB/스키마 변경(있다면):
  - 없음
- 롤백 방법(필수):
  - 해당 JSON의 expression을 이전 버전으로 복원

---

## 7. 검증
- 실행 명령/절차:
  - `jq . config/n8n_workflows/trade_notification.json >/dev/null`
  - n8n UI에서 `Trade Notification` workflow 업데이트/활성화 후 BUY/SELL 테스트 webhook 호출
- 결과:
  - JSON 문법 검증 통과
  - 운영 환경 테스트 필요(OCI n8n 반영 후 확인)

- 운영 확인 체크:
  1) BUY 알림에 Quantity 실제 값 표기 확인
  2) SELL 알림이 빨간색(`15548997`)으로 표기되는지 확인

---

## 8. 재발 방지
- 가드레일(테스트/알림/검증 스크립트/권한/필터/타임아웃 등):
  - webhook payload contract 변경 시 `$json/$json.body` 혼용 대응 템플릿 사용
- 문서 반영:
  - plan/result 업데이트 여부: YES
  - troubleshooting 링크 추가 여부: YES
  - PROJECT_CHARTER.md 변경(있다면): 8.5 참고 목록/8.9 changelog에 18-17 반영

---

## 9. References
- `docs/work-plans/18-17_trade_notification_payload_fallback_and_color_split_plan.md`
- `config/n8n_workflows/trade_notification.json`
- `docs/work-result/18-17_trade_notification_payload_fallback_and_color_split_result.md`

## 10. 배운점
- 알림 계층은 "전송 성공"만으로 충분하지 않고 "필드 매핑 정합성"까지 검증해야 한다.
- 포트폴리오에서는 payload 경로 불일치 문제를 재현하고 fallback 설계로 복원한 점을 강조할 수 있다.
- 운영 관점에서 webhook schema drift 대응 능력이 향상됐다.
