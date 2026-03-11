# 21-10. 주문 사이징과 리스크 캡 정렬 검증 및 보정 계획

작성일: 2026-03-11  
작성자: Codex  
상태: Approved  
상위 계획 문서: `docs/work-plans/21_live_trading_transition_1m_krw_plan.md`  
관련 선행 문서: `docs/work-plans/21-01_reference_equity_three_cap_execution_plan.md`, `docs/work-result/21-01_reference_equity_three_cap_execution_result.md`, `docs/work-result/29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md`, `docs/work-result/30_strategy_feedback_automation_spec_first_result.md`  
관련 트러블슈팅 문서: (필요 시 생성)

---

## 0. 트리거(Why started)
- 사용자 질문:
  - `max_per_order=20%`를 "5종목이면 총 100%까지 채울 수 있도록 한 종목당 최대치"로 의도했는데, 왜 `risk_reject(max_per_order)`가 대량 발생하는지 설명이 필요함.
  - 현재 병목이 실제 리스크 정책 때문인지, 주문 사이징 계산과 하드 캡 검증이 서로 어긋난 설계 문제인지 분리해달라는 요구가 있었음.
- 현재 관측:
  - `SIDEWAYS rule_pass=113`, `risk_reject=108`, 그중 `max_per_order=102`
  - Strategy Feedback Gate에서는 같은 구간에 `gate_result=discard`, `profit_factor=0.5807`, `avg_realized_pnl_pct=-0.6369%`
- 의심 지점:
  - 주문 목표 계산은 `reference_equity * max_per_order * regime_ratio * symbol_multiplier`
  - 최종 리스크 검증은 `reference_equity * max_per_order * vol_multiplier`
  - 즉, 목표 주문금액과 하드 캡 검증 기준이 서로 다를 가능성이 있음.

## 1. 해결할 문제 정의
- 증상:
  - Rule Funnel에서 `risk_reject(max_per_order)`가 과다하게 누적된다.
  - 사용자 의도는 "종목당 최대 20%"인데, 실제 구현은 `regime_ratio`, `symbol_multiplier`, `vol_multiplier`가 서로 다른 지점에서 적용돼 주문 목표와 검증 캡이 다를 수 있다.
- 영향:
  - 운영자는 "신호 질이 나빠서 막히는 것"과 "설계 mismatch로 막히는 것"을 구분하지 못한다.
  - 잘못 해석하면 실제로는 설계 결함인데도 전략 품질 문제로 오판할 수 있다.
  - 반대로 성급한 `max_per_order` 완화는 손실 확대를 유발할 수 있다.
- 재현 조건:
  - `position_size_ratio * symbol_multiplier > 1.0`인 심볼/레짐 조합
  - 또는 `vol_multiplier < 1.0`인 고변동성 구간
  - 동일 신호가 `target_invest_amount` 단계에서는 허용되나 `check_order_validity()`에서 `max_per_order` 위반으로 거절되는 경우
- Root cause(가설):
  - 주문 목표값 생성식과 RiskManager의 단일 주문 상한 계산식이 동일한 정책을 공유하지 않는다.

## 2. 목표
1. `max_per_order` 병목이 "정상적인 리스크 정책 결과"인지 "설계 mismatch"인지 정량적으로 분리한다.
2. mismatch가 확인되면, 주문 목표 계산과 하드 캡 검증을 같은 기준으로 정렬한다.
3. 정렬 후에도 남는 `max_per_order` reject만 실제 리스크 병목으로 해석할 수 있게 만든다.
4. Rule Funnel/Strategy Feedback 해석 문구를 "리스크 한도 자체 문제"가 아니라 "정책 정렬 여부 확인 후 병목 판단"으로 교정한다.

## 3. 대응 전략

### 3.1 최종 선택(채택 예정)
- **주문 목표 계산식과 RiskManager 하드 캡 계산식을 동일 정책으로 정렬**
  - 주문 목표 계산에서 사용하는 배율(`regime_ratio`, `symbol_multiplier`, 필요 시 `vol_multiplier`)과
  - 최종 하드 캡 검증에서 사용하는 배율을 같은 기준으로 맞춘다.
- 핵심 원칙:
  1. `max_per_order`는 "종목당 최대 허용 비중"이라는 의미를 유지한다.
  2. 목표 주문금액은 어떤 경우에도 하드 캡 의미를 조용히 초과하도록 만들지 않는다.
  3. 추가 비중 조정(`regime_ratio`, `symbol_multiplier`, `vol_multiplier`)은 모두 "캡 안에서의 목표 주문량 조정"으로만 동작하게 한다.

### 3.2 고려한 대안
1. `max_per_order` 자체를 상향
- 장점:
  - 즉시 `risk_reject` 수를 줄일 수 있다.
- 단점:
  - 현재 `profit_factor=0.5807` 구간에서는 손실 거래량 확대 위험이 크다.
  - 설계 mismatch를 정책 완화로 가리는 꼴이 될 수 있다.

2. 목표 주문금액은 그대로 두고 RiskManager에서만 허용 폭 확대
- 장점:
  - 변경 범위가 작아 보인다.
- 단점:
  - `max_per_order` 의미가 흐려진다.
  - 추후 문서/운영 해석이 더 복잡해진다.

3. 목표 주문금액을 초과 시 자동 절삭(clamp)해 주문 진행
- 장점:
  - reject가 줄어든다.
- 단점:
  - 전략이 의도한 포지션 크기를 조용히 바꿔버린다.
  - audit/readability가 떨어진다.

4. **주문 목표 계산과 하드 캡 계산식을 정렬 (채택)**
- 장점:
  - `max_per_order` 의미를 유지한다.
  - Rule Funnel 해석이 정확해진다.
  - "설계 문제"와 "정상 리스크 정책"을 분리할 수 있다.
- 단점:
  - 계산식/주석/문서/테스트를 함께 정리해야 한다.

## 4. 구현 범위

### Phase A. mismatch 정량 검증
- `src/bot/main.py`
  - `target_invest_amount`, `actual_invest_amount` 계산 지점 계측 포인트 확인
- `src/engine/risk_manager.py`
  - `max_order_amount` 계산 경로 확인
- 검증 스크립트/SQL 또는 단위 테스트로 아래를 분리
  1. `effective_ratio > 1.0` 때문에 생긴 reject
  2. `vol_multiplier < 1.0` 때문에 생긴 reject
  3. 실제 현금/총노출 부족 때문에 생긴 reject

### Phase B. 정책 정렬 보정
- 주문 목표 계산과 하드 캡 계산에 동일 기준 적용
- 선택지:
  1. `effective_ratio`를 1.0 이하로 clamp
  2. 또는 하드 캡 계산에 동일 배율을 반영
- 구현 중 하나를 선택하되, `max_per_order`의 의미가 "종목당 최대 허용 비중"으로 유지되도록 설계

### Phase C. 검증 및 문서 정리
- Rule Funnel 재확인
- Strategy Feedback 해석 문구 보정
- 필요한 경우 `PROJECT_CHARTER.md` 리스크 규칙 설명 수정

## 5. 상세 설계 원칙
- `max_per_order`는 "종목당 최대 허용 비중"으로 남겨둔다.
- `position_size_ratio`와 `symbol_position_multiplier`는 "목표 주문량 조정 계수"이지, 하드 캡을 깨는 계수가 되면 안 된다.
- `vol_multiplier`는 고변동성 시 주문량을 줄이는 보수 장치이므로, 앞단/뒷단 모두에서 해석이 일관돼야 한다.
- reject 발생 시 운영자가 원인을 읽을 수 있도록 아래 reason 분리를 유지/강화한다:
  - `max_per_order`
  - `max_total_exposure`
  - `cash_cap`
  - `volatility_clamp` 또는 유사 사유(필요 시)

## 6. 정량 검증 기준
- Before 기준:
  - `SIDEWAYS rule_pass=113`, `risk_reject=108`, `max_per_order=102`
  - Strategy Feedback Gate: `profit_factor=0.5807`, `avg_realized_pnl_pct=-0.6369%`
- 성공 기준:
  1. 계산식 mismatch가 테스트/로그로 재현 가능하게 설명될 것
  2. 보정 후 "하드 캡보다 큰 목표 주문" 케이스가 0건일 것
  3. Rule Funnel에서 `max_per_order` reject 해석이 "설계 mismatch"가 아닌 "정상 정책 차단"으로 바뀔 것
  4. 보정 자체가 손익 개선을 의미하지는 않음을 문서에 명시할 것
- 실패 기준:
  1. `max_per_order` 의미가 변경되는데 문서/Charter가 갱신되지 않음
  2. 주문 목표와 검증 캡이 여전히 다른 정책을 사용
  3. clamp/완화로 인해 전략 의도와 실제 주문량 차이가 불명확해짐

## 7. How to verify
예정 검증 명령:
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/engine/test_risk_manager_position_cap_alignment.py
python3 -m py_compile src/bot/main.py src/engine/risk_manager.py
```

OCI 재검증(예정):
```bash
cd /opt/coin-pilot
scripts/ops/rule_funnel_regime_report.sh 72
docker exec -u postgres coinpilot-db psql -d coinpilot -c "
SELECT regime, stage, reason_code, count(*)
FROM rule_funnel_events
WHERE created_at >= now() - interval '72 hours'
GROUP BY 1,2,3
ORDER BY 1,2,3;
"
```

기대 체크:
- 정렬 보정 후에는 `max_per_order` reject가 "정말 캡을 넘는 주문"에서만 발생
- 과거처럼 배율 조합 때문에 목표 주문이 캡보다 커지는 구조적 reject는 사라질 것

## 8. 리스크 / 가정 / 미확정 사항
- 리스크:
  - 잘못 보정하면 실제로는 주문량이 줄어들어 "reject는 감소하지만 거래량도 감소"할 수 있다.
  - 반대로 잘못된 완화는 손실 거래량 확대를 유발할 수 있다.
- 가정:
  - 현재 운영 병목의 일부는 전략 품질이 아니라 설계 mismatch일 수 있다.
- 미확정:
  - 정렬 이후 운영 Rule Funnel에서 `max_per_order` reject 비중이 어떻게 재형성되는지는 후속 운영 관측이 필요하다.

## 9. 문서/정책 영향
- 구현 과정에서 `max_per_order` 정의/의미가 바뀌면 [PROJECT_CHARTER.md](/home/syt07203/workspace/coin-pilot/docs/PROJECT_CHARTER.md)를 함께 갱신한다.
- `29-01`, `30` 결과 문서의 병목 해석도 필요 시 후속 보정한다.

## 10. 변경 이력
- 2026-03-11: 사용자 질문을 계기로 신규 하위 계획 생성. 초기 상태는 `Approval Pending`.
- 2026-03-11: 사용자 승인 후 구현 단계로 전환. `max_per_order` 의미를 유지한 채 주문 목표 계산과 하드 캡 검증을 동일 정책으로 정렬하는 방향으로 확정.
- 2026-03-11: 구현 완료. 주문 목표 계산식을 `기준자산 × max_per_order × volatility_multiplier × min(position_size_ratio × symbol_multiplier, 1.0)`로 정렬하고, 신규 sizing 정렬 테스트(`3 passed`) 및 포지션 사이징 회귀 포함(`5 passed`) 검증 결과를 남겼다.
- 2026-03-11: OCI 반영 후 초기 모니터링 전환. bot 재배포 시각 이후 `max_per_order` 신규 reject 0건, 신규 BUY 0건을 확인했고 동일 오류 패턴 미재현 상태에서 운영 표본 추가 관측 단계로 전환했다.
