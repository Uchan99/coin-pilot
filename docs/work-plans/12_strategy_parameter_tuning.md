# 12. 전략 파라미터 튜닝 계획 (확정)

**작성일**: 2026-02-08
**최종 수정**: 2026-02-12 (Claude Code Review 반영, 확정)
**작성자**: Antigravity (AI Architect) + Claude Code (Operator & Reviewer)
**상태**: ✅ 확정 (Implementation Ready)

---

## 1. 배경

v3.1 Rule Engine 배포 후 2~3일간 운영 결과, **단 한 건의 매수 주문도 발생하지 않음**.
진입 조건이 지나치게 엄격하여 모든 코인에서 첫 번째 관문(RSI14)부터 100% 거절됨.

### 실제 운영 로그 (2026-02-10~12)

```
[KRW-BTC] ❌ RSI14 조건 실패: 56.7 > 40
[KRW-ETH] ❌ RSI14 조건 실패: 55.6 > 40
[KRW-XRP] ❌ RSI14 조건 실패: 49.5 > 40
[KRW-SOL] ❌ RSI14 조건 실패: 54.6 > 40
[KRW-DOGE] ❌ RSI14 조건 실패: 69.2 > 40
[KRW-BTC] ❌ RSI14 조건 실패: 67.7 > 40
[KRW-ETH] ❌ RSI14 조건 실패: 70.6 > 40
[KRW-XRP] ❌ RSI14 조건 실패: 70.7 > 40
[KRW-SOL] ❌ RSI14 조건 실패: 68.4 > 40
[KRW-DOGE] ❌ RSI14 조건 실패: 69.2 > 40
```

- **RSI14**: 관측 범위 49~71 vs 현재 임계값 40 → 모든 코인에서 100% 거절
- **거래량**: 이전 로그 기준 실측 0.06~0.12 vs 최소 요구 0.5 → 약 5~8배 차이
- **RSI7 반등**: trigger<30 조건 미충족 빈번

---

## 2. 문제 분석

### 2.1 RSI14 임계값 과도 (핵심 병목)

현재 BEAR/SIDEWAYS `rsi_14_max: 40`은 "RSI 40 이하의 강한 과매도"만 허용하는데,
실제 시장에서 RSI14가 40 이하로 떨어지는 경우는 급락장에서만 발생.
평상시 RSI14 범위가 45~70이므로 거의 모든 진입 기회가 차단됨.

### 2.2 RSI7 trigger/recover 조건 과도

BEAR `rsi_7_trigger: 30`은 "RSI7이 30 이하로 진입 후 30 이상으로 반등"을 요구.
RSI14보다 빠른 RSI7이라도 30 이하 진입은 급락 시에만 발생하여 기회가 극히 제한적.

### 2.3 RSI7 최소 반등폭 과도

`min_rsi_7_bounce_pct: 3.0`은 1시간봉 한 캔들에서 RSI7이 3포인트 반등을 요구.
실제로는 2~3캔들에 걸쳐 서서히 반등하는 경우가 더 많아 진입 기회를 놓침.

### 2.4 거래량 하한 과도

`volume_min_ratio: 0.5`는 평균 거래량의 50% 이상을 요구하지만,
거래량 평균 계산(20캔들)에 급등 캔들 포함 시 평균이 과대 추정되어
야간/주말 저거래량 시간대에 실측값이 0.06~0.12까지 떨어짐.

### 2.5 `detect_regime()` threshold 하드코딩 버그

`src/common/indicators.py:detect_regime()` 함수 내부에 `2.0`이 하드코딩되어 있어,
YAML의 `bull_threshold_pct`/`bear_threshold_pct` 설정값이 **실제 레짐 판단에 반영되지 않음**.
Phase 2 레짐 조정의 전제 조건이므로 Phase 1에서 함께 수정.

---

## 3. 개선 계획

### 설계 철학 변경

```
기존: Rule Engine (엄격) → AI Agent (엄격)
변경: Rule Engine (느슨) → AI Agent (엄격)
```
- Rule Engine: 명백한 노이즈만 제거 (문을 넓게)
- AI Agent: 실질적 판단 (깐깐하게)

### Phase 1: 진입 조건 완화 + 버그 수정 (즉시 실행)

#### 3.1 파라미터 변경 사항

| 레짐 | 항목 | 현재 | 변경 | 비고 |
|------|------|------|------|------|
| **BULL** | `rsi_14_max` | 45 | **50** | 상승장 진입 여유 확보 (단계적 완화) |
| | `rsi_7_trigger` | 40 | **45** | RSI7 과매도 진입 조건 완화 |
| | `rsi_7_recover` | 40 | **45** | trigger와 동일 |
| | `min_rsi_7_bounce_pct` | 3.0 | **2.0** | 서서히 반등하는 패턴도 포착 |
| | `volume_ratio` (상한) | 1.2 | **유지** | 거래량 동반 필요 |
| | `volume_min_ratio` | null | **유지** | 상승장에서는 미적용 |
| **SIDEWAYS** | `rsi_14_max` | 40 | **45** | 중립 구간 확대 |
| | `rsi_7_trigger` | 35 | **40** | RSI7 과매도 진입 조건 완화 |
| | `rsi_7_recover` | 35 | **40** | trigger와 동일 |
| | `min_rsi_7_bounce_pct` | 3.0 | **2.0** | 서서히 반등하는 패턴도 포착 |
| | `volume_min_ratio` | 0.5 | **0.2** | 저거래량 허용 |
| **BEAR** | `rsi_14_max` | 40 | **45** | 로그 기준 최소 49.5 관측, 45까지 확대 |
| | `rsi_7_trigger` | 30 | **35** | RSI7 과매도 진입 조건 완화 |
| | `rsi_7_recover` | 30 | **35** | trigger와 동일 |
| | `min_rsi_7_bounce_pct` | 3.0 | **2.0** | 서서히 반등하는 패턴도 포착 |
| | `volume_min_ratio` | 0.5 | **0.1** | 최소 거래량만 확인 |

> **참고**: RSI14 완화는 단계적 접근. BULL=50, SIDEWAYS=45, BEAR=45로 시작 후 1~2일 모니터링.
> 부족하면 BULL=55, SIDEWAYS=50으로 2차 완화 검토.

#### 3.2 `detect_regime()` threshold 버그 수정

**현재 코드** (`src/common/indicators.py:180-185`):
```python
def detect_regime(ma50, ma200) -> str:
    diff_pct = (ma50 - ma200) / ma200 * 100
    if diff_pct > 2.0:        # ← 하드코딩
        return "BULL"
    elif diff_pct < -2.0:     # ← 하드코딩
        return "BEAR"
```

**수정**: threshold 파라미터 추가하여 YAML 설정값 연동
```python
def detect_regime(ma50, ma200, bull_threshold=2.0, bear_threshold=-2.0) -> str:
    diff_pct = (ma50 - ma200) / ma200 * 100
    if diff_pct > bull_threshold:
        return "BULL"
    elif diff_pct < bear_threshold:
        return "BEAR"
```

**호출부 수정**: `src/bot/main.py`, `scripts/backtest_v3.py`에서 config 값 전달

#### 3.3 백테스트 코드 v3.1 조건 동기화

`scripts/backtest_v3.py`의 `check_entry_signal()` 함수에 운영 코드와 동일한 v3.1 조건 추가:
- `min_rsi_7_bounce_pct` 체크
- `require_price_above_bb_lower` 체크
- `volume_min_ratio` 하한 체크
- `volume_surge_check` 체크
- `proximity_or_above` MA 조건

현재 백테스트가 운영 코드(`src/engine/strategy.py`)의 진입 조건과 **불일치** 상태이므로,
정확한 파라미터 효과 검증을 위해 동기화 필수.

### Phase 2: 레짐 감지 기간 조정 (Phase 1 결과 확인 후)

Phase 1 배포 → 1~2일 모니터링 → 백테스트 비교 후 결정.
**Option B (권장)** 진행 가능성 높게 유지.

| 설정 | 현재 | Option B |
|------|------|----------|
| MA Fast | 50 | 30 |
| MA Slow | 200 | 100 |
| Threshold | ±2% | ±2% (유지) |

Phase 2 실행 전 3.2에서 수정한 `detect_regime()` threshold 파라미터를 통해
YAML 설정값이 정상 반영되는 것을 확인해야 함.

---

## 4. 리스크 분석

### RSI 조건 완화 시

| 리스크 | 설명 | 대응 |
|--------|------|------|
| 과매수 진입 | RSI 높은 구간 진입 시 고점 물림 | AI Agent가 캔들 패턴/추세 분석으로 필터링 |
| 신호 과다 | Rule Engine 통과 건수 증가 | AI Agent 호출 비용 모니터링 (상한 1일 20회) |

### 거래량 조건 완화 시

| 리스크 | 설명 | 대응 |
|--------|------|------|
| 저유동성 진입 | 거래량 적은 시점 진입 시 슬리피지 증가 | 포지션 사이즈 축소로 완화 |
| 허위 신호 증가 | 거래량 없는 가격 움직임에 반응 | AI Agent가 2차 필터링 |

### RSI7 trigger/bounce 완화 시

| 리스크 | 설명 | 대응 |
|--------|------|------|
| 약한 반등 포착 | 확실한 V자가 아닌 약한 반등에 진입 | AI Agent confidence 80 미만 강제 REJECT 정책 유지 |
| 진입 빈도 증가 | RSI7 조건 통과 건수 증가 | 후속 조건(MA, BB, 거래량)이 추가 필터링 |

### v3.1 기존 안전장치 (변경 없음)

다음 조건들은 그대로 유지되어 추가적인 리스크 방어:
- `require_price_above_bb_lower`: BB 하단 아래 진입 금지 (Falling Knife 방지)
- `volume_surge_check` (BEAR 전용): 거래량 급증 시 패닉셀링으로 간주, 진입 보류
- AI Agent confidence < 80 → 강제 REJECT
- Risk Manager: 일일 최대 손실 -5%, 일일 최대 거래 10회, 쿨다운 규칙

---

## 5. 구현 범위 및 수정 파일

### Phase 1 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `config/strategy_v3.yaml` | RSI14, RSI7 trigger/recover, bounce_pct, volume_min_ratio 파라미터 수정 |
| `src/config/strategy.py` | Python 기본값 동기화 (YAML fallback용) |
| `src/common/indicators.py` | `detect_regime()` threshold 파라미터 추가 (버그 수정) |
| `src/bot/main.py` | `detect_regime()` 호출부에 config threshold 전달 |
| `scripts/backtest_v3.py` | v3.1 조건 동기화 + `detect_regime()` 호출부 수정 |

### 변경하지 않는 파일

| 파일 | 사유 |
|------|------|
| `src/engine/strategy.py` | 진입/청산 로직 자체는 변경 불필요 (설정값만 변경) |
| `src/agents/*.py` | AI Agent 코드 변경 없음 |
| `src/common/models.py` | DB 스키마 변경 없음 |

---

## 6. 구현 순서

### Step 1: 코드 수정 및 백테스트
1. `config/strategy_v3.yaml` 파라미터 수정
2. `src/config/strategy.py` 기본값 동기화
3. `src/common/indicators.py` → `detect_regime()` threshold 파라미터 추가
4. `src/bot/main.py` → 호출부 수정
5. `scripts/backtest_v3.py` → v3.1 조건 동기화 + 호출부 수정
6. 백테스트 실행하여 파라미터 변경 효과 확인

### Step 2: 배포
1. Docker 이미지 빌드 및 K8s 배포
2. `DEBUG_ENTRY=1` 환경변수 활성화 (`kubectl set env deployment/bot -n coin-pilot-ns DEBUG_ENTRY=1`)

### Step 3: 효과 검증 (1~2일)
1. 로그 분석: 조건별 통과/실패율 확인 (DEBUG_ENTRY 출력)
2. AI Agent 호출 빈도 확인
3. 실제 CONFIRM/REJECT 비율 분석
4. 필요 시 RSI14를 BULL=55, SIDEWAYS=50으로 2차 완화

### Step 4: Phase 2 검토 (선택)
1. Phase 1 결과 안정화 확인
2. 백테스트로 Option B (MA 30/100) 비교
3. 결정 및 배포

---

## 7. 테스트 계획

### 백테스트 (배포 전)

```bash
PYTHONPATH=. python scripts/backtest_v3.py
```

현재 설정(변경 전)과 새 설정(변경 후)의 거래 건수, 승률, 수익률을 비교.

### 운영 모니터링 (배포 후)

```bash
# 디버그 로그 활성화 (이미 설정됨)
kubectl set env deployment/bot -n coin-pilot-ns DEBUG_ENTRY=1

# 조건별 실패 통계 (실시간)
kubectl logs -f deployment/bot -n coin-pilot-ns | grep "❌\|✅"

# 조건별 실패 집계
kubectl logs deployment/bot -n coin-pilot-ns | grep "❌" | cut -d']' -f2 | sort | uniq -c | sort -rn
```

### 성공 기준

- [ ] RSI14 조건 통과율 0% → 20% 이상으로 증가
- [ ] Rule Engine 전체 통과 → AI Agent 호출 1일 3~20회
- [ ] AI Agent의 CONFIRM/REJECT 판단 발생 (최소 1건)
- [ ] AI Agent 호출 비용 1일 $1 이내

---

## 8. 롤백 계획

문제 발생 시 (과도한 거래, 연속 손실 등):

### 즉시 롤백

```bash
# 1. 봇 중단
kubectl scale deployment/bot -n coin-pilot-ns --replicas=0

# 2. YAML 원복 후 재배포
# config/strategy_v3.yaml 롤백 값:
```

```yaml
# 롤백 값 (모든 레짐)
BEAR:
  entry:
    rsi_14_max: 40
    rsi_7_trigger: 30
    rsi_7_recover: 30
    min_rsi_7_bounce_pct: 3.0
    volume_min_ratio: 0.5
SIDEWAYS:
  entry:
    rsi_14_max: 40
    rsi_7_trigger: 35
    rsi_7_recover: 35
    min_rsi_7_bounce_pct: 3.0
    volume_min_ratio: 0.5
BULL:
  entry:
    rsi_14_max: 45
    rsi_7_trigger: 40
    rsi_7_recover: 40
    min_rsi_7_bounce_pct: 3.0
```

> `detect_regime()` threshold 수정은 기존 동작과 동일하므로 (기본값 2.0) 롤백 불필요.

---

## Claude Code Review

**검토일**: 2026-02-12
**검토자**: Claude Code (Opus 4.6)
**상태**: ✅ APPROVED - 구현 진행

### Review Summary

1. **Phase 1 파라미터 변경**: 운영 로그 기반의 실증적 완화. RSI14는 단계적 접근(50/45/45 → 필요 시 55/50/45).
2. **RSI7 trigger/recover 완화**: RSI14만 완화해도 RSI7에서 재차 걸리는 AND 조건 특성 반영. BEAR 30→35, SIDEWAYS 35→40, BULL 40→45.
3. **min_rsi_7_bounce_pct 통일**: 모든 레짐 2.0으로 통일. 3.0은 1시간봉에서 과도하며, 레짐별 차별화(2.0 vs 2.5)의 실질적 필터링 효과가 미미.
4. **detect_regime() 버그 수정**: YAML threshold가 무시되는 하드코딩 버그. Phase 2 전제조건이므로 Phase 1에서 선행 수정.
5. **백테스트 코드 동기화**: 운영 코드와 백테스트 코드의 진입 조건 불일치 해소. 정확한 파라미터 효과 검증의 전제.
6. **v3.1 안전장치 유지**: BB 하단 방어, 거래량 급증 체크, AI confidence 80 미만 강제 REJECT 등 기존 방어막 그대로 유지.
