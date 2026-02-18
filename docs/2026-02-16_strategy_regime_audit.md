# CoinPilot 전략/레짐 종합 점검 리포트 (2026-02-16)

## 1. 검토 범위
- `docs/PROJECT_CHARTER.md`
- `docs/work-result/*.md` 전체 스캔
- `docs/TroubleCheck.md`
- 마지막 커밋: `65c0cbe` (`fix(strategy): relax BULL/SIDEWAYS entry params and fix dashboard false positives`)
- 핵심 코드:
  - `src/bot/main.py`
  - `src/engine/strategy.py`
  - `src/common/indicators.py`
  - `src/config/strategy.py`
  - `config/strategy_v3.yaml`
  - `src/agents/{analyst.py,runner.py,prompts.py,factory.py}`
  - `src/engine/executor.py`

## 2. 프로젝트 전체 요약 (문서 기반)
- 프로젝트 철학: 예측이 아닌 반응(`Rule Engine 중심 + AI 보조`) 구조.
- 진행 이력:
  - Week 1~2: DB/Collector/Rule Engine/Risk Manager 기반 구축.
  - Week 3/7: AI Agent + Chatbot 연동.
  - Week 4~6: K8s 배포/운영 대시보드/알림 체계.
  - Week 8+: 레짐 기반 적응형 전략(v3.x), 모니터링/자동화 고도화.
- 현재 전략 성격: 레짐별 파라미터를 가진 Mean Reversion 변형이며, Rule Engine 통과 후 AI가 2차 승인.

## 3. 마지막 커밋 반영 상태 점검
커밋 메시지의 주요 항목은 코드에 반영되어 있음.
- BULL/SIDEWAYS/BEAR 파라미터 변경: `config/strategy_v3.yaml`, `src/config/strategy.py`
- `build_status_reason` 조건 확장(3개 → 9개): `src/bot/main.py`
- AI confidence 가이드 80→60: `src/agents/prompts.py`, `src/agents/analyst.py`
- 타임아웃 20s→40s: `src/agents/runner.py`
- `LLM_MODE` dev→prod: `k8s/apps/bot-deployment.yaml`

주의:
- `src/agents/runner.py` 타임아웃 예외 로그 문구는 아직 `20s`로 남아 있음(실제 timeout 값은 40.0).

## 4. 실측 로그 검증 (kubectl)
실행 명령:
- `kubectl logs deployment/bot -n coin-pilot-ns | grep "❌\\|✅" | tail -n 200`
- 추가 집계:
  - `entry=0`
  - `ai_reject=0`
  - `ai_approve=0`
  - `bb_recovery_fail=7`
  - `rsi14_fail=882`
  - `rsi7_fail=392`

해석:
- 최근 로그 구간에서 Rule Engine 진입 성공 자체가 0건.
- AI 승인/거절 이전에 Rule 단계에서 대부분 차단됨.
- 차단 주 원인: `RSI14`, `RSI7 trigger→recover`, `BB 터치 회복`.

### 4.1 BEAR AI REJECT 이력 검증 (DB)
Redis는 `bot:status:*`(TTL 300초) 중심이라 과거 REJECT 이력을 보관하지 않음.  
과거 BEAR REJECT 분석은 `agent_decisions` 테이블 기준으로 수행.

- `BEAR + REJECT`: **67건**
- 유형별 분류:
  - `FALLING_KNIFE`: **41건**
  - `VOLUME`(거래량 급감/이상): **22건**
  - `TIMEOUT`: **4건**
- confidence 분포:
  - 평균 `48.3`, 최소 `15`, 최대 `85`
  - `NULL confidence` 4건(Timeout fallback)

해석:
- BEAR에서 AI는 주로 “하락 지속/칼날 낙하”와 “거래량 신뢰도 부족”을 핵심 위험으로 거절.
- 일부는 confidence가 60 이상이어도(예: 75, 85) REJECT 자체를 반환했으므로, 단순 `confidence cutoff` 조정만으로 해결되지 않음.
- 즉, BEAR 병목은 **Rule 통과 후보의 품질**과 **AI 입력 컨텍스트 품질** 문제를 함께 다뤄야 개선 가능.

## 5. 코드 기반 핵심 문제 진단

### 5.1 SIDEWAYS `bb_touch_recovery` 계산 경로가 구조적으로 매우 불리함
- `main.py`는 기본 `get_recent_candles(..., limit=200)` 사용.
- SIDEWAYS에서만 1분봉을 1시간봉으로 리샘플 후 `len(hourly_df) >= 20`일 때만 `bb_touch_recovery` 계산.
- 200분 데이터는 1시간봉 3~4개 수준이라 조건을 거의 만족 못함.
- 동시에 `strategy.py`는 SIDEWAYS에서 `bb_touch_recovery=False/없음`이면 즉시 FAIL.
- 따라서 `bb_touch_lookback` 파라미터(예: 3→30)만 바꿔도 현재 경로에서는 실효성이 거의 없음.
  - 호출부가 설정값을 일관 전달하지 않고, 계산 자체가 생략되는 구간이 많아 파라미터 튜닝 효과가 무력화됨.
- 결과적으로 SIDEWAYS에서 진입 경로가 과도하게 막힘.

### 5.2 RSI(7) 반등 판정이 1캔들 점프 조건
- 현재 판정: `(rsi_short_prev < trigger) and (rsi_short >= recover)`.
- 즉 “직전 1분봉이 trigger 아래, 현재 1분봉이 recover 이상”이어야만 통과.
- 완만한 반등(여러 캔들 회복)은 대량 누락.
- `min_rsi_7_bounce_pct`도 `rsi_short - rsi_short_prev` 1캔들 기준이라 동일한 문제를 강화.

### 5.3 AI 컨텍스트 품질 저하
- 주석/의도는 “1시간봉 최대 24개 컨텍스트 제공”이나, 소스는 `df(limit=200)`에서 리샘플한 결과 사용.
- 실제로는 3~4개 1시간봉만 전달되는 경우가 대부분.
- BEAR 구간에서 AI가 보수적으로 REJECT하는 현상을 더 강화할 가능성 큼.
- 실제 REJECT reason 다수가 “최근 캔들에서 하락 지속/반등 약함”을 지적하고 있어, 컨텍스트 길이 부족이 판단 편향을 키웠을 가능성이 높음.

### 5.4 프롬프트 불일치/사문화
- `src/agents/prompts.py`의 `get_analyst_prompt()`(레짐 설명/가이드 포함)가 실제 `analyst.py`에서 사용되지 않음.
- 시스템 프롬프트는 적용되지만, 레짐 가이드 강화 설계가 실제 입력에 충분히 반영되지 않음.

## 6. 중복/비효율/리스크 코드

### 6.1 조건 로직 중복 (유지보수 리스크 높음)
- `strategy.check_entry_signal()`와 `build_status_reason()`가 진입 조건을 별도로 거의 중복 구현.
- 조건 변경 시 둘 중 하나만 수정되면 대시보드 reason과 실제 엔진 결과가 다시 불일치 가능.

### 6.2 설정값 미활용
- `bb_touch_lookback`를 YAML/Config에 올렸지만, 실제 계산(`check_bb_touch_recovery`) 호출에 전달하지 않음.
- 현재 호출은 기본값/하드코딩 경로로 동작.

### 6.3 잠재 버그 1: Position 모델 import 누락
- `main.py`에서 `update(Position)` 사용하지만 `Position` import가 없음.
- 포지션 보유 상태에서 HWM 업데이트 분기 진입 시 `NameError` 가능.

### 6.4 잠재 버그 2: 포지션 조회 필드 누락
- `executor.get_position()`이 `regime`, `high_water_mark`를 반환하지 않음.
- 결과적으로:
  - `check_exit_signal()`의 `entry_regime`이 기본 `SIDEWAYS`로 폴백될 가능성.
  - HWM 추적/트레일링 동작이 왜곡될 가능성.

### 6.5 불필요 코드/낡은 흔적
- `RegimeEntryConfig` dataclass는 현재 실질 사용되지 않음(딕셔너리 기반 설정 사용).
- `runner.py` 타임아웃 주석/로그(`20s`)와 실제 값(`40s`) 불일치.

## 7. 권장 진행 방향 (우선순위)

### P0. 진입 불능 완화 (즉시)
1. SIDEWAYS `bb_touch_recovery`를 1분봉 기준으로 `get_all_indicators()`에서 계산.
2. `bb_touch_lookback`를 설정값에서 읽어 실제 함수 인자로 전달.
3. `main.py`의 SIDEWAYS 전용 hourly 계산 블록 제거 또는 fallback 용도로만 유지.

### P1. RSI 반등 로직 개선
1. 1캔들 판정 대신 lookback 기반 판정 추가:
   - 예: “최근 N개 캔들 중 RSI7 최소값 < trigger AND 현재 RSI7 >= recover”.
2. `min_rsi_7_bounce_pct`를 `현재 RSI7 - 최근 N개 RSI7 최저점`으로 평가.

### P2. AI 판정 품질/비용 균형
1. Rule 통과 시점에만 추가 데이터 조회(예: AI용 별도 1시간봉 24개).
2. 레짐별 confidence 정책 차등 적용 또는 confidence를 포지션 사이징에 연동.
3. 실제 적용 중인 프롬프트 템플릿을 단일 경로로 정리(`get_analyst_prompt` 사용 여부 확정).
4. BEAR 전용으로 AI 입력에 “최근 N캔들 하락 연속성/거래량 회복률” 같은 요약 feature를 함께 제공(모델이 반복적으로 보는 거절 근거를 구조화).
5. Timeout 4건은 직접 손실 요인이라, AI 호출 전 로컬 pre-filter를 두어 불필요 호출을 줄이고 타임아웃 위험을 낮춤.

### P3. 코드 건전성 정리
1. `build_status_reason()`를 전략 평가 결과 객체 기반으로 리팩터링(중복 제거).
2. `Position` import 누락 및 `get_position()` 반환 필드 보강(regime/high_water_mark).
3. 타임아웃 로그/주석, 미사용 dataclass, 미사용 함수 정리.

## 8. 결론
- 현재 관측된 “BEAR에서 AI 거절 많음 / SIDEWAYS에서 AI 판단 0건”은 코드 구조와 일치함.
- 특히 최근 로그 기준 병목은 AI 이전 단계(Rule Engine)이며, SIDEWAYS는 `bb_touch_recovery` 경로 개선이 최우선.
- 단기적으로는 P0+P1만 적용해도 “신호 0건” 문제를 크게 완화할 가능성이 높음.
