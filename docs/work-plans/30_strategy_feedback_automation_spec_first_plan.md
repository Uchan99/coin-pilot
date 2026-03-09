# 30. 전략 피드백 자동화(Spec-First) 계획

**작성일**: 2026-03-06  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/15_post_exit_analysis_enhancement_plan.md`, `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`, `docs/work-plans/28_ai_decision_strategy_case_rag_plan.md`, `docs/work-plans/29_regime_transition_strategy_evaluation_and_hotfix_plan.md`  
**승인 정보**: 승인 / 2026-03-10 / 사용자 승인 후 구현 착수  
**관련 트러블슈팅**: `docs/troubleshooting/30_strategy_feedback_ops_script_runtime_compatibility.md`

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 전략 수정 판단이 현재는 수동 해석 중심(Exit analysis, AI Decisions, risk, history)으로 분산되어 있음.
  - 기존 주간 Exit 리포트는 있으나, Rule Funnel/백테스트 기반 "전략 수정 제안"은 포함되어 있지 않음.
  - Daily Report에 신호는 있으나, Rule Engine 파라미터(진입/익절/손절/레짐)를 체계적으로 피드백하는 자동 루프가 없음.
  - 29번 검증에서 데이터 윈도우/표본 부족 문제가 확인되어, 관측→개선 제안→검증의 자동 체계 필요성이 증가.
  - 2026-03-09 기준 최신 상태:
    - `21-03`: canary 경로는 정상 활성(`72h canary=6`)이나 모델별 최소 표본 `N>=20` 미달로 관측만 지속 중
    - `21-04`: 내부 usage ledger는 동작하지만 `llm_provider_cost_snapshots=0`으로 reconciliation 미완료
    - `29-01`: Rule Funnel 구현/Discord 노출까지 완료됐고, 현재는 `BULL`/`AI stage` 표본 대기만 남음
- 왜 지금 필요한지:
  - FE/BE 이관(23)보다 전략 품질과 손익 안정성에 직접 영향을 주는 기반 자동화가 우선임.
  - 관측성 스트림들이 모두 “구현 완료 + 운영 표본 대기” 단계에 들어갔으므로, 다음 신규 구현 포커스는 전략 피드백 spec 확정이 적절함.

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
3. 자동 제안 체계를 기본으로 하되, 파라미터 변경에 한해 제한적 자동 적용 가능 여부를 운영정책으로 명확화
4. 추후 28번 RAG와 결합 가능한 근거 데이터 계약(spec) 확정
5. 기존 Discord 주간 Exit 리포트에 전략 제안 섹션을 증분 통합(주 1회 7일 고정)
6. 승인 전에는 코드 변경/배포/마이그레이션 없이, 결과 스키마와 운영 게이트만 확정한다.

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

## 3.1 자동 수정 범위 정책(초안)
1. Tier-A (허용): `config/strategy_v3.yaml` 내 허용 파라미터(임계값/TP/SL 등) 자동 변경
2. Tier-B (제한): 파이썬 코드 로직 변경은 자동 "제안 PR 생성"까지만 허용, 자동 배포 금지
3. 기본 운영 모드:
   - 초기 2주: Shadow(제안만 생성, 적용 금지)
   - 이후: Tier-A만 제한적 자동 적용 검토

## 4. 대응 전략
- 단기:
  - 전략 피드백 표준 스키마/리포트/검증 게이트를 먼저 문서화(Spec-First)
  - 이번 턴 목표는 “바로 구현 가능한 spec 수준”까지 세부화하고 승인 대기 상태를 명확히 유지하는 것
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

#### Phase A 세부 계약(이번 턴에 고정할 항목)
1. 기본 집계 윈도우:
   - `lookback_days=7` (주간 보고 기본값)
   - 승인 판단 기본값: `lookback_days=14`
   - 보조 비교/표본 확장: `lookback_days=30`
   - 최근 레짐 전환 구간은 `29` 결과 기준 동일 심볼/동일 기간 재사용
2. 최소 표본 게이트:
   - `SELL >= 12`이면 “검토 가능(reviewable)” 상태로 올릴 수 있음
   - `SELL >= 20`이면 “강한 승인(strong approval)” 게이트 충족
   - `SELL < 12`이면 파라미터 변경 제안은 생성 가능하지만 자동으로 `hold with candidate`
   - `AI decisions >= 20` 미만이면 AI 병목 해석을 보조 참고치로만 취급
   - `rule_funnel BULL rule_pass >= 5` 미만이면 BULL 병목 해석 자동 보류
3. 입력 소스별 역할:
   - `trading_history`: 실현손익/exit reason/보유시간
   - `agent_decisions`: AI confirm/reject/parse_fail/timeout/model mix
   - `rule_funnel_events`: Rule/Risk/AI 퍼널 병목
   - `llm_usage_events`: 비용/호출량 증가율
   - `market_data`: 재현 백테스트/워크포워드 입력
4. 산출 JSON 초안:
```json
{
  "window": {"days": 7, "start": "...", "end": "..."},
  "readiness": {
    "sell_samples": 0,
    "ai_decisions": 0,
    "bull_rule_pass": 0,
    "approval_tier": "hold",
    "eligible_for_change": false,
    "hold_reasons": []
  },
  "scoreboard": {
    "avg_realized_pnl_krw": 0,
    "profit_factor": 0.0,
    "max_drawdown_pct": 0.0,
    "ai_reject_rate_pct": 0.0,
    "llm_cost_delta_pct": 0.0
  },
  "bottlenecks": [],
  "candidate_changes": [],
  "gate_result": "hold",
  "evidence": []
}
```

### Phase B. 자동 분석 리포트
1. 손익 분해:
   - 진입 실패 / 청산 실패 / 레짐 오판 / AI 과차단 점수
2. 품질 지표:
   - 승률, PF, MDD, 체결당 평균손익, REJECT율, Timeout율
3. 보고서 산출:
   - 일간 요약 + 주간 비교(전주 대비 변화량)
4. 주간 리포트 통합 방식:
   - 기존 `Weekly Exit Report` payload에 `Strategy Feedback` 블록 추가
   - Discord에는 요약(판정/핵심 수치) + 상세(파라미터 후보/근거) 2단 메시지로 전송

#### Phase B 세부 산출(이번 턴에 고정할 항목)
1. 요약 블록 필수 필드:
   - `gate_result`: `recommend | hold | discard`
   - `approval_tier`: `hold | reviewable | strong_approval`
   - `top_bottleneck`: 예) `SIDEWAYS max_per_order`, `BULL rule_pass shortage`
   - `kpi_delta`: 전주 대비 `avg_realized_pnl`, `PF`, `MDD`, `AI reject rate`, `LLM cost`
2. 상세 블록 필수 필드:
   - `candidate_id`
   - `target_param`
   - `current_value`
   - `proposed_value`
   - `expected_effect`
   - `hold_reason` 또는 `approval_reason`
3. Discord 표준 포맷:
   - 메시지 1: `판정 + KPI 4줄 + 병목 2줄`
   - 메시지 2: 파라미터 후보별 diff + 백테스트 결과 + config hash + `approval_tier`

### Phase C. 파라미터 후보 생성(룰 기반)
1. 후보 생성 범위 제한:
   - RSI/MA/거래량 임계값, TP/SL, trailing 설정
2. 변경 폭 제한:
   - 과도 변경 방지(예: RSI ±2, TP/SL ±0.5%p)
3. 금지 규칙:
   - 리스크 한도/절대 안전규칙은 자동 변경 불가

#### Phase C 세부 후보 규칙(초안 고정)
1. 후보 허용 파라미터:
   - `bull.rsi_14_max`
   - `sideways.rsi_14_max`
   - `bear.rsi_14_max`
   - `take_profit_pct`
   - `stop_loss_pct`
   - `trailing_stop_pct`
   - `volume_ratio_min`
2. 후보 생성 조건 예시:
   - `RSI_OVERBOUGHT` 비중 과대 + 평균 수익 양호: `take_profit_pct` 상향 후보
   - `TIME_LIMIT` 이후 후행 하락 지속: 현행 유지 또는 더 조기 청산 후보
   - `rule_pass` 충분하나 `ai_reject` 과다: 파라미터 후보 생성 금지, AI/RAG 관측 이슈로 분류
   - `rule_pass` 자체 부족: 레짐 진입 조건 후보만 생성
3. 후보 생성 금지 조건:
   - `BULL rule_pass < 5`
   - `parse_fail_rate >= 10%`
   - `provider cost snapshot missing`
4. 후보 생성/승인 분리 규칙:
   - `SELL < 12`: 후보 생성만 허용, `gate_result=hold`
   - `12 <= SELL < 20`: 후보 생성 + 수동 검토 가능, `approval_tier=reviewable`
   - `SELL >= 20`: 정식 승인 심사 가능, `approval_tier=strong_approval`

### Phase D. 검증 게이트 자동화
1. 백테스트 게이트:
   - 워크포워드 + 최근 구간 재검증 동시 통과
2. 승인 기준:
   - 수익/리스크 동시 기준 미달 시 자동 보류
3. 산출물:
   - “승인 가능/보류/폐기” 판정 + 근거 지표

#### Phase D 세부 게이트(이번 턴에 고정할 항목)
1. 필수 통과 게이트:
   - `avg_realized_pnl_per_sell > 0`
   - `profit_factor >= 1.0`
   - `max_drawdown_pct` 악화 `+2%p` 이내
   - `ai_reject_rate_pct` 악화 `+10%p` 이내
   - `llm_cost_delta_pct` 증가 `+20%` 이내
2. 자동 보류(`hold`) 조건:
   - `SELL < 12`
   - 비용 snapshot 누락
   - 카나리 실험 표본 부족
   - Rule Funnel 병목이 운영 한도(`max_per_order`)에 집중돼 전략 파라미터 조정 근거가 약한 경우
3. 조건부 검토(`reviewable`) 조건:
   - `12 <= SELL < 20`
   - 필수 KPI 급락 없음
   - Rule Funnel 또는 백테스트 근거가 명확
   - 최종 적용은 수동 승인만 가능
4. 자동 폐기(`discard`) 조건:
   - 백테스트 수익/리스크 동시 악화
   - 변경폭 제한 위반
   - 재현성 해시 누락

### Phase E. 승인 배포/롤백 운영
1. 승인형 배포:
   - 제안안은 PR/문서 승인 후 적용
2. 배포 후 관측:
   - 24h/72h 악화 지표 트리거 시 즉시 롤백
3. 변경 이력:
   - 변경 전/후 지표 자동 기록

### Phase F. 운영 가드레일(요청 반영)
1. 주간 변경 예산(cap):
   - 주당 파라미터 변경 최대 2개
   - 변경폭 제한: RSI ±2, TP/SL ±0.5%p
2. 2주 Shadow 모드:
   - 최초 2회(2주)는 제안만 생성, 자동 적용 금지
3. 자동 보류 기준:
   - `SELL < 20` 또는 `AI decisions < 80`이면 자동 보류
4. 롤백 트리거:
   - 적용 후 7일 내 `PF -10%` 또는 `MDD +2%p` 악화 시 즉시 원복
5. 재현성 고정:
   - 제안서에 백테스트 기간/심볼/설정 해시(config hash) 필수 기록
6. Discord 승인 워크플로우 표준:
   - `추천/보류/폐기 + 근거 4줄 + diff 경로` 고정 포맷

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
- 자동 적용 허용 조건(추가):
  - Shadow 모드 종료 + 주간 변경 cap 충족 + 자동 보류 기준 미충족 + 롤백 트리거 미발생

### 6.1 이번 Plan 구체화 완료 기준
1. 입력 데이터 계약과 최소 표본 게이트가 문서에 고정될 것
2. `gate_result`(`recommend|hold|discard`) 판정 로직이 정량 기준으로 정의될 것
3. `approval_tier`(`hold|reviewable|strong_approval`)가 명시될 것
4. Discord/주간 리포트에 들어갈 표준 필드가 확정될 것
5. 승인 전 구현/배포 금지 원칙이 명시될 것

## 7. 예상 변경 파일
1. `docs/work-plans/30_strategy_feedback_automation_spec_first_plan.md` (본 문서)
2. `docs/work-result/30_strategy_feedback_automation_spec_first_result.md` (구현 후)
3. `docs/checklists/remaining_work_master_checklist.md` (상태 동기화)
4. (예정) `scripts/ops/strategy_feedback_report.sh`
5. (예정) `scripts/ops/strategy_feedback_gate.sh`
6. (예정) `src/analytics/strategy_feedback.py`
7. (예정) `scripts/ops/strategy_feedback_apply.sh` (Tier-A 한정 자동 적용기)
8. (예정) `scripts/ops/strategy_feedback_open_pr.sh` (Tier-B 코드 변경 제안 PR 생성기)

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
6. 주간 리포트 통합 점검:
   - `python -c "import asyncio; from src.bot.main import weekly_exit_report_job; asyncio.run(weekly_exit_report_job())"`
7. 재현성 해시 검증:
   - `sha256sum config/strategy_v3.yaml`
8. Rule Funnel 병목 확인:
   - `scripts/ops/rule_funnel_regime_report.sh 72`

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

## 10.1 이번 턴 산출물 범위(승인 전)
- 포함:
  - 본 계획서 구체화
  - 체크리스트 최근 업데이트 메모
- 제외:
  - 코드 구현
  - 배포/마이그레이션
  - 자동 적용 스크립트 실행

## 10.2 승인 후 1차 구현 범위(2026-03-10)
- 포함:
  - `src/analytics/strategy_feedback.py`
  - `scripts/ops/strategy_feedback_report.sh`
  - `scripts/ops/strategy_feedback_gate.sh`
  - 분석기 단위 테스트
- 제외:
  - Discord/n8n 통합
  - 자동 적용기(`strategy_feedback_apply.sh`)
  - PR 자동 생성기

## 11. 후속 조치
1. 29 결과(핫픽스 결론)를 30 입력 기준선으로 연결
2. 28(RAG)에서 전략 설명 근거 생성 시 30의 피드백 스키마를 재사용
3. 23(이관) 이후에도 백엔드 독립으로 동작 가능한 운영 스크립트 구조 유지

## 12. 계획 변경 이력
- 2026-03-06: 사용자 요청(전략 피드백 자동화 아이디어)을 반영해 신규 main 계획 30 생성. 구현 전 Spec-First + 승인형 배포 원칙으로 범위를 확정.
- 2026-03-07: 사용자 요청에 따라 주기 정책을 "주 1회(7일 고정)"로 명확화하고, 기존 Weekly Exit Report 경로에 전략 제안 섹션을 증분 통합하는 방식을 추가.
- 2026-03-07: 사용자 요청에 따라 운영 가드레일 6종(주간 cap, 2주 shadow, 자동 보류 기준, 롤백 트리거, 재현성 해시, Discord 표준 승인 포맷)과 자동 수정 범위(Tier-A/Tier-B)를 추가.
- 2026-03-10: 사용자 요청(`f30` 브랜치에서 30 plan 구체화 시작)에 따라 최신 관측 상태(`21-03/21-04/29-01`)를 입력 조건으로 반영하고, 데이터 계약/출력 JSON/gate_result/Discord 포맷/자동 보류 조건을 바로 구현 가능한 수준으로 세부화했다. 상태는 여전히 `Approval Pending`이며 승인 전 구현/배포는 수행하지 않는다.
- 2026-03-10: 사용자 피드백을 반영해 `SELL >= 20` 단일 하드 게이트를 `SELL >= 12` 검토 게이트 + `SELL >= 20` 강한 승인 게이트로 이원화했다. 승인 판단 기본 윈도우는 14일, 표본 부족 시 30일 확장으로 명시했다.
- 2026-03-10: 사용자 승인에 따라 상태를 `Approved`로 변경하고, 1차 구현 범위를 `분석기 + report/gate 스크립트 + 테스트`로 고정했다.
- 2026-03-10: OCI 운영 검증 중 `Permission denied`와 `python: command not found`를 확인해, ops 스크립트 실행 권한 비트 및 `python3/python` 호환성, heredoc 환경 변수 export 보정을 후속 수정 범위에 추가했다.
