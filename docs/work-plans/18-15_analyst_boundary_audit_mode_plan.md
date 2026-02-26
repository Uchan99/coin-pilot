# 18-15. Analyst Rule Boundary Audit Mode 전환 계획

**작성일**: 2026-02-26  
**작성자**: Codex (GPT-5)  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/18-02_ai_model_404_and_notification_reliability_plan.md`, `docs/work-plans/18-06_ai_decision_confidence_field_restore_plan.md`  
**승인 정보**: 사용자 채팅 승인(2026-02-26, 경계 위반 강제 REJECT/재시도 제거 + audit 기록 전환 요청)

---

## 0. 트리거(Why started)
- 최근 AI Decision 다수에서 `분석가 응답이 재시도 후에도 룰 경계를 위반... REJECT`가 반복됨.
- 사용자 관측 기준 최근 10건이 모두 경계 위반 경로로 REJECT되어, 실제 전략 신호 품질과 무관하게 호출 비용/지연/거절 노이즈가 증가함.

## 1. 문제 요약
- 증상:
  - Analyst 응답에서 Rule Engine 영역 단어가 포함되면 재시도 후 강제 REJECT
  - `confidence=0` 거절이 반복되어 운영 판단 신뢰도 저하
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: 유효 신호까지 차단될 가능성
  - 리스크: 진입 기회 손실 + 판단 흐름 왜곡
  - 데이터: REJECT 사유 분포가 "경계 위반"으로 편향
  - 비용: 재시도 호출로 LLM credit 추가 소모
- 재현 조건:
  - Analyst reasoning에 `RSI/MA20/거래량/볼린저` 등 키워드 포함 시

## 2. 원인 분석
- 가설:
  - 키워드 기반 경계 검사와 재시도 강제정책이 과도하게 엄격
- 조사 과정:
  - `src/agents/analyst.py` 경계 검사/재시도/강제 REJECT 경로 확인
  - `src/agents/prompts.py`에서 프롬프트 금지 지시가 있어도 응답에서 재판단이 발생함을 확인
- Root cause:
  - 프롬프트 제약은 확률적이며 100% 강제되지 않는데, 경계 위반 처리 정책은 하드 차단(재시도+REJECT)이라 운영 비용/오탐을 증폭

## 3. 대응 전략
- 단기 핫픽스:
  - 경계 위반 시 재시도 제거(단일 호출)
  - 경계 위반 시 강제 REJECT 제거
- 근본 해결:
  - Boundary 정책을 `enforce`에서 `audit`으로 전환
  - 경계 위반은 판단 차단 대신 `reasoning`/로그에 감사 태그로 기록
  - 프롬프트를 강화하되, 위반 발생 자체는 관측 지표로 관리
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - 기존 `confidence < 60 => REJECT` 정책 유지
  - Timeout/파싱 실패 시 보수적 REJECT 유지

## 4. 구현/수정 내용
- 변경 파일:
  - `src/agents/analyst.py`
  - `src/agents/prompts.py`
  - `src/agents/runner.py`
  - `tests/agents/test_analyst_rule_boundary.py`
  - `docs/troubleshooting/18-15_analyst_rule_boundary_false_rejects.md` (신규)
  - `docs/work-result/18-15_analyst_boundary_audit_mode_result.md` (신규)
- DB 변경(있다면):
  - 없음(기존 `reasoning` 텍스트에 boundary audit 태그 기록)
- 주의점:
  - Rule Engine 재판단 흔적은 "허용"하지만 "관측"은 계속 유지
  - 차단 기준은 RiskManager + confidence + timeout/exception에 집중

## 5. 검증 기준
- 재현 케이스에서 해결 확인:
  - 경계 위반 단어가 포함돼도 즉시 REJECT되지 않고 일반 의사결정 경로 유지
  - 재시도 호출이 사라졌는지 확인
- 회귀 테스트:
  - 파싱 실패/타임아웃 REJECT 경로 정상 동작
  - confidence<60 강제 REJECT 정책 유지
- 운영 체크:
  - boundary audit 태그가 Discord/DB reasoning에 남는지 확인

## 6. 롤백
- 코드 롤백:
  - `analyst.py`, `prompts.py`, `runner.py` 변경 revert
- 데이터/스키마 롤백:
  - 없음

## 7. 문서 반영
- work-plan/work-result 업데이트:
  - 18-15 plan/result 생성 및 상호 링크
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 필요(18-15 계획/결과/트러블슈팅 링크 + changelog 추가)

## 8. 후속 조치
- 다음에 유사 문제 방지를 위한 작업:
  1) boundary audit 비율 지표화(예: 24h 비율)
  2) 필요 시 boundary 탐지 로직을 "언급"과 "재판단(임계치 판정)"으로 분리 정교화

## 9. 아키텍처 선택/대안/트레이드오프
- 최종 선택:
  - **Prompt 강화 + Boundary audit 모드 + 재시도 제거**
- 대안:
  1) 기존 유지(재시도+강제 REJECT)
  2) 경계 검사 완전 비활성화
  3) Sonnet 업그레이드로 모델 품질로만 해결
  4) audit 모드 전환(채택)
- 채택 이유:
  - 1은 비용/오탐 문제 지속
  - 2는 관측성 상실
  - 3은 비용 증가 대비 정책 문제를 직접 해결하지 못함
  - 4는 비용/안정성/관측성을 균형 있게 충족

