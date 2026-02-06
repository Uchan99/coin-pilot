# CoinPilot v3.0 — 마켓 레짐 기반 적응형 트레이딩 전략

## 1. 개요

### 1.1 목적
기존 v2.5 듀얼 RSI 전략의 한계를 극복하기 위해, 마켓 레짐(Market Regime)을 감지하고 레짐별로 최적화된 진입/청산 파라미터를 동적으로 적용하는 적응형 전략을 구현한다.

### 1.2 기존 전략(v2.5) 문제점
- 하락장에서 MA20 돌파 조건이 거의 충족되지 않아 매수 0건 발생
- RSI 40으로 완화 후에도 MA 조건이 병목
- 백테스트 결과: 104건 거래, 승률 48.1%, 누적 수익률 **-74.91%**
- RSI(70) 과매수 청산이 68%로 조기 청산 빈발
- Stop Loss(-3%)가 하락장 변동성 대비 너무 타이트

### 1.3 v3.0 핵심 변경사항
1. 마켓 레짐 감지 (상승 / 횡보 / 하락) 도입
2. 레짐별 진입 조건 분기
3. 청산 조건 전면 개편 (트레일링 스탑 도입)
4. RSI 청산 로직 조건부 변경

---

## 2. 데이터 타임프레임 정책

### 2.1 현행 시스템
- 데이터 수집: **1분봉** (`src/collector/main.py`)
- 봇 실행 주기: **1분마다**

### 2.2 v3.0 타임프레임 정책
- 데이터 수집: **1분봉 유지** (기존 시스템 변경 없음)
- 지표 계산: **1시간봉으로 리샘플링** 후 계산
- 진입/청산 체크: **1분마다** (기존 루프 유지, 캐시된 레짐/지표 사용)
- 레짐 판단: **1시간마다** (스케줄러)

### 2.3 1분봉 → 1시간봉 리샘플링

`src/common/indicators.py`에 리샘플링 함수를 추가한다.

```python
def resample_to_hourly(df_1m: pd.DataFrame) -> pd.DataFrame:
    """
    1분봉 데이터를 1시간봉으로 리샘플링

    Args:
        df_1m: 1분봉 DataFrame (columns: timestamp, open, high, low, close, volume)

    Returns:
        1시간봉 DataFrame
    """
    df = df_1m.set_index('timestamp') if 'timestamp' in df_1m.columns else df_1m
    return df.resample('1H').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
```

### 2.4 데이터 요구량
- MA200 (1시간봉) 계산 시 최소 **200개 1시간봉** = 약 8.3일치 1분봉 필요
- 신규 코인 추가 시 최소 9일간 데이터 수집 후 레짐 판단 가능

---

## 3. 마켓 레짐 감지 (Market Regime Detection)

### 3.1 판단 기준

MA50(50기간)과 MA200(200기간)의 관계로 레짐을 판단한다. 모든 MA는 **1시간봉 기준**이다.

```python
def detect_regime(ma50: float | None, ma200: float | None) -> str:
    """
    마켓 레짐 감지

    Args:
        ma50: 50기간(1시간봉) 이동평균선 값 (None이면 데이터 부족)
        ma200: 200기간(1시간봉) 이동평균선 값 (None이면 데이터 부족)

    Returns:
        "BULL" | "SIDEWAYS" | "BEAR" | "UNKNOWN"
    """
    # Fallback: 데이터 부족 시 UNKNOWN 반환
    if ma50 is None or ma200 is None:
        return "UNKNOWN"

    diff_pct = (ma50 - ma200) / ma200 * 100

    if diff_pct > 2.0:
        return "BULL"       # 상승장: MA50이 MA200보다 2% 이상 위
    elif diff_pct < -2.0:
        return "BEAR"       # 하락장: MA50이 MA200보다 2% 이상 아래
    else:
        return "SIDEWAYS"   # 횡보장: MA50과 MA200 차이 ±2% 이내
```

### 3.2 UNKNOWN 레짐 Fallback 정책

데이터 부족으로 레짐이 `UNKNOWN`인 경우:
- **진입**: 거래를 보류한다 (매수 시그널 발생하지 않음)
- **청산**: 기존 보유 포지션은 SIDEWAYS 파라미터로 청산 관리
- **로그**: `UNKNOWN` 상태와 데이터 부족 사유를 로그에 기록

```python
# UNKNOWN 레짐 처리
if regime == "UNKNOWN":
    logger.warning(f"{symbol}: 레짐 판단 불가 (데이터 부족). 거래 보류.")
    entry_allowed = False
    exit_config = SIDEWAYS_EXIT  # 청산은 SIDEWAYS 기준 적용
```

### 3.3 레짐 판단 주기 및 캐싱

- **판단 주기**: 1시간마다 (APScheduler 활용, 기존 구현 활용)
- **캐싱**: Redis에 레짐 정보 저장, 1분 루프에서 캐시된 레짐 사용

```python
# Redis 키 구조
REGIME_KEY = "market:regime:{symbol}"            # 값: "BULL" | "SIDEWAYS" | "BEAR" | "UNKNOWN"
REGIME_META_KEY = "market:regime_meta:{symbol}"  # 값: JSON {ma50, ma200, diff_pct, detected_at}
REGIME_TTL = 3900  # 65분 (1시간 + 5분 여유)

# 1시간마다 스케줄러에서 실행
async def update_regime(symbol: str):
    hourly_df = resample_to_hourly(get_1m_candles(symbol))
    ma50 = hourly_df['close'].rolling(50).mean().iloc[-1] if len(hourly_df) >= 50 else None
    ma200 = hourly_df['close'].rolling(200).mean().iloc[-1] if len(hourly_df) >= 200 else None
    regime = detect_regime(ma50, ma200)

    await redis.set(REGIME_KEY.format(symbol=symbol), regime, ex=REGIME_TTL)
    await redis.set(REGIME_META_KEY.format(symbol=symbol), json.dumps({
        "ma50": float(ma50) if ma50 else None,
        "ma200": float(ma200) if ma200 else None,
        "diff_pct": float((ma50 - ma200) / ma200 * 100) if (ma50 and ma200) else None,
        "detected_at": datetime.utcnow().isoformat()
    }), ex=REGIME_TTL)

# 1분 루프에서 캐시 조회
async def get_current_regime(symbol: str) -> str:
    regime = await redis.get(REGIME_KEY.format(symbol=symbol))
    return regime or "UNKNOWN"
```

### 3.4 레짐 변경 시 처리
- 레짐 변경 시 기존 미체결 주문은 취소한다.
- 보유 포지션의 청산 조건 처리: **섹션 6.4 참조**
- 레짐 변경 이력을 DB에 기록한다 (`regime_history` 테이블).

---

## 4. 레짐별 진입 조건

### 4.1 상승장 (BULL) 진입 조건

상승 추세를 신뢰하고, 풀백(pullback) 매수를 노린다.

```python
BULL_ENTRY = {
    "rsi_14_max": 45,          # RSI(14) ≤ 45
    "rsi_7_trigger": 40,       # RSI(7) ≤ 40 이하였다가
    "rsi_7_recover": 40,       # RSI(7)이 다시 40 위로 복귀 시 진입
    "ma_condition": "crossover", # 현재가가 MA20을 상향 돌파
    "ma_period": 20,
    "volume_ratio": 1.2,       # 거래량이 20일 평균의 1.2배 이상
}
```

**진입 로직 (의사코드):**
```
IF rsi_14 ≤ 45
   AND rsi_7이 직전 캔들에서 40 이하였고 현재 40 이상으로 복귀
   AND current_price > MA20
   AND volume > volume_ma20 * 1.2
THEN 매수 시그널 발생
```

### 4.2 횡보장 (SIDEWAYS) 진입 조건

볼린저밴드 하단 + RSI 과매도를 활용한 Mean Reversion 전략.

```python
SIDEWAYS_ENTRY = {
    "rsi_14_max": 40,          # RSI(14) ≤ 40
    "rsi_7_trigger": 35,       # RSI(7) ≤ 35 이하였다가
    "rsi_7_recover": 35,       # RSI(7)이 다시 35 위로 복귀 시 진입
    "ma_condition": "proximity", # 현재가가 MA20의 97% 이내
    "ma_period": 20,
    "ma_proximity_pct": 0.97,
    "bb_condition": True,      # 볼린저밴드 하단 터치 또는 이탈 후 복귀
    "bb_period": 20,
    "bb_std": 2.0,
    "bb_touch_lookback": 3,    # 최근 3캔들(1시간봉) 내 BB 하단 터치 확인
    "volume_ratio": 1.0,       # 거래량 조건 완화 (평균 이상이면 OK)
}
```

**볼린저밴드 터치 판정 로직:**

최근 `bb_touch_lookback` 캔들(1시간봉) 이내에 종가가 볼린저밴드 하단 이하를 터치한 적이 있고, 현재 캔들에서는 하단 위로 복귀한 경우를 "터치 후 복귀"로 판정한다.

```python
def check_bb_touch_recovery(df: pd.DataFrame, lookback: int = 3) -> bool:
    """
    최근 N캔들(1시간봉) 내 볼린저밴드 하단 터치 후 현재 복귀 여부 판정

    Args:
        df: 1시간봉 DataFrame (columns: close, bb_lower)
        lookback: 터치 확인 캔들 수 (기본 3)

    Returns:
        True이면 BB 하단 터치 후 복귀 확인
    """
    if len(df) < lookback + 1:
        return False

    recent = df.tail(lookback + 1)
    # 직전 N캔들 중 BB 하단 이하 터치가 있었는지
    touched = any(recent['close'].iloc[:-1] <= recent['bb_lower'].iloc[:-1])
    # 현재 캔들은 BB 하단 위에 있는지
    recovered = recent['close'].iloc[-1] > recent['bb_lower'].iloc[-1]
    return touched and recovered
```

**진입 로직 (의사코드):**
```
IF rsi_14 ≤ 40
   AND rsi_7이 직전 캔들에서 35 이하였고 현재 35 이상으로 복귀
   AND current_price ≥ MA20 * 0.97
   AND check_bb_touch_recovery(df, lookback=3) == True
   AND volume ≥ volume_ma20 * 1.0
THEN 매수 시그널 발생
```

### 4.3 하락장 (BEAR) 진입 조건

보수적 진입. 강한 과매도 + 반등 확인 후 소규모 진입.

```python
BEAR_ENTRY = {
    "rsi_14_max": 40,          # RSI(14) ≤ 40
    "rsi_7_trigger": 30,       # RSI(7) ≤ 30 이하였다가
    "rsi_7_recover": 30,       # RSI(7)이 다시 30 위로 복귀 시 진입
    "ma_condition": "proximity", # 현재가가 MA20의 97% 이내
    "ma_period": 20,
    "ma_proximity_pct": 0.97,
    "volume_ratio": None,      # 거래량 조건 비활성화
    "position_size_ratio": 0.5, # 건당 투자금 50%로 축소
}
```

**진입 로직 (의사코드):**
```
IF rsi_14 ≤ 40
   AND rsi_7이 직전 캔들에서 30 이하였고 현재 30 이상으로 복귀
   AND current_price ≥ MA20 * 0.97
THEN 매수 시그널 발생 (투자금 50%로 축소)
```

---

## 5. 레짐별 청산 조건

### 5.1 청산 파라미터 총괄표

| 항목 | 상승장 (BULL) | 횡보장 (SIDEWAYS) | 하락장 (BEAR) |
|------|:---:|:---:|:---:|
| Take Profit (고정) | +5% | +3% | +3% |
| Stop Loss (고정) | -3% | -4% | -5% |
| 트레일링 스탑 | 최고점 -3% | 최고점 -2.5% | 최고점 -2% |
| 트레일링 스탑 활성화 | 수익 +1% 이상 | 수익 +1% 이상 | 수익 +1% 이상 |
| RSI 과매수 청산 | RSI(14) > 75 AND 수익 > +1% | RSI(14) > 70 AND 수익 > +1% | RSI(14) > 70 AND 수익 > +0.5% |
| 시간 제한 | 72시간 | 48시간 | 24시간 |

### 5.2 청산 파라미터 코드

```python
BULL_EXIT = {
    "take_profit_pct": 0.05,               # +5%
    "stop_loss_pct": 0.03,                 # -3%
    "trailing_stop_pct": 0.03,             # 최고점 대비 -3%
    "trailing_stop_activation_pct": 0.01,  # +1% 이상 시 활성화
    "rsi_overbought": 75,                  # RSI(14) > 75
    "rsi_exit_min_profit": 0.01,           # RSI 청산 시 최소 수익 +1%
    "time_limit_hours": 72,
}

SIDEWAYS_EXIT = {
    "take_profit_pct": 0.03,               # +3%
    "stop_loss_pct": 0.04,                 # -4%
    "trailing_stop_pct": 0.025,            # 최고점 대비 -2.5%
    "trailing_stop_activation_pct": 0.01,  # +1% 이상 시 활성화
    "rsi_overbought": 70,                  # RSI(14) > 70
    "rsi_exit_min_profit": 0.01,           # RSI 청산 시 최소 수익 +1%
    "time_limit_hours": 48,
}

BEAR_EXIT = {
    "take_profit_pct": 0.03,               # +3%
    "stop_loss_pct": 0.05,                 # -5%
    "trailing_stop_pct": 0.02,             # 최고점 대비 -2%
    "trailing_stop_activation_pct": 0.01,  # +1% 이상 시 활성화
    "rsi_overbought": 70,                  # RSI(14) > 70
    "rsi_exit_min_profit": 0.005,          # RSI 청산 시 최소 수익 +0.5%
    "time_limit_hours": 24,
}
```

### 5.3 청산 우선순위

청산 조건은 아래 우선순위로 평가한다. **먼저 충족되는 조건으로 청산.**

```
1. Stop Loss (고정) → 최우선 손절
2. 트레일링 스탑 → 수익 보호 (활성화 조건 충족 시)
3. Take Profit (고정) → 목표 익절
4. RSI 과매수 청산 (조건부) → 모멘텀 기반 청산
5. 시간 제한 초과 → 강제 청산
```

---

## 6. 트레일링 스탑 상세 구현

### 6.1 동작 방식

트레일링 스탑은 보유 기간 동안 도달한 **최고가(high water mark)**를 추적하고, 현재가가 최고가 대비 일정 비율 이상 하락하면 청산한다.

```python
class TrailingStop:
    """
    트레일링 스탑 관리

    - 매수 직후 high_water_mark = 매수가로 초기화
    - 매 캔들마다 현재가 > high_water_mark이면 갱신
    - 활성화 조건: 수익이 activation_pct 이상일 때부터 작동
    - 현재가 ≤ high_water_mark * (1 - trailing_stop_pct)이면 청산
    """
    def __init__(self, entry_price: float, trailing_stop_pct: float,
                 activation_pct: float = 0.01, high_water_mark: float = None):
        self.entry_price = entry_price
        self.high_water_mark = high_water_mark or entry_price
        self.trailing_stop_pct = trailing_stop_pct
        self.activation_pct = activation_pct

    def update(self, current_price: float) -> bool:
        """
        현재가로 트레일링 스탑 업데이트

        Returns:
            True이면 청산 시그널
        """
        # 최고가 갱신
        if current_price > self.high_water_mark:
            self.high_water_mark = current_price

        # 활성화 조건 체크: 수익이 activation_pct 이상이어야 함
        profit_pct = (current_price - self.entry_price) / self.entry_price
        if profit_pct < self.activation_pct:
            return False  # 아직 활성화 안 됨

        # 청산 조건 체크
        stop_price = self.high_water_mark * (1 - self.trailing_stop_pct)
        if current_price <= stop_price:
            return True  # 청산

        return False
```

### 6.2 트레일링 스탑 상태 저장

봇 재시작 시 `high_water_mark` 유실을 방지하기 위해 **이중 저장** 한다.

**실시간 저장 (Redis):**
```python
# Redis 키 구조
HWM_KEY = "position:{symbol}:hwm"

# 매 캔들마다 high_water_mark 업데이트 시 Redis에 저장
async def save_hwm_to_redis(symbol: str, hwm: float):
    await redis.set(HWM_KEY.format(symbol=symbol), str(hwm))

# 봇 시작 시 Redis에서 HWM 복구
async def load_hwm_from_redis(symbol: str) -> float | None:
    hwm = await redis.get(HWM_KEY.format(symbol=symbol))
    return float(hwm) if hwm else None
```

**영구 저장 (DB):**
```python
# trades 테이블의 high_water_mark 컬럼에 주기적으로 동기화 (1분마다)
async def sync_hwm_to_db(trade_id: int, hwm: float):
    await db.execute(
        "UPDATE trades SET high_water_mark = $1 WHERE id = $2",
        hwm, trade_id
    )
```

**복구 우선순위:**
1. Redis에서 복구 시도
2. Redis 없으면 DB에서 복구
3. 둘 다 없으면 매수가로 초기화

```python
async def restore_trailing_stop(symbol: str, trade) -> TrailingStop:
    hwm = await load_hwm_from_redis(symbol)
    if hwm is None:
        hwm = trade.high_water_mark  # DB에서 복구
    if hwm is None:
        hwm = trade.entry_price  # 최종 Fallback

    config = get_exit_config(trade.regime)
    return TrailingStop(
        entry_price=trade.entry_price,
        trailing_stop_pct=config["trailing_stop_pct"],
        activation_pct=config["trailing_stop_activation_pct"],
        high_water_mark=hwm
    )
```

### 6.3 포지션 청산 시 정리

포지션 청산 시 Redis의 HWM 키를 삭제한다.

```python
async def on_position_closed(symbol: str):
    await redis.delete(HWM_KEY.format(symbol=symbol))
```

### 6.4 레짐 변경 시 기존 포지션 처리 정책

레짐이 변경되면 기존 보유 포지션의 청산 조건을 업데이트해야 한다. **리스크 확대를 방지**하기 위해 아래 정책을 적용한다.

**원칙: Stop Loss는 타이트한 쪽 유지, 나머지는 새 레짐 적용**

```python
def update_position_on_regime_change(
    position,
    old_exit_config: dict,
    new_exit_config: dict
) -> dict:
    """
    레짐 변경 시 기존 포지션의 청산 파라미터 업데이트

    정책:
    - Stop Loss: 기존과 새 레짐 중 타이트한(작은) 값 유지 → 리스크 확대 방지
    - Take Profit: 새 레짐 값 적용
    - 트레일링 스탑: 새 레짐 값 적용 (더 타이트해지는 방향이므로 안전)
    - RSI 청산: 새 레짐 값 적용
    - 시간 제한: 새 레짐 값 적용

    예시: BULL(SL -3%) → BEAR(SL -5%) 전환 시 → SL -3% 유지 (확대 방지)
    예시: BEAR(SL -5%) → BULL(SL -3%) 전환 시 → SL -3% 적용 (타이트하게)
    """
    updated_config = new_exit_config.copy()
    updated_config["stop_loss_pct"] = min(
        old_exit_config["stop_loss_pct"],
        new_exit_config["stop_loss_pct"]
    )
    return updated_config
```

---

## 7. RSI 청산 로직 변경

### 7.1 기존 문제
- RSI(14) > 70이면 무조건 청산
- 하락장에서 소폭 반등에도 RSI가 70에 도달하여 조기 청산 빈발
- 백테스트 기준 68%의 거래가 RSI 과매수로 청산되었으나 수익이 미미

### 7.2 변경된 RSI 청산 로직

```python
def should_exit_by_rsi(
    rsi_14: float,
    entry_price: float,
    current_price: float,
    regime: str
) -> bool:
    """
    조건부 RSI 청산

    RSI가 과매수 구간에 진입하더라도,
    최소 수익 조건을 충족해야만 청산한다.
    """
    config = {
        "BULL": {"rsi_threshold": 75, "min_profit": 0.01},
        "SIDEWAYS": {"rsi_threshold": 70, "min_profit": 0.01},
        "BEAR": {"rsi_threshold": 70, "min_profit": 0.005},
    }

    # UNKNOWN 레짐은 SIDEWAYS 기준 적용
    c = config.get(regime, config["SIDEWAYS"])
    profit_pct = (current_price - entry_price) / entry_price

    if rsi_14 > c["rsi_threshold"] and profit_pct >= c["min_profit"]:
        return True

    return False
```

---

## 8. 포지션 사이징

### 8.1 레짐별 투자금 비율

| 레짐 | 건당 투자금 비율 | 설명 |
|------|:---:|------|
| 상승장 (BULL) | 100% | 기본 투자금 전액 |
| 횡보장 (SIDEWAYS) | 80% | 소폭 축소 |
| 하락장 (BEAR) | 50% | 리스크 관리를 위해 절반 |
| UNKNOWN | 0% | 거래 보류 |

### 8.2 구현

```python
POSITION_SIZE_RATIO = {
    "BULL": 1.0,
    "SIDEWAYS": 0.8,
    "BEAR": 0.5,
    "UNKNOWN": 0.0,  # 거래 보류
}

def calculate_position_size(base_amount: float, regime: str) -> float:
    """
    레짐에 따른 실제 투자금 계산

    Args:
        base_amount: 기본 건당 투자금 (예: 100,000원)
        regime: 현재 마켓 레짐

    Returns:
        실제 투자금 (UNKNOWN이면 0 → 거래 발생 안 함)
    """
    ratio = POSITION_SIZE_RATIO.get(regime, 0.0)
    return base_amount * ratio
```

---

## 9. 전체 매매 플로우

```
[1시간마다 - 스케줄러]
│
├─ A. 1분봉 → 1시간봉 리샘플링
├─ B. MA50, MA200 계산
├─ C. detect_regime() → 레짐 판단
├─ D. Redis에 레짐 캐싱 (TTL: 65분)
└─ E. regime_history 테이블에 기록 (변경 시)

[1분마다 - 봇 메인 루프]
│
├─ 1. 마켓 데이터 수집 (1분봉: 가격, 거래량)
│
├─ 2. Redis에서 캐시된 레짐 조회
│   └─ get_current_regime(symbol) → BULL / SIDEWAYS / BEAR / UNKNOWN
│
├─ 3. UNKNOWN이면 진입 스킵, 청산만 수행
│
├─ 4. 레짐별 파라미터 로드
│   └─ entry_config, exit_config, position_size_ratio
│
├─ 5. 지표 계산 (1시간봉 리샘플링 데이터 기반)
│   ├─ RSI(14), RSI(7)
│   ├─ MA20
│   ├─ [횡보장] 볼린저밴드 (period=20, std=2.0)
│   └─ [상승/횡보] 거래량 MA20
│
├─ 6. 진입 시그널 평가
│   ├─ RSI(14) 조건 충족?
│   ├─ RSI(7) 반등 확인?
│   ├─ MA 조건 충족? (돌파 or proximity)
│   ├─ [횡보장] BB 터치 후 복귀? (lookback=3)
│   └─ [상승/횡보] 거래량 조건?
│
├─ 7. 매수 실행
│   ├─ 포지션 사이징 적용
│   ├─ TrailingStop 객체 초기화 (Redis + DB에 HWM 저장)
│   └─ DB에 포지션 기록 (regime 컬럼 포함)
│
├─ 8. 보유 포지션 청산 평가 (매 1분마다)
│   ├─ TrailingStop.update(current_price) → HWM 갱신 (Redis + DB 동기화)
│   ├─ [1순위] Stop Loss 도달? → 즉시 청산
│   ├─ [2순위] 트레일링 스탑 트리거? → 청산 (수익 +1% 이상 시 활성화)
│   ├─ [3순위] Take Profit 도달? → 청산
│   ├─ [4순위] RSI 과매수 + 최소 수익 충족? → 청산
│   └─ [5순위] 시간 제한 초과? → 강제 청산
│
└─ 9. 로깅 및 리포팅
    ├─ 거래 내역 DB 기록 (exit_reason 포함)
    ├─ 청산 시 Redis HWM 키 삭제
    └─ 일일 리포트 생성
```

---

## 10. 기술 지표 계산 요구사항

### 10.1 필수 지표

| 지표 | 파라미터 | 타임프레임 | 용도 |
|------|----------|:---:|------|
| RSI(14) | period=14 | 1시간봉 | 중기 과매도/과매수 판단 |
| RSI(7) | period=7 | 1시간봉 | 단기 반등 감지 |
| MA20 | period=20 | 1시간봉 | 진입 조건 (돌파/proximity) |
| MA50 | period=50 | 1시간봉 | 레짐 감지 |
| MA200 | period=200 | 1시간봉 | 레짐 감지 |
| 볼린저밴드 | period=20, std=2.0 | 1시간봉 | 횡보장 진입 조건 |
| 거래량 MA20 | period=20 | 1시간봉 | 거래량 필터 |

### 10.2 데이터 소스
- 원본: 1분봉 데이터 (기존 collector 유지)
- 지표 계산: 1분봉 → 1시간봉 리샘플링 후 계산
- MA200 계산을 위해 최소 **200개 1시간봉** (약 8.3일치) 필요

---

## 11. DB 스키마 변경사항

### 11.1 regime_history 테이블 (신규)

```sql
CREATE TABLE regime_history (
    id SERIAL PRIMARY KEY,
    detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
    regime VARCHAR(10) NOT NULL,  -- 'BULL', 'SIDEWAYS', 'BEAR', 'UNKNOWN'
    ma50 DECIMAL(20, 8),          -- NULL 허용 (데이터 부족 시)
    ma200 DECIMAL(20, 8),         -- NULL 허용 (데이터 부족 시)
    diff_pct DECIMAL(10, 4),      -- NULL 허용 (데이터 부족 시)
    coin_symbol VARCHAR(10) NOT NULL DEFAULT 'BTC'
);

CREATE INDEX idx_regime_history_symbol_time ON regime_history (coin_symbol, detected_at DESC);
```

### 11.2 trading_history 테이블 변경

기존 `trading_history` 테이블에 아래 컬럼을 추가한다.

```sql
ALTER TABLE trading_history ADD COLUMN regime VARCHAR(10);              -- 진입 시 레짐
ALTER TABLE trading_history ADD COLUMN high_water_mark DECIMAL(20, 8);  -- 청산 시점 최고가 기록
ALTER TABLE trading_history ADD COLUMN exit_reason VARCHAR(30);         -- 청산 사유
-- exit_reason 값: 'TAKE_PROFIT', 'STOP_LOSS', 'TRAILING_STOP',
--                 'RSI_OVERBOUGHT', 'TIME_LIMIT', 'MANUAL'
```

### 11.3 positions 테이블 변경

보유 중인 포지션의 트레일링 스탑 상태를 추적하기 위해 `positions` 테이블에 아래 컬럼을 추가한다.

```sql
ALTER TABLE positions ADD COLUMN regime VARCHAR(10);              -- 진입 시 레짐
ALTER TABLE positions ADD COLUMN high_water_mark DECIMAL(20, 8);  -- 보유 중 최고가 (실시간 갱신)
```

### 11.4 마이그레이션 스크립트

```sql
-- migrations/v3_0_regime_trading.sql

BEGIN;

-- 1. regime_history 테이블 생성
CREATE TABLE IF NOT EXISTS regime_history (
    id SERIAL PRIMARY KEY,
    detected_at TIMESTAMP NOT NULL DEFAULT NOW(),
    regime VARCHAR(10) NOT NULL,
    ma50 DECIMAL(20, 8),
    ma200 DECIMAL(20, 8),
    diff_pct DECIMAL(10, 4),
    coin_symbol VARCHAR(10) NOT NULL DEFAULT 'BTC'
);

CREATE INDEX IF NOT EXISTS idx_regime_history_symbol_time
    ON regime_history (coin_symbol, detected_at DESC);

-- 2. trading_history 테이블 컬럼 추가
ALTER TABLE trading_history ADD COLUMN IF NOT EXISTS regime VARCHAR(10);
ALTER TABLE trading_history ADD COLUMN IF NOT EXISTS high_water_mark DECIMAL(20, 8);
ALTER TABLE trading_history ADD COLUMN IF NOT EXISTS exit_reason VARCHAR(30);

-- 3. positions 테이블 컬럼 추가
ALTER TABLE positions ADD COLUMN IF NOT EXISTS regime VARCHAR(10);
ALTER TABLE positions ADD COLUMN IF NOT EXISTS high_water_mark DECIMAL(20, 8);

COMMIT;
```

---

## 12. 설정 파일 구조

### 12.1 파일 경로

`config/strategy_v3.yaml` (프로젝트 루트의 config 디렉토리)

### 12.2 YAML 설정 내용

모든 전략 파라미터는 설정 파일로 관리하여, 코드 변경 없이 파라미터 튜닝이 가능하도록 한다.

```yaml
# config/strategy_v3.yaml

regime_detection:
  ma_fast_period: 50
  ma_slow_period: 200
  bull_threshold_pct: 2.0
  bear_threshold_pct: -2.0
  check_interval_hours: 1
  unknown_fallback: "SIDEWAYS"    # UNKNOWN 시 청산에 사용할 Fallback 레짐
  redis_ttl_seconds: 3900         # 65분

data:
  source_timeframe: "1m"              # 원본 데이터 타임프레임
  indicator_timeframe: "1h"           # 지표 계산 타임프레임
  min_hourly_candles_for_regime: 200  # 레짐 판단에 필요한 최소 1시간봉 수

regimes:
  BULL:
    entry:
      rsi_14_max: 45
      rsi_7_trigger: 40
      rsi_7_recover: 40
      ma_condition: "crossover"
      ma_period: 20
      volume_ratio: 1.2
    exit:
      take_profit_pct: 0.05
      stop_loss_pct: 0.03
      trailing_stop_pct: 0.03
      trailing_stop_activation_pct: 0.01
      rsi_overbought: 75
      rsi_exit_min_profit_pct: 0.01
      time_limit_hours: 72
    position:
      size_ratio: 1.0

  SIDEWAYS:
    entry:
      rsi_14_max: 40
      rsi_7_trigger: 35
      rsi_7_recover: 35
      ma_condition: "proximity"
      ma_period: 20
      ma_proximity_pct: 0.97
      bb_enabled: true
      bb_period: 20
      bb_std: 2.0
      bb_touch_lookback: 3
      volume_ratio: 1.0
    exit:
      take_profit_pct: 0.03
      stop_loss_pct: 0.04
      trailing_stop_pct: 0.025
      trailing_stop_activation_pct: 0.01
      rsi_overbought: 70
      rsi_exit_min_profit_pct: 0.01
      time_limit_hours: 48
    position:
      size_ratio: 0.8

  BEAR:
    entry:
      rsi_14_max: 40
      rsi_7_trigger: 30
      rsi_7_recover: 30
      ma_condition: "proximity"
      ma_period: 20
      ma_proximity_pct: 0.97
      volume_ratio: null
    exit:
      take_profit_pct: 0.03
      stop_loss_pct: 0.05
      trailing_stop_pct: 0.02
      trailing_stop_activation_pct: 0.01
      rsi_overbought: 70
      rsi_exit_min_profit_pct: 0.005
      time_limit_hours: 24
    position:
      size_ratio: 0.5

regime_change_policy:
  stop_loss: "keep_tighter"        # 기존과 새 레짐 중 타이트한 SL 유지
  cancel_pending_orders: true      # 미체결 주문 취소
  log_regime_change: true          # 레짐 변경 이력 DB 기록
```

### 12.3 YAML 로더

`src/config/strategy.py`에 YAML 로더를 추가한다.

```python
import yaml
from pathlib import Path

def load_strategy_config(path: str = "config/strategy_v3.yaml") -> dict:
    """
    전략 설정 파일 로드

    Args:
        path: YAML 파일 경로

    Returns:
        설정 딕셔너리
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"전략 설정 파일 없음: {path}")

    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def get_regime_config(config: dict, regime: str) -> dict:
    """
    레짐별 설정 반환. UNKNOWN이면 Fallback 레짐 사용.
    """
    if regime == "UNKNOWN":
        fallback = config["regime_detection"]["unknown_fallback"]
        return config["regimes"][fallback]
    return config["regimes"].get(regime, config["regimes"]["SIDEWAYS"])
```

---

## 13. AI Agent 연동

### 13.1 레짐 정보를 AI Agent 프롬프트에 포함

현재 AI Agent(LangGraph)가 매수 최종 승인/거절을 하므로, 레짐 정보를 프롬프트에 포함하여 레짐 인식 판단을 유도한다.

```python
# src/agents/prompts.py 수정

REGIME_DESCRIPTIONS = {
    "BULL": "상승장 (MA50 > MA200, 골든크로스 상태). 추세를 신뢰하고 풀백 매수에 유리한 환경.",
    "SIDEWAYS": "횡보장 (MA50 ≈ MA200). Mean Reversion 전략이 효과적인 환경.",
    "BEAR": "하락장 (MA50 < MA200, 데드크로스 상태). 보수적 진입, 빠른 청산이 필요한 환경.",
    "UNKNOWN": "레짐 판단 불가 (데이터 부족). 신규 거래 보류 권장.",
}

ANALYST_PROMPT = """
현재 마켓 레짐: {regime}
레짐 설명: {regime_description}
레짐 지표: MA50={ma50:.2f}, MA200={ma200:.2f}, 차이={diff_pct:.2f}%

위 마켓 레짐을 고려하여 매매 판단을 내려주세요.
{regime} 레짐에서는 {regime_guidance}
...
"""
```

---

## 14. 기존 코드베이스 호환성

### 14.1 변경이 필요한 파일

| 구성 요소 | 현재 상태 | v3.0 변경 내용 |
|-----------|-----------|----------------|
| `src/config/strategy.py` | dataclass 기반 | YAML 로더 추가, 레짐별 config 반환 함수 |
| `src/engine/strategy.py` | 단일 전략 클래스 | 레짐별 분기 로직 추가 (Strategy Factory 또는 if/else) |
| `src/common/indicators.py` | 1분봉 기준 지표 | 1시간봉 리샘플링 함수 추가, RSI(7) 추가 |
| `src/bot/main.py` | 심볼별 1분 루프 | 레짐 캐시 조회, TrailingStop 관리 추가 |
| DB 스키마 | 현행 | `regime_history` 테이블, `trades` 컬럼 추가 |
| `src/agents/prompts.py` | 레짐 미인식 | 레짐 정보 프롬프트 포함 |

### 14.2 새로 추가할 파일

| 파일 | 용도 |
|------|------|
| `config/strategy_v3.yaml` | 전략 파라미터 설정 |
| `src/engine/regime.py` | 레짐 감지 모듈 |
| `src/engine/trailing_stop.py` | 트레일링 스탑 클래스 |
| `migrations/v3_0_regime_trading.sql` | DB 마이그레이션 |
| `scripts/backtest_v3.py` | v3.0 백테스트 스크립트 |

---

## 15. 백테스트 검증 계획

### 15.1 검증 항목

구현 완료 후 아래 항목을 백테스트로 검증한다.

1. **레짐별 거래 건수**: 각 레짐에서 충분한 매수 시그널이 발생하는지
2. **레짐별 승률**: 각 레짐의 승률이 50% 이상인지
3. **레짐별 수익률**: 각 레짐의 평균 수익률
4. **청산 사유 분포**: 트레일링 스탑, TP, SL, RSI, 시간제한 비율
5. **전체 누적 수익률**: v2.5(-74.91%) 대비 개선 여부
6. **최대 낙폭(MDD)**: 연속 손실 구간의 최대 손실

### 15.2 백테스트 데이터 기간
- 최소 6개월 이상의 1시간봉 데이터
- 상승장 / 횡보장 / 하락장이 모두 포함된 기간

### 15.3 비교 대상
- v2.5 (기존): 동일 기간 백테스트 결과와 비교
- Buy & Hold: 단순 보유 전략과 수익률 비교

---

## 16. 구현 우선순위

| 순서 | 항목 | 설명 |
|:---:|------|------|
| 1 | DB 마이그레이션 | `regime_history` 테이블, `trades` 컬럼 추가 |
| 2 | 1시간봉 리샘플링 | `src/common/indicators.py`에 `resample_to_hourly()` 추가 |
| 3 | 레짐 감지 모듈 | `src/engine/regime.py` — `detect_regime()`, Redis 캐싱 |
| 4 | YAML 설정 파일 및 로더 | `config/strategy_v3.yaml`, `src/config/strategy.py` 수정 |
| 5 | 진입 조건 리팩토링 | Rule Engine에 레짐별 분기 적용, BB 터치 판정 |
| 6 | 트레일링 스탑 구현 | `src/engine/trailing_stop.py` — Redis/DB 이중 저장 |
| 7 | 청산 로직 리팩토링 | 우선순위 기반 청산 평가, 레짐 변경 시 SL 정책 |
| 8 | RSI 청산 로직 변경 | 조건부 RSI 청산 |
| 9 | 포지션 사이징 | 레짐별 투자금 비율 적용, UNKNOWN 보류 |
| 10 | AI Agent 연동 | 프롬프트에 레짐 정보 포함 |
| 11 | 백테스트 스크립트 | v3.0 전략 검증용 백테스트 |
| 12 | 대시보드 업데이트 | 레짐 표시, 트레일링 스탑 시각화 |

---

## Claude Code Review (2차)

**검토일**: 2026-02-06
**검토자**: Claude Code (Opus 4.5)

### 1. 1차 리뷰 반영 확인 ✅

1차 리뷰에서 제시한 6가지 개선사항이 모두 반영되었습니다:

| 항목 | 1차 리뷰 이슈 | 반영 상태 |
|:---:|---------------|:---------:|
| 1 | 데이터 타임프레임 명시 부족 | ✅ 섹션 2 추가 (1분봉 → 1시간봉 리샘플링) |
| 2 | UNKNOWN 레짐 Fallback 정책 부재 | ✅ 섹션 3.2 추가 (진입 보류, 청산은 SIDEWAYS 기준) |
| 3 | 레짐 캐싱 주기 미정의 | ✅ 섹션 3.3 추가 (Redis TTL 65분, 1시간마다 갱신) |
| 4 | BB 터치 lookback 기간 미정의 | ✅ 섹션 4.2에 `bb_touch_lookback: 3` 명시 |
| 5 | 트레일링 스탑 상태 저장 방안 미정의 | ✅ 섹션 6.2 추가 (Redis + DB 이중 저장) |
| 6 | 레짐 변경 시 SL 처리 정책 미정의 | ✅ 섹션 6.4 추가 (타이트한 SL 유지 정책) |

### 2. 파일 경로 검증 결과 ✅

**기존 파일 (모두 존재 확인):**
- `src/collector/main.py` ✅
- `src/common/indicators.py` ✅
- `src/config/strategy.py` ✅
- `src/engine/strategy.py` ✅
- `src/bot/main.py` ✅
- `src/agents/prompts.py` ✅

**신규 생성 예정 파일 (디렉토리 존재 확인):**
- `config/strategy_v3.yaml` - config/ 디렉토리 존재 ✅
- `src/engine/regime.py` - src/engine/ 디렉토리 존재 ✅
- `src/engine/trailing_stop.py` - src/engine/ 디렉토리 존재 ✅
- `migrations/v3_0_regime_trading.sql` - migrations/ 디렉토리 존재 ✅
- `scripts/backtest_v3.py` - scripts/ 디렉토리 존재 ✅

### 3. 발견된 이슈 ⚠️

#### 3.1 테이블명 불일치 (Critical)

문서 섹션 11.2와 11.3에서 `trades` 테이블이라고 명시했으나, 실제 프로젝트의 거래 테이블명은 `trading_history`입니다.

**현재 문서:**
```sql
ALTER TABLE trades ADD COLUMN regime VARCHAR(10);
ALTER TABLE trades ADD COLUMN high_water_mark DECIMAL(20, 8);
ALTER TABLE trades ADD COLUMN exit_reason VARCHAR(30);
```

**수정 필요:**
```sql
ALTER TABLE trading_history ADD COLUMN regime VARCHAR(10);
ALTER TABLE trading_history ADD COLUMN high_water_mark DECIMAL(20, 8);
ALTER TABLE trading_history ADD COLUMN exit_reason VARCHAR(30);
```

#### 3.2 Position 테이블 확장 고려

현재 `positions` 테이블(`src/common/models.py`)에는 보유 중인 포지션 정보가 저장됩니다. 트레일링 스탑의 `high_water_mark`는 보유 **중**에 추적해야 하므로:

- `positions` 테이블에도 `high_water_mark`, `regime` 컬럼 추가 고려
- 또는 Redis만으로 실시간 추적하고, 청산 **후** `trading_history`에 최종값 기록

**권장**: 문서 섹션 11에 `positions` 테이블 변경사항도 명시

```sql
-- positions 테이블 (보유 중 포지션)
ALTER TABLE positions ADD COLUMN regime VARCHAR(10);
ALTER TABLE positions ADD COLUMN high_water_mark DECIMAL(20, 8);
```

### 4. 기술적 타당성 검토 ✅

| 항목 | 평가 |
|------|:----:|
| MA50/MA200 기반 레짐 감지 | ✅ 업계 표준 방식 |
| 1시간봉 리샘플링 접근법 | ✅ 노이즈 감소에 효과적 |
| Redis + DB 이중 저장 | ✅ 안정성과 성능 균형 |
| 레짐별 파라미터 분리 | ✅ 유연한 튜닝 가능 |
| YAML 설정 파일 구조 | ✅ 운영 편의성 증가 |
| AI Agent 레짐 연동 | ✅ 컨텍스트 기반 판단 강화 |

### 5. 최종 의견

**Overall: APPROVED with Minor Fixes**

문서의 전략 설계는 기술적으로 타당하며, 프로젝트 구조와 잘 맞습니다. 1차 리뷰의 모든 피드백이 적절히 반영되었습니다.

**수정 완료 (2026-02-06):**
1. ✅ **섹션 11.2**: `trades` → `trading_history`로 테이블명 수정
2. ✅ **섹션 11.3 추가**: `positions` 테이블 변경사항 추가
3. ✅ **섹션 11.4**: 마이그레이션 스크립트에 모든 테이블 반영

모든 수정이 완료되어 바로 구현 착수 가능합니다.