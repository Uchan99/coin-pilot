# 18-18. 알림 이모지 제거 및 AI Decision CONFIRM/REJECT 색상 분기 계획

**작성일**: 2026-02-26  
**작성자**: Codex (GPT-5)  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/18-17_trade_notification_payload_fallback_and_color_split_plan.md`  
**승인 정보**: 사용자 채팅 승인 / 2026-02-26 / "수정하고 json파일도 바꿔줘", "Decision도 confime이랑 reject 색상 다르게... 이모지는 다 제외"

---

## 0. 트리거(Why started)
- 사용자가 Discord 알림 포맷에서 이모지 제거를 요청했고, AI Decision 알림은 CONFIRM/REJECT를 색상으로 명확히 구분하고 싶다고 요청했다.

## 1. 문제 요약
- 증상:
  - Trade/AI Decision 알림에 이모지가 포함되어 운영 채널 스타일과 맞지 않음
  - AI Decision 색상이 REJECT 기준으로 고정되어 CONFIRM/REJECT 직관적 구분이 어려움
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 알림 시각적 구분성/일관성 저하
  - 리스크: 운영자가 알림 우선순위를 빠르게 구분하기 어려움
  - 데이터: 없음(표시 포맷 문제)
  - 비용: 모니터링 피로 증가
- 재현 조건:
  - 현재 n8n workflow JSON 기본 템플릿 사용 시

## 2. 원인 분석
- 가설:
  - 알림 템플릿이 초기 디자인(이모지 기반)에서 업데이트되지 않음
- 조사 과정:
  - `config/n8n_workflows/trade_notification.json` value expression 확인
  - `config/n8n_workflows/ai_decision.json` value expression 확인
- Root cause:
  - 표현식에서 title/field name에 이모지가 하드코딩되어 있고, AI Decision color가 decision 상태와 무관하게 고정

## 3. 대응 전략
- 단기 핫픽스:
  - Trade/AI Decision 템플릿에서 이모지 제거
  - AI Decision color를 decision 값에 따라 분기
- 근본 해결:
  - 알림 템플릿을 경량 텍스트 기반 표준으로 통일
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 기존 payload fallback(`$json.body`/`$json`) 유지
  - 누락 값은 `"-"` 기본값으로 안전 처리

## 4. 구현/수정 내용
- 변경 파일:
  - `config/n8n_workflows/trade_notification.json`
  - `config/n8n_workflows/ai_decision.json`
  - `docs/troubleshooting/18-18_notification_style_and_decision_color.md`
  - `docs/work-result/18-18_notification_emoji_removal_and_ai_decision_color_split_result.md`
  - `docs/PROJECT_CHARTER.md`
- DB 변경(있다면):
  - 없음
- 주의점:
  - repo JSON 변경 후 OCI n8n workflow 동기화 필요

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - Trade/AI Decision 알림에서 이모지 미표시 확인
  - AI Decision CONFIRM/REJECT 각각 색상 분기 확인
- 회귀 테스트:
  - 기존 필드(symbol/price/quantity/confidence/reason) 출력 유지
- 운영 체크:
  - BUY, SELL, CONFIRM, REJECT 샘플 webhook 테스트

## 6. 롤백
- 코드 롤백:
  - 해당 JSON의 value expression 이전 버전 복원
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 18-18 plan/result/troubleshooting 생성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 필요(8.5 문서 참고 + 8.9 changelog)

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) n8n workflow 템플릿 스타일 가이드(텍스트/색상/필드명) 문서화
  2) workflow JSON 반영 후 자동 스모크 테스트 스크립트 검토

## 9. 아키텍처 선택/대안/트레이드오프
- 최종 선택:
  - 표현식 레벨 스타일 통일 + decision 기반 color 분기
- 대안:
  1) 현행 유지(이모지 + 고정 색상)
  2) n8n UI 수동 편집만 수행(Repo 미반영)
  3) Repo JSON 표준 반영 + 운영 반영(채택)
- 채택 이유:
  - 1은 사용자 요구 불충족
  - 2는 드리프트 재발 가능성 높음
  - 3은 버전관리/재현성 확보

## 10. 계획 변경 이력
- 2026-02-26 (초기): 이모지 제거 + AI Decision 색상 분기 범위로 승인
- 2026-02-26 (확장): 운영 n8n 파서 호환성을 고려해 화살표 함수/`const`/`??` 사용 표현식을 순수 ternary 기반 expression으로 재작성
