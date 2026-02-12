# 12. 전략 파라미터 튜닝 구현 결과

**작성일**: 2026-02-12
**작성자**: Antigravity (AI Architect)
**관련**: `docs/work-plans/12_strategy_parameter_tuning.md`

---

## 1. 개요

`docs/work-plans/12_strategy_parameter_tuning.md` 계획에 따라 전략 파라미터 튜닝 및 관련 코드 수정을 완료했습니다.
주요 목표였던 "지나치게 엄격한 진입 조건 완화"를 달성하여, 백테스트상 BEAR 레짐에서도 유의미한 거래가 발생함을 확인했습니다.

---

## 2. 구현 사항

### 2.1 전략 파라미터 변경 (Phase 1)

**파일**: `config/strategy_v3.yaml`, `src/config/strategy.py`

| 레짐 | 항목 | 변경 전 | 변경 후 | 비고 |
|------|------|---------|---------|------|
| **BULL** | `rsi_14_max` | 45 | **50** | 상승장 진입 기회 확대 |
| | `rsi_7_trigger` | 40 | **45** | 과매도 진입 기준 완화 |
| | `rsi_7_recover` | 40 | **45** | |
| | `min_rsi_7_bounce_pct` | 3.0 | **2.0** | 반등 폭 조건 완화 |
| **SIDEWAYS** | `rsi_14_max` | 40 | **45** | 중립 구간 진입 허용 |
| | `rsi_7_trigger` | 35 | **40** | |
| | `rsi_7_recover` | 35 | **40** | |
| | `volume_min_ratio` | 0.5 | **0.2** | 저거래량 허용 |
| **BEAR** | `rsi_14_max` | 40 | **45** | 하락장 진입 기회 확대 |
| | `rsi_7_trigger` | 30 | **35** | |
| | `rsi_7_recover` | 30 | **35** | |
| | `volume_min_ratio` | 0.5 | **0.1** | 최소 거래량 체크로 변경 |

### 2.2 레짐 감지 로직 개선 (버그 수정)

**파일**: `src/common/indicators.py`, `src/bot/main.py`

*   **기존 버그**: `detect_regime()` 함수 내부에 threshold가 `2.0`으로 하드코딩되어 있어, YAML의 `bull_threshold_pct`/`bear_threshold_pct` 설정값이 실제 레짐 판단에 반영되지 않았음
*   **수정**: `detect_regime()` 함수에 `bull_threshold`, `bear_threshold` 파라미터 추가 (기본값 2.0으로 하위 호환성 유지)
*   **호출부 수정**: `bot/main.py`와 `backtest_v3.py`에서 config 값을 동적으로 전달
*   이 수정은 Phase 2(레짐 감지 MA 기간 조정) 진행의 **전제 조건**이기도 함

### 2.3 백테스트 코드 동기화

**파일**: `scripts/backtest_v3.py`

*   운영 코드(`src/engine/strategy.py`)와 동일하게 진입 조건을 동기화했습니다.
    *   `min_rsi_7_bounce_pct` 로직 추가
    *   `require_price_above_bb_lower` (Falling Knife 방지) 추가
    *   `volume_min_ratio` 및 `volume_surge_check` 추가
    *   `regime_detection` 동적 임계값 적용

### 2.4 배포 설정 개선

**파일**: `deploy/docker/bot.Dockerfile`

*   Docker 이미지 빌드 시 `config/` 디렉토리가 COPY 대상에 포함되지 않아, K8s 배포 시 `strategy_v3.yaml`이 이미지 내에 존재하지 않고 Python 기본값(`src/config/strategy.py`)만 사용되던 문제를 수정
*   `COPY config/ ./config/` 추가하여 YAML 설정이 이미지에 포함되도록 조치
*   **환경변수 추가**: `k8s/apps/bot-deployment.yaml`에 `OPENAI_API_KEY` (DailyReporter용), `N8N_URL`, `N8N_WEBHOOK_SECRET` 추가하여 배포 시 누락 방지

---

## 3. 검증 결과 (백테스트)

수정된 파라미터와 로직으로 백테스트를 수행한 결과, 기존에 전무했던 진입 신호가 발생하기 시작했습니다.

**테스트 기간**: 최근 약 13~24일 데이터 (1시간봉)
**결과 요약**:
*   **총 거래**: 13건 (모두 BEAR 레짐)
*   **승률**: 30.8% (4승 9패)
*   **의의**: 수익성은 아직 낮으나(하락장 특성), **"거래가 전혀 안 되는 문제"는 해결**됨. AI Agent가 활동할 수 있는 후보군이 생성되기 시작함.

**주요 거래 예시**:
```
[KRW-BTC][BEAR] 02/02 06:00 → 02/02 15:00 (+3.08%) [TAKE_PROFIT]
[KRW-SOL][BEAR] 02/09 14:00 → 02/09 17:00 (+3.02%) [TAKE_PROFIT]
```

---

## 4. 배포 가이드

### 4.1 배포 명령

`./deploy/deploy_to_minikube.sh` 스크립트를 실행하면 자동으로 다음 과정이 수행됩니다:

1.  **Docker 이미지 재빌드**: 수정된 코드와 `config/` 디렉토리가 이미지에 포함됩니다.
2.  **ConfigMap 적용**: K8s 설정을 갱신합니다.
3.  **Pod 재배포**: 새로운 이미지로 봇이 재시작됩니다.

```bash
./deploy/deploy_to_minikube.sh
```

### 4.2 확인 사항

배포 후 다음 명령어로 파라미터가 잘 적용되었는지 로그를 확인할 수 있습니다.

```bash
# 진입 조건 체크 로그 확인
kubectl logs -f deployment/bot -n coin-pilot-ns | grep "RSI"
```

---

## 5. 후속 계획

### Phase 2: 레짐 감지 MA 기간 조정

Phase 1 배포 후 1~2일 모니터링 결과를 확인한 뒤, **Option B (MA 30/100, Threshold ±2% 유지)**를 기본 방향으로 백테스트 비교 후 진행 예정. `detect_regime()` threshold 파라미터 수정이 완료되었으므로 Phase 2 실행 준비 완료.

### 2차 파라미터 조정

RSI14 통과율이 여전히 낮을 경우 BULL=55, SIDEWAYS=50으로 추가 완화 검토.
RSI7 trigger/recover 분리(trigger > recover) 방식도 모니터링 데이터에 따라 재검토.

---

## Claude Code Review

**검토일**: 2026-02-12
**검토자**: Claude Code (Opus 4.6)
**대상**: 보고서 내용 vs 계획서(`docs/work-plans/12_strategy_parameter_tuning.md`) vs 실제 코드

---

### 1. 계획서 대비 구현 완료 항목

| 계획 항목 | 구현 상태 | 검증 위치 |
|-----------|:---------:|-----------|
| RSI14 완화 (BULL 50, SIDEWAYS 45, BEAR 45) | ✅ | `strategy_v3.yaml:21,41,67`, `strategy.py:53,68,85` |
| RSI7 trigger/recover 완화 (BULL 45, SW 40, BEAR 35) | ✅ | `strategy_v3.yaml:22-23,42-43,68-69`, `strategy.py:53,68,85` |
| min_rsi_7_bounce_pct 통일 (2.0) | ✅ | `strategy_v3.yaml:24,44,70`, `strategy.py:54,69,86` |
| volume_min_ratio 완화 (SW 0.2, BEAR 0.1) | ✅ | `strategy_v3.yaml:54,76`, `strategy.py:74,90` |
| `detect_regime()` threshold 파라미터 추가 | ✅ | `indicators.py:163-164` |
| `bot/main.py` 호출부 config 전달 | ✅ | `main.py:416-420` |
| `backtest_v3.py` v3.1 조건 동기화 | ✅ | `backtest_v3.py:108-160` |
| `backtest_v3.py` detect_regime 호출부 수정 | ✅ | `backtest_v3.py:76-84` |
| Dockerfile config/ COPY 추가 | ✅ | `deploy/docker/bot.Dockerfile:21` |
| YAML과 Python 기본값 동기화 | ✅ | 양쪽 값 일치 확인 |

**계획서 대비 미구현 항목: 없음** ✅

---

### 2. 코드 품질 검증

#### 2.1 `detect_regime()` 수정 ✅ 정확

- 기본값 `bull_threshold=2.0, bear_threshold=-2.0`으로 설정하여 **하위 호환성 유지**
- `bot/main.py`에서 `config.BULL_THRESHOLD_PCT`, `config.BEAR_THRESHOLD_PCT` 전달 확인
- `backtest_v3.py`에서도 동일하게 config 값 전달 확인

#### 2.2 백테스트 v3.1 동기화 ✅ 정확

추가된 조건들이 운영 코드(`src/engine/strategy.py:77-194`)와 일치하는지 확인:

| 조건 | 운영 코드 | 백테스트 | 일치 |
|------|-----------|----------|:----:|
| RSI14 | `strategy.py:110` | `backtest_v3.py:99` | ✅ |
| RSI7 trigger/recover | `strategy.py:118` | `backtest_v3.py:105` | ✅ |
| min_rsi_7_bounce_pct | `strategy.py:125-131` | `backtest_v3.py:108-113` | ✅ |
| MA crossover | `strategy.py:137-141` | `backtest_v3.py:116-118` | ✅ |
| MA proximity | `strategy.py:142-147` | `backtest_v3.py:119-122` | ✅ |
| MA proximity_or_above | `strategy.py:148-153` | `backtest_v3.py:123-126` | ✅ |
| BB 하단 체크 | `strategy.py:156-160` | `backtest_v3.py:129-131` | ✅ |
| volume_ratio 상한 | `strategy.py:163-167` | `backtest_v3.py:134-136` | ✅ |
| volume_min_ratio 하한 | `strategy.py:170-174` | `backtest_v3.py:139-141` | ✅ |
| volume_surge_check | `strategy.py:177-183` | `backtest_v3.py:144-149` | ✅ |
| BB 터치 회복 (SIDEWAYS) | `strategy.py:186-190` | `backtest_v3.py:152-158` | ✅ |

#### 2.3 `vol_ratios` 컬럼 생성 ✅

`backtest_v3.py:71`에서 `calculate_volume_ratios()`를 호출하여 `vol_ratios` 컬럼 생성.
`check_entry_signal()`의 volume_surge_check(line 147)에서 `df.iloc[...]['vol_ratios']`로 참조. 정상 연결.

#### 2.4 변경하지 않아야 할 파일 ✅

| 파일 | 변경 여부 | 판정 |
|------|:---------:|:----:|
| `src/engine/strategy.py` | 미변경 | ✅ 정상 (설정값만 변경) |
| `src/agents/*.py` | 미변경 | ✅ 정상 |
| `src/common/models.py` | 미변경 | ✅ 정상 |

---

### 3. 보고서 내용 검증

#### 3.1 보고서에서 누락된 사항 ⚠️

1. **`detect_regime()` 수정의 의미 설명 부족**: 보고서 2.2절에서 "하드코딩 2.0 제거"만 언급했으나, 이것이 **기존 버그 수정**이라는 맥락(YAML 설정이 무시되던 문제)이 명시되지 않음. Phase 2 진행의 전제조건이라는 점도 누락.

2. **Dockerfile 수정 사항의 배경 설명 부족**: 2.4절에서 `config/` 디렉토리 누락 문제를 언급했으나, 이 문제로 인해 **K8s 배포 시 YAML 설정이 반영되지 않아 Python 기본값만 사용되던 상태**였는지, 아니면 다른 방식(ConfigMap 등)으로 마운트하고 있었는지 명확하지 않음. 이전 배포에서 YAML이 적용되고 있었다면 이 수정은 불필요한 중복일 수 있으므로 확인 필요.

3. **Phase 2 관련 언급 없음**: 계획서에 명시된 Phase 2(레짐 감지 MA 30/100, Option B) 방향성에 대한 후속 계획이 보고서에 없음. "Phase 1 완료, Phase 2는 모니터링 후 진행 예정" 정도의 한 줄은 있는 것이 좋음.

#### 3.2 백테스트 결과 기술 ✅ 적절

- 13건 거래, 30.8% 승률, BEAR 레짐 집중 → 현재 시장 상황(하락장)과 일치
- TAKE_PROFIT 달성 사례 존재 (+3.08%, +3.02%) → BEAR TP 3% 설정과 일치
- "수익성은 아직 낮으나 거래가 전혀 안 되는 문제는 해결" → 정직한 평가

#### 3.3 보고서에 포함되었으나 계획서에 없었던 추가 사항

- **2.4 Dockerfile 수정**: 계획서 수정 파일 목록에 없었으나 배포 과정에서 발견된 실용적 문제 해결. 추가 구현으로 적절.

---

### 4. 잠재적 이슈

#### 4.1 `vol_ratios` 데이터 타입 주의 ⚠️

`backtest_v3.py:147`에서 `df.iloc[max(0, idx-2):idx+1]['vol_ratios'].tolist()`를 호출하는데, `vol_ratios`는 `calculate_volume_ratios()`가 반환한 단일 float 값의 Series입니다. 운영 코드(`strategy.py:179`)에서는 `indicators.get("recent_vol_ratios", [])` 리스트의 마지막 3개를 사용합니다. 백테스트에서는 DataFrame 슬라이싱으로 동일한 효과를 얻으므로 **로직은 동일하나 접근 방식이 다름**. 결과에는 영향 없으나 참고.

#### 4.2 `get_regime()` 호출 시그니처 변경

`backtest_v3.py:76`에서 `get_regime(row, config)`로 변경했으므로, `simulate_trades()`의 호출부(`line 214`)도 `get_regime(row, config)`로 변경되었는지 확인 완료 (✅ `backtest_v3.py:214`).

---

### 5. 최종 판정

**Overall: APPROVED ✅**

계획서의 모든 구현 항목이 정확하게 반영되었으며, 추가로 Dockerfile 배포 문제까지 해결. 코드 품질에 문제 없음.

**배포 후 체크리스트:**
- [ ] `DEBUG_ENTRY=1` 활성화하여 조건별 통과/실패율 수집
- [ ] RSI14 통과율 0% → 20% 이상 증가 확인
- [ ] AI Agent 호출 발생 여부 확인
- [ ] 1~2일 모니터링 후 Phase 2(레짐 MA 조정) 검토
