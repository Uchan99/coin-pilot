# CoinPilot v3.0 전략 구현 결과 보고서

**작성일**: 2026-02-06
**작성자**: Antigravity (AI Architect)
**관련 계획**: `docs/work-plans/coinpilot_v3_strategy.md`

## 1. 개요
기존 v2.5 전략의 하락장 대응 한계를 극복하기 위해, 마켓 레짐(Market Regime)을 감지하고 상황에 맞는 파라미터를 동적으로 적용하는 적응형 전략(v3.0) 구현을 완료했습니다.

## 2. 주요 구현 사항

### 2.1 마켓 레짐 감지 (Market Regime Detection)
- **로직**: 1시간봉 기준 MA50과 MA200의 이격도를 계산하여 시장을 3가지 레짐으로 분류
    - **BULL (상승장)**: 이격도 > +2.0%
    - **BEAR (하락장)**: 이격도 < -2.0%
    - **SIDEWAYS (횡보장)**: 그 외 구간
- **구현**: `src/common/indicators.py`에 `detect_regime` 함수 추가 및 `src/bot/main.py`에 스케줄러(`update_regime_job`) 추가 (1시간 주기 갱신)

### 2.2 적응형 전략 (Adaptive Strategy)
레짐별로 진입/청산 파라미터를 다르게 적용하여 최적 대응합니다. (`src/config/strategy.py`)

| 구분 | BULL (상승) | SIDEWAYS (횡보) | BEAR (하락) |
|---|---|---|---|
| **진입** | MA20 돌파 + 거래량(1.2배) | BB 하단 터치 + 복귀 | 강한 과매도 후 반등 |
| **목표익(TP)** | +5% | +3% | +3% |
| **손절(SL)** | -3% | -4% | -5% |
| **비중** | 100% | 80% | 50% |

### 2.3 트레일링 스탑 (Trailing Stop)
- **기능**: 수익이 발생하면 최고가(High Water Mark)를 추적하여, 하락 반전 시 이익을 확정 짓고 청산합니다.
- **로직**: 수익률 1% 도달 시 활성화, 최고점 대비 2~3%(레짐별 상이) 하락 시 청산.
- **구현**: `src/engine/strategy.py` 내 `TrailingStop` 클래스 및 DB/Redis 연동 구현.

### 2.4 조건부 RSI 청산
- RSI 과매수 구간에 진입해도, 최소 수익률(0.5%~1.0%)을 확보하지 못하면 청산을 보류하여 조기 청산 방지.

### 2.5 레짐 변경 시 SL 정책 (추가 구현)
- **기능**: 레짐이 변경되어도 기존 포지션의 Stop Loss는 타이트한 값을 유지하여 리스크 확대 방지.
- **예시**: BULL(SL -3%) → BEAR(SL -5%) 전환 시 → SL -3% 유지
- **구현**: `src/engine/strategy.py`의 `get_adjusted_exit_config()` 함수

### 2.6 대시보드 레짐 표시 (추가 구현)
- **기능**: Market 페이지에서 현재 마켓 레짐(BULL/SIDEWAYS/BEAR/UNKNOWN)을 시각적으로 표시.
- **표시 정보**: 레짐 아이콘, 설명, HWM(트레일링 스탑용 최고가)
- **구현**: `src/dashboard/pages/2_market.py`

### 2.7 AI Agent 레짐 연동 (추가 구현)
- **기능**: AI Agent 프롬프트에 레짐 정보를 포함하여 레짐 인식 판단 유도.
- **추가 내용**: `REGIME_DESCRIPTIONS`, `REGIME_GUIDANCE`, 레짐별 판단 가이드
- **구현**: `src/agents/prompts.py`

### 2.8 v3.0 백테스트 스크립트 (추가 구현)
- **기능**: v3.0 전략의 레짐별 성과를 검증하는 백테스트 스크립트.
- **분석 항목**: 레짐별 거래 수, 승률, 수익률, 청산 사유 분포
- **구현**: `scripts/backtest_v3.py`

## 3. 변경 파일 목록

| 파일 경로 | 주요 변경 내용 |
|---|---|
| `src/common/models.py` | `regime`, `high_water_mark`, `exit_reason` 컬럼 및 `RegimeHistory` 테이블 추가 |
| `src/common/indicators.py` | 1분봉→1시간봉 리샘플링, 레짐 감지, BB 터치 감지 로직 추가 |
| `src/config/strategy.py` | 레짐별 파라미터 구조체 정의 및 YAML 설정 로더 구현 |
| `src/engine/strategy.py` | `AdaptiveMeanReversion` 로직 구현, `TrailingStop` 클래스, **레짐 변경 SL 정책** 추가 |
| `src/bot/main.py` | 레짐 갱신 스케줄러 추가, 봇 루프에 레짐/HWM 연동, **numpy import 추가** |
| `src/engine/executor.py` | 거래 실행 시 레짐 및 HWM 정보 DB 기록 |
| `src/dashboard/pages/2_market.py` | **레짐 표시 UI 추가** (아이콘, 설명, HWM) |
| `src/agents/prompts.py` | **레짐 정보 프롬프트 추가** (REGIME_DESCRIPTIONS, 가이드) |
| `scripts/backtest_v3.py` | **v3.0 전략 백테스트 스크립트** (신규) |
| `migrations/v3_0_regime_trading.sql` | DB 스키마 변경을 위한 SQL 스크립트 |
| `config/strategy_v3.yaml` | 전략 설정 YAML 파일 |

## 4. 검증 결과

- **단위 테스트**: `tests/test_strategy_v3_logic.py` 수행 완료.
    - 트레일링 스탑 활성화 및 트리거 로직 검증 통과 (✅ Passed)
    - 레짐별 진입 조건 분기 로직 검증 통과 (✅ Passed)
    - 조건부 RSI 청산 로직 검증 통과 (✅ Passed)

## 5. 향후 계획 (Verification Plan)
1. **DB 마이그레이션**: `psql`을 통해 `migrations/v3_0_regime_trading.sql` 실행 필요.
2. **실전 모니터링**: 봇 재시작 후 로그 및 대시보드에서 레짐("BULL", "BEAR" 등)이 정상 표시되는지 확인.

---

## Claude Code Review

**검토일**: 2026-02-06
**검토자**: Claude Code (Opus 4.5)
**최종 업데이트**: 2026-02-06 (추가 구현 완료 후)

### 1. 계획서 대비 구현 완료 항목 ✅

| 계획 항목 | 구현 상태 | 구현 위치 |
|-----------|:---------:|-----------|
| 1분봉 → 1시간봉 리샘플링 | ✅ | `src/common/indicators.py:resample_to_hourly()` |
| 마켓 레짐 감지 (BULL/SIDEWAYS/BEAR/UNKNOWN) | ✅ | `src/common/indicators.py:detect_regime()` |
| UNKNOWN 레짐 Fallback 정책 | ✅ | `src/engine/strategy.py:check_entry_signal()` |
| 레짐 캐싱 (Redis, TTL 65분) | ✅ | `src/bot/main.py:update_regime_job()` |
| 레짐별 진입 조건 분기 | ✅ | `src/engine/strategy.py:MeanReversionStrategy` |
| 레짐별 청산 조건 (TP/SL/트레일링) | ✅ | `src/engine/strategy.py:check_exit_signal()` |
| 트레일링 스탑 클래스 | ✅ | `src/engine/strategy.py:TrailingStop` |
| HWM 이중 저장 (Redis + DB) | ✅ | `src/bot/main.py` (Redis set + DB update) |
| 조건부 RSI 청산 | ✅ | `src/engine/strategy.py` (rsi_exit_min_profit_pct 체크) |
| 포지션 사이징 (레짐별) | ✅ | `src/bot/main.py` (position_size_ratio 적용) |
| DB 스키마 변경 | ✅ | `src/common/models.py` + `migrations/v3_0_regime_trading.sql` |
| YAML 설정 파일 | ✅ | `config/strategy_v3.yaml` |
| RegimeHistory DB 기록 | ✅ | `src/bot/main.py:update_regime_job()` |
| BB 터치 후 복귀 판정 | ✅ | `src/common/indicators.py:check_bb_touch_recovery()` |
| 단위 테스트 | ✅ | `tests/test_strategy_v3_logic.py` |
| **레짐 변경 시 SL 정책** | ✅ | `src/engine/strategy.py:get_adjusted_exit_config()` |
| **AI Agent 레짐 연동** | ✅ | `src/agents/prompts.py` (REGIME_DESCRIPTIONS, 가이드) |
| **백테스트 스크립트** | ✅ | `scripts/backtest_v3.py` |
| **대시보드 레짐 표시** | ✅ | `src/dashboard/pages/2_market.py` |

### 2. 미구현 항목

**모든 계획 항목 구현 완료** ✅

### 3. 코드 품질 이슈 (해결됨) 🔧

#### 3.1 Import 누락 → ✅ 해결

`src/bot/main.py` 상단에 `import numpy as np` 추가 완료.

#### 3.2 YAML 로더 제한사항

`src/config/strategy.py:load_strategy_config()`에서 중첩된 딕셔너리 매핑 제한이 있으나, 기본값이 잘 정의되어 있어 운영에 문제없음. 향후 YAML override 기능 필요 시 개선 권장.

### 4. 아키텍처 적합성 ✅

- **프로젝트 구조**: 기존 디렉토리 구조를 잘 따름 (config/, engine/, common/, bot/)
- **DB 설계**: `trading_history`, `positions` 테이블 확장이 계획서와 일치
- **Redis 키 구조**: `market:regime:{symbol}`, `position:{symbol}:hwm` 형식 적절
- **스케줄러 통합**: APScheduler 활용하여 기존 volatility job과 함께 관리
- **AI Agent 연동**: 프롬프트에 레짐 정보 포함으로 컨텍스트 기반 판단 강화

### 5. 테스트 커버리지 ✅

단위 테스트가 핵심 로직을 커버:
- 트레일링 스탑 활성화/트리거
- 레짐별 진입 조건 분기
- 조건부 RSI 청산

### 6. 추가 구현 내역 (2026-02-06)

| 항목 | 구현 내용 |
|------|----------|
| numpy import | `src/bot/main.py` 상단에 `import numpy as np` 추가 |
| 대시보드 레짐 | Market 페이지에 레짐 아이콘/설명/HWM 표시 추가 |
| AI Agent 프롬프트 | `REGIME_DESCRIPTIONS`, `REGIME_GUIDANCE`, `get_analyst_prompt()` 함수 추가 |
| 백테스트 스크립트 | `scripts/backtest_v3.py` - 레짐별 성과 분석 기능 포함 |
| SL 정책 | `get_adjusted_exit_config()` - 레짐 변경 시 타이트한 SL 유지 |

### 7. 최종 의견

**Overall: APPROVED (100%)** ✅

계획서의 모든 항목이 구현 완료되었습니다. DB 마이그레이션 실행 후 즉시 운영 테스트 가능합니다.

**배포 전 체크리스트:**
1. `psql`로 `migrations/v3_0_regime_trading.sql` 실행
2. 봇 재시작 후 로그에서 `[Scheduler] Regime Update` 메시지 확인
3. 대시보드 Market 페이지에서 레짐 표시 확인
4. `PYTHONPATH=. python scripts/backtest_v3.py`로 전략 검증 실행
