# 30. 전략 피드백 자동화(Spec-First) 계획

**작성일**: 2026-03-06  
**작성자**: Codex  
**상태**: Approval Pending  
**관련 계획 문서**: `docs/work-plans/15_post_exit_analysis_enhancement_plan.md`, `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`, `docs/work-plans/28_ai_decision_strategy_case_rag_plan.md`, `docs/work-plans/29_regime_transition_strategy_evaluation_and_hotfix_plan.md`  
**승인 정보**: 미승인 (구현/배포 승인 대기)

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 전략 수정 판단이 현재는 수동 해석 중심(Exit analysis, AI Decisions, risk, history)으로 분산되어 있음.
  - Daily Report에 신호는 있으나, Rule Engine 파라미터(진입/익절/손절/레짐)를 체계적으로 피드백하는 자동 루프가 없음.
  - 29번 검증에서 데이터 윈도우/표본 부족 문제가 확인되어, 관측→개선 제안→검증의 자동 체계 필요성이 증가.
- 왜 지금 필요한지:
  - FE/BE 이관(23)보다 전략 품질과 손익 안정성에 직접 영향을 주는 기반 자동화가 우선임.

## 1. 문제 요약
- 증상:
  - 전략 수정 근거가 문서/로그/리포트에 분산되어, 개선 제안이 사람 판단에 과의존.
  - 같은 이슈가 반복되어도 “언제/왜/얼마나 개선됐는지” 추적이 어려움.
  - 레짐 전환 구간에서 진입/청산 정책 적합성을 빠르게 재평가하기 어려움.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: Rule Engine 파라미터 튜닝 주기 지연
  - 리스크: 과보수/과공격 조정 실패로 기회손실 또는 DD 확대
  - 데이터: `trading_history`, `agent_decisions`, `risk_audit`, `llm_usage_events` 활용 비효율
  - 비용: 분석/튜닝 반복 인력비 + 불필요 LLM 호출비 증가
- 재현 조건:
  - 시장 레짐 변화가 빠른 구간, SELL 표본이 아직 작은 구간, 카나리 실험 동시 진행 구간

## 2. 목표 / 비목표
### 2.1 목표
1. 전략 피드백 루프를 자동화: `관측 -> 원인분해 -> 파라미터 제안 -> 백테스트 검증 -> 승인 배포`
2. Rule Engine 핵심 항목(레짐 임계값, 진입 필터, TP/SL/트레일링)별 영향도를 정량화
3. “자동 수정”이 아니라 “자동 제안 + 사람 승인” 운영 표준 확정
4. 추후 28번 RAG와 결합 가능한 근거 데이터 계약(spec) 확정

### 2.2 비목표
1. 본 계획에서 무인 자동 배포/무인 자동 파라미터 변경은 수행하지 않음
2. 본 계획에서 LLM 모델 교체/카나리 최종 확정은 다루지 않음(21-03)
3. 본 계획에서 FE/BE 구조 변경은 수행하지 않음(22/23)

## 3. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **Spec-First + Human-in-the-loop** (자동 분석/제안, 수동 승인 배포)

- 고려 대안:
  1) 현행 유지(수동 분석/수동 수정)
  2) 완전 자동 파라미터 튜닝/자동 배포
  3) 자동 분석+자동 제안+수동 승인(채택)

- 대안 비교:
  1) 현행 유지:
    - 장점: 구현 비용 최소
    - 단점: 의사결정 속도 느림, 근거 추적/재현성 취약
  2) 완전 자동:
    - 장점: 반응 속도 최고
    - 단점: 오탐/과최적화 시 실거래 리스크 큼, 운영 통제 약화
  3) 자동 분석+제안+수동 승인(채택):
    - 장점: 속도/안전성/감사 가능성 균형
    - 단점: 승인 프로세스 설계/운영 비용 필요

## 4. 대응 전략
- 단기:
  - 전략 피드백 표준 스키마/리포트/검증 게이트를 먼저 문서화(Spec-First)
- 중기:
  - 자동 분석 리포트/파라미터 후보 생성 스크립트 구현
  - 워크포워드 백테스트 게이트 자동 실행
- 장기:
  - 28번 RAG와 결합해 “변경 제안의 근거 설명” 품질 고도화

## 5. 구현/수정 내용 (예정)
### Phase A. 데이터 계약(Strategy Feedback Spec) 확정
1. 입력 데이터셋 계약:
   - `trading_history`, `agent_decisions`, `risk_audit`, `daily_report`, `market_data`
2. 공통 키/시간축:
   - symbol, decision_window, regime_window, execution_window
3. 출력 스키마:
   - 전략 상태 점수, 원인 분해 점수, 파라미터 후보 목록, 검증 결과, 최종 권고

### Phase B. 자동 분석 리포트
1. 손익 분해:
   - 진입 실패 / 청산 실패 / 레짐 오판 / AI 과차단 점수
2. 품질 지표:
   - 승률, PF, MDD, 체결당 평균손익, REJECT율, Timeout율
3. 보고서 산출:
   - 일간 요약 + 주간 비교(전주 대비 변화량)

### Phase C. 파라미터 후보 생성(룰 기반)
1. 후보 생성 범위 제한:
   - RSI/MA/거래량 임계값, TP/SL, trailing 설정
2. 변경 폭 제한:
   - 과도 변경 방지(예: RSI ±2, TP/SL ±0.5%p)
3. 금지 규칙:
   - 리스크 한도/절대 안전규칙은 자동 변경 불가

### Phase D. 검증 게이트 자동화
1. 백테스트 게이트:
   - 워크포워드 + 최근 구간 재검증 동시 통과
2. 승인 기준:
   - 수익/리스크 동시 기준 미달 시 자동 보류
3. 산출물:
   - “승인 가능/보류/폐기” 판정 + 근거 지표

### Phase E. 승인 배포/롤백 운영
1. 승인형 배포:
   - 제안안은 PR/문서 승인 후 적용
2. 배포 후 관측:
   - 24h/72h 악화 지표 트리거 시 즉시 롤백
3. 변경 이력:
   - 변경 전/후 지표 자동 기록

## 6. 검증 기준(정량)
- 측정 기간/표본:
  - 기본 30일 + 최근 레짐 전환 구간 별도
  - 최소 SELL 20건(미달 시 대체 지표 병행)
- 핵심 KPI:
  1) 체결당 평균 실현손익(SELL 기준) > 0 KRW
  2) Profit Factor >= 1.0
  3) Max Drawdown 악화 +2%p 이내
  4) AI REJECT율 급증 없음(+10%p 초과 시 실패)
  5) LLM 비용/호출량 증가율 관리(변경 전 대비 +20% 이내)
- 성공/실패 정의:
  - 위 KPI 중 수익+리스크 필수 항목 동시 만족 시 “승인 가능”

## 7. 예상 변경 파일
1. `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md` (본 문서)
2. `docs/work-result/30_strategy_feedback_automation_spec_first_result.md` (구현 후)
3. `docs/checklists/remaining_work_master_checklist.md` (상태 동기화)
4. (예정) `scripts/ops/strategy_feedback_report.sh`
5. (예정) `scripts/ops/strategy_feedback_gate.sh`
6. (예정) `src/analytics/strategy_feedback.py`

## 8. 검증 명령(초안)
1. 데이터 범위 점검:
   - `SELECT symbol, MIN(timestamp), MAX(timestamp), COUNT(*) FROM market_data WHERE interval='1m' GROUP BY symbol;`
2. 성과 지표 점검:
   - `SELECT ... FROM trading_history ...` (SELL 표본/손익)
3. AI 의사결정 점검:
   - `scripts/ops/ai_decision_canary_report.sh 24`
4. 비용 점검:
   - `scripts/ops/llm_usage_cost_report.sh 24`
5. 전략 시나리오 점검:
   - `PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 120`

## 9. 롤백
- 코드 롤백:
  - 피드백 자동화 모듈/스크립트 revert
- 운영 롤백:
  - 제안 파라미터 적용 시 이전 YAML 즉시 복원
- 데이터 롤백:
  - 없음(분석/제안 산출 중심)

## 10. 문서 반영
- Result 문서:
  - `docs/work-result/30_strategy_feedback_automation_spec_first_result.md`
- 트러블슈팅(이슈 발생 시):
  - `docs/troubleshooting/30_strategy_feedback_automation_incidents.md`
- 체크리스트 동기화:
  - `docs/checklists/remaining_work_master_checklist.md`
- Charter 반영:
  - 승인형 자동화 정책이 운영 규칙으로 확정되면 changelog에 반영

## 11. 후속 조치
1. 29 결과(핫픽스 결론)를 30 입력 기준선으로 연결
2. 28(RAG)에서 전략 설명 근거 생성 시 30의 피드백 스키마를 재사용
3. 23(이관) 이후에도 백엔드 독립으로 동작 가능한 운영 스크립트 구조 유지

## 12. 계획 변경 이력
- 2026-03-06: 사용자 요청(전략 피드백 자동화 아이디어)을 반영해 신규 main 계획 30 생성. 구현 전 Spec-First + 승인형 배포 원칙으로 범위를 확정.
