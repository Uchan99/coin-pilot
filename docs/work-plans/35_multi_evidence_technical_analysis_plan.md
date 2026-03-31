# 35. 다중 근거 기술적 분석(Multi-Evidence TA) 진입 체계 도입

**작성일**: 2026-03-31
**작성자**: Claude (assistant)
**상태**: Approved
**관련 문서**:
- Charter: docs/PROJECT_CHARTER.md
- 전략 참고: docs/strategy/TradingMethod.md
- 선행 작업: docs/work-plans/34_adaptive_mean_reversion_4stage_improvement_plan.md (Phase 5 결과 활용)
**승인 정보**: -

**변경 이력**:
- 2026-03-31: 초안 작성 (백테스트 우선 검증 계획)
- 2026-03-31: v2 — 외부 피드백 반영 (Unmitigated 구간 추적, MTF 필터, 구조적 R:R 사전 필터)
- 2026-03-31: v2.1 — 2차 피드백 반영 (R:R 기본값 2.0→3.0 상향, 최소 근거 N=2 확정)

---

## 0. 트리거(Why started)
- 34번 Phase 5 분석에서 Rule Engine 진입 조건이 과도하게 관대함 발견 (1,361건 통과 중 AI Confirm 26건 = 1.9%)
- 현재 진입 로직은 RSI/BB/MA/거래량 수치 기반 → 가격 구조(수급/세력 흔적)를 반영하지 못함
- 사용자가 오더블럭/FVG/추세선/채널/Fakeout/스윙 프렉탈 기반 다중 근거 진입 체계를 제안
- 핵심 원칙: **단일 지표가 아닌 여러 근거가 겹치는 구간에서만 진입** (승률 극대화)

---

## 1. 문제 요약
- **증상**: Rule Engine이 너무 많은 신호를 통과시키고 (98.1% AI 거부), AI 필터에 과도하게 의존
- **영향**: AI 호출 비용 낭비 + AI 판단 오류 시 저품질 진입 가능성
- **근본 원인**: 현재 진입 조건이 수치 임계값(RSI < 48, MA proximity 등) 기반이라 가격 구조/수급 패턴을 포착하지 못함

---

## 2. 제안 전략: 다중 근거 스코어링

### 2.1 5가지 기술적 분석 피처

| # | 피처 | 정의 | 자동화 | 백테스트 |
|---|------|------|--------|---------|
| 1 | **오더블럭 (Order Block)** | 이전 캔들 몸통을 완전히 감싸는 장악형 캔들 → 지지/저항 구간 | ✅ OHLC 연산 | ✅ |
| 2 | **FVG (Fair Value Gap)** | 3캔들 사이 겹치지 않는 빈 공간(갭) → 되돌림 시 지지/저항 | ✅ High/Low 비교 | ✅ |
| 3 | **스윙 프렉탈 (Swing Fractal)** | 3캔들 중 가운데가 최고/최저 → 유동성 밀집 위치 파악 | ✅ 3캔들 비교 | ✅ |
| 4 | **추세선/채널** | 저점-저점 또는 고점-고점 연결선 + 평행선 → 지지/저항 구간 | ❌ 자동 작도 난이도 높음 | ❌ |
| 5 | **Fakeout/Trap** | 주요 지지/저항선 돌파 후 즉시 복귀 → 역진입 타점 | ⚠️ BB/스윙 저점 기반 부분 자동화 | ⚠️ |

### 2.2 적용 방식 (A+B 조합)

**Rule Engine 레이어 (자동 계산):**
- 오더블럭, FVG, 스윙 프렉탈 → 수치 피처로 계산하여 `indicators`에 추가
- Unmitigated(미해소) 구간만 유효 — 가격이 이미 침범한 구간은 무효화
- 구조적 R:R 사전 필터링 — 손익비 3:1 미만이면 스코어 탈락
- 기존 RSI/BB/MA 조건과 함께 스코어링

**AI Analyst 레이어 (LLM 판단):**
- 추세선/채널 구조, Fakeout 패턴 → OHLC 데이터 기반 AI 판단
- 프롬프트에 "다중 근거 N개 이상 충족 시 CONFIRM" 기준 반영

### 2.3 진입 규칙 (안)
```
전체 근거 점수 = Rule Engine 자동 피처 점수 + AI 판단 점수
진입 조건: 전체 근거 ≥ 2개 충족 (최소 2개 — 원칙: "근거가 2개 이상일 때만 진입")
추가 가드: 구조적 손절매 기반 R:R ≥ 3:1 필수 (원칙: "손익비 최소 3:1 이상")
```

---

## 3. 외부 피드백 반영 (v2 변경사항)

### 3.1 피드백 요약

| # | 지적 사항 | 핵심 | 반영 |
|---|----------|------|------|
| 1 | lookback=10은 너무 짧음 | SMC/ICT에서 신뢰도 높은 OB/FVG는 수십 캔들 전에 형성되어 미해소 상태로 유지 | lookback 100~200으로 확장 + Unmitigated 추적 |
| 2 | 구조적 손절매(Structural SL) 부재 | OB/FVG 존재만 확인하고 R:R 계산 안 하면 불량 타점 통과 | R:R 사전 필터 추가 (OB 하단 + ATR 버퍼 = SL, 스윙 고점 = TP, **기본 R:R ≥ 3.0**) |
| 3 | 시간대/세션 맥락 누락 | 아시아 세션 OB vs 뉴욕 세션 OB 신뢰도 차이 | 상위 타임프레임(HTF) 추세 정렬 필터 추가 |

### 3.2 반영 내용

**3.2.1 Unmitigated(미해소) 구간 추적**
- 초안: `lookback=10`으로 최근 OB/FVG만 감지
- 변경: `lookback=168` (1시간봉 × 168 = 7일)로 확장, 형성된 모든 OB/FVG를 배열로 관리
- 이후 가격이 해당 구간을 침범(Mitigate)했는지 추적 → 미해소 구간만 유효 반환
- 왜 7일: 현재 전략이 1시간봉 기반, 코인 시장 특성상 7일 이상 된 구간은 유효성 급감

**3.2.2 구조적 R:R 사전 필터링**
- AI 호출 전에 Rule Engine 단에서 "이 타점에 진입하면 R:R이 최소 2:1인가" 자동 계산
- 손절가(SL): OB 하단 또는 스윙 저점 - ATR(14) × 0.5 버퍼
- 익절 목표(TP): 가장 가까운 반대편 유동성 구간 (스윙 고점 또는 약세 OB)
- R:R < 3.0이면 스코어링에서 탈락 → AI에게 넘기지 않음

**3.2.3 상위 타임프레임(HTF) 추세 정렬**
- 현재 데이터: 1분봉 수집 → 1시간봉 리샘플링 (`resample_to_hourly()`)
- 추가: 4시간봉 리샘플링 함수 구현 (1분봉 원본으로부터 가능)
- `htf_trend_alignment` 피처: 4시간봉 추세 방향과 1시간봉 진입 방향 일치 여부
- 불일치 시 스코어 감점 또는 진입 차단

**3.2.4 세션 가중치 (코인 시장 적응)**
- 전통 시장: 아시아/런던/뉴욕 세션 구분
- 코인 시장: 24시간 운영이지만, 미국 시장 시간대(22:00~06:00 KST)에 변동성 집중
- 구현: OB/FVG 형성 시간대 기록 → 고변동성 시간대 형성 구간에 가중치 부여
- 백테스트에서 시간대별 OB 신뢰도를 검증하여 가중치 결정

---

## 4. 대안 비교

| # | 대안 | 채택 | 장점 | 단점 |
|---|------|------|------|------|
| 1 | **Rule Engine 피처 확장 + Unmitigated 추적 + R:R 필터 + HTF 정렬 (채택)** | ✅ | 기존 아키텍처 유지, 백테스트 가능 3개 피처 + R:R 가드 + HTF 필터. 단계적 검증 | 구현 복잡도 증가 (Unmitigated 배열 관리) |
| 2 | 초안 방식 (lookback=10, R:R 없음) | ❌ | 구현 간단 | 핵심 유동성 구간 누락, 불량 타점 필터링 불가 |
| 3 | AI에게 전부 위임 (프롬프트만 변경) | ❌ | 구현 최소 | LLM 판단 일관성 불확실, 백테스트 불가, 비용 증가 |
| 4 | 별도 스코어링 엔진 신설 | ❌ | 가장 정교 | 아키텍처 대규모 변경 |
| 5 | TradingView 시그널 외부 연동 | ❌ | 추세선/채널 포함 완전 자동화 | 외부 의존성, API 비용, 실시간성 문제 |

---

## 5. 구현 계획

### Phase 1: 피처 계산 함수 구현 + 백테스트 (코드 변경 없이 검증)

**목적**: 오더블럭/FVG/스윙 프렉탈 + Unmitigated 추적 + R:R 필터가 실제 진입 품질 개선에 유효한지 데이터로 확인

**5.1 오더블럭 (Order Block) 감지 — Unmitigated 추적 포함**
```python
def detect_order_blocks(candles: List[Dict], lookback: int = 168) -> Dict:
    """
    최근 lookback(7일) 캔들에서 장악형 캔들(Engulfing) 감지 후,
    이후 가격이 해당 구간을 침범(Mitigate)했는지 추적.
    미해소(Unmitigated) 구간만 유효 반환.

    감지 로직:
    - 강세 OB: 음봉 → 양봉이 음봉 몸통을 완전히 감싸는 패턴 → 지지 구간
    - 약세 OB: 양봉 → 음봉이 양봉 몸통을 완전히 감싸는 패턴 → 저항 구간
    - Mitigation: 이후 캔들이 OB 구간 내부로 진입하면 해소 처리

    Returns:
        unmitigated_bullish_obs: List[Dict]  — 미해소 강세 OB [{price_low, price_high, candle_idx, formed_at}]
        unmitigated_bearish_obs: List[Dict]  — 미해소 약세 OB
        nearest_bullish_ob: Optional[Dict]   — 현재가 아래 가장 가까운 강세 OB
        nearest_bearish_ob: Optional[Dict]   — 현재가 위 가장 가까운 약세 OB
        distance_to_ob_pct: float            — 현재가와 가장 가까운 OB까지 거리(%)
        price_in_ob: bool                    — 현재가가 OB 구간 내에 있는지
    """
```

**5.2 FVG (Fair Value Gap) 감지 — Unmitigated 추적 포함**
```python
def detect_fvg(candles: List[Dict], lookback: int = 168) -> Dict:
    """
    최근 lookback(7일) 캔들에서 3캔들 갭 감지 후, 미해소 갭만 반환.

    감지 로직:
    - 강세 FVG: candle[i-1].high < candle[i+1].low → 상승 갭 (되돌림 시 지지)
    - 약세 FVG: candle[i-1].low > candle[i+1].high → 하락 갭 (되돌림 시 저항)
    - Mitigation: 이후 캔들이 FVG 영역의 50% 이상을 침범하면 해소 처리

    Returns:
        unmitigated_bullish_fvgs: List[Dict]  — 미해소 강세 FVG [{gap_low, gap_high, candle_idx, formed_at}]
        unmitigated_bearish_fvgs: List[Dict]  — 미해소 약세 FVG
        nearest_bullish_fvg: Optional[Dict]   — 현재가 아래 가장 가까운 강세 FVG
        price_in_fvg: bool                    — 현재가가 FVG 구간 내에 있는지
    """
```

**5.3 스윙 프렉탈 (Swing Fractal) 감지**
```python
def detect_swing_fractals(candles: List[Dict], lookback: int = 168) -> Dict:
    """
    3캔들 중 가운데가 최고/최저인 프렉탈 포인트 감지.
    유동성 밀집 위치 파악 + R:R 계산의 SL/TP 기준점 제공.

    Returns:
        swing_highs: List[Dict]       — [{price, candle_idx}] 최근→과거 순
        swing_lows: List[Dict]        — [{price, candle_idx}]
        nearest_swing_low: Dict       — 현재가 아래 가장 가까운 스윙 저점
        nearest_swing_high: Dict      — 현재가 위 가장 가까운 스윙 고점
        near_swing_support: bool      — 현재가가 스윙 저점 근처(2% 이내)인지
    """
```

**5.4 구조적 R:R 사전 필터**
```python
def calculate_structural_rr(
    current_price: float,
    structural_sl: float,   # OB 하단 또는 스윙 저점 - ATR 버퍼
    structural_tp: float,   # 스윙 고점 또는 약세 OB
    atr_14: float,
    sl_buffer_multiplier: float = 0.5,
) -> Dict:
    """
    구조적 손절/익절 기반 R:R 비율 사전 계산.
    R:R < 3.0이면 진입 불가 판정.

    Returns:
        sl_price: float      — 최종 손절가 (structural_sl - ATR * buffer)
        tp_price: float      — 익절 목표가
        risk_pct: float      — 진입가 대비 손절 거리(%)
        reward_pct: float    — 진입가 대비 익절 거리(%)
        rr_ratio: float      — reward / risk
        rr_valid: bool       — R:R >= 3.0 여부
    """
```

**5.5 상위 타임프레임(HTF) 추세 정렬**
```python
def calculate_htf_trend(candles_1m: pd.DataFrame) -> Dict:
    """
    1분봉을 4시간봉으로 리샘플링하여 상위 추세 방향 판단.
    현재 데이터 인프라: 1분봉 수집 → DB 저장, 리샘플링 가능.

    판단 기준:
    - 4시간봉 MA20 기울기: 양수=상승, 음수=하락
    - 최근 3개 4시간봉 고점/저점 추세: HH+HL=상승, LH+LL=하락

    Returns:
        htf_trend: str             — "BULLISH" | "BEARISH" | "NEUTRAL"
        htf_aligned: bool          — 1시간봉 진입 방향과 일치 여부
        htf_ma20_slope: float      — 4시간봉 MA20 기울기
    """
```

**5.6 다중 근거 스코어링 종합**
```python
def score_multi_evidence(
    ob_result: Dict, fvg_result: Dict, fractal_result: Dict,
    rr_result: Dict, htf_result: Dict,
    session_weight: float = 1.0,
) -> Dict:
    """
    각 피처의 결과를 종합하여 진입 점수 산출.

    스코어링 규칙:
    - 현재가가 미해소 강세 OB 내/근처: +1점
    - 현재가가 미해소 강세 FVG 내/근처: +1점
    - 현재가가 스윙 저점 근처 (2% 이내): +1점
    - R:R >= 3.0: +1점 (필수 조건, 미충족 시 총점 0)
    - HTF 추세 정렬: +1점
    - 세션 가중치: 고변동성 시간대면 × 1.2

    Returns:
        total_score: int        — 총 점수 (0~5)
        details: List[str]      — 충족된 근거 목록
        entry_eligible: bool    — N개 이상 충족 여부 (N은 백테스트로 결정)
        structural_sl: float    — 구조적 손절가
        structural_tp: float    — 구조적 익절 목표가
    """
```

**5.7 백테스트 검증 방법**

기존 `backtest_v3.py`에 `--multi-evidence` 플래그 추가:

```
# 백테스트 비교
python scripts/backtest_v3.py --multi-evidence

# 비교 시나리오 (10가지)
 1) baseline: 기존 진입 조건만
 2) baseline + OB 필터 (Unmitigated only)
 3) baseline + FVG 필터 (Unmitigated only)
 4) baseline + 스윙 프렉탈 필터
 5) baseline + R:R ≥ 2.0 필터 단독 (비교용)
 6) baseline + R:R ≥ 3.0 필터 단독 (기본값)
 7) baseline + HTF 추세 정렬 필터 단독
 8) baseline + 3개 구조 피처 중 2개 이상 + R:R ≥ 2.0
 9) baseline + 3개 구조 피처 중 2개 이상 + R:R ≥ 3.0
10) baseline + 3개 구조 피처 중 2개 이상 + R:R ≥ 3.0 + HTF 정렬
```

**검증 지표**:
- 진입 건수 변화 (기존 대비 필터링 비율)
- 승률 변화
- avg_win / avg_loss 변화 (R:R 개선 핵심)
- 총 PnL 변화
- 시간대별 OB/FVG 신뢰도 (세션 가중치 결정용)
- 시나리오별 비교 테이블 출력

### Phase 2: Rule Engine 통합 (백테스트 유효성 확인 후)
- `check_entry_signal()` 또는 별도 스코어 함수에 피처 추가
- `indicators` dict에 다중 근거 피처 포함
- YAML config에 활성화/비활성화 플래그 + R:R 임계값 + HTF 활성화 설정
- 구조적 SL/TP를 `signal_info`에 저장 → 청산 시 활용 가능

### Phase 3: AI Analyst 프롬프트 반영
- 추세선/채널/Fakeout 판단을 프롬프트에 포함
- "다중 근거 N개 충족" 기준 CONFIRM 조건 강화
- Rule Engine이 계산한 구조적 SL/TP와 R:R을 AI에게 컨텍스트로 전달
- Phase 1 백테스트에서 최적 N값 도출 후 적용

---

## 6. 검증 기준

### 6.1 Phase 1 백테스트 성공 기준
- R:R ≥ 3.0 필터 적용 시나리오가 baseline 대비:
  - **avg_loss 개선** (현재 -3.86% → 구조적 SL로 축소 기대)
  - 승률 유지 또는 개선
- R:R 2.0 vs 3.0 비교: 3.0이 과도하게 필터링하면 2.0으로 완화 검토
- 3개 구조 피처 + R:R 필터 조합 시나리오가 baseline 대비:
  - 승률 +5%p 이상 **또는** R:R 비율 1:3 → 1:2 이하로 개선
  - 진입 건수가 baseline의 20% 이상 유지 (과도한 필터링 방지)
- HTF 정렬 추가 시 승률 추가 개선 여부 확인

### 6.2 Phase 2 라이브 성공 기준
- Rule Engine 통과 → AI Confirm 비율 개선 (현재 1.9% → 목표 5% 이상)
- SIDEWAYS 레짐 R:R 개선 (현재 avg_win:avg_loss = 1:3.02 → 구조적 SL로 avg_loss 축소)
- 구조적 SL 기반 avg_loss 개선

---

## 7. 롤백
- Phase 1: 백테스트 전용 → 롤백 불필요
- Phase 2: YAML config `multi_evidence_enabled: false`로 비활성화
- Phase 3: 프롬프트 롤백 (v3.5.1로 복원)

---

## 8. 파일 변경 예상

| Phase | 파일 | 변경 내용 |
|-------|------|----------|
| 1 | `src/analysis/multi_evidence.py` (신규) | OB/FVG/프렉탈 감지 + Unmitigated 추적 + R:R 계산 + HTF 추세 + 스코어링 |
| 1 | `src/common/indicators.py` | `resample_to_4h()` 함수 추가 (1분봉→4시간봉) |
| 1 | `scripts/backtest_v3.py` | `--multi-evidence` 10가지 시나리오 비교 추가 |
| 2 | `src/engine/strategy.py` | `check_entry_signal()`에 다중 근거 스코어링 통합 |
| 2 | `config/strategy_v3.yaml` | multi_evidence 설정 블록 (enabled, rr_min, htf_enabled, score_threshold) |
| 3 | `src/agents/prompts.py` | Analyst 프롬프트에 다중 근거 기준 + 구조적 SL/TP 컨텍스트 반영 |

---

## 9. 선행 조건
- [x] 34번 Phase 3/4 모니터링 진행 중 (병행 가능)
- [ ] `market_data` 테이블에 7일 이상 OHLCV 데이터 존재 확인 (lookback=168 지원)
- 참고: 34번 Phase 5(Rule Engine SQL 분석)는 별도 진행. Phase 5 결과는 35번 Phase 2 통합 시 반영 가능

---

## 10. 데이터 인프라 확인

| 항목 | 현재 상태 | Phase 1 필요 |
|------|----------|-------------|
| 소스 데이터 | 1분봉 수집 (`source_timeframe: "1m"`) | ✅ 충분 |
| 1시간봉 | `resample_to_hourly()` 존재 | ✅ OB/FVG/프렉탈 계산용 |
| 4시간봉 | 미구현 | 신규: `resample_to_4h()` 필요 (HTF 추세용) |
| lookback | AI 컨텍스트 24시간 | 168시간(7일)으로 확장 필요 (백테스트에서는 DB 직접 조회) |
| ATR(14) | 미확인 | R:R 계산용 ATR 함수 필요 (1시간봉 기준) |

---

## 11. 일정

```
Phase 1 (백테스트): 34번 Phase 3/4 모니터링과 병행하여 즉시 시작
  → 피처 함수 구현 (OB/FVG/프렉탈 + Unmitigated + R:R + HTF)
  → 10가지 시나리오 백테스트 비교
  → 시간대별 OB/FVG 신뢰도 분석 (세션 가중치 결정)
Phase 2 (Rule Engine 통합): Phase 1 백테스트 유효성 확인 후
  → 34번 Phase 5 SQL 분석 결과도 함께 반영
  → 구조적 SL/TP를 signal_info에 저장
Phase 3 (AI 프롬프트): Phase 2 라이브 모니터링 확인 후
  → 다중 근거 + R:R 정보를 AI 컨텍스트로 전달
```

---

## 12. 문서 반영
- 체크리스트: `docs/checklists/remaining_work_master_checklist.md`에 35번 항목 추가
- PROJECT_CHARTER.md: Phase 2 Rule Engine 통합 시 진입 조건 변경 반영 필요
- README.md: Phase 2 완료 시 전략 설명 업데이트

---

## 13. References
- docs/strategy/TradingMethod.md — 오더블럭/FVG/추세선/채널/Fakeout/프렉탈 개념 정리
- 34번 Plan Phase 5 — Rule Engine 진입 조건 분석 (선행 작업)
- 외부 피드백 (2026-03-31) — SMC/ICT 기반 Unmitigated 추적, 구조적 SL, MTF 필터 제안
