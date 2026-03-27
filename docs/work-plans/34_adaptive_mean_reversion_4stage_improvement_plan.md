# 34. AdaptiveMeanReversion 전략 3단계 개선 계획

**작성일**: 2026-03-27
**작성자**: Claude (assistant)
**상태**: Approved
**관련 계획 문서**: `docs/work-plans/33_strategy_exit_parameter_tuning_plan.md`
**승인 정보**: 사용자 승인 (2026-03-27) — 데이터 분석 결과로 1단계(volume_surge 필터) 폐기 후 3단계로 재편

---

## 0. 트리거(Why started)

- **1개월 실운영 데이터 분석**: 38건 거래, 평균 P&L -0.33%/거래, 누적 -1.87% (-18,700원 on 100만원 seed)
- **R:R 역전 확인**: 평균 수익 +1.28% vs 평균 손실 -3.86%, 손익분기 승률 73.5% 요구 vs 실제 66.7%
- **청산 파라미터 튜닝 결과 (33번 작업)**: SL%, min_profit%, rsi_overbought 3가지 시도 → 모두 개선 미미
- 근본 원인: **exit 조건 미흡** + **AI 판단 품질 개선 여지**

---

## 1. 문제 요약

### 증상
- 평균 손실(-3.86%)이 평균 수익(+1.28%)의 3배 이상 → R:R 역전
- 수익 구간에서 BB 중심선(MA20) 복귀 실패 시 STOP_LOSS 또는 TIME_LIMIT로 전환되는 패턴
- Analyst의 boundary_violation 33.6% — 금지어 위주 프롬프트로 무엇을 봐야 하는지 불명확
- Guardian이 숫자 지표만 받아 캔들 흐름 기반 위험 판단 불가

### 영향 범위
- **수익성**: 1개월 -1.87% 손실, R:R 역전으로 구조적 손실 지속
- **AI 판단 품질**: Analyst 33.6% boundary_violation, Guardian OHLC 정보 부재

---

## 2. 원인 분석

### ~~Root cause 1 (폐기): SIDEWAYS volume_surge 필터 부재~~

> **데이터로 반증됨 (2026-03-27)**
>
> 초기 가설: "STOP_LOSS 진입의 avg vol_ratio = 38.14x → 패닉 구간 진입이 손실 원인"
>
> **실제 데이터**:
> - BUY 진입 시 vol_ratio: 평균 **0.81x** (97%가 < 2x) — 진입은 항상 저거래량
> - 38.14x는 STOP_LOSS **청산 시점**의 vol_ratio였음 (진입 시점 아님)
> - STOP_LOSS vs RSI_OVERBOUGHT 진입 지표 비교: RSI14(40-47), RSI7(42-57), vol_ratio(0.4-2.3) **모두 동일**
> - `volume_surge_check` 추가 시 역사적으로 차단될 진입이 거의 없음 → **효과 없음**
>
> **패턴 재정의**: 진입은 잔잔(0.81x) → 진입 후 시장이 하락 → STOP_LOSS 청산 시 패닉(246x)
> → 진입 필터가 아닌 **진입 후 대응(청산 로직)**과 **AI 질적 분석 강화**가 올바른 방향

### Root cause 1: exit 조건 미흡 — BB 중심선(MA20) 이탈 시 익절 없음

- 현재 exit 순서: STOP_LOSS → TRAILING_STOP → TAKE_PROFIT → RSI_OVERBOUGHT → TIME_LIMIT
- BB 중심선(MA20) 하향 이탈 = SIDEWAYS 전략의 전제 조건(BB 밴드 내 횡보) 붕괴
- 이탈 후 가격이 계속 하락하면 수익이 손실로 전환되어 STOP_LOSS 청산
- **존 볼린저의 권고**: BB 중심선 이탈 시 청산이 횡보 전략의 기본 출구

### Root cause 2: Analyst 프롬프트 판단 기준 불명확

- 현재: "RSI/MA/Volume 재판단 금지" 등 **금지어 나열** 위주
- boundary_violation 33.6% → Analyst가 Rule Engine 항목 재판단 시도 반복
- 기술적 지표로 수익/손절 구분 불가(데이터 증명) → **캔들 패턴 판단이 유일한 추가 정보**
- CONFIRM 기준이 "장악형 양봉인지, 망치형인지" 등 구체적 패턴으로 명시되지 않음

### Root cause 3: Guardian 정보 부족

- 현재 입력: symbol + numeric indicators (RSI, vol_ratio 등 숫자만)
- OHLC 캔들 없이 "가짜 돌파(Head Fake)", "급락 중" 판단 불가
- 최종 위험 차단 역할이 구조적으로 약화

---

## 3. 대응 전략

### 아키텍처 선택 및 대안 비교

| 대안 | 설명 | 채택 여부 | 이유 |
|------|------|-----------|------|
| **전략 전환** (트렌드팔로잉/BB스퀴즈) | 완전히 다른 전략으로 교체 | ❌ 기각 | 1개월 데이터로 판단 이르다. 실거래 승률 66.7% 허용 수준. 근본 원인 진단됨 |
| **파라미터 추가 튜닝** | SL/TP/RSI 범위 조정 | ❌ 기각 | 33번 작업 3가지 시도 → 모두 개선 미미 |
| **진입 필터 추가 (volume_surge_check)** | SIDEWAYS에 거래량 급증 차단 | ❌ 폐기 | 데이터 분석: 진입 vol_ratio 0.81x(평균) → 역사적 차단 건수 거의 없음. 효과 없음 확인 |
| **3단계 순차 개선 (채택)** | exit 로직 + AI 프롬프트 + Guardian 강화 | ✅ 채택 | 각 단계 데이터 근거 명확, 코드/프롬프트 단계적 검증 가능 |

---

## 4. 3단계 구현 계획

### 1단계: BB 중심선(MA20) 하향 이탈 시 익절 exit 추가

**목적**: 수익 구간에서 BB 중심선 이탈 시 조기 익절 → 손실 전환 방지
**변경 파일**: `src/engine/strategy.py`

**추가 exit 조건** (SIDEWAYS 레짐 전용):
- `close < ma20` (BB 중심선 하향 이탈)
- `current_pnl > 0` (수익 중일 때만 트리거, 손실 중엔 기존 SL에 맡김)
- exit_reason: `BB_MIDLINE_EXIT`

**아키텍처 대안 비교**:

| 대안 | 설명 | 채택 여부 | 트레이드오프 |
|------|------|-----------|------------|
| `close < ma20` 단순 이탈 (채택) | 현재가가 MA20 아래면 즉시 청산 | ✅ | 단순, 명확. 단점: MA20 위아래 노이즈로 조기 청산 가능 |
| `close < ma20` + 연속 N캔들 확인 | N캔들 연속 이탈 시 청산 | 보류 | 노이즈 감소 but 반응 지연 → 손실 확대 위험 |
| `close < bb_lower` (BB 하단 재돌파) | BB 하단 아래로 떨어질 때 청산 | ❌ 기각 | 이미 크게 하락 후 청산 → 너무 늦음 |
| pnl 조건 없이 항상 청산 | 수익/손실 무관하게 MA20 이탈 시 청산 | ❌ 기각 | 손실 중 추가 조기 청산 → STOP_LOSS보다 불리 |

**백테스트**: `backtest_v3.py` baseline vs tuned 비교
**성공 기준**: avg_win 소폭 감소 허용, STOP_LOSS 비율 감소 또는 TIME_LIMIT 비율 감소

---

### 2단계: Analyst 프롬프트 판단 기준 구체화

**목적**: 금지어 나열 → 구체적 캔들 패턴 판단 기준으로 전환, boundary_violation 감소
**변경 파일**: `src/agents/prompts.py`

**데이터 근거**: 기술 지표(RSI/vol/MA)로는 수익/손절 구분 불가 → 캔들 패턴이 AI의 유일한 추가 변별 정보

**개선 방향**:
- CONFIRM 기준 명시: 최근 1~2캔들 장악형 양봉(몸통 > 이전 캔들 범위), 망치형(아래꼬리 > 몸통 2배)
- REJECT 기준 명시: 음봉 3개 이상 연속, 위꼬리 몸통의 2배 이상 (상단 저항)
- "RSI/MA/거래량은 Rule Engine이 이미 확인했습니다. 재판단하지 마십시오" 명시 강화

**성공 기준**: boundary_violation 비율 33.6% → 20% 이하

---

### 3단계: Guardian OHLC 캔들 컨텍스트 전달

**목적**: 최종 위험 차단 강화 — Head Fake, 급락 흐름 감지
**변경 파일**: `src/agents/guardian.py`, `src/agents/prompts.py`

**현재 입력**: symbol + numeric indicators
**추가 입력**: 최근 6개 1시간봉 OHLC (Analyst의 `sanitize_market_context_for_analyst` 동일 로직)

**아키텍처 대안 비교**:

| 대안 | 설명 | 채택 여부 | 트레이드오프 |
|------|------|-----------|------------|
| 최근 6개 OHLC 전달 (채택) | Analyst와 동일 범위 | ✅ | 일관성, 토큰 증가 최소화 |
| 최근 12개 OHLC 전달 | 더 많은 컨텍스트 | 보류 | 토큰 비용 증가, 단기 패턴엔 6개면 충분 |
| 패턴 요약 피처만 전달 | direction/streak 등 숫자 요약 | ❌ 기각 | Guardian이 raw 캔들 구조 직접 해석해야 효과 있음 |

**성공 기준**: Guardian reasoning에 "캔들 패턴", "하락 흐름", "위꼬리" 등 구조적 언급 증가

---

## 5. 단계별 검증 기준

| 단계 | 변경 범위 | 검증 방법 | 성공 기준 |
|------|-----------|-----------|-----------|
| 1단계 | strategy.py | backtest_v3.py baseline vs tuned | STOP_LOSS 또는 TIME_LIMIT 비율 감소, avg_loss 개선 |
| 2단계 | prompts.py | 실운영 2주 후 SQL | boundary_violation 33.6% → 20% 이하 |
| 3단계 | guardian.py + prompts.py | 실운영 2주 후 reasoning 샘플링 | 캔들 구조 언급 reasoning 비율 증가 |

### 백테스트 명령 (1단계)
```bash
# OCI에서 실행
docker exec coinpilot-bot python scripts/backtest_v3.py
docker exec coinpilot-bot python scripts/backtest_v3.py --config config/strategy_v3_tuned.yaml
```

### 실운영 검증 SQL (2단계)
```sql
SELECT
  COUNT(*) FILTER (WHERE (meta->>'boundary_violation')::boolean = true) AS boundary_cnt,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE (meta->>'boundary_violation')::boolean = true) / COUNT(*), 1) AS pct
FROM agent_decisions
WHERE route = 'ai_decision_analyst'
  AND created_at >= NOW() - INTERVAL '14 days';
```

### 실운영 검증 SQL (3단계)
```sql
SELECT reasoning, created_at
FROM agent_decisions
WHERE route = 'ai_decision_guardian'
  AND created_at >= NOW() - INTERVAL '14 days'
ORDER BY created_at DESC
LIMIT 20;
```

---

## 6. 구현 순서

```
1단계 (즉시) → backtest_v3.py 검증 → OCI 배포
    ↓
2단계 (1단계 배포 후) → 2주 실운영 관측
    ↓
3단계 (2단계 안정 확인 후) → 2주 실운영 관측
```

---

## 7. 롤백 계획

| 단계 | 롤백 방법 |
|------|-----------|
| 1단계 | `src/engine/strategy.py` git revert |
| 2단계 | `src/agents/prompts.py` git revert |
| 3단계 | `src/agents/guardian.py` + `prompts.py` git revert |

---

## 8. 변경 파일 목록

| 단계 | 파일 | 변경 내용 |
|------|------|-----------|
| 1 | `src/engine/strategy.py` | `check_exit_signal()` — SIDEWAYS 전용 `BB_MIDLINE_EXIT` 조건 추가 |
| 2 | `src/agents/prompts.py` | `ANALYST_SYSTEM_PROMPT` — 금지어 위주 → 장악형 양봉/망치형 등 구체 판단 기준 |
| 3 | `src/agents/guardian.py` | state에서 OHLC 캔들 추출 → human prompt에 추가 전달 |
| 3 | `src/agents/prompts.py` | `GUARDIAN_SYSTEM_PROMPT` — OHLC 캔들 활용 지침 추가 |

---

## 9. 관련 문서

- 관련 계획: `docs/work-plans/33_strategy_exit_parameter_tuning_plan.md`
- 결과 문서: `docs/work-result/34_adaptive_mean_reversion_4stage_improvement_result.md` (구현 후 작성)
- PROJECT_CHARTER.md 업데이트: 1단계 배포(strategy.py) 완료 시 기록

---

## 10. 데이터 근거 요약

| 지표 | 값 | 출처 | 비고 |
|------|----|------|------|
| SIDEWAYS BUY 진입 avg vol_ratio | **0.81x** | `trading_history` signal_info | volume_surge_check 폐기 근거 |
| STOP_LOSS 진입 avg vol_ratio | **0.93x** | 동일 | RSI_OVERBOUGHT(0.83x)와 거의 동일 |
| 38.14x vol_ratio | STOP_LOSS **청산 시점** vol | `trading_history` SELL side | 초기 가설 반증 |
| RSI14 진입 범위 (수익 vs 손절) | 40~47 vs 40~47 | `trading_history` JOIN | 진입 지표로 결과 구별 불가 |
| boundary_violation 비율 | 33.6% of ai_reject | `rule_funnel_events` | 2단계 개선 근거 |
| 평균 수익 | +1.28% | 실운영 38건 | |
| 평균 손실 | -3.86% | 실운영 38건 | |
| 손익분기 승률 | 73.5% 필요 / 66.7% 실제 | R:R 역산 | |
