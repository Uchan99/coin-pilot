# 34. AdaptiveMeanReversion 전략 4단계 개선 계획

**작성일**: 2026-03-27
**작성자**: Claude (assistant)
**상태**: Approval Pending
**관련 계획 문서**: `docs/work-plans/33_strategy_exit_parameter_tuning_plan.md`
**승인 정보**: 사용자 승인 (2026-03-27) — 데이터 분석 결과로 volume_surge 필터 폐기 후 3단계로 재편
**변경 이력**:
- 2026-03-27: 초안 작성 및 승인 (3단계 구조)
- 2026-03-28: **실거래 데이터 심층 분석 반영하여 4단계로 재편** (Approval Pending)
  - STOP_LOSS 클러스터 분석 → 1단계(동시 포지션 제한) 신규 추가
  - BB_MIDLINE_EXIT 성공 기준 수정 (STOP_LOSS 방지 → TIME_LIMIT 손실 축소)
  - 데이터 근거 섹션 보강

---

## 0. 트리거(Why started)

- **1개월 실운영 데이터 분석**: 38건 거래, 평균 P&L -0.33%/거래, 누적 -1.87% (-18,700원 on 100만원 seed)
- **R:R 역전 확인**: 평균 수익 +1.28% vs 평균 손실 -3.86%, 손익분기 승률 73.5% 요구 vs 실제 66.7%
- **청산 파라미터 튜닝 결과 (33번 작업)**: SL%, min_profit%, rsi_overbought 3가지 시도 → 모두 개선 미미
- 근본 원인: **상관 손실 집중** + **exit 조건 미흡** + **AI 판단 품질 개선 여지**

---

## 1. 문제 요약

### 증상
- 평균 손실(-3.86%)이 평균 수익(+1.28%)의 3배 이상 → R:R 역전
- **STOP_LOSS 9건 중 7건이 2~3심볼 동시 발생** → 시장 전체 급락 시 상관 손실 집중
- 수익 구간에서 BB 중심선(MA20) 복귀 실패 시 TIME_LIMIT로 전환되는 패턴
- Analyst의 boundary_violation 33.6% — 금지어 위주 프롬프트로 무엇을 봐야 하는지 불명확
- Guardian이 숫자 지표만 받아 캔들 흐름 기반 위험 판단 불가

### 영향 범위
- **수익성**: 1개월 -1.87% 손실, R:R 역전으로 구조적 손실 지속
- **리스크 집중**: 동시 다심볼 SL 발생 시 단일 이벤트로 누적 손실의 대부분 발생
- **AI 판단 품질**: Analyst 33.6% boundary_violation, Guardian OHLC 정보 부재

---

## 2. 원인 분석

### ~~Root cause (폐기): SIDEWAYS volume_surge 필터 부재~~

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

### Root cause 1 (신규): 포트폴리오 레벨 상관 손실 집중

> **실거래 데이터 심층 분석으로 발견 (2026-03-28)**

- STOP_LOSS 9건의 시간 분포를 분석한 결과, **7건이 2~3심볼 동시 발생**:

| 날짜 | 동시 SL 건수 | 심볼 | PnL 합계 |
|------|-------------|------|----------|
| 2/27 | 2건 | XRP(-4.33%), SOL(-3.09%) | **-7.42%** |
| 2/28 | 3건 | ETH(-4.01%), XRP(-4.02%), DOGE(-4.29%) | **-12.32%** |
| 3/22 | 2건 | SOL(-4.17%), ETH(-4.03%) | **-8.20%** |

- 이 3개 이벤트(7건)의 손실 합계: **-27.94%** → 전체 STOP_LOSS 손실의 대부분
- 현재 `MAX_CONCURRENT_POSITIONS = 3` → 시장 크래시 시 3심볼이 동시에 SL에 진입
- **핵심 문제**: 개별 거래의 exit 로직이 아니라, **동시 노출(exposure)**이 손실 집중의 주 원인

### Root cause 2: exit 조건 미흡 — BB 중심선(MA20) 도달 시 익절 없음

- 현재 exit 순서: STOP_LOSS → TRAILING_STOP → TAKE_PROFIT → RSI_OVERBOUGHT → TIME_LIMIT
- SIDEWAYS 평균 회귀 전략: BB 하단 진입 → MA20(평균)으로 회귀가 목표
- 가격이 MA20에 도달해도 청산 조건 없음 → 이후 하락 시 TIME_LIMIT(-2.24%) 또는 STOP_LOSS(-3.86%)로 전환
- **존 볼린저의 권고**: BB 중심선 도달 시 청산이 횡보 전략의 기본 출구

> **STOP_LOSS 방지 효과에 대한 현실적 기대치 조정 (2026-03-28)**
>
> STOP_LOSS 거래의 청산 시점 RSI14: 16~36 (극심한 과매도)
> → 대부분 "진입 → 한 번도 MA20에 도달하지 못하고 → 즉시 하락 → SL" 패턴
> → BB_MIDLINE_EXIT가 STOP_LOSS를 직접 방지할 가능성은 **낮음**
>
> **실제 효과 대상**: TIME_LIMIT 3건(avg -2.24%) — 48h 보유 중 MA20 터치 후 하락한 경우 조기 익절 가능
> → BB_MIDLINE_EXIT의 주 효과는 **TIME_LIMIT 손실 축소** + **수익 확보 빈도 증가**

### Root cause 3: Analyst 프롬프트 판단 기준 불명확

- 현재: "RSI/MA/Volume 재판단 금지" 등 **금지어 나열** 위주
- boundary_violation 33.6% → Analyst가 Rule Engine 항목 재판단 시도 반복
- 기술적 지표로 수익/손절 구분 불가(데이터 증명) → **캔들 패턴 판단이 유일한 추가 정보**
- CONFIRM 기준이 "장악형 양봉인지, 망치형인지" 등 구체적 패턴으로 명시되지 않음

### Root cause 4: Guardian 정보 부족

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
| **진입 필터 추가 (volume_surge_check)** | SIDEWAYS에 거래량 급증 차단 | ❌ 폐기 | 데이터 분석: 진입 vol_ratio 0.81x(평균) → 역사적 차단 건수 거의 없음 |
| **시간 기반 동적 SL** | 보유 시간 길어질수록 SL 축소 | ❌ 보류 | 구현 복잡, SIDEWAYS에서 시간이 약이 될 수도 있어 효과 불확실 |
| **부분 청산** | 목표가 도달 시 50% 청산, 나머지 trailing | ❌ 보류 | 현 아키텍처 미지원, 장기 과제 (avg_win 감소 vs SL 방지의 이상적 해결책) |
| **4단계 순차 개선 (채택)** | 동시 포지션 제한 + exit 로직 + AI 프롬프트 + Guardian 강화 | ✅ 채택 | 각 단계 데이터 근거 명확, 코드/프롬프트 단계적 검증 가능 |

---

## 4. 4단계 구현 계획

### 1단계: 포트폴리오 동시 포지션 제한 축소 (3 → 2)

**목적**: 시장 전체 급락 시 상관 손실 집중 완화
**변경 파일**: `src/config/strategy.py`
**데이터 근거**: STOP_LOSS 9건 중 7건이 2~3심볼 동시 발생 → 동시 노출이 손실 집중의 주 원인

**변경 내용**:
```python
# src/config/strategy.py line 155
MAX_CONCURRENT_POSITIONS: int = 2  # 기존 3 → 2로 축소
```

**효과 추정**:
- 2/28 3건 동시 SL(합계 -12.32%) → 2건 제한 시 최소 1건(-4.01~4.29%) 차단
- 보수적 추정: **-4%p 손실 절감** (38건 기준 -0.11%/건 개선)
- 가장 큰 단일 이벤트(2/28 -12.32%)가 -8.03%로 축소

**아키텍처 대안 비교**:

| 대안 | 설명 | 채택 여부 | 트레이드오프 |
|------|------|-----------|------------|
| MAX_CONCURRENT_POSITIONS = 2 (채택) | 단순 하드캡 축소 | ✅ | 구현 1줄. 상승장에서 3번째 심볼 기회 손실 |
| 상관 자산 그룹별 제한 | ETH/SOL 같은 상관도 높은 그룹별 1개 | 보류 | 정교하지만 상관도 계산/유지 복잡. 데이터 부족 |
| 동일 시간대 진입 쿨다운 | 같은 1h 내 2번째 진입부터 거부 | 보류 | 시간 기반이라 정교하지만, 1h 밖에서도 동시 보유는 가능 |
| MAX = 1 (극단적 보수) | 동시 1개만 보유 | ❌ 기각 | 기회 비용 과다. 수익 거래도 절반으로 감소 |

**리스크 & 완화**:
- **기회 비용**: 수익 거래도 동시 2개로 제한 → 누적 수익 감소 가능
- **완화**: 실운영 2주 후 "3번째 심볼 진입 차단 횟수 중 수익 전환 가능 비율" SQL로 검증
- **추가 완화**: 기존 rule_funnel에 `max_concurrent_positions` reason_code로 자동 기록됨 → 기회 비용 정량 추적 가능

**검증**: 코드 변경 즉시 적용 가능, 별도 백테스트 불필요 (리스크 관리 파라미터)
**성공 기준**: 동시 3심볼 SL 이벤트 재발 없음

---

### 2단계: BB 중심선(MA20) 도달 시 익절 exit (구현 완료 — 검증 필요)

**목적**: 수익 구간에서 BB 중심선(MA20) 도달 시 조기 익절 → TIME_LIMIT 손실 전환 방지
**변경 파일**: `src/engine/strategy.py` (이미 구현됨, v3.4)
**현재 코드 상태**: `strategy.py:312-322` — `close >= bb_mid AND pnl_ratio >= 0.003`

**구현된 exit 조건** (SIDEWAYS 레짐 전용):
- `close >= bb_mid` (BB 중심선 MA20 **도달**)
- `pnl_ratio >= 0.003` (0.3% 최소 수익 가드 — 노이즈 청산 방지)
- exit_reason: `BB_MIDLINE_EXIT`
- 우선순위: STOP_LOSS → TRAILING_STOP → TAKE_PROFIT → **BB_MIDLINE_EXIT** → RSI_OVERBOUGHT → TIME_LIMIT

> **Plan 초안(close < ma20 "하향 이탈") vs 실제 구현(close >= bb_mid "도달") 차이 설명**:
>
> 초안은 "BB 중심선 이탈 = 전제 붕괴 → 방어 청산"으로 설계했으나,
> 커밋 `710398b`에서 "BB 하단 진입 → MA20 회귀 = 목표 달성 → 수익 확정"으로 변경.
> SIDEWAYS 평균 회귀 전략에서는 **MA20 도달 = 목표가 도달**이 더 논리적으로 정합적임.

**아키텍처 대안 비교**:

| 대안 | 설명 | 채택 여부 | 트레이드오프 |
|------|------|-----------|------------|
| `close >= bb_mid` 도달 시 청산 (채택) | MA20 도달 = 평균 회귀 완성 → 수익 확정 | ✅ | 단순, 전략 논리 정합. 단점: RSI_OVERBOUGHT(+1.26%) 대비 조기 청산으로 avg_win 감소 가능 |
| `close >= bb_mid` + 연속 N캔들 확인 | N캔들 연속 MA20 위 유지 시 청산 | 보류 | 노이즈 감소 but 반응 지연 → 이후 하락 시 수익 유실 |
| `close < bb_lower` (BB 하단 재돌파) | BB 하단 아래로 떨어질 때 청산 | ❌ 기각 | 이미 크게 하락 후 청산 → 너무 늦음 |
| pnl 조건 없이 항상 청산 | 수익/손실 무관하게 MA20 도달 시 청산 | ❌ 기각 | 손실 중 추가 조기 청산 → STOP_LOSS보다 불리 |

**0.3% 가드 수치 검증 필요**:
- 현재 0.3%는 수수료(0.05% x 2 = 0.1%) 커버 + 약간의 마진을 고려한 감각적 기준
- 백테스트에서 0.1%, 0.3%, 0.5%, 1.0% 등 여러 임계값 비교 필요
- 너무 낮으면(0.1%) 노이즈 청산 증가, 너무 높으면(1.0%) BB_MIDLINE_EXIT 발동 빈도 감소

**백테스트**: `backtest_v3.py` baseline vs tuned 비교
**성공 기준** (수정):
- ~~STOP_LOSS 비율 감소~~ → **TIME_LIMIT 손실 건의 avg_loss 개선**
- avg_win 감소폭이 0.3%p 이내 (기존 +1.28% → 최소 +0.98% 이상 유지)
- BB_MIDLINE_EXIT 발동 건의 평균 PnL > 0.3% (의미 있는 수익 확보)

---

### 3단계: Analyst 프롬프트 판단 기준 구체화

**목적**: 금지어 나열 → 구체적 캔들 패턴 판단 기준으로 전환, boundary_violation 감소
**변경 파일**: `src/agents/prompts.py`

**데이터 근거**: 기술 지표(RSI/vol/MA)로는 수익/손절 구분 불가 → 캔들 패턴이 AI의 유일한 추가 변별 정보

**개선 방향**:
- CONFIRM 기준 명시: 최근 1~2캔들 장악형 양봉(몸통 > 이전 캔들 범위), 망치형(아래꼬리 > 몸통 2배)
- REJECT 기준 명시: 음봉 3개 이상 연속, 위꼬리 몸통의 2배 이상 (상단 저항)
- "RSI/MA/거래량은 Rule Engine이 이미 확인했습니다. 재판단하지 마십시오" 명시 강화

**성공 기준**: boundary_violation 비율 33.6% → 20% 이하

---

### 4단계: Guardian OHLC 캔들 컨텍스트 전달

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
| 1단계 | strategy.py (config) | 실운영 2주 후 SQL | 동시 3심볼 SL 이벤트 재발 없음, 기회 비용 추적 |
| 2단계 | strategy.py (exit) | backtest_v3.py baseline vs tuned | TIME_LIMIT avg_loss 개선, avg_win 감소 0.3%p 이내 |
| 3단계 | prompts.py | 실운영 2주 후 SQL | boundary_violation 33.6% → 20% 이하 |
| 4단계 | guardian.py + prompts.py | 실운영 2주 후 reasoning 샘플링 | 캔들 구조 언급 reasoning 비율 증가 |

### 백테스트 명령 (2단계)
```bash
# OCI에서 실행
docker exec coinpilot-bot python scripts/backtest_v3.py
docker exec coinpilot-bot python scripts/backtest_v3.py --config config/strategy_v3_tuned.yaml
```

### 실운영 검증 SQL (1단계 — 기회 비용 추적)
```sql
-- 동시 포지션 제한으로 차단된 진입 건수 & 이후 해당 심볼 가격 변화
SELECT
  COUNT(*) FILTER (WHERE reason_code = 'max_per_order' OR reason_code LIKE '%포지션 한도%') AS blocked_by_position_limit,
  COUNT(*) AS total_risk_rejects
FROM rule_funnel_events
WHERE stage = 'risk_reject'
  AND created_at >= NOW() - INTERVAL '14 days';
```

### 실운영 검증 SQL (1단계 — 동시 SL 재발 확인)
```sql
-- 동일 날짜에 2건 이상 STOP_LOSS가 발생했는지 확인
SELECT
  DATE(created_at AT TIME ZONE 'Asia/Seoul') AS kst_date,
  COUNT(*) AS sl_count,
  ARRAY_AGG(symbol) AS symbols,
  SUM(pnl_pct) AS total_pnl
FROM trading_history
WHERE exit_reason = 'STOP_LOSS'
  AND created_at >= NOW() - INTERVAL '14 days'
GROUP BY DATE(created_at AT TIME ZONE 'Asia/Seoul')
HAVING COUNT(*) >= 2
ORDER BY kst_date;
```

### 실운영 검증 SQL (3단계)
```sql
SELECT
  COUNT(*) FILTER (WHERE (meta->>'boundary_violation')::boolean = true) AS boundary_cnt,
  COUNT(*) AS total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE (meta->>'boundary_violation')::boolean = true) / COUNT(*), 1) AS pct
FROM agent_decisions
WHERE route = 'ai_decision_analyst'
  AND created_at >= NOW() - INTERVAL '14 days';
```

### 실운영 검증 SQL (4단계)
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
1단계 (즉시) → MAX_CONCURRENT_POSITIONS 3→2 변경 → OCI 배포
    ↓
2단계 (1단계와 동시 또는 직후) → backtest_v3.py 검증 → BB_MIDLINE_EXIT OCI 배포
    ↓
3단계 (1·2단계 배포 후) → 2주 실운영 관측
    ↓
4단계 (3단계 안정 확인 후) → 2주 실운영 관측
```

> **1단계와 2단계를 동시 배포 가능한 이유**:
> - 1단계(포지션 제한)는 리스크 관리 파라미터, 2단계(exit 로직)는 청산 조건 — 상호 독립
> - 동시 변경해도 각각의 효과를 구분할 수 있음 (rule_funnel vs exit_reason으로 분리 측정)

---

## 7. 롤백 계획

| 단계 | 롤백 방법 |
|------|-----------|
| 1단계 | `src/config/strategy.py` — MAX_CONCURRENT_POSITIONS를 3으로 복원 |
| 2단계 | `src/engine/strategy.py` git revert (BB_MIDLINE_EXIT 블록 제거) |
| 3단계 | `src/agents/prompts.py` git revert |
| 4단계 | `src/agents/guardian.py` + `prompts.py` git revert |

---

## 8. 변경 파일 목록

| 단계 | 파일 | 변경 내용 |
|------|------|-----------|
| 1 | `src/config/strategy.py` | `MAX_CONCURRENT_POSITIONS: 3 → 2` |
| 2 | `src/engine/strategy.py` | `check_exit_signal()` — SIDEWAYS 전용 `BB_MIDLINE_EXIT` 조건 (이미 구현, 검증 필요) |
| 3 | `src/agents/prompts.py` | `ANALYST_SYSTEM_PROMPT` — 금지어 위주 → 장악형 양봉/망치형 등 구체 판단 기준 |
| 4 | `src/agents/guardian.py` | state에서 OHLC 캔들 추출 → human prompt에 추가 전달 |
| 4 | `src/agents/prompts.py` | `GUARDIAN_SYSTEM_PROMPT` — OHLC 캔들 활용 지침 추가 |

---

## 9. 관련 문서

- 관련 계획: `docs/work-plans/33_strategy_exit_parameter_tuning_plan.md`
- 실거래 운영 데이터: `docs/operating_data.md`
- 결과 문서: `docs/work-result/34_adaptive_mean_reversion_4stage_improvement_result.md` (구현 후 작성)
- PROJECT_CHARTER.md 업데이트: 1단계 배포(동시 포지션 제한) 완료 시 기록

---

## 10. 데이터 근거 요약

### 기존 분석 (2026-03-27)

| 지표 | 값 | 출처 | 비고 |
|------|----|------|------|
| SIDEWAYS BUY 진입 avg vol_ratio | **0.81x** | `trading_history` signal_info | volume_surge_check 폐기 근거 |
| STOP_LOSS 진입 avg vol_ratio | **0.93x** | 동일 | RSI_OVERBOUGHT(0.83x)와 거의 동일 |
| 38.14x vol_ratio | STOP_LOSS **청산 시점** vol | `trading_history` SELL side | 초기 가설 반증 |
| RSI14 진입 범위 (수익 vs 손절) | 40~47 vs 40~47 | `trading_history` JOIN | 진입 지표로 결과 구별 불가 |
| boundary_violation 비율 | 33.6% of ai_reject | `rule_funnel_events` | 3단계 개선 근거 |
| 평균 수익 | +1.28% | 실운영 38건 | |
| 평균 손실 | -3.86% | 실운영 38건 | |
| 손익분기 승률 | 73.5% 필요 / 66.7% 실제 | R:R 역산 | |

### 신규 분석 (2026-03-28) — `docs/operating_data.md` 기반

| 지표 | 값 | 출처 | 비고 |
|------|----|------|------|
| STOP_LOSS 동시 발생 비율 | 9건 중 **7건(78%)** | `trading_history` 시간 클러스터 | 1단계 신설 근거 |
| 2/28 동시 3심볼 SL 손실 | **-12.32%** | ETH+XRP+DOGE 동시 SL | 단일 최대 손실 이벤트 |
| 동시 SL 이벤트 3건 합계 | **-27.94%** | 7건 합계 | 전체 SL 손실의 대부분 |
| STOP_LOSS 청산 시점 RSI14 | **16~36** (극심한 과매도) | `trading_history` SELL side | BB_MIDLINE_EXIT 효과 제한 근거 — 진입 후 MA20 미도달 추정 |
| TIME_LIMIT 3건 avg PnL | **-2.24%** | 실운영 3건 | BB_MIDLINE_EXIT 실제 효과 대상 |
| 최악 시간대 (KST) | 15시(-2.70%), 22시(-3.76%) | `trading_history` 시간 분석 | 표본 적어 관측만 (5건, 2건) |
| 심볼별 성과 | DOGE(+1.24%) > ETH(-0.13%) > SOL(-0.25%) > XRP(-0.36%) > BTC(-1.00%) | `trading_history` | DOGE 4/5 승, BTC 1/2 승 (표본 적음) |
| 퍼널: rule_pass → ai_confirm | 1361 → 26 (1.9%) | `rule_funnel_events` | 98.1% 거부율 |
| MAX_CONCURRENT_POSITIONS 현재값 | **3** | `src/config/strategy.py:155` | 1단계에서 2로 축소 |
