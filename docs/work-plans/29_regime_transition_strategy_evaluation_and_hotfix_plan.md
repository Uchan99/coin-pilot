# 29. 레짐 전환 구간 전략 평가 및 핫픽스 의사결정 계획

**작성일**: 2026-03-05  
**작성자**: Codex  
**상태**: In Progress  
**관련 계획 문서**: `docs/work-plans/21-03_ai_decision_model_canary_experiment_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`, `docs/work-plans/28_ai_decision_strategy_case_rag_plan.md`  
**승인 정보**: 사용자 / 2026-03-06 / "f29 브랜치로 옮겨서 시작해줘"

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 최근 AI Decision에서 REJECT 비율이 높고, 상승 전환 구간에서 기회 손실 가능성이 제기됨.
  - Daily Report/Exit Analysis 기반 전략 평가 필요성이 증가.
  - 현재 SELL 표본이 20건 미만이라 exit 성능 해석 신뢰도가 제한적일 가능성이 있음.
  - 사용자 관측(2026-03-06): 최근 약 8일 동안 총 체결 27회, 누적 실현손익 약 `-13,000 KRW`, 1회 진입금 약 `180,000 KRW`, 최대 손실 `-7,000 KRW`, 최대 수익 `+5,000 KRW`.
- 왜 지금 필요한지:
  - FE/BE 이관(23)보다 실거래 성능/리스크에 직접 영향을 주는 전략 검증이 우선임.

## 1. 문제 요약
- 증상:
  - 상승장 전환 국면에서 진입/보유/청산 정책이 보수적으로 동작할 가능성
  - AI 의사결정의 고REJECT 편향이 수익 기회에 미친 영향이 불명확
  - 손익 변동폭이 작고(수천원 단위), 누적 손익이 음수라 “전략 우위(edge)”가 아직 확인되지 않음
- 영향 범위(기능/리스크/데이터/비용):
  - 기능: Rule Engine + AI Decision 결합 의사결정 품질
  - 리스크: 과도한 보수성으로 기회손실, 반대로 완화 시 DD 확대 가능
  - 데이터: `agent_decisions`, `trading_history`, post-exit 추적 데이터 신뢰도
  - 비용: 불필요 AI 호출/재검토 비용 가능성
- 재현 조건:
  - `SIDEWAYS -> BULL` 또는 `BEAR -> BULL` 전환 직후 변동성 확장 구간

## 2. 목표 / 비목표
### 2.1 목표
1. 현재 전략이 "잘못된 것인지"와 "단지 표본 부족인지"를 정량으로 구분
2. 레짐 전환 구간 전용 백테스트를 수행해 개선 후보를 수치로 검증
3. 핫픽스 필요 시 즉시 적용 가능한 최소 변경안(guarded hotfix) 정의

### 2.2 비목표
1. 본 계획에서 FE/BE 이관 작업(22/23) 착수하지 않음
2. AI 모델 교체(21-03 최종결정) 자체를 본 계획에서 확정하지 않음
3. 대규모 아키텍처 변경(서비스 분해/레포 분리) 수행하지 않음

## 3. 원인 가설
1. 레짐 전환 감지 지연
   - MA50/MA200 임계값 기반 분류가 전환 초기에 보수적으로 유지될 가능성
2. 진입 조건 과보수
   - RSI/MA/거래량/BB 조건 조합으로 전환 초반 진입 신호 누락 가능성
3. AI 게이트 과차단
   - Rule Engine 통과 후 Analyst/Guardian 단계에서 REJECT 편향 발생 가능성
4. Exit 데이터 표본 부족
   - SELL<20 구간에서는 exit reason/post-exit 성과 비교의 통계적 신뢰도 제한

## 4. 대응 전략
- 단기 핫픽스:
  - 핫픽스는 “정량 기준 통과 시”에만 적용 (무증거 변경 금지)
- 근본 해결:
  - 전략 평가를 3축으로 분리:
    1) 운영 데이터 감사(Decision/Report/Exit)
    2) 레짐 전환 백테스트(시나리오 비교)
    3) 핫픽스 승인 게이트(수익/리스크 동시 조건)
- 안전장치(가드레일):
  - 적용 시 feature flag 또는 YAML 파라미터 변경으로 즉시 롤백 가능해야 함
  - 핫픽스 적용 후 24h/72h 관측에서 악화 시 즉시 원복

## 5. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **운영 데이터 감사 + 오프라인 백테스트 + 조건부 핫픽스** 3단계

- 고려 대안:
  1) 표본 충분할 때까지 관측만 지속
  2) 즉시 전략 완화 핫픽스 적용
  3) 오프라인 백테스트 후 조건부 적용 (채택)

- 대안 비교:
  1) 관측만 지속:
    - 장점: 실거래 리스크 최소
    - 단점: 개선 속도 느림, 기회비용 증가
  2) 즉시 핫픽스:
    - 장점: 빠른 반응
    - 단점: 근거 부족 시 손실 확대 위험
  3) 백테스트 기반 조건부 핫픽스(채택):
    - 장점: 속도/안전성 균형, 의사결정 근거 명확
    - 단점: 실데이터/백테스트 간 괴리 관리 필요

## 6. 구현/분석 내용 (예정)
### Phase A. 운영 데이터 감사
1. AI Decisions 분포/REJECT 사유/신뢰도 길이 분석
2. Daily Report 지표와 실제 의사결정 간 정합성 점검
3. Exit Analysis 표본 점검(SELL>=20 여부, 부족 시 대체 지표 정의)

### Phase B. 레짐 전환 백테스트
1. Baseline: 현재 `config/strategy_v3.yaml`
2. Scenario-1: 전환 민감도 완화(레짐 임계값/전환 판정)
3. Scenario-2: BULL 구간 진입 조건 완화(보수폭 소폭 축소)
4. Scenario-3: 보수성 유지 + 리스크/청산 조건만 미세조정

### Phase C. 핫픽스 의사결정
1. 적용 기준 통과 시 YAML 파라미터 hotfix 제안
2. 미통과 시 관측 연장 + 다음 실험 설계

### Phase D. 백테스트 데이터 윈도우 확장(장기 백필)
1. `market_data` 유효 기간 점검(SQL: symbol별 first_ts/last_ts/rows)
2. `scripts/backfill_for_regime.py`를 장기 백필 모드(`--days`, `--symbols`)로 실행해 표본 확대
3. 백필 후 7/21/120+/240일 재실행으로 시나리오 순위의 안정성 확인

## 7. 정량 검증 기준
- 공통 측정 기준:
  - 기간: 최근 90일(기본) + 최근 전환 구간(별도)
  - 표본: 거래 건수, SELL 건수, 결정 건수
  - 성공/실패 정의: 수익성 + 리스크 동시 충족

- 핫픽스 승인 게이트(초안):
1. 전환 구간 누적 수익률: Baseline 대비 +3%p 이상 또는 +10% 상대 개선
2. Max Drawdown 악화: +2%p 이내
3. 거래 수: Baseline 대비 50~200% 범위(과매매 방지)
4. 실운영 EXIT 표본:
   - 원칙: SELL 20건 이상 확보 후 최종 판단
   - 예외: 20건 미만이면 “측정 불가 사유 + 대체 지표(미실현 PnL/포지션 품질)” 명시
5. 손익 규모(체결 효율) 기준:
   - 체결당 평균 실현손익(SELL 기준) `> 0 KRW`
   - 평균 이익/평균 손실 비율(Reward/Risk) `>= 1.0` 또는
   - 해당 비율이 1.0 미만이면 손익분기 승률 대비 실제 승률이 +5%p 이상

## 8. 검증 명령(초안)
1. 백테스트:
   - `PYTHONPATH=. python scripts/backtest_v3.py`
2. AI Decision 집계:
   - `scripts/ops/ai_decision_canary_report.sh 24`
3. 비용/오류 체크:
   - `scripts/ops/llm_usage_cost_report.sh 24`
   - `SELECT created_at, route, status, error_type FROM llm_usage_events WHERE status='error' ORDER BY created_at DESC LIMIT 30;`
4. Exit 표본 체크:
   - `SELECT count(*) FILTER (WHERE side='SELL') AS sell_count FROM trading_history WHERE executed_at >= now() - interval '30 days';`
5. 장기 백필:
   - `PYTHONPATH=. python scripts/backfill_for_regime.py --days 120`
   - `PYTHONPATH=. python scripts/backfill_for_regime.py --days 240 --symbols KRW-BTC,KRW-ETH,KRW-XRP,KRW-SOL,KRW-DOGE`

## 9. 롤백
- 코드/설정 롤백:
  - `config/strategy_v3.yaml` 파라미터를 직전 버전으로 복원
- 운영 롤백:
  - bot 재기동 후 24h 모니터링 재검증
- 데이터 롤백:
  - 없음(관측/분석 중심)

## 10. 문서 반영
- 결과 문서(구현 후):
  - `docs/work-result/29_regime_transition_strategy_evaluation_and_hotfix_result.md`
- 트러블슈팅(핫픽스/이슈 발생 시):
  - `docs/troubleshooting/29_regime_transition_strategy_hotfix.md`
- 체크리스트 동기화:
  - `docs/checklists/remaining_work_master_checklist.md` 상태 업데이트

## 11. 계획 변경 이력
- 2026-03-05: 초기 계획 생성(Approval Pending). FE/BE 이관보다 전략 성능 검증을 우선하도록 실행 순서를 명시.
- 2026-03-06: 사용자 운영 관측(체결 27회, 누적 -13,000 KRW, max loss -7,000 / max win +5,000)을 반영해 “손익 규모(체결 효율)”를 핵심 검증 축으로 추가하고 핫픽스 승인 게이트를 보강.
- 2026-03-06: 사용자 승인 후 `f29` 브랜치에서 구현 착수. 상태를 `In Progress`로 전환.
- 2026-03-06: Phase 1 도구 준비 반영. `scripts/backtest_regime_transition_scenarios.py`를 추가해 baseline+3개 시나리오 자동 비교 실행 경로를 마련.
- 2026-03-06: Phase 2 1차 실행 반영(OCI 120일). baseline 대비 `transition_sensitive`가 수익/승률/MDD 동시 개선을 보였으나 표본 부족으로 추가 검증 게이트(180/240일, 심볼별 확인)를 유지.
- 2026-03-06: Phase 2 확장 실행(OCI 180/240일) 결과가 120일과 동일함을 확인. 유효 데이터 윈도우 점검(SQL)과 표본 확대를 선행 조건으로 추가.
- 2026-03-06: Phase D 착수. `scripts/backfill_for_regime.py`를 장기 백필 대응(`--days`, `--symbols`, 진행률/재시도/중복통계)으로 확장하고, 기존 무인자 실행(12,000분) 호환을 유지.
