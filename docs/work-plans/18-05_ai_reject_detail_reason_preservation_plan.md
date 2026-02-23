# 18-05. AI REJECT 상세 Reason 보존 작업 계획

**작성일**: 2026-02-23  
**작성자**: Codex (GPT-5)  
**상태**: Verified  
**관련 계획 문서**: `docs/work-plans/18_cloud_migration_cost_optimized_deployment_plan.md`, `docs/work-plans/18-04_ai_reject_reason_koreanization_plan.md`

---

## 0. 트리거(Why started)
- 운영 알림에서 AI REJECT 사유가 한 줄 고정 문구로 표시되어 기존의 상세 분석 근거가 사라짐.
- 사용자 노출 메시지의 해석 가능성이 저하되어 운영 판단 품질에 직접 영향.

## 1. 문제 요약
- 증상:
  - `Analyst reasoning violated rule boundary after retry ...`(또는 한국어 치환 문구)만 표시되고 상세 근거 미노출.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 주문 차단 자체는 정상.
  - 운영: REJECT 사유의 설명력이 급감하여 대응 난이도 상승.
  - 데이터/비용: 추가 영향 없음.
- 재현 조건:
  - Analyst가 Rule boundary 재검증 문구를 포함해 2회 연속 감지되는 강제 REJECT 경로.

## 2. 원인 분석
- 가설:
  1) 강제 REJECT 경로에서 `reasoning`을 고정 문자열로 덮어씀.
- 조사 과정:
  - `src/agents/analyst.py`에서 재시도 후 REJECT 반환 경로 점검.
  - `src/agents/runner.py`에서 Discord 페이로드가 `reason` 필드를 그대로 전달하는지 확인.
- Root cause:
  - 강제 REJECT 분기에서 모델의 원본 reasoning을 버리고 단문 고정 사유를 사용.

## 3. 대응 전략
- 단기 핫픽스:
  - 강제 REJECT 시에도 원본 reasoning을 함께 포함해 상세성을 유지.
- 근본 해결:
  - "정책 사유(룰 경계 위반) + 원본 분석 근거" 병기 포맷 정착.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - REJECT 판단 로직은 그대로 유지(차단 강도 변경 없음).

## 4. 구현/수정 내용
- 변경 파일:
  - `src/agents/analyst.py`
  - `tests/agents/test_analyst_rule_boundary.py`
- DB 변경(있다면):
  - 없음
- 주의점:
  - Reason 길이는 기존 Discord 전송 상한(1500자) 정책을 준수.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - 강제 REJECT 경로에서도 원본 상세 reasoning이 Reason에 포함되는지 확인.
- 회귀 테스트:
  - analyst rule boundary 테스트 통과.
- 운영 체크:
  - bot 재기동 후 AI Decision 알림에서 REJECT 본문 상세성 확인.

## 6. 롤백
- 코드 롤백:
  - `src/agents/analyst.py` 해당 helper/return 구문 원복.
- 데이터/스키마 롤백:
  - 없음.

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 결과서 작성.
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 정책 정의 변경 없음(표현/가독성 개선), 업데이트 불필요.

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) 알림 포맷 검증을 위한 n8n 샘플 payload 회귀 테스트 스크립트 추가.
  2) REJECT 사유 템플릿 표준화(운영/개발 분리).
