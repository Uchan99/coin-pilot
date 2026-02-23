# CoinPilot 데이터 흐름도 (Data Flow Reference)

**작성일**: 2026-02-19
**최종 업데이트**: 2026-02-23
**기준 브랜치**: `dev_v2`
**기준 커밋**: `65c0cbe`

---

## 0. 운영 모드 업데이트 (2026-02-23)

- 기본 운영 모드가 `Minikube`에서 `Docker Compose`로 전환되었다.
- Minikube는 레거시/검증용으로 유지하며, 일일 운영/장애 대응은 Compose 기준이다.
- 전환 배경/비교/보안 검토 기록:
  - `docs/troubleshooting/18-01_system_health_agent_decisions_and_data_sync.md`
  - `docs/work-plans/20_oci_paid_tier_security_and_cost_guardrails_plan.md`
  - `docs/work-result/20_oci_paid_tier_security_and_cost_guardrails_result.md`

---

## 1. 시스템 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────────┐
│                        External Services                            │
│  ┌──────────┐   ┌──────────────┐   ┌──────────┐   ┌─────────────┐  │
│  │ Upbit API│   │ Anthropic API│   │ OpenAI   │   │ n8n → Discord│  │
│  │ (시세)   │   │ (AI 분석)    │   │ (리포트) │   │ (알림)       │  │
│  └────┬─────┘   └──────┬───────┘   └────┬─────┘   └──────┬──────┘  │
└───────┼────────────────┼────────────────┼────────────────┼──────────┘
        │                │                │                │
┌───────▼────────────────▼────────────────▼────────────────▼──────────┐
│       Runtime Layer (Docker Compose Primary / Minikube Legacy)       │
│                                                                     │
│  ┌──────────┐   ┌──────────────────────────────────┐   ┌─────────┐ │
│  │Collector │   │            Bot (main.py)          │   │Dashboard│ │
│  │Container │   │  ┌────────┐ ┌────────┐ ┌───────┐ │   │Streamlit│ │
│  │          │   │  │Strategy│ │Executor│ │Risk   │ │   │         │ │
│  │          │   │  │Engine  │ │        │ │Manager│ │   │         │ │
│  │          │   │  └────────┘ └────────┘ └───────┘ │   │         │ │
│  │          │   │  ┌─────────────────────────────┐  │   │         │ │
│  │          │   │  │   AI Agent (LangGraph)      │  │   │         │ │
│  │          │   │  │  Analyst → Guardian          │  │   │         │ │
│  │          │   │  └─────────────────────────────┘  │   │         │ │
│  │          │   │  ┌──────────┐  ┌───────────────┐  │   │         │ │
│  │          │   │  │Scheduler │  │Metrics(/8000) │  │   │         │ │
│  └─────┬────┘   └──┬─────────┴──┴───────────────┴──┘   └────┬────┘ │
│        │           │                                         │      │
│  ┌─────▼───────────▼─────────────────────────────────────────▼────┐ │
│  │                   PostgreSQL (TimescaleDB)                     │ │
│  └────────────────────────────────┬───────────────────────────────┘ │
│  ┌────────────────────────────────▼───────────────────────────────┐ │
│  │                          Redis                                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 데이터 저장소 상세

### 2.1 PostgreSQL (TimescaleDB) — 영구 저장소

| 테이블 | 모델 클래스 | 역할 | 주요 컬럼 | 쓰기 주체 | 읽기 주체 |
|--------|------------|------|-----------|----------|----------|
| `market_data` | `MarketData` | 1분봉 OHLCV (하이퍼테이블) | symbol, interval, open/high/low/close_price, volume, timestamp | Collector | Bot, Dashboard, DailyReporter |
| `positions` | `Position` | 현재 보유 포지션 | symbol, quantity, avg_price, regime, high_water_mark, opened_at | Executor | Bot, RiskManager, Dashboard |
| `trading_history` | `TradingHistory` | 거래 체결 이력 | symbol, side, price, quantity, strategy_name, signal_info(JSONB), regime, exit_reason | Executor | Dashboard, DailyReporter |
| `agent_decisions` | `AgentDecision` | AI 판단 이력 | symbol, decision, reasoning, confidence, model_used, price_at_decision, regime | AgentRunner | Dashboard |
| `daily_risk_state` | `DailyRiskState` | 일일 리스크 상태 | date, total_pnl, trade_count, consecutive_losses, cooldown_until, is_trading_halted | RiskManager | Bot, DailyReporter, Dashboard |
| `account_state` | `AccountState` | 계좌 잔고 (Paper Trading) | balance | Executor | Bot, RiskManager, Dashboard |
| `risk_audit` | `RiskAudit` | 리스크 위반 기록 | violation_type, description, related_order_id | RiskManager(`log_risk_violation`, 현재 미연결) | Dashboard |
| `regime_history` | `RegimeHistory` | 마켓 레짐 감지 이력 | regime, ma50, ma200, diff_pct, coin_symbol | Scheduler(update_regime_job) | Dashboard |
| `agent_memory` | `AgentMemory` | AI 에이전트 벡터 기억 (pgvector) | agent_type, context(JSONB), decision, outcome, embedding(1536) | (미사용/예비) | (미사용/예비) |

### 2.2 Redis — 실시간 캐시/상태 저장소

| Key 패턴 | 값 형식 | TTL | 쓰기 주체 | 읽기 주체 | 용도 |
|----------|---------|-----|----------|----------|------|
| `market:regime:{symbol}` | `"BULL"/"SIDEWAYS"/"BEAR"/"UNKNOWN"` | 7200s | Scheduler(update_regime_job) | Bot(bot_loop) | 현재 레짐 캐시 |
| `bot:status:{symbol}` | JSON (price, regime, indicators, position, action, reason) | 300s | Bot(bot_loop) | Dashboard | 봇 실시간 상태 |
| `position:{symbol}:hwm` | float 문자열 | 없음 | Bot(bot_loop) | Bot(bot_loop) | 포지션 HWM 실시간 추적 |
| `coinpilot:volatility_state` | JSON {current_volatility, is_high_volatility, timestamp} | 없음 | Scheduler(retrain_volatility_job) | RiskManager | 변동성 상태 |
| `ai:guard:global:block` | `"low_credit"/"error_streak"` | 설정값(분) | guardrails | guardrails | AI 글로벌 차단 |
| `ai:guard:symbol:{symbol}:cooldown` | cooldown 분 수 | 설정값(분) | guardrails | guardrails | 심볼별 AI 쿨다운 |
| `ai:guard:symbol:{symbol}:reject_count` | 정수 | 설정값(분) | guardrails | guardrails | 연속 REJECT 횟수 |
| `ai:guard:error_streak` | 정수 | 3600s | guardrails | guardrails | 연속 AI 에러 횟수 |
| `ai:usage:hour:{YYYYMMDDHH}` | 정수 | 7200s | guardrails | guardrails | 시간당 AI 호출 카운터 |
| `ai:usage:day:{YYYYMMDD}` | 정수 | 172800s | guardrails | guardrails | 일일 AI 호출 카운터 |

참고:
- `RiskManager`에는 `price:{symbol}` 조회 fallback 경로가 구현되어 있으나, 현재 Bot에서 해당 키를 쓰지 않으므로 실운영에서는 DB 최신가 fallback이 주 경로입니다.

### 2.3 Prometheus Metrics — 관측 지표

| 메트릭 이름 | 타입 | 갱신 주체 | 용도 |
|-------------|------|----------|------|
| `coinpilot_active_positions` | Gauge | Bot(bot_loop) | 활성 포지션 수 |
| `coinpilot_total_pnl` | Gauge | Bot(bot_loop) | 누적 PnL |
| `coinpilot_trade_count_total` | Counter | Bot(bot_loop) | 총 거래 횟수 |
| `coinpilot_ai_requests_total` | Counter | Bot(bot_loop) | AI 분석 요청 횟수 |
| `coinpilot_ai_prefilter_skips_total` | Counter | Bot(bot_loop) | AI pre-filter 스킵 횟수 |
| `coinpilot_ai_context_candles` | Histogram | Bot(bot_loop) | AI 컨텍스트 캔들 수 분포 |
| `coinpilot_volatility_index` | Gauge | (예비) | 변동성 지수 |
| `coinpilot_api_latency_seconds` | Histogram | Bot(get_recent_candles) | DB 조회 지연 시간 |

---

## 3. 주요 데이터 흐름

### 3.1 시세 데이터 수집 (Collector)

```
Upbit REST API (1분봉)
    │
    │  GET /v1/candles/minutes/1?market={symbol}&count=1
    │  (55초 간격 폴링)
    ▼
┌─────────────────────────┐
│  UpbitCollector          │
│  fetch_candles()        │
│  save_candles()         │
│  ┌─────────────────┐    │
│  │ JSON → Decimal  │    │
│  │ opening_price   │    │
│  │ → open_price    │    │
│  │ trade_price     │    │
│  │ → close_price   │    │
│  └─────────────────┘    │
└───────────┬─────────────┘
            │  INSERT ... ON CONFLICT DO NOTHING
            ▼
    ┌───────────────┐
    │  market_data  │  (TimescaleDB 하이퍼테이블)
    │  1분봉 OHLCV  │
    └───────────────┘
```

**backfill 동작**: 서버 재시작 시 마지막 저장 시점 ~ 현재까지 누락분을 200개 단위 페이지네이션으로 보정.

---

### 3.2 봇 메인 루프 (Bot Loop) — 진입 경로

```
                              ┌──────────────────────┐
                              │   bot_loop() 60초 주기│
                              └──────────┬───────────┘
                                         │
                     ┌───────────────────┐│┌──────────────────────┐
                     │ Step 0: 전역 상태 │││ Redis: regime 조회   │
                     │ daily_risk_state  │││ market:regime:{sym}  │
                     │ open_positions    │││                      │
                     └───────────────────┘│└──────────────────────┘
                                         │
                              ┌──────────▼───────────┐
                              │ Step 1: DB 캔들 조회  │
                              │ get_recent_candles()  │
                              │ market_data → 200행   │
                              │ → pd.DataFrame        │
                              └──────────┬───────────┘
                                         │
                              ┌──────────▼───────────┐
                              │ Step 2: 지표 계산     │
                              │ get_all_indicators()  │
                              │  - RSI(14), RSI(7)    │
                              │  - MA(20)             │
                              │  - BB(20, 2.0)        │
                              │  - Volume Ratio       │
                              │  - bb_touch_recovery  │
                              │  - rsi_short_min_     │
                              │    lookback           │
                              └──────────┬───────────┘
                                         │
                              ┌──────────▼───────────┐
                              │ Step 3: 포지션 조회   │
                              │ executor.get_position │
                              │ positions 테이블      │
                              └──────────┬───────────┘
                                         │
                          ┌──────────────┴──────────────┐
                          │                             │
                  ┌───────▼───────┐             ┌──────▼──────┐
                  │  포지션 보유  │             │ 포지션 없음 │
                  │  → Exit 체크 │             │ → Entry 체크│
                  └───────┬───────┘             └──────┬──────┘
                          │                            │
                  (3.3절 참조)              ┌───────────▼───────────┐
                                           │ check_entry_signal()  │
                                           │ evaluate_entry_       │
                                           │ conditions() 호출     │
                                           │                       │
                                           │ 조건 체크 순서:       │
                                           │ 1. RSI14 ≤ max       │
                                           │ 2. RSI7 lookback     │
                                           │    과매도→반등        │
                                           │ 3. RSI7 반등폭       │
                                           │ 4. MA 필터           │
                                           │ 5. BB 하단 위 확인   │
                                           │ 6. 거래량 조건       │
                                           │ 7. 거래량 급증 체크  │
                                           │ 8. BB recovery(SW)   │
                                           └───────────┬───────────┘
                                                       │
                                              ┌────────▼────────┐
                                              │  PASS           │
                                              │ RiskManager     │
                                              │ check_order_    │
                                              │ validity()      │
                                              └────────┬────────┘
                                                       │ PASS
                                     ┌─────────────────▼─────────────────┐
                                     │ AI 전용 데이터 추가 조회           │
                                     │ get_recent_candles(limit=36*60)   │
                                     │ → resample_to_hourly()           │
                                     │ → build_market_context(24 candle)│
                                     │ → compute_bear_context_features()│
                                     └─────────────────┬─────────────────┘
                                                       │
                                     ┌─────────────────▼─────────────────┐
                                     │ should_run_ai_analysis()          │
                                     │ (pre-filter: 컨텍스트 길이,      │
                                     │  BEAR falling knife, volume)     │
                                     └─────────────────┬─────────────────┘
                                                       │ PASS
                                     ┌─────────────────▼─────────────────┐
                                     │ executor.execute_order("BUY")     │
                                     │   └→ AgentRunner.run()            │
                                     │      (3.4절: AI 판단 흐름)        │
                                     └───────────────────────────────────┘
```

---

### 3.3 청산(Exit) 데이터 흐름

```
┌─────────────────────────────────────┐
│ check_exit_signal(indicators, pos) │
│                                     │
│  입력:                              │
│    indicators: 현재 지표            │
│    pos: {avg_price, opened_at,     │
│          regime, high_water_mark}  │
│                                     │
│  체크 순서:                         │
│  1. Stop Loss (레짐 변경 시 타이트)│
│  2. Trailing Stop (HWM 기반)       │
│  3. Take Profit                    │
│  4. RSI 과매수 (최소수익 조건부)   │
│  5. Time Limit                     │
└────────────────┬────────────────────┘
                 │ EXIT 발생
                 ▼
┌─────────────────────────────────────┐
│ executor.execute_order("SELL")     │
│                                     │
│  DB 갱신:                           │
│  1. account_state.balance += 금액  │
│  2. positions 삭제                  │
│  3. trading_history INSERT          │
│     (side=SELL, exit_reason 포함)   │
│                                     │
│  후속:                              │
│  4. risk_manager.update_after_trade │
│     → daily_risk_state 갱신        │
│     → 3연패 시 cooldown 설정       │
│  5. Redis: position:{sym}:hwm 삭제│
│  6. n8n webhook → Discord 알림    │
└─────────────────────────────────────┘
```

**HWM(High Water Mark) 실시간 갱신 경로** (포지션 보유 중, EXIT 미발생 시):
```
현재가 > HWM → TrailingStop.update()에서 HWM 갱신
              → Redis SET position:{symbol}:hwm
              → DB UPDATE positions SET high_water_mark
```

---

### 3.4 AI 판단 흐름 (LangGraph)

```
┌────────────────────────────────────────────────────────┐
│  executor.execute_order("BUY")                        │
│    │                                                   │
│    ▼                                                   │
│  AgentRunner.run()   timeout: 40s                     │
│    │                                                   │
│    ▼                                                   │
│  ┌──────────────────────────────────────────┐          │
│  │ LangGraph StateGraph                      │          │
│  │                                           │          │
│  │  ┌──────────────┐    ┌───────────────┐   │          │
│  │  │   Analyst    │───▶│   Guardian    │   │          │
│  │  │ (시장분석)   │    │ (리스크검토) │   │          │
│  │  └──────┬───────┘    └───────┬───────┘   │          │
│  │         │                     │           │          │
│  │    REJECT → END          SAFE/WARNING     │          │
│  │    CONFIRM → Guardian        │            │          │
│  └──────────────────────────────┼────────────┘          │
│                                 │                       │
│  최종 판정:                     │                       │
│  CONFIRM + SAFE → approved      │                       │
│  그 외 → rejected               │                       │
│    │                                                    │
│    ▼                                                    │
│  _log_decision()                                       │
│    │                                                    │
│    ├── DB: agent_decisions INSERT                      │
│    │   (symbol, decision, reasoning, confidence,       │
│    │    model_used, price_at_decision, regime)         │
│    │                                                    │
│    └── n8n webhook: /webhook/ai-decision → Discord     │
└────────────────────────────────────────────────────────┘
```

**Analyst 노드 입력/출력:**
```
입력:
  - symbol: 심볼명
  - indicators: 1분봉 기반 지표 + ai_context_candles + BEAR feature
  - market_context: 1시간봉 24개 (list of dict)
  - analyst_prompt: get_analyst_prompt() (레짐 설명/가이드 포함)

LLM 호출:
  - ChatAnthropic(model=haiku/sonnet)
  - structured_output → AnalystDecision(decision, confidence, reasoning)

출력:
  - confidence < 60 → 강제 REJECT
  - parsing 실패 → REJECT + 에러 reason
```

**Guardian 노드 입력/출력:**
```
입력:
  - symbol, indicators (Analyst와 동일)

출력:
  - GuardianDecision(decision=SAFE/WARNING, reasoning)
```

---

### 3.5 AI Guardrails 데이터 흐름

```
┌──────────────────────────────────────────────────────┐
│ execute_order() → AI 호출 전/후                      │
│                                                       │
│  [호출 전] should_block_ai_call()                    │
│    Redis 읽기:                                        │
│    ├─ ai:guard:global:block          → 글로벌 차단?  │
│    ├─ ai:guard:symbol:{sym}:cooldown → 심볼 쿨다운?  │
│    ├─ ai:usage:hour:{YYYYMMDDHH}     → 시간 한도?    │
│    └─ ai:usage:day:{YYYYMMDD}        → 일일 한도?    │
│                                                       │
│  [호출 시] mark_ai_call_started()                    │
│    Redis 쓰기:                                        │
│    ├─ ai:usage:hour:* INCR                           │
│    └─ ai:usage:day:* INCR                            │
│                                                       │
│  [호출 후] update_ai_guardrails_after_decision()     │
│    approved:                                          │
│      Redis 삭제: reject_count, error_streak          │
│    rejected:                                          │
│      Redis 쓰기:                                      │
│      ├─ reject_count INCR                            │
│      ├─ symbol cooldown SET (5/10/15분)              │
│      ├─ low credit → global block SET               │
│      └─ error streak → INCR, 임계 초과 시 block     │
└──────────────────────────────────────────────────────┘
```

---

### 3.6 스케줄러 작업 데이터 흐름

#### A. 레짐 업데이트 (`update_regime_job`, 1시간 간격)

```
DB: market_data (1분봉, limit=200*60=12000행)
    │
    ▼
resample_to_hourly() → 1시간봉 DataFrame
    │
    ▼
calculate_ma(period=50), calculate_ma(period=200)
    │
    ▼
detect_regime(ma50, ma200, thresholds)
    │
    ├──▶ Redis SET market:regime:{symbol} (TTL 7200s)
    │
    └──▶ DB INSERT regime_history
         (regime, ma50, ma200, diff_pct, coin_symbol)
```

#### B. 변동성 모델 재학습 (`retrain_volatility_job`, 매일 00:05 UTC)

```
DB: market_data (1분봉, limit=1000)
    │
    ▼
VolatilityModel.fit_predict()
  - 로그 수익률 계산
  - GARCH(1,1) 학습
  - 다음 시점 변동성 예측
    │
    ▼
VolatilityModel.update_volatility_state()
    │
    └──▶ Redis SET coinpilot:volatility_state
         {current_volatility, is_high_volatility, timestamp}
```

#### C. 일간 리포트 (`daily_reporter_job`, 매일 22:00 KST)

```
DB 읽기:
  ├─ daily_risk_state (오늘자 PnL, trade_count)
  └─ trading_history (오늘 체결 건)
    │
    ▼
OpenAI GPT-4o-mini
  - 3줄 요약 브리핑 생성
    │
    ▼
n8n webhook: /webhook/daily-report → Discord
  payload: {title, pnl, trades, win_rate, mdd, summary}
```

단위 참고:
- 종목/주문 엔진은 KRW 마켓(`KRW-*`) 기준으로 동작
- 일간 리포트 payload의 `pnl` 문자열은 현재 `USDT` 표기(`DailyReporter`)를 사용하므로, 표시 단위 통일이 필요하면 후속 정리 권장

---

### 3.7 대시보드 데이터 흐름 (Streamlit)

```
┌───────────────────────────────────────────┐
│  Dashboard (Streamlit, 동기식 psycopg2)  │
│                                           │
│  db_connector.get_data_as_dataframe()    │
│    └─ SQL 직접 실행 (30초 캐시)          │
│                                           │
│  읽는 테이블:                            │
│  ├─ market_data       (시세 차트)        │
│  ├─ positions         (보유 현황)        │
│  ├─ trading_history   (거래 이력)        │
│  ├─ agent_decisions   (AI 판단 이력)     │
│  ├─ daily_risk_state  (리스크 상태)      │
│  ├─ account_state     (잔고)             │
│  ├─ risk_audit        (위반 기록)        │
│  └─ regime_history    (레짐 이력)        │
│                                           │
│  Redis 읽기 (bot:status:{symbol}):       │
│  └─ 봇 실시간 상태 표시                  │
└───────────────────────────────────────────┘
```

---

### 3.8 알림(Notification) 데이터 흐름

```
NotificationManager (src/common/notification.py)
  │
  │  POST {N8N_URL}{endpoint}
  │  Headers: X-Webhook-Secret
  │  Retry: 3회, Exponential Backoff
  │
  ├─ /webhook/trade         ← Executor (BUY/SELL 체결 시)
  │   {symbol, side, price, quantity, strategy, executed_at}
  │
  ├─ /webhook/ai-decision   ← AgentRunner (AI 판단 결과)
  │   {symbol, decision, regime, rsi, confidence, reason}
  │
  ├─ /webhook/risk          ← RiskManager (위반/쿨다운)
  │   {type, message, level}
  │
  └─ /webhook/daily-report  ← DailyReporter (일간 리포트)
      {title, pnl, trades, win_rate, mdd, summary}
```

---

## 4. 설정 데이터 흐름

```
config/strategy_v3.yaml
    │
    ▼
load_strategy_config() → StrategyConfig dataclass
    │
    ├─ REGIMES: Dict[str, Dict]  ← 레짐별 entry/exit 파라미터
    │    ├─ BULL.entry: {rsi_14_max, rsi_7_trigger, rsi_7_recover, ...}
    │    ├─ SIDEWAYS.entry: {bb_enabled, bb_touch_lookback, ...}
    │    ├─ BEAR.entry: {volume_surge_check, ai_prefilter_*, ...}
    │    └─ *.exit: {take_profit_pct, stop_loss_pct, trailing_stop_pct, ...}
    │
    ├─ SYMBOLS: ["KRW-BTC", "KRW-ETH", ...]
    ├─ MIN_HOURLY_CANDLES_FOR_REGIME: 200
    ├─ BULL/BEAR_THRESHOLD_PCT: ±2.0%
    │
    └─ 리스크 설정:
       MAX_POSITION_SIZE: 5%
       MAX_TOTAL_EXPOSURE: 20%
       MAX_CONCURRENT_POSITIONS: 3
       MAX_DAILY_LOSS: 5%
       MAX_DAILY_TRADES: 10
       COOLDOWN_HOURS: 2

사용 위치:
  ├─ Bot: get_config() → strategy, risk_manager, bot_loop
  ├─ Collector: get_config() → SYMBOLS 목록
  └─ Scheduler: get_config() → SYMBOLS, thresholds
```

**LLM 모델 선택 (factory.py):**
```
ENV: LLM_MODE
  ├─ "dev"  → claude-haiku-4-5-20251001
  └─ "prod" → claude-sonnet-4-5-20250929

ENV: ANTHROPIC_API_KEY → ChatAnthropic 인증
ENV: OPENAI_API_KEY    → DailyReporter (GPT-4o-mini)
```
참고: 비용(토큰 단가)은 모델/시점에 따라 변동되므로 고정 수치 대신 Anthropic 가격 페이지 기준으로 운영 시점에 재확인 권장.

---

## 5. 트랜잭션 경계 및 주의사항

### 5.1 DB 세션 범위

```
bot_loop():
  async with get_db_session() as session:  ← 전체 심볼 루프가 하나의 트랜잭션
    for symbol in SYMBOLS:
      ... 지표 계산, 포지션 조회, 주문 실행 ...
      ... Redis 상태 전송 (dumps_json) ...
    ← session.commit() (컨텍스트 매니저 종료 시)

주의:
  - 과거에는 Redis 직렬화 예외(예: numpy.bool_)가 동일 세션 rollback을 유발할 수 있었음
  - 현재는 `json_utils.to_builtin()` + `dumps_json()` 적용 및 status 전송 `try/except`로 방어되어 재발 리스크가 낮음
```

### 5.2 AI 판단 로깅의 별도 세션

```
AgentRunner._log_decision():
  async with get_db_session() as session:  ← 별도 세션
    session.add(AgentDecision(...))
    await session.commit()

이유: AI 판단 기록이 실패해도 메인 봇 루프에 영향 없도록 분리
```

---

## 6. 전체 데이터 생명주기 요약

```
[1분 주기] Upbit API → Collector → market_data (DB)
                                        │
[60초 주기] Bot Loop ◄──────────────────┘
              │
              ├─ DB 읽기: market_data → DataFrame → 지표 계산
              ├─ Redis 읽기: market:regime:{symbol}
              ├─ DB 읽기: positions
              │
              ├─ [포지션 있음] Exit 판정 → SELL → trading_history + account_state + daily_risk_state
              │                                     └─ n8n → Discord
              │
              ├─ [포지션 없음] Entry 판정
              │   ├─ Rule Engine (evaluate_entry_conditions)
              │   ├─ RiskManager (check_order_validity)
              │   ├─ AI 컨텍스트 조회 (36h 1분봉 → 1시간봉 24개)
              │   ├─ AI Pre-filter (should_run_ai_analysis)
              │   ├─ AI Guardrails (should_block_ai_call)
              │   └─ AI Agent (Analyst → Guardian)
              │       ├─ Anthropic API 호출
              │       ├─ agent_decisions (DB)
              │       └─ n8n → Discord
              │
              ├─ BUY 체결 → positions + trading_history + account_state
              │              └─ n8n → Discord
              │
              └─ Redis 쓰기: bot:status:{symbol} (실시간 상태)

[1시간 주기] Scheduler → market_data → 1시간봉 리샘플 → MA50/MA200 → regime_history (DB) + Redis

[일 1회] Scheduler → market_data → GARCH → Redis(volatility_state)

[일 1회] DailyReporter → daily_risk_state + trading_history → GPT-4o-mini → n8n → Discord

[실시간] Dashboard (Streamlit) ← DB 전 테이블 + Redis(bot:status)
```

---

## 7. 기술 스택 선정 근거

### 7.1 PostgreSQL + TimescaleDB (영구 저장소)

**선택 이유:**
- 1분봉 OHLCV 데이터는 전형적인 시계열 데이터로, 시간축 기반 범위 조회(`WHERE timestamp BETWEEN ...`)가 전체 쿼리의 80% 이상을 차지함.
- TimescaleDB는 PostgreSQL 위에 시계열 최적화 계층(하이퍼테이블, 자동 청크 파티셔닝, 압축)을 제공하면서도 표준 SQL/인덱스/조인을 그대로 사용할 수 있음.
- `market_data`(시계열)와 `trading_history`, `positions`, `agent_decisions`(관계형)가 같은 DB에 공존하므로, 단일 트랜잭션 안에서 "시세 조회 → 주문 기록 → 잔고 차감"이 원자적으로 가능.
- pgvector 확장으로 `agent_memory` 테이블에서 벡터 유사도 검색도 지원(향후 RAG 패턴 확장 대비).

**고려했던 대안:**

| 대안 | 장점 | CoinPilot에서 탈락한 이유 |
|------|------|--------------------------|
| **InfluxDB / QuestDB** | 시계열 전용 DB로 쓰기 성능이 극도로 높음 | 관계형 데이터(포지션, 거래이력, AI 판단)를 별도 DB에 저장해야 하므로 운영 복잡도 증가. 트랜잭션 ACID 보장이 약함 |
| **MySQL / MariaDB** | 범용적이고 운영 생태계가 성숙 | 시계열 파티셔닝/압축/연속 집계를 위한 네이티브 지원이 없어 직접 구현 필요. JSONB 지원이 PostgreSQL 대비 미흡 |
| **MongoDB** | 스키마 유연성, JSONB 네이티브 | 시계열 데이터의 범위 집계 성능이 RDBMS 대비 불리. 트랜잭션 보장이 약함. SQL 기반 대시보드/분석 도구 연동이 불편 |
| **SQLite** | 제로 설정, 단일 파일 | 동시 쓰기 제한(단일 Writer Lock)으로 Collector + Bot + Dashboard 병렬 접근 불가. K8s 환경에서 영속 볼륨 관리 복잡 |

**CoinPilot에서의 핵심 이점:**
1. **하이퍼테이블 자동 파티셔닝**: `market_data`가 수백만 행으로 늘어도 시간 범위 쿼리 성능이 일정하게 유지됨
2. **JSONB + signal_info**: `trading_history.signal_info`에 진입 시점의 모든 지표를 비정형으로 저장하여, 사후 분석 시 스키마 변경 없이 새 지표를 추가 가능
3. **단일 DB 트랜잭션**: 주문 실행 시 `account_state` 차감 + `positions` 생성 + `trading_history` 기록이 하나의 commit으로 원자적 처리 → 부분 반영(잔고만 차감되고 포지션 미생성) 방지

---

### 7.2 Redis (실시간 캐시/상태 관리)

**선택 이유:**
- 봇 루프(60초 주기)에서 매 사이클 레짐 정보, 변동성 상태, AI 쿨다운 등을 조회해야 하는데, 이를 매번 DB에서 읽으면 불필요한 부하가 발생.
- Redis는 단순 key-value 조회가 O(1)이고, TTL 기반 자동 만료, INCR 원자 연산, 키 패턴 기반 네임스페이스 분리가 네이티브로 지원됨.
- CoinPilot에서 Redis가 담당하는 데이터는 모두 "손실되어도 재생성 가능한" 파생 데이터(레짐 캐시, HWM, 호출 카운터)이므로, Redis 장애 시 DB fallback으로 복구 가능.

**고려했던 대안:**

| 대안 | 장점 | CoinPilot에서 탈락한 이유 |
|------|------|--------------------------|
| **Memcached** | 단순 캐시 성능이 Redis와 유사 | TTL 외에 INCR, 키 패턴 조회, Pub/Sub 등 데이터 구조 지원이 없음. AI 쿨다운 카운터(INCR + EXPIRE)를 구현하려면 별도 로직 필요 |
| **DB 직접 조회** | 추가 인프라 불필요 | 매 루프(60초 × 5심볼)마다 레짐/변동성/쿨다운 조회 시 DB 커넥션 풀 부하 증가. 특히 `ai:usage:hour:*` 같은 고빈도 카운터를 DB 행으로 관리하면 잠금 경합 발생 |
| **로컬 인메모리 (Python dict)** | 제로 의존성, 최고 속도 | K8s Pod 재시작 시 모든 상태 소실. 여러 Pod(수평 확장) 간 상태 공유 불가. 현재는 단일 Bot Pod이지만 확장성을 고려 |

**CoinPilot에서의 핵심 이점:**
1. **TTL 기반 자동 만료**: `market:regime:{symbol}`(2시간), `bot:status:{symbol}`(5분), AI 쿨다운(5~15분)이 별도 정리 로직 없이 자동 소멸
2. **INCR 원자 연산**: AI 호출 카운터(`ai:usage:hour:*`, `ai:usage:day:*`)를 race condition 없이 안전하게 증감
3. **Pod 재시작 내성**: Bot Pod가 재시작되어도 레짐 캐시와 AI 쿨다운 상태가 Redis에 보존됨
4. **Dashboard 실시간 연동**: `bot:status:{symbol}`을 통해 Bot과 Dashboard가 DB 없이 실시간 상태 공유

---

### 7.3 Python + FastAPI (봇/API 서버)

**선택 이유:**
- 데이터 분석/지표 계산(pandas, numpy), ML 모델(GARCH/arch), LLM 연동(LangChain/LangGraph) 등 핵심 라이브러리가 모두 Python 생태계에 집중.
- FastAPI는 asyncio 네이티브이므로, 봇 루프(`asyncio.sleep`) + 스케줄러(APScheduler) + HTTP 엔드포인트(`/health`, `/metrics`)를 단일 프로세스에서 non-blocking으로 운영 가능.
- Pydantic 기반 자동 검증으로 AI 에이전트의 structured output(`AnalystDecision`, `GuardianDecision`) 파싱이 간결.

**고려했던 대안:**

| 대안 | 장점 | CoinPilot에서 탈락한 이유 |
|------|------|--------------------------|
| **Node.js / TypeScript** | 이벤트 루프 기반 비동기 성능 우수 | pandas/numpy/GARCH 등 수치 계산 라이브러리가 없음. LangChain JS 생태계가 Python 대비 기능/안정성에서 뒤처짐 |
| **Go** | 동시성 모델(goroutine)이 강력. 바이너리 배포 간편 | ML/데이터 분석 라이브러리 부재. LLM 프레임워크(LangChain/LangGraph) 미지원 |
| **Flask / Django** | Python 생태계 접근 가능 | Flask는 async 네이티브가 아니라 비동기 DB/Redis 호출 시 복잡도 증가. Django는 ORM이 무겁고 비동기 지원이 불완전 |

**CoinPilot에서의 핵심 이점:**
1. **단일 프로세스 통합**: Bot Loop + Scheduler + Health API + Metrics Endpoint가 하나의 FastAPI 앱 내에서 동작 → K8s Pod 1개로 관리
2. **asyncpg + aioredis**: DB/Redis 조회가 I/O 대기 중 다른 심볼 처리로 양보 가능 (현재는 순차 처리이나 확장 시 유리)
3. **LangGraph 네이티브 통합**: Analyst → Guardian 워크플로우를 StateGraph로 선언적으로 정의하고 `ainvoke()`로 비동기 실행

---

### 7.4 LangGraph + Anthropic Claude (AI 에이전트)

**선택 이유:**
- CoinPilot의 AI는 "예측"이 아닌 "2차 필터"(Rule Engine 통과 후보의 위험 요소 판단) 역할. 이를 위해 구조화된 의사결정 워크플로우(Analyst → Guardian)가 필요했고, LangGraph의 StateGraph가 이 패턴에 정확히 부합.
- Claude의 structured output(`with_structured_output`)이 Pydantic 모델과 직접 매핑되어, `decision`/`confidence`/`reasoning` 필드를 타입 안전하게 추출 가능.
- `LLM_MODE` 환경변수 하나로 Haiku(저비용 개발)↔Sonnet(고성능 운영) 전환이 가능하여, 개발/운영 비용 관리가 유연.

**고려했던 대안:**

| 대안 | 장점 | CoinPilot에서 탈락한 이유 |
|------|------|--------------------------|
| **OpenAI GPT-4o 단독** | Function Calling 성숙, 응답 안정적 | 비용 대비 구조화 출력 품질이 Claude와 유사하나, Anthropic의 Haiku/Sonnet 티어 구분이 비용 최적화에 더 유리. 일간 리포트(GPT-4o-mini)에는 별도 사용 |
| **자체 ML 모델** | API 비용 0, 지연 시간 최소 | 학습 데이터 부족(운영 이력이 짧음), 모델 학습/배포 파이프라인 구축 부담이 큼. "패턴 판단 + 자연어 설명"을 동시에 하는 모델을 자체 구축하는 것은 비현실적 |
| **LangChain AgentExecutor** | 도구 호출(Tool Use) 등 범용 에이전트 패턴 지원 | CoinPilot의 AI는 도구 호출이 불필요하고 Analyst→Guardian 고정 파이프라인이므로, AgentExecutor의 유연성이 오히려 예측 불가능한 동작(루프, 과다 호출) 위험을 높임. StateGraph가 더 결정적(deterministic) |
| **CrewAI / AutoGen** | 멀티 에이전트 오케스트레이션 프레임워크 | 2개 노드(Analyst, Guardian) 고정 파이프라인에는 과도한 추상화. LangGraph의 StateGraph가 더 가볍고 디버깅이 용이 |

**CoinPilot에서의 핵심 이점:**
1. **결정적 흐름 제어**: Analyst REJECT → 즉시 종료, CONFIRM → Guardian으로 진행. 비결정적 루프 없음
2. **비용 계층화**: `dev`(Haiku) vs `prod`(Sonnet)를 `LLM_MODE` 환경변수로 분리해, 운영 목적에 맞게 비용/성능 프로파일을 선택 가능
3. **타임아웃 + Fallback**: `asyncio.wait_for(40s)`로 LLM 응답 지연 시 보수적 REJECT fallback → 봇 루프 블로킹 방지

---

### 7.5 Container Runtime (Docker Compose Primary + Minikube Legacy)

**선택 이유:**
- 현재 단일 노드(OCI VM) 운영에서 가장 중요한 기준은 비용 효율/장애 복구 속도/운영 단순성이다.
- Compose는 `docker compose up/ps/logs` 중심 운영으로 진입 장벽이 낮고, 리소스 오버헤드가 작다.
- Minikube는 여전히 K8s 매니페스트 검증/회귀 테스트 용도로 활용 가능하다.

**고려했던 대안:**

| 대안 | 장점 | CoinPilot에서 탈락한 이유 |
|------|------|--------------------------|
| **Kubernetes(계속 기본 운영)** | 정책/확장성/배포 전략이 정교 | 현재 단일 노드/소규모 운영에서는 복잡도 대비 효익이 낮고, 포트포워딩/리소스 계층 때문에 운영 난이도 증가 |
| **AWS ECS / GCP Cloud Run** | 관리형 서비스로 운영 부담 최소 | 클라우드 종속(vendor lock-in), 비용 예측 어려움 |
| **Bare Metal (systemd 단독)** | 가장 가벼움, 오버헤드 최소 | 서비스 격리/재현성/의존성 관리가 불리 |

**CoinPilot에서의 핵심 이점:**
1. **Compose 기본 운영**: `docker compose ps/logs/up -d --build`로 일일 운영 단순화
2. **보안 점검 자동화**: `preflight_security_check.sh`로 env/포트/워크플로우 가드 일괄 점검
3. **K8s 병행 가능**: 필요 시 Minikube 원본 데이터/매니페스트를 검증할 수 있어 이행 리스크 완화

---

### 7.6 Streamlit (대시보드)

**선택 이유:**
- 대시보드의 핵심 요구사항은 "DB의 시계열/거래 데이터를 차트와 테이블로 시각화"이며, 프론트엔드 개발 없이 Python 코드만으로 구현 가능해야 함.
- Streamlit은 pandas DataFrame을 `st.dataframe()`, `st.line_chart()`로 즉시 렌더링하고, `@st.cache_data(ttl=30)`로 DB 조회 결과를 자동 캐싱.

**고려했던 대안:**

| 대안 | 장점 | CoinPilot에서 탈락한 이유 |
|------|------|--------------------------|
| **Grafana** | Prometheus/시계열 시각화에 최적화, 알림 내장 | DB의 관계형 데이터(거래이력, AI 판단 reasoning 텍스트)를 표현하기 어려움. SQL 쿼리 패널이 있으나 커스텀 로직 제한적 |
| **React / Next.js** | 완전한 커스터마이징 가능 | 프론트엔드 개발 공수가 큼. API 서버를 별도 구축해야 함. 1인 운영 프로젝트에서 유지보수 부담 과다 |
| **Dash (Plotly)** | Python 기반, Plotly 차트 품질 우수 | Streamlit 대비 보일러플레이트가 많고, 콜백 기반 구조가 복잡. 빠른 프로토타이핑에 불리 |

**CoinPilot에서의 핵심 이점:**
1. **멀티 페이지 구조**: `pages/` 디렉토리로 Overview, Market, Risk, History, System, Chatbot 페이지를 파일 단위로 분리
2. **동기식 DB 접근**: asyncio 대신 psycopg2 동기 드라이버를 사용하여 Streamlit의 멀티스레드 모델과 호환성 문제 회피
3. **빠른 이터레이션**: 코드 변경 시 Streamlit이 자동 리로드 → 차트/쿼리 수정이 즉시 반영

---

### 7.7 n8n (워크플로우 자동화 / 알림)

**선택 이유:**
- 봇의 알림 대상(Discord)과 알림 형식(매매 체결, AI 판단, 리스크 경고, 일간 리포트)이 다양한데, 이를 봇 코드에 직접 구현하면 Discord API 인증/포맷팅/에러 처리가 코드에 혼재.
- n8n은 웹훅 수신 → 메시지 포맷팅 → Discord 전송을 노코드 워크플로우로 분리하여, 알림 채널 변경(Slack, Telegram 등) 시 봇 코드 수정 없이 n8n 워크플로우만 변경.

**고려했던 대안:**

| 대안 | 장점 | CoinPilot에서 탈락한 이유 |
|------|------|--------------------------|
| **Discord.py 직접 연동** | 의존성 최소, 중간 계층 제거 | 봇 코드에 Discord 포맷팅/인증 로직이 혼재. 알림 채널 변경 시 코드 수정 필요. 웹훅 재시도 로직 직접 구현 필요 |
| **AWS SNS / GCP Pub/Sub** | 관리형, 높은 안정성 | 단순 알림 용도에 과도한 인프라. 클라우드 의존성 증가 |
| **Zapier / Make** | SaaS형으로 설정 간편 | 자체 호스팅 불가, 호출량 기반 과금, K8s 내부 통신 불가 |

**CoinPilot에서의 핵심 이점:**
1. **코드/알림 관심사 분리**: 봇은 `notifier.send_webhook(endpoint, data)`만 호출. Discord embed 포맷, 채널 라우팅은 n8n에서 관리
2. **K8s 내부 통신**: `http://n8n:5678` DNS로 K8s Service 간 직접 통신 → 외부 네트워크 불필요
3. **보안**: `X-Webhook-Secret` 헤더로 인증, n8n 워크플로우에서 검증

---

### 7.8 Prometheus (메트릭 관측)

**선택 이유:**
- Bot Pod의 비즈니스 메트릭(거래 횟수, PnL, AI 호출 수)과 시스템 메트릭(API 지연)을 표준화된 형식으로 노출하여, 향후 Grafana 연동 또는 알림 규칙 설정이 가능하도록 함.
- `prometheus_client` 라이브러리가 FastAPI의 ASGI 미들웨어와 바로 통합 가능(`/metrics` 엔드포인트).

**고려했던 대안:**

| 대안 | 장점 | CoinPilot에서 탈락한 이유 |
|------|------|--------------------------|
| **DB에 메트릭 저장** | 추가 인프라 불필요 | 고빈도 카운터/히스토그램을 DB 행으로 관리하면 쓰기 부하 및 잠금 경합 발생. 시각화를 위한 별도 쿼리 필요 |
| **StatsD / Datadog** | 풍부한 대시보드, 이상 탐지 | SaaS 비용 또는 자체 호스팅 인프라 필요. Prometheus가 K8s 생태계 표준이라 통합이 더 자연스러움 |
| **커스텀 로깅만** | 가장 간단 | 시계열 집계/알림/대시보드 연동이 어려움. 로그 파싱에 의존하게 됨 |

**CoinPilot에서의 핵심 이점:**
1. **Pull 모델**: Prometheus 서버가 `/metrics`를 주기적으로 scrape → Bot Pod는 메트릭 노출만 하면 됨
2. **타입별 메트릭**: Counter(누적), Gauge(현재값), Histogram(분포) 타입으로 거래 횟수, PnL, 지연 시간을 각각 최적의 형태로 추적
3. **K8s ServiceMonitor 연동**: 향후 Prometheus Operator 도입 시 자동 scrape 대상 등록 가능

---

### 7.9 기술 스택 의존성 요약도

```
┌─────────────────────────────────────────────────────────┐
│                    CoinPilot Tech Stack                  │
│                                                         │
│  ┌─── 언어/프레임워크 ───┐  ┌─── 데이터 저장 ────────┐  │
│  │ Python 3.10+         │  │ PostgreSQL+TimescaleDB │  │
│  │ FastAPI (async)      │  │  └ 시계열+관계형 통합  │  │
│  │ SQLAlchemy (asyncpg) │  │ Redis                  │  │
│  │ pandas / numpy       │  │  └ 캐시+상태+카운터    │  │
│  └──────────────────────┘  └────────────────────────┘  │
│                                                         │
│  ┌─── AI/ML ────────────┐  ┌─── 인프라 ─────────────┐  │
│  │ LangGraph (워크플로우)│  │ Docker Compose + K8s   │  │
│  │ LangChain (프롬프트) │  │ Prometheus (메트릭)    │  │
│  │ Anthropic Claude     │  │ n8n (알림 워크플로우)  │  │
│  │  └ Haiku / Sonnet    │  │ Streamlit (대시보드)   │  │
│  │ OpenAI GPT-4o-mini   │  │                        │  │
│  │  └ 일간 리포트 전용  │  │                        │  │
│  │ GARCH (변동성 예측)  │  │                        │  │
│  └──────────────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 8. 코드 기준 검증 정보

### 8.1 검증 일시/기준

- 검증 일시 (KST): 2026-02-19
- 검증 환경: `docker compose` (primary), `minikube + coin-pilot-ns` (legacy)
- 검증 기준:
  - 문서화된 키/테이블/스케줄/모델 선택 로직이 현재 코드와 일치하는지 점검
  - 최근 핫픽스(`dumps_json`, dashboard width 대응, SELL 경로 안정화) 반영 상태 교차 확인

### 8.2 재현용 확인 명령어

```bash
# 1) 핵심 경로/키 사용 여부 확인
rg -n "market:regime|bot:status|position:{symbol}:hwm|ai:guard|dumps_json|get_position|check_exit_signal" src -S

# 2) Bot/Scheduler 동작 축 확인
nl -ba src/bot/main.py | sed -n '180,560p'

# 3) Guardrails 키 정책 확인
sed -n '1,260p' src/agents/guardrails.py

# 4) Dashboard DB 접근 방식 확인 (sync + cache)
sed -n '1,220p' src/dashboard/utils/db_connector.py

# 5) Collector backfill/수집 주기 확인
sed -n '1,260p' src/collector/main.py

# 6) 전략/설정 로딩 경로 확인
sed -n '1,260p' src/config/strategy.py
sed -n '1,260p' config/strategy_v3.yaml

# 7) 관련 테스트(회귀) 빠른 확인
PYTHONPATH=. .venv/bin/pytest -q tests/test_bot_reason_consistency.py tests/test_strategy_v3_logic.py tests/test_indicators.py
```

### 8.3 검증 시 유의사항

- 본 문서는 아키텍처/흐름 레퍼런스이며, 운영 값(모델 가격, API 한도, 외부 서비스 정책)은 시점에 따라 변동될 수 있음
- 배포 시점에는 반드시 실행 중 Pod 기준으로 환경변수/이미지/코드 반영 여부를 재확인할 것
