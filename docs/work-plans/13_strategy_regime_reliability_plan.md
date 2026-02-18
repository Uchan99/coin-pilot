# 14. 전략 레짐 신뢰성 회복 및 실행률 개선 계획 (v1.0)

**작성일**: 2026-02-16  
**기반 문서**: `docs/2026-02-16_strategy_regime_audit.md`  
**상태**: Phase 3 In Progress

---

## 1. 배경

최근 운영/코드 점검 결과, 병목은 AI 이전 단계(Rule Engine)에 집중됨.

- 최근 봇 로그 집계:
  - `entry=0`
  - `ai_reject=0`
  - `ai_approve=0`
  - `rsi14_fail=882`
  - `rsi7_fail=392`
  - `bb_recovery_fail=7`
- DB(`agent_decisions`) 기준 BEAR 거절:
  - `BEAR + REJECT = 67건`
  - `FALLING_KNIFE 41`, `VOLUME 22`, `TIMEOUT 4`

핵심 문제:
1. `SIDEWAYS`의 BB 터치 회복 계산 경로가 데이터 길이와 불일치.
2. RSI(7) 반등 판정이 1캔들 점프 조건이라 신호 누락이 큼.
3. AI 컨텍스트 길이/프롬프트 경로 불일치로 BEAR에서 과도한 거절 패턴 강화.
4. 유지보수 리스크(중복 조건 구현, 잠재 버그)가 존재.

중요 보완:
- `bb_touch_lookback`(3→30) 변경은 현재 계산 경로에서 실질 효과가 거의 없음.
  - 이유: `check_bb_touch_recovery()` 호출 시 설정값 전달이 누락되어 기본 인자/하드코딩 경로로 동작.
  - 따라서 파라미터 변경만으로는 SIDEWAYS 신호 개선이 불가능하며, 계산 경로 자체 수정이 선행되어야 함.

---

## 2. 목표 (이번 사이클)

### 2.1 기능 목표
1. `SIDEWAYS`에서 구조적 진입 불능 상태 해소.
2. `RSI7` 반등 판정을 lookback 기반으로 전환.
3. BEAR AI 입력 품질 개선으로 “반복적 동일 사유 거절” 완화.
4. 진입 로직/상태 로직의 코드 건전성 개선.

### 2.2 정량 목표 (배포 후 72시간 관측)
1. `entry=0` 상태 탈출.
2. `SIDEWAYS`에서 AI 판단 호출(approve/reject 포함) 최소 1건 이상 발생.
3. BEAR REJECT 중 `TIMEOUT` 비중 10% 미만 유지.
4. Rule 실패 상위 사유 개선 목표는 Phase별로 분리:
   - Phase 1(구조 수정): `BB recovery 미계산/기본값` 유형 0건화
   - Phase 2(파라미터 조정 포함 시): `RSI14` 실패 비중을 baseline 대비 유의미하게 감소(예: 20%p)

---

## 2.3 선행 핫픽스 (P0-Immediate)

### 2.3.1 런타임 안정성 핫픽스

**변경 내용**
1. `main.py`의 `Position` import 누락 즉시 수정.
2. `executor.get_position()` 반환 필드에 `regime`, `high_water_mark` 포함.

**사유**
- 현재는 포지션 보유 중 분기에서 `update(Position)` 실행 시 `NameError`로 루프 실패 가능성이 있음.
- 해당 항목은 기능 개선 이전의 안정성 이슈로 P3가 아니라 P0 즉시 처리 대상.

**수정 파일**
- `src/bot/main.py`
- `src/engine/executor.py`

---

## 3. 구현 범위

## Phase 1. Rule Engine 실행 가능성 복구 (P0)

### 3.1 SIDEWAYS BB 터치 회복 계산 경로 정렬

**변경 내용**
- `bb_touch_recovery`를 `get_all_indicators()`에서 1분봉 기준으로 계산.
- `bb_touch_lookback`를 설정값(`config/strategy_v3.yaml`)에서 읽어 실제 함수 인자로 전달.
- `main.py`의 SIDEWAYS 전용 1시간봉 재계산 블록 제거(또는 fallback 옵션화).
- BB 타임프레임 결정을 명시:
  - 기본안: **1분봉 lookback(30)** 를 canonical 경로로 채택.
  - 대안: 1시간봉 경로는 충분 데이터 확보 시 보조 검증 지표로만 유지.

**수정 파일**
- `src/common/indicators.py`
- `src/engine/strategy.py` (entry config 전달 경로 보완 시)
- `src/bot/main.py`
- `src/config/strategy.py`
- `config/strategy_v3.yaml`

**완료 기준**
- `SIDEWAYS + bb_enabled=true`에서 `bb_touch_recovery`가 실제 값(True/False)로 매 루프 계산됨.
- `bb_touch_lookback` 변경 시 동작이 즉시 반영됨.
- 1시간봉 경로는 주 신호 판정에서 제거되거나, fallback임이 코드/주석에 명확히 구분됨.

### 3.2 RSI(7) 반등 로직 lookback 전환

**변경 내용**
- 기존: `(rsi_short_prev < trigger) and (rsi_short >= recover)`
- 개선: “최근 N캔들 최소 RSI7 < trigger” AND “현재 RSI7 >= recover”
- `min_rsi_7_bounce_pct` 기준도 `현재 RSI7 - 최근 N캔들 RSI7 최저점`으로 전환.
- 지표 반환 확장:
  - `rsi_short_min_lookback`
  - (선택) `rsi_short_series_tail`
  를 `get_all_indicators()` 반환값에 추가하여 전략/사유 생성 로직 공통 사용.

**수정 파일**
- `src/common/indicators.py` (lookback min 값 산출)
- `src/engine/strategy.py`
- `src/bot/main.py` (`build_status_reason` 동기화)
- `config/strategy_v3.yaml` (lookback 파라미터 필요 시 추가)

**완료 기준**
- 완만 반등(다캔들) 케이스가 진입 후보로 포착됨.
- reason 문구와 실제 전략 판정 결과가 일치함.

---

## Phase 2. AI 판단 품질/비용 균형 (P1)

### 3.3 AI 컨텍스트 품질 개선

**변경 내용**
- Rule 통과 시점에만 AI 전용 데이터 추가 조회:
  - 1시간봉 24개를 실제로 제공 가능한 길이로 조회.
- BEAR 전용 요약 feature 전달:
  - 최근 하락 연속성
  - 최근 거래량 회복률
  - 단기 저점 대비 회복폭

**수정 파일**
- `src/bot/main.py`
- `src/agents/analyst.py`
- `src/agents/prompts.py`

**완료 기준**
- AI 입력의 `market_context` 길이가 의도한 범위에 근접(24개 목표).
- BEAR REJECT 사유가 “컨텍스트 부족/모호성” 중심에서 패턴 분화.

### 3.4 프롬프트 경로 단일화

**변경 내용**
- `analyst.py`가 `get_analyst_prompt()`를 사용하도록 경로 통일.
- 레짐 설명/가이드가 실제 분석 입력에 포함되게 정리.

**수정 파일**
- `src/agents/analyst.py`
- `src/agents/prompts.py`

**완료 기준**
- 레짐 가이드가 실제 프롬프트 payload에 포함됨(로그/디버깅 기준 확인).

### 3.5 Timeout 손실 최소화

**변경 내용**
- AI 호출 전 cheap pre-filter 도입(명백한 노이즈 케이스 skip).
- timeout 로그 문구와 실제 값(40s) 동기화.

**수정 파일**
- `src/bot/main.py`
- `src/agents/runner.py`

**완료 기준**
- `AI Analysis Timed Out` 건수 감소.
- 운영 로그의 timeout 문구/실제 정책 불일치 제거.

---

## Phase 3. 코드 건전성/버그 수정 (P1)

### 3.6 중복 조건 로직 축소

**변경 내용**
- `check_entry_signal()`와 `build_status_reason()` 중복 판정을 단일 소스로 통합.
- 최소한 조건 상수/판정 헬퍼 공유로 드리프트 방지.

**수정 파일**
- `src/engine/strategy.py`
- `src/bot/main.py`

**완료 기준**
- 향후 조건 변경 시 한 곳 수정으로 동작/사유가 일치.

### 3.7 잠재 버그 후속 점검

**변경 내용**
- P0 핫픽스(Import/position 반환필드) 적용 이후, 관련 회귀 테스트/로그 점검 수행.

**완료 기준**
- 핫픽스 적용 후 포지션 보유 루프에서 예외 미발생.
- exit 경로에서 폴백 레짐 사용 빈도 감소.

---

## 4. 작업 순서 (실행 플로우)

1. P0-Immediate 핫픽스 적용 (`Position` import, position 반환 필드).
2. Phase 1 구현 + 단위 테스트/시뮬레이션.
3. 로컬/스테이징에서 reason 로그 검증.
4. Phase 2 구현 (AI 컨텍스트/프롬프트/timeout).
5. Phase 3 코드 정리/후속 점검.
6. 배포 후 24h / 72h 지표 점검.

---

## 5. 검증 계획

### 5.1 코드/테스트
- `tests/test_strategy_v3_logic.py` 보강:
  - SIDEWAYS BB recovery true/false 케이스
  - RSI7 lookback 반등 케이스
  - BEAR volume_surge + recovery 동시 케이스
- 신규 테스트(필요 시):
  - `tests/test_bot_reason_consistency.py` (전략 판정 vs reason 일치)

### 5.2 운영 검증
- 로그:
  - `kubectl logs deployment/bot -n coin-pilot-ns | grep "❌\\|✅"`
  - `kubectl logs deployment/bot -n coin-pilot-ns | grep -E "Entry Signal|Trade Rejected by AI Agent|Trade Approved by AI Agent|Timed Out"`
- DB:
  - `agent_decisions`에서 regime/decision/reasoning/confidence 집계
- Redis:
  - `bot:status:*` reason 필드 실시간 확인

### 5.3 관측 지표
- Rule 단계 통과율
- 레짐별 AI 호출 수
- 레짐별 최종 체결 수
- BEAR REJECT reason 타입 분포
- timeout 발생률

---

## 6. 롤백 계획

1. `config/strategy_v3.yaml`를 직전 안정 버전으로 복원.
2. Phase 1 로직 플래그(가능하면 env/config)로 기존 RSI/BB 판정 방식으로 즉시 회귀.
3. AI 컨텍스트 확장으로 부하 발생 시 “Rule 통과 시 추가조회”만 비활성화.
4. 배포 롤백:
   - `kubectl rollout undo deployment/bot -n coin-pilot-ns`

---

## 7. 리스크 및 대응

1. 신호 과다 증가
- 대응: RiskManager 한도 유지, 필요 시 `position_size_ratio` 임시 하향.

2. AI 비용 증가
- 대응: pre-filter + 후보 발생 시점 추가조회 방식으로 호출 수 제한.

3. 조건 변경 후 reason 불일치 재발
- 대응: 판정/사유 로직 공통화 및 테스트로 회귀 방지.

4. BEAR에서 여전히 REJECT 과다
- 대응: BEAR 전용 feature/프롬프트 개선 후, 72시간 단위로 규칙 미세조정.

---

## 8. 산출물

1. 코드 수정 PR (Phase 1~3)
2. 테스트 결과 리포트
3. 배포 후 24h/72h 운영 리포트
4. `docs/work-result/13_*.md` 결과 문서

---

## 9. 진행 현황 업데이트 (2026-02-18)

### 9.1 완료 항목 (P0 + Phase 1)

- [x] `main.py`의 `Position` import 누락 수정
- [x] `executor.get_position()` 반환 필드에 `regime`, `high_water_mark` 추가
- [x] `get_all_indicators()`에서 1분봉 기준 `bb_touch_recovery` canonical 계산 경로 도입
- [x] `bb_touch_lookback` 설정값 전달 경로 연결
- [x] `main.py`의 SIDEWAYS 전용 hourly BB recovery 재계산 블록 제거
- [x] RSI7 반등 조건 lookback 기반 전환
- [x] `min_rsi_7_bounce_pct` 기준을 `현재 RSI7 - 최근 N캔들 RSI7 최저점`으로 전환
- [x] `build_status_reason()`를 전략 판정 로직과 동일 기준으로 동기화
- [x] `rsi_7_recovery_lookback` 설정 항목 추가 (`strategy.py`, `strategy_v3.yaml`)
- [x] 관련 테스트 보강 및 회귀 확인 (`tests/test_strategy_v3_logic.py`, `tests/test_indicators.py`)

검증 결과:
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_strategy_v3_logic.py tests/test_indicators.py`
- 결과: `10 passed`

참고 산출물:
- `docs/work-result/13_strategy_regime_phase1_implementation_result.md`

### 9.2 Phase 2 구현 체크리스트 (반영 완료)

#### 3.3 AI 컨텍스트 품질 개선
- [x] Rule 통과 시점 전용 AI 추가 조회 경로 분리 (`36h 1m -> 1h 24 candles` 목표)
- [x] `market_context` 길이 관측 메트릭 추가 (`coinpilot_ai_context_candles`)
- [x] BEAR 전용 요약 feature 추가:
  - [x] 최근 하락 연속성 (`bear_downtrend_ratio_8h`)
  - [x] 최근 거래량 회복률 (`bear_volume_recovery_ratio_8h`)
  - [x] 단기 저점 대비 회복폭 (`bear_rebound_from_recent_low_pct_8h`)
- [ ] `agent_decisions` 기준 REJECT reason 분포 전/후 비교 쿼리 정리

#### 3.4 프롬프트 경로 단일화
- [x] `analyst.py`에서 `get_analyst_prompt()` 사용 경로 연결
- [x] 레짐 가이드/설명 + BEAR 요약 feature를 실제 prompt payload에 포함
- [ ] 프롬프트 템플릿 중복 문구 정리(원시 입력 vs 요약 입력 역할 분리)

#### 3.5 Timeout 손실 최소화
- [x] timeout 로그 문구를 실제 정책(40s)과 동기화
- [x] AI pre-filter 규칙 정의 및 구현 (`main.py`, `context_features.py`)
- [x] pre-filter skip/통과 관측 메트릭 추가
- [ ] 배포 후 timeout 비중 72h 추적 및 기준(10% 미만) 확인

Phase 2 검증 결과:
- `PYTHONPATH=. .venv/bin/pytest -q tests/agents/test_context_features.py tests/test_agents.py tests/test_strategy_v3_logic.py tests/test_indicators.py`
- 결과: `18 passed`

관련 산출물:
- `docs/work-result/13_strategy_regime_phase1_implementation_result.md` (하단 Phase 2 섹션 포함)

### 9.3 현재 잔여 작업 (Phase 3 + 운영 검증)

- [x] `check_entry_signal()` vs `build_status_reason()` 중복 로직 공통화
- [x] reason/판정 드리프트 방지 테스트(`tests/test_bot_reason_consistency.py`) 추가
- [ ] 배포 후 24h/72h 운영 지표 점검 및 리포트 작성

Phase 3 중간 검증 결과:
- `PYTHONPATH=. .venv/bin/pytest -q tests/test_bot_reason_consistency.py tests/test_strategy_v3_logic.py tests/test_indicators.py tests/agents/test_context_features.py tests/test_agents.py`
- 결과: `20 passed`

---


