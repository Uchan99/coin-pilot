# 18-06. AI Decision Confidence 필드 복구 작업 계획

**작성일**: 2026-02-23  
**작성자**: Codex (GPT-5)  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`

---

## 0. 트리거(Why started)
- Discord AI Decision 메시지에서 기존에 보이던 `Confidence` 항목이 사라짐.
- 운영자가 REJECT/CONFIRM 판단 강도를 즉시 파악하기 어려워짐.

## 1. 문제 요약
- 증상:
  - AI Decision embed fields에 Symbol/Regime/RSI만 출력되고 Confidence 미출력.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능/주문 로직 영향 없음.
  - 운영 가시성 저하(판단 신뢰도 확인 불가).
- 재현 조건:
  - n8n `AI Decision Notification` 워크플로우 실행 시.

## 2. 원인 분석
- 가설:
  1) n8n HTTP Request node의 embeds fields 정의에서 confidence 필드 제거.
- 조사 과정:
  - `config/n8n_workflows/ai_decision.json` 점검.
  - `src/agents/runner.py`에서 confidence 페이로드 송신 확인.
- Root cause:
  - 워크플로우 템플릿에서 embed field 누락.

## 3. 대응 전략
- 단기 핫픽스:
  - `ai_decision.json` embeds fields에 Confidence 항목 복구.
- 근본 해결:
  - 워크플로우 포맷 변경 시 핵심 필드(심볼/레짐/RSI/신뢰도) 체크리스트화.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 없음(표시 계층 수정).

## 4. 구현/수정 내용
- 변경 파일:
  - `config/n8n_workflows/ai_decision.json`
- DB 변경(있다면):
  - 없음
- 주의점:
  - JSON escaping 유지 및 n8n import 호환성 확인.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - AI Decision 알림에 Confidence 필드가 출력되는지 확인.
- 회귀 테스트:
  - JSON 파싱 검증(`jq`).
- 운영 체크:
  - n8n UI 반영 후 테스트 webhook 실행.

## 6. 롤백
- 코드 롤백:
  - 해당 field 추가 변경 되돌림.
- 데이터/스키마 롤백:
  - 없음.

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 및 결과서 작성.
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 운영 정책 변경 없음, 업데이트 불필요.

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) n8n 워크플로우 필수 필드 검증 스크립트 도입 검토.
