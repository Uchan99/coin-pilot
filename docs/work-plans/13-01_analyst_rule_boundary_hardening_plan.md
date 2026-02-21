# 13-01. Analyst Rule Boundary Hardening 작업 계획

**작성일**: 2026-02-21  
**작성자**: Codex  
**상태**: Fixed  
**관련 계획 문서**: `docs/work-plans/13_strategy_regime_reliability_plan.md`  

---

## 0. 트리거(Why started)
- 운영 알림에서 `AI REJECT` 사유가 Rule Engine 검증 항목(RSI/MA/거래량)을 반복 언급하는 현상이 재확인됨.
- 이로 인해 Rule Engine 통과 신호가 AI 단계에서 중복 보수화되어 체결 기회 손실과 판단 근거 일관성 저하가 발생함.

## 1. 문제 요약
- 증상:
  - Analyst reasoning에 RSI, MA20, 거래량 부족 등의 재검증 근거가 반복적으로 포함됨.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: Rule Engine/AI 역할 분리 원칙 위반.
  - 리스크: 강제 REJECT(Confidence < 60)와 결합되어 과거절 가능성 확대.
  - 비용: 불필요한 AI 호출 및 저품질 추론 누적.
- 재현 조건:
  - SIDEWAYS/BEAR에서 진입 후보가 생성되어 AI Analyst가 호출될 때 재현 가능.

## 2. 원인 분석
- 가설:
  - 프롬프트 템플릿과 원시 입력 전달 구조가 Rule Engine 검증 지표를 Analyst에 그대로 노출해 재검증을 유도한다.
- 조사 과정:
  - `src/agents/prompts.py`, `src/agents/analyst.py`, `src/agents/runner.py` 검토.
  - 운영 로그 샘플에서 RSI/MA/거래량 재근거 문구 확인.
- Root cause:
  - 역할 분리 지시(system prompt)와 충돌되는 입력 구성(user prompt + raw indicators 전달)으로 인해 모델이 정책과 달리 중복 판단함.

## 3. 대응 전략
- 단기 핫픽스:
  - Analyst 입력에서 Rule Engine 검증 지표 직접 노출을 제거하고 캔들 패턴 전용 요약 피처 중심으로 변경.
- 근본 해결:
  - reasoning에 Rule Engine 재검증 단서가 포함되면 1회 재시도 후, 재발 시 정책 위반으로 보수 REJECT 처리하는 경계 검증 로직 추가.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 기존 timeout/reject 정책은 유지하고, Analyst 출력 품질 가드레일만 추가.

## 4. 구현/수정 내용
- 변경 파일:
  - `src/agents/prompts.py`
  - `src/agents/analyst.py`
  - `tests/agents/test_analyst_rule_boundary.py` (신규)
- DB 변경(있다면):
  - 없음.
- 주의점:
  - 기존 전략/리스크 규칙 정의는 변경하지 않음.
  - 프롬프트 입력 축소에 따른 판단 품질 저하가 없는지 테스트와 로그로 확인.

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - Analyst 프롬프트 본문에서 RSI/MA/거래량 직접 검증 지시/필드가 제거되었는지 확인.
  - Rule 재검증 근거가 포함된 reasoning에 대해 재시도/차단 로직 동작 확인.
- 회귀 테스트:
  - 에이전트 관련 단위 테스트 + 신규 경계 테스트 통과.
- 운영 체크:
  - 배포 후 `agent_decisions.reasoning`에서 Rule 중복 키워드 비율 추적.

## 6. 롤백
- 코드 롤백:
  - 본 작업 커밋 되돌림으로 즉시 복구 가능.
- 데이터/스키마 롤백:
  - 해당 없음.

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획서 + 대응 결과서 작성.
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 불필요. 기존 Charter의 역할 분리 원칙을 구현 레벨에서 정합화하는 작업임.

## 8. 설계/아키텍처 선택 근거
- 최종 선택:
  - 입력 최소화(캔들 패턴 전용) + 출력 경계 검증(재시도 1회) 이중 방어.
- 고려 대안:
  1. 프롬프트 문구만 강화하고 입력은 그대로 유지.
  2. 모델을 Sonnet 고정으로 상향해 추론 품질로 해결.
  3. Critic Agent를 추가해 2차 규칙 위반 판정.
  4. 입력 축소 + 경계 검증(선택안).
- 대안 비교:
  - 1은 구조적 원인(입력 과노출)을 제거하지 못함.
  - 2는 비용 증가 대비 문제 재발 가능성이 남음.
  - 3은 복잡도/지연/비용 증가가 큼.
  - 4는 가장 작은 변경으로 재발 확률을 실질적으로 낮춤.

## 9. 후속 조치
- 운영 24~72시간 관찰 후, 필요 시 forbidden 패턴 정밀화(오탐/미탐 조정).
- 레짐별 AI REJECT 품질 지표(중복 검증 비율, 평균 confidence) 대시보드화 검토.

## 10. 변경 이력
- 2026-02-21:
  - 테스트 실행성 개선을 위해 `pytest.ini`에 `pythonpath = .` 반영 항목 추가.
  - 배경: `.venv` 환경에서 `pytest` 엔트리포인트 실행 시 `src` 모듈 import 실패 재현.
