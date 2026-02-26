# 18-17. Trade Notification payload fallback + BUY/SELL 색상 분기 계획

**작성일**: 2026-02-26  
**작성자**: Codex (GPT-5)  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/18-11_n8n_backup_automation_plan.md`  
**승인 정보**: 사용자 채팅 승인 / 2026-02-26 / "수정부탁해."

---

## 0. 트리거(Why started)
- Discord `Trade Executed: BUY` 알림에서 `Quantity`가 `-`로 표시되는 사례가 운영 중 확인되었다.
- 동일 이벤트에서 가격 포맷이 기존 템플릿과 다르게 보여, n8n webhook payload 경로(`$json` vs `$json.body`) 불일치 가능성이 제기되었다.

## 1. 문제 요약
- 증상:
  - 체결 이벤트는 발생했는데 Discord 알림의 `Quantity`가 빈값/`-`로 표시됨
  - 템플릿별로 `BUY/SELL` 시각적 구분(color/title) 일관성이 약함
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 알림 가독성 저하, 운영자 오판 가능성 증가
  - 리스크: 실제 체결 수량 누락으로 체결 상태 추적 난이도 증가
  - 데이터: 거래 DB 자체는 정상일 가능성이 높음(표시 계층 문제)
  - 비용: 조사/확인 시간 증가
- 재현 조건:
  - n8n Webhook 입력 구조가 환경/노드 버전에 따라 `$json.body.*` 또는 `$json.*`로 달라지는 경우

## 2. 원인 분석
- 가설:
  - Discord Webhook 노드 expression이 특정 경로만 참조하여 필드 누락 발생
- 조사 과정:
  - `src/engine/executor.py`의 webhook payload 키(`symbol`, `side`, `price`, `quantity`) 확인
  - `config/n8n_workflows/trade_notification.json`의 expression 참조 키 확인
- Root cause:
  - n8n 실행 컨텍스트 차이로 인해 입력 경로가 달라질 때 fallback이 부족하면 `quantity`가 비어 보일 수 있음

## 3. 대응 전략
- 단기 핫픽스:
  - trade notification expression을 `$json.body`/`$json` 동시 fallback 형태로 보강
- 근본 해결:
  - `side/action`, `qty/quantity`, `timestamp` 등 다중 키를 안전 매핑
  - BUY/SELL/기타에 따른 title icon + color 분기 일관화
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 누락 값은 `"-"`로 처리해 expression 실패 대신 정상 전송 유지

## 4. 구현/수정 내용
- 변경 파일:
  - `config/n8n_workflows/trade_notification.json`
  - `docs/troubleshooting/18-17_trade_notification_quantity_blank.md`
  - `docs/work-result/18-17_trade_notification_payload_fallback_and_color_split_result.md`
  - `docs/PROJECT_CHARTER.md`
- DB 변경(있다면):
  - 없음
- 주의점:
  - repo JSON 반영 후 OCI n8n UI에 workflow import/동기화가 필요할 수 있음

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - BUY 체결 알림에서 `Quantity`가 `-`가 아닌 실제 값으로 노출되는지 확인
- 회귀 테스트:
  - SELL 체결 알림도 동일 템플릿으로 정상 노출되는지 확인
- 운영 체크:
  - n8n Test execution payload 경로 변화(`$json`/`$json.body`)에 관계없이 필드 출력

## 6. 롤백
- 코드 롤백:
  - `config/n8n_workflows/trade_notification.json`의 expression을 이전 버전으로 복원
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 18-17 plan/result/troubleshooting 문서 신규 작성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 필요 (8.5 문서 참고 목록 + 8.9 changelog 반영)

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) 나머지 n8n workflow(예: ai/risk/daily)도 동일 fallback 템플릿 정책 적용 검토
  2) webhook payload contract 테스트 스크립트 도입 검토

## 9. 아키텍처 선택/대안/트레이드오프
- 최종 선택:
  - n8n expression 레벨에서 다중 경로 fallback + color 분기 처리
- 대안:
  1) bot payload를 n8n 친화 포맷으로 단일화(코드 변경)
  2) n8n 중간 Set 노드 추가로 정규화 후 Discord 전송
  3) Discord Webhook expression 자체를 강건화(채택)
- 채택 이유:
  - 1은 앱 배포와 연계되어 영향 범위가 큼
  - 2는 n8n UI 수동 변경 포인트가 늘어 관리 복잡도 증가
  - 3은 변경 범위가 최소이고 즉시 재현 문제를 해결 가능

## 10. 계획 변경 이력
- 2026-02-26 (초기): trade 알림 필드 fallback + BUY/SELL color 분기 반영 범위로 승인
