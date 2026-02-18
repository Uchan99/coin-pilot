코드 5개를 기준으로 보면, 지금 “조건이 빡세서”가 아니라 **SIDEWAYS는 구조적으로 매수 시그널이 거의 영구적으로 False가 되는 버그/설계 미스가 1개 있고**, 그 위에 **RSI(7) 반등 판정 로직이 1분봉에서 ‘1캔들 V반등’만 잡게 되어 있어 전체적으로 체결이 극도로 희박**해진 상태입니다.

아래는 **코드에 근거한 객관적 진단 + 바로 적용 가능한 수정안(비용 고려 포함)**입니다.

---

## 1) SIDEWAYS에서 “AI 판단조차 0건”인 진짜 원인 (코드상 결정적)

### 문제 A — `bb_touch_recovery`가 계산 자체가 거의 안 됨

`main.py`에서 매 루프마다 가져오는 1분봉 데이터는 기본 `limit=200`이고(약 200분 = 3.3시간), SIDEWAYS일 때 `bb_touch_recovery`를 **1시간봉으로 리샘플링한 뒤 `len(hourly_df) >= 20`일 때만** 계산합니다. 

즉,

* 200분 → 1시간봉으로 바꾸면 대략 3~4개 캔들
* `>= 20` 조건을 절대 만족 못함
* 결과적으로 `indicators["bb_touch_recovery"]`가 세팅되지 않음

### 문제 B — 그런데 전략은 `bb_touch_recovery`가 없으면 무조건 FAIL

`strategy.py`의 진입 로직에서 SIDEWAYS이며 `bb_enabled`가 켜져 있으면, `bb_touch_recovery`가 False(또는 key 없음 → 기본 False)이면 **무조건 진입 실패**입니다. 

결론:

> **현재 구조에서는 SIDEWAYS에서 `bb_enabled=True`인 순간, 매수 시그널이 사실상 불가능**
> → 그래서 “AI 판단 호출이 0건”이 정상 동작처럼 발생합니다.

이건 전략이 빡센 문제가 아니라, **데이터 길이/타임프레임 설계가 맞지 않아 조건이 영구적으로 충족되지 않는 상태**예요.

---

## 2) 모든 레짐에서 매수 빈도를 극단적으로 낮추는 두 번째 원인

### RSI(7) trigger→recover 판정이 “직전 1개 캔들”만 보고 결정

현재 진입 조건은:

```python
(rsi_7_prev < trigger) and (rsi_7 >= recover)
```

즉, **바로 직전 1분봉에서 trigger 아래였다가, 이번 1분봉에서 recover 이상으로 “한 번에 점프”해야만** 진입으로 인정합니다. 

이 로직은 “과매도 진입 → 몇 분간 바닥 다지기 → 서서히 반등” 같은 가장 흔한 반등 패턴을 거의 다 놓칩니다.
1분봉에서 이런 **1캔들 V반등**은 생각보다 희귀합니다.

게다가 `min_rsi_7_bounce_pct`도 `rsi_7 - rsi_7_prev`로 **1캔들 반등 폭만** 보고 추가로 필터링합니다. 
→ 실제로는 “최근 저점 대비 얼마나 회복했는지”가 더 의미 있는데, 지금은 그걸 못 봅니다.

---

## 3) BEAR에서 Rule은 통과하는데도 체결이 안 되는 이유 (AI/컨텍스트/정책)

### (1) AI가 CONFIRM해도 confidence < 60이면 강제 REJECT

`analyst.py`에서 **정책으로 confidence < 60은 자동 REJECT** 처리합니다. 

BEAR 레짐에서는 캔들 패턴이 애매한 경우가 많아서 confidence가 55~59로 자주 나올 가능성이 높고,
그럼 “사실상 CONFIRM을 받아도 거절”이 됩니다.

### (2) AI에게 주는 1시간봉 컨텍스트도 실제로는 24개가 거의 안 나감

BUY 시점에 AI에게 준다는 1시간봉 24개는:

```python
hourly_for_ai = resample_to_hourly(df).tail(24)
```

인데, 이 `df` 자체가 200분짜리라서 1시간봉이 3~4개밖에 없습니다. 

즉 AI 입장에서는:

* “최근 24시간 흐름”이 아니라 “최근 3~4시간”
* 패턴 확신을 주기 어려움
* confidence가 떨어질 확률 ↑
* 결국 강제 REJECT ↑

### (3) 프롬프트 설계도 ‘레짐 가이드’를 제대로 못 쓰고 있음

`prompts.py`에는 레짐 설명/가이드까지 포함한 템플릿이 있는데, 실제 `analyst.py`에서는 그 템플릿(`get_analyst_prompt`)을 안 쓰고 별도 human 메시지를 구성하고 있습니다.
→ AI가 레짐별 기대 행동을 더 잘 따르도록 하려면, 이 불일치를 정리하는 게 좋습니다.

---

# 4) “지금 당장” 우선순위 수정안 (효과 큰 순서)

## 우선순위 1 — SIDEWAYS 진입 불능 버그부터 풀기 (필수)

선택지는 2개인데, **비용/성능 고려하면 B를 추천**합니다.

### A안) 1시간봉 BB 터치 회복을 유지하되, 데이터 fetch를 늘린다

* SIDEWAYS일 때만 `get_recent_candles(..., limit=1500~2000)` 정도로 늘려서 (최소 20시간+)
* hourly_df가 20개 이상 나오게 만듦

장점: 기존 의도(“시간봉 기반 안정 신호”) 유지
단점: **DB 조회/리샘플 비용 증가**, 심볼이 많으면 루프가 무거워짐

### ✅ B안) “30분 내 BB 하단 터치+복귀”를 1분봉/5분봉에서 계산한다 (추천)

원래 설명하신 조건이 “30분” 기반이라면 시간봉 20개 요구 자체가 논리적으로도 안 맞습니다.

`indicators.py`에는 `check_bb_touch_recovery()`가 이미 있으니, 1분봉 기준으로 이렇게 쓰는 게 정합적입니다. 

**구현 방향(권장):**

* `get_all_indicators()`에서 BB 시리즈(`bb_df`)는 이미 계산하니, 그 안에서 1분봉 기준 `bb_touch_recovery`를 만들어 indicators에 넣으세요.
* lookback을 30(30분) 또는 60으로 설정.

예시(개념 코드):

```python
# indicators.py get_all_indicators 내부에서
tmp = pd.DataFrame({"close": df["close"], "bb_lower": bb_df["BBL"]})
bb_touch_recovery_1m = check_bb_touch_recovery(tmp, lookback=30)
...
return {..., "bb_touch_recovery": bb_touch_recovery_1m}
```

그리고 `main.py`의 SIDEWAYS 전용 hourly 계산 블록은 제거/축소 가능.

이렇게 하면 **SIDEWAYS에서 AI 호출 0건 문제가 즉시 해소**될 가능성이 큽니다.

---

## 우선순위 2 — RSI(7) 반등 로직을 “상태 기반” 또는 “lookback 기반”으로 바꾸기

현재 “1캔들 V반등”만 잡는 구조를 바꾸면, 모든 레짐에서 체결 가능성이 올라갑니다. 

### ✅ 가장 간단한 무상태(stateless) 개선

“직전 1캔들” 대신 “최근 N캔들 중 한 번이라도 trigger 아래였고, 지금 recover 이상”으로 바꾸세요.

필요한 건 rsi_short 시리즈의 최근 최소값이므로, `get_all_indicators()`에서 다음을 추가하면 됩니다. 

* `rsi_short_min_N = rsi_short_series.tail(N).min()`

그 뒤 진입 조건을:

* `rsi_short_min_N < trigger` AND `rsi_7 >= recover` AND `(rsi_7 > rsi_7_prev)` 정도로.

그리고 `min_rsi_7_bounce_pct`도 `rsi_7 - rsi_7_prev` 대신:

* `rsi_7 - rsi_short_min_N` (최근 저점 대비 회복폭)으로 바꾸는 게 훨씬 합리적입니다.

### 상태 기반(stateful) 개선(더 강력)

Redis(이미 사용 중)에 per-symbol로:

* oversold_armed 플래그 + 타임스탬프 저장
* trigger 아래 들어가면 armed=True
* recover 이상이면 entry
* armed는 예: 15분 지나면 만료

이 방식이 “과매도→바닥→반등”을 가장 잘 포착합니다.

---

## 우선순위 3 — AI 비용/거절률을 동시에 낮추는 구조 변경

### (1) “24개 1시간봉”을 진짜로 주거나, 아예 요약 피처만 주기

지금은 200분 데이터로 리샘플해서 3~4개밖에 못 줍니다. 

**비용까지 고려하면 추천은 2단계:**

* 평소엔 작은 df(200)로 Rule만 돌림
* “진입 후보 발생” 순간에만 추가 조회(예: 1500~3000)해서 AI 컨텍스트 생성

  * 또는 DB에 1시간봉 테이블/뷰가 있으면 그걸 직접 읽기 (가장 깔끔)

### (2) 강제 REJECT(60 미만) 정책을 레짐별로 다르게

현재는 전 레짐 공통으로 60 미만이 자동 거절입니다. 

추천 정책:

* SIDEWAYS: 50~55까지 허용 (대신 포지션 사이징 축소)
* BEAR: 60~70 유지 (보수적)
* BULL: 55~60

또는 더 좋은 방식:

* `confidence`를 “진입 허용/거절”로 쓰지 말고 **포지션 크기 스케일러**로 쓰기
  예: `actual_invest_amount *= (confidence / 100)`

이러면 **AI 비용은 그대로인데 체결이 늘고, 리스크는 자동으로 줄어듭니다.**

### (3) API 비용 절감: “AI 호출 전 점수 필터(cheap gate)” 추가

가장 돈 아끼는 패턴은 이겁니다:

1. Rule Engine(느슨) 통과
2. 로컬 점수화(0~5점)
3. 점수 4~5일 때만 AI 호출 (또는 BEAR에서만 호출)

이러면 **AI 호출 수를 70~90% 줄이면서도**, 애매한 케이스만 AI가 보게 할 수 있어요.

---

# 5) 추가로 꼭 체크해야 하는 “숨은 0체결” 원인 1개

`main.py`에서 실제 매수 수량은:

```python
regime_ratio = config.REGIMES.get(regime, {}).get("position_size_ratio", 0.0)
actual_invest_amount = invest_amount * regime_ratio
quantity = actual_invest_amount / current_price
if quantity > 0:
    execute_order(...)
```

만약 설정에서 특정 레짐의 `position_size_ratio`가 0이면, **시그널이 떠도 무조건 수량이 0 → 주문 자체가 안 나갑니다.** 

이건 로그가 애매하면 “BUY로 보이는데 체결이 없다” 같은 착시를 만들 수 있으니,

* `quantity == 0`일 때 `bot_reason`에 명시적으로 남기도록 방어 로그 추가 추천합니다.

---

# 6) 내가 제안하는 “가장 현실적인” 적용 순서 (최소 변경으로 효과 최대)

### Step 1 (즉시 체결 가능하게 만들기)

* SIDEWAYS `bb_touch_recovery`를 1분봉(lookback 30) 기반으로 계산해서 indicators에 포함
* RSI(7) 반등 판정을 lookback 기반으로 변경
  → **이 두 개만 해도 SIDEWAYS에서 AI 호출이 생기고, 엔트리 빈도가 살아날 확률이 큼**

### Step 2 (AI 거절률/비용 개선)

* “진입 후보 순간에만” 추가 데이터 로드해서 AI 컨텍스트를 제대로 주기
* confidence 강제 REJECT 정책 레짐별 완화 또는 사이징 스케일로 변경

### Step 3 (레짐별 철학 분리)

* BULL은 Mean Reversion이 아니라 추세추종(풀백 매수/돌파)로 전략 자체 분리
  지금 클래스가 `MeanReversionStrategy` 하나로 전 레짐을 커버하고 있어, 구성상 철학 분리가 약합니다. 

---

## 바로 다음 액션

원하면 내가 **패치 형태로 정확히 어떤 파일 어디를 어떻게 바꿀지**까지 “diff 스타일”로 정리해줄게요.

가장 먼저는:

1. `indicators.py`의 `get_all_indicators()`에 `bb_touch_recovery(1m, lookback=30)` 추가
2. `strategy.py`의 RSI7 반등 조건을 lookback 기반으로 변경
3. `main.py`의 SIDEWAYS hourly bb_touch_recovery 블록 제거(또는 옵션화)

이 3개가 “SIDEWAYS 0건”을 깨는 핵심입니다.
