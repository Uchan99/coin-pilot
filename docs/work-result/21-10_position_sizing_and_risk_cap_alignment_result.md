# 21-10. 주문 사이징과 리스크 캡 정렬 검증 및 보정 결과

작성일: 2026-03-11  
작성자: Codex  
관련 계획 문서: [21-10_position_sizing_and_risk_cap_alignment_plan.md](/home/syt07203/workspace/coin-pilot/docs/work-plans/21-10_position_sizing_and_risk_cap_alignment_plan.md)

---

## 0. 해결한 문제

### 문제 정의
- 증상:
  - Rule Funnel에서 `SIDEWAYS rule_pass=113`, `risk_reject=108`, `max_per_order=102`가 관측되며 `max_per_order` 병목이 과도하게 누적됐다.
- 영향:
  - 운영자는 이 병목을 "전략 품질 문제"로 해석할 수 있었지만, 실제로는 주문 목표 계산식과 RiskManager 하드 캡 계산식이 서로 다른 정책을 사용해 구조적 reject가 발생할 가능성이 있었다.
- 재현 조건:
  - `position_size_ratio * symbol_multiplier > 1.0` 이거나 `vol_multiplier < 1.0`인 구간에서, 앞단 주문 목표는 `max_per_order`를 초과하는 금액을 만들 수 있지만 뒤단 검증은 더 작은 하드 캡을 적용했다.

### 원인
- 구현 전 주문 목표 계산:
  - `reference_equity * max_per_order * regime_ratio * symbol_multiplier`
- 구현 전 최종 하드 캡 검증:
  - `reference_equity * max_per_order * vol_multiplier`
- 즉, 목표 주문량과 최종 허용 캡이 동일한 정책을 공유하지 않아, 의도상 "종목당 최대 20%"인데도 앞단 목표가 하드 캡을 조용히 초과할 수 있었다.

## 1. 적용한 변경

### 핵심 수정
- [risk_manager.py](/home/syt07203/workspace/coin-pilot/src/engine/risk_manager.py)
  - `normalize_position_sizing_ratio()` 추가
  - `get_dynamic_max_order_amount()` 추가
  - `build_target_order_sizing()` 추가
  - 주문 목표 계산과 하드 캡 계산을 동일 정책으로 정렬
- [main.py](/home/syt07203/workspace/coin-pilot/src/bot/main.py)
  - 직접 계산하던 `target_invest_amount`를 `RiskManager.build_target_order_sizing()` 결과로 대체
  - `signal_info`에 정렬된 sizing trace(`raw_effective_position_ratio`, `effective_position_ratio`, `volatility_position_multiplier`, `dynamic_max_order_amount`) 기록
- [PROJECT_CHARTER.md](/home/syt07203/workspace/coin-pilot/docs/PROJECT_CHARTER.md)
  - `max_per_order` 의미와 동적 하드 캡 정렬 정책 문서화
- [README.md](/home/syt07203/workspace/coin-pilot/README.md)
  - 운영 변경 요약과 현재 백로그 상태 동기화

### 최종 정책
- 최종 목표 주문금액:
  - `기준자산 × max_per_order × volatility_multiplier × min(position_size_ratio × symbol_multiplier, 1.0)`
- 의미:
  - `max_per_order`는 여전히 "종목당 최대 허용 비중"
  - `position_size_ratio`, `symbol_multiplier`는 캡 안에서의 목표 주문량 조정 계수
  - `volatility_multiplier`는 고변동성 시 주문량을 줄이는 보수 장치이며, 목표 주문량과 검증 캡 모두에 동일하게 반영

## 2. 설계 선택 이유

### 채택한 방식
- 주문 목표 계산과 하드 캡 검증을 같은 정책으로 정렬했다.

### 고려한 대안
1. `max_per_order` 자체를 상향
2. RiskManager의 검증 한도만 완화
3. 초과 주문을 자동 절삭(clamp)해 강제로 집행
4. 목표 계산과 하드 캡 계산을 동일 정책으로 정렬

### 왜 이 방식을 택했는가
- `max_per_order` 의미를 유지할 수 있다.
- Rule Funnel의 `max_per_order` 병목 해석이 정확해진다.
- 설계 mismatch와 정상 리스크 정책을 분리할 수 있다.
- 전략 의도와 실제 주문량 차이를 숨기지 않는다.

### 트레이드오프
- reject 수가 줄더라도 손익이 자동 개선되는 것은 아니다.
- 문서/테스트/정책 설명을 함께 갱신해야 한다.

## 3. 정량 증빙

### Before / After 비교

측정 기준:
- 기준자산(reference equity): `1,000,000`
- 기본 단일 주문 한도(`max_per_order`): `20%`
- 예시 1: `position_size_ratio=0.9`, `symbol_multiplier=1.2`, `vol_multiplier=1.0`
- 예시 2: 동일 배율 + `vol_multiplier=0.5`

| 구분 | Before 목표 주문금액 | 하드 캡 | 차이 | After 목표 주문금액 | 차이 |
|---|---:|---:|---:|---:|---:|
| 예시 1 (`0.9 × 1.2`, 변동성 배율 1.0) | 216,000 | 200,000 | +16,000 (`+8.0%`) | 200,000 | 0 |
| 예시 2 (`0.9 × 1.2`, 변동성 배율 0.5) | 216,000 | 100,000 | +116,000 (`+116.0%`) | 100,000 | 0 |

해석:
- 구현 전에는 목표 주문금액이 하드 캡보다 큰 값으로 계산될 수 있었다.
- 구현 후에는 하드 캡을 초과하는 목표 주문이 구조적으로 생성되지 않는다.

### 운영 해석 변화
- Before:
  - Rule Funnel의 `max_per_order` reject 중 일부는 전략 품질이 아니라 계산식 mismatch가 원인일 수 있었다.
- After:
  - `max_per_order` reject는 "정렬된 정책 기준으로도 실제 하드 캡을 넘는 주문"에서만 발생한다.

## 4. 검증 결과

### 통과한 검증
```bash
python3 -m py_compile src/bot/main.py src/engine/risk_manager.py src/config/strategy.py tests/conftest.py tests/test_risk_manager_position_cap_alignment.py
env PYTHONPATH=. .venv/bin/pytest -q tests/test_risk_manager_position_cap_alignment.py
env PYTHONPATH=. .venv/bin/pytest -q tests/test_strategy_position_sizing.py tests/test_risk_manager_position_cap_alignment.py
```

결과:
- `py_compile` 통과
- `tests/test_risk_manager_position_cap_alignment.py`: `3 passed`
- `tests/test_strategy_position_sizing.py` + 신규 테스트: `5 passed`

### 부분 실패한 검증
```bash
env PYTHONPATH=. .venv/bin/pytest -q tests/test_risk.py tests/test_risk_manager_trade_counts.py tests/test_risk_manager_position_cap_alignment.py
```

결과:
- `2 passed, 7 errors`
- 에러 유형: `ConnectionRefusedError: ('127.0.0.1', 5432)`

측정 불가 사유:
- 로컬 PostgreSQL test DB(`coinpilot_test`)가 실행 중이지 않아 DB 의존 테스트가 실패했다.

대체 지표:
- pure unit test와 sizing 전용 회귀 테스트는 모두 통과했다.
- 수식 정렬 자체는 deterministic helper 테스트로 재현/검증했다.

추후 측정 계획:
- OCI 또는 로컬 test DB가 준비된 환경에서 DB-backed risk regression을 재실행한다.

## 5. 증빙 근거
- 코드:
  - [risk_manager.py](/home/syt07203/workspace/coin-pilot/src/engine/risk_manager.py)
  - [main.py](/home/syt07203/workspace/coin-pilot/src/bot/main.py)
- 테스트:
  - [test_risk_manager_position_cap_alignment.py](/home/syt07203/workspace/coin-pilot/tests/test_risk_manager_position_cap_alignment.py)
- 관련 운영 해석 문서:
  - [29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md](/home/syt07203/workspace/coin-pilot/docs/work-result/29-01_bull_regime_rule_funnel_observability_and_review_automation_result.md)
  - [30_strategy_feedback_automation_spec_first_result.md](/home/syt07203/workspace/coin-pilot/docs/work-result/30_strategy_feedback_automation_spec_first_result.md)

## 6. 영향 및 후속
- 이번 변경은 "리스크를 완화"한 작업이 아니다.
- 설계 mismatch를 제거해 `max_per_order` 병목 해석이 신뢰 가능하도록 만든 작업이다.
- 실제 손익 개선 여부는 별도 전략 품질/리스크 정책 검증으로 판단해야 한다.
- 후속으로는 `29-01/30` 문서에서 `max_per_order` 병목을 재해석할 때, "정렬 전 운영 구간"과 "정렬 후 운영 구간"을 구분해 봐야 한다.

## 7. README 동기화 확인
- 이번 변경 세트에서 [README.md](/home/syt07203/workspace/coin-pilot/README.md)를 함께 갱신했다.
- 반영 내용:
  - 포지션 사이징 설명을 `3중 캡 + 동적 하드 캡 정렬 로직` 기준으로 수정
  - 현재 백로그 상태에서 `28`을 `in_progress`로 동기화

