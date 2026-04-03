# 35. 다중 근거 기술적 분석(Multi-Evidence TA) 구현 결과

작성일: 2026-03-31
작성자: Claude (assistant)
관련 계획서: docs/work-plans/35_multi_evidence_technical_analysis_plan.md
상태: Partial
완료 범위: Phase 1
선반영/추가 구현: 없음

---

## 1. 개요
- 구현 범위 요약: Phase 1 — 피처 계산 함수 구현 + 10가지 시나리오 백테스트 비교
- 목표: OB/FVG/Fractal/R:R/HTF 기반 다중 근거 진입 필터가 기존 Rule Engine 대비 진입 품질을 개선하는지 데이터로 검증
- 이번 구현이 해결한 문제: Rule Engine이 과도한 진입 신호를 통과시키는 문제(98.1% AI 거부)에 대해, 구조적 기술 분석 필터의 유효성을 백테스트로 검증
- 해결한 문제의 구체 정의:
  - 증상: Rule Engine 1,361건 통과 중 AI Confirm 26건 (1.9%)
  - 영향: AI 호출 비용 낭비 + 저품질 진입 가능성
  - 재현 조건: 현재 진입 조건(RSI/BB/MA/Volume)이 가격 구조/수급 패턴 미반영
- 기존 방식(Before): RSI/BB/MA/Volume 수치 기반 진입 → 구조적 분석 없음

---

## 2. 구현 내용

### 2.1 다중 근거 피처 계산 모듈 (`src/analysis/multi_evidence.py`)
- 파일: `src/analysis/multi_evidence.py` (신규, ~550 lines)
- 7개 핵심 함수 구현:
  1. `detect_order_blocks()` — 장악형 캔들 감지 + Unmitigated 추적 (lookback=168, 7일)
  2. `detect_fvg()` — 3캔들 갭 감지 + 50% 해소 기준 Unmitigated 추적
  3. `detect_swing_fractals()` — 3캔들 고저점 프렉탈 감지
  4. `calculate_structural_rr()` — 구조적 SL/TP 기반 R:R 비율 계산 (R:R ≥ 3.0 필수)
  5. `resample_to_4h()` — 1시간봉 → 4시간봉 리샘플링
  6. `calculate_htf_trend()` — 4시간봉 MA20 기울기 + HH/HL 패턴 추세 판단
  7. `calculate_atr()` — ATR(14) 계산 (R:R 버퍼용)
- 내부 유틸리티: `_filter_unmitigated`, `_filter_unmitigated_fvg`, `_nearest_below/above` 등

### 2.2 백테스트 통합 (`scripts/backtest_v3.py`)
- 파일: `scripts/backtest_v3.py` (수정)
- `--multi-evidence` CLI 플래그 추가
- `simulate_trades_me()` — 시나리오별 ME 필터 적용 시뮬레이션
- `_compute_me_at_entry()` — 진입 시점 데이터로 OB/FVG/Fractal/HTF/R:R 계산
- `_passes_me_filter()` — 10개 시나리오별 필터 통과 판단
- `run_compare_multi_evidence()` — 비교 테이블 출력 (거래수/승률/PnL/필터율/청산사유/레짐분포)

---

## 3. 변경 파일 목록

### 3.1 수정
1) `scripts/backtest_v3.py` — `--multi-evidence` 모드, `simulate_trades_me()`, 10 시나리오 비교

### 3.2 신규
1) `src/analysis/multi_evidence.py` — OB/FVG/Fractal/R:R/HTF/ATR 피처 계산 모듈
2) `src/analysis/__init__.py` — 패키지 init

---

## 4. DB/스키마 변경
- 없음 (백테스트 전용, DB 읽기만)

---

## 5. 검증 결과

### 5.1 코드/정적 검증
- 실행 명령: `python3 -c "import ast; ast.parse(open('scripts/backtest_v3.py').read()); print('OK')"`
- 결과: OK (구문 오류 없음)

### 5.2 백테스트 실행 검증
- 실행 명령:
  ```bash
  docker cp scripts/backtest_v3.py coinpilot-bot:/app/scripts/backtest_v3.py
  docker cp src/analysis/ coinpilot-bot:/app/src/analysis/
  docker exec coinpilot-bot python scripts/backtest_v3.py --multi-evidence
  ```
- 결과: 10개 시나리오 모두 정상 실행, 비교 테이블 출력 완료

### 5.3 정량 개선 증빙

- 측정 기간: OCI DB 약 90일 1시간봉 데이터
- 측정 기준: 5개 심볼 (KRW-BTC/ETH/XRP/SOL/DOGE)
- 데이터 출처: `scripts/backtest_v3.py --multi-evidence` 실행 결과
- 재현 명령:
  ```bash
  docker exec coinpilot-bot python scripts/backtest_v3.py --multi-evidence
  ```

#### Before/After 비교표 (baseline vs FVG 필터 — 최우수 시나리오)

| 지표 | Before (baseline) | After (+FVG) | 변화량 | 변화율 |
|------|------------------:|-------------:|-------:|-------:|
| 거래 건수 | 99 | 23 | -76 | -76.8% |
| 승률 | 50.5% | 65.2% | +14.7pp | +29.1% |
| 누적 PnL | -80.85% | -8.78% | +72.07pp | +89.1% |
| 예상 수익 | -74,143원 | -9,933원 | +64,210원 | +86.6% |
| STOP_LOSS | 27건 | 4건 | -23 | -85.2% |
| BEAR 진입 | 40건 | 5건 | -35 | -87.5% |

---

## 6. 배포/운영 확인 체크리스트
1) 백테스트 전용 — 실거래 영향 없음
2) 기존 `--compare-bb-guards`, `--compare-rsi` 모드 영향 없음 (독립 경로)
3) OCI Docker에서 정상 실행 확인 완료

---

## 7. 설계/아키텍처 결정 리뷰

### 최종 선택한 구조
- 진입 시점 데이터(df_slice)로 ME 피처를 계산하여 시나리오별 필터 적용
- baseline 시뮬레이션과 동일한 프레임워크에서 비교 (동일 청산 로직)

### 고려했던 대안
1) 전체 데이터 사전 계산 + 캔들별 lookup → 빠르지만 미래 데이터 참조 위험
2) 매 캔들마다 전체 재계산 → 정확하지만 O(n²) 성능
3) **(채택)** 진입 시점에만 df_slice로 계산 + lookback=168 제한 → 정확성과 성능 균형

### 대안 대비 실제 이점
- 진입 시점에만 계산: 불필요한 비진입 캔들에서 연산 절약
- lookback=168 제한: 계산량 O(entries × 168)으로 제한, 90일 백테스트 수 분 내 완료

### 트레이드오프
1) HTF 추세를 매 진입마다 재계산 → 최적화 여지 있음 (사전 계산 가능)
2) Unmitigated 필터가 df_slice 기반이라 미래 해소 여부는 반영 안 됨 (정상 동작)

---

## 8. 한국어 주석 반영 결과
- 주석을 추가/강화한 주요 지점:
  1) `multi_evidence.py` — 모든 공개 함수에 한국어 docstring (의도/판단기준/반환값)
  2) `backtest_v3.py` — `_compute_me_at_entry`, `_passes_me_filter`, `simulate_trades_me`에 역할/로직 설명
- 주석 핵심 요소: 각 피처의 SMC/ICT 이론적 배경, Unmitigated 개념, R:R 필수 조건 이유

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분: 10가지 시나리오 비교, OB/FVG/Fractal/R:R/HTF 피처 구현
- 변경/추가된 부분:
  - `resample_to_4h()`를 `src/common/indicators.py`가 아닌 `multi_evidence.py` 내부에 구현 (백테스트 전용 단계이므로)
  - 세션 가중치(§3.2.4) 미구현 → Phase 1-2로 이연
- 계획에서 비효율적/오류였던 점:
  - R:R 필터를 진입에만 적용하고 청산은 고정 비율 유지 → R:R 0% 승률의 근본 원인
  - HTF 정렬이 역효과 → BEAR 레짐에서도 유효 진입 존재

---

## 10. 결론 및 다음 단계

### 현재 상태
- Phase 1 백테스트 완료. **FVG 필터가 유일하게 유효한 진입 필터**로 확인됨.
- R:R 필터는 진입-청산 로직 불일치로 현 상태에서 비효과적.
- 3차 외부 피드백 반영: AI 청산 전면 보류, 포지션 사이징 역산 선행 필요.

### 후속 작업
1) **Phase 1-2**: 구조적 청산 + 포지션 사이징 역산 백테스트
   - `check_exit_signal`에 구조적 TP/SL 옵션 추가
   - `Position Size = (Equity × 0.02) / Risk` 공식 적용
   - FVG 진입 + 구조적 청산 조합 시나리오
   - 트레일링 스탑 고도화 (Parabolic SAR / ATR 기반)
2) **Phase 2**: FVG 필터 Rule Engine 적용 (Phase 1-2 검증 후)
3) **Phase 3**: AI Analyst 프롬프트 반영 (진입 전용, 청산 보류)

---

## 12. References
- docs/work-plans/35_multi_evidence_technical_analysis_plan.md
- docs/strategy/TradingMethod.md
- 3차 외부 피드백 (2026-03-31): 구조적 청산/AI 청산 냉정한 평가 → Plan §14에 기록
