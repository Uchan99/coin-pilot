# 29. 레짐 전환 구간 전략 평가 및 핫픽스 의사결정 구현 결과

작성일: 2026-03-06
작성자: Codex
관련 계획서: `docs/work-plans/29_regime_transition_strategy_evaluation_and_hotfix_plan.md`
상태: In Progress
완료 범위: Phase 1~5
선반영/추가 구현: 있음(Phase 2~5)
관련 트러블슈팅(있다면): 없음

---

## 1. 개요
- 구현 범위 요약:
  - `f29` 브랜치 생성 후 29 작업 착수.
  - 레짐 전환 시나리오 비교용 백테스트 스크립트 추가.
- 목표(요약):
  - baseline 대비 전환 민감도/진입/청산 시나리오를 한 번에 비교 가능한 실행 도구 마련.
- 이번 구현이 해결한 문제(한 줄):
  - 수동 백테스트 반복/비교 부담을 줄여 핫픽스 의사결정 준비 시간을 단축.
- 해결한 문제의 구체 정의(증상/영향/재현 조건):
  - 증상: 시나리오별 백테스트를 수동으로 각각 실행/기록해야 해 비교 재현이 번거로움.
  - 영향: 핫픽스 판단 지연, 비교 기준 불일치 가능성 증가.
  - 재현 조건: 레짐 임계값/진입/청산 조건을 동시에 실험하려는 경우.
- 기존 방식/상태(Before) 기준선 요약:
  - 비교 자동화 스크립트 0개, 단일 `scripts/backtest_v3.py` 기반 수동 비교.

---

## 2. 구현 내용(핵심)
### 2.1 시나리오 비교 스크립트 추가
- 파일/모듈: `scripts/backtest_regime_transition_scenarios.py`
- 변경 내용:
  - baseline + 3개 실험 시나리오(전환 민감도/상승장 진입 완화/손익비 재조정)를 한 번에 실행.
  - 심볼/기간 옵션(`--symbols`, `--days`) 제공.
  - 시나리오별 핵심 지표(거래수, 승률, 총손익, 평균 체결손익, RR, PF, MDD) 집계.
- 효과/의미:
  - 핫픽스 후보를 “감”이 아니라 동일 기준 수치로 비교 가능.

### 2.2 OCI 실데이터 시나리오 실행 및 중간 판정
- 실행 환경:
  - OCI `coinpilot-bot` 컨테이너 내부
- 실행 명령:
  - `PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 120 --output /tmp/regime_scenarios_120d.csv`
- 핵심 결과(Scenario Summary):
  - `baseline`: trades 5, win_rate 40.0%, total_profit `-4,408 KRW`, avg/trade `-882 KRW`, PF 0.7007, MDD `14,726 KRW`
  - `transition_sensitive`: trades 6, win_rate 66.7%, total_profit `+4,687 KRW`, avg/trade `+781 KRW`, PF 1.4800, MDD `9,765 KRW`
  - `bull_entry_relaxed`: trades 6, total_profit `+504 KRW` (거의 손익분기)
  - `exit_rr_rebalanced`: trades 6, total_profit `-4,835 KRW` (baseline 대비 악화)
- 중간 결론:
  - 현재 표본에서는 `transition_sensitive`(레짐 임계값 완화)가 baseline 대비 수익/승률/MDD 모두 개선.
  - 단, 표본이 매우 작고(`5~6 trades`) ETH 거래 0건이라 즉시 확정 배포 대신 추가 검증 필요.

### 2.3 장기 백필 스크립트 확장(Phase 3)
- 파일/모듈: `scripts/backfill_for_regime.py`
- 변경 내용:
  - 기존 고정 로직(심볼 5개, 12,000분)을 인자 기반 장기 백필로 확장:
    - `--days`(일 단위 목표)
    - `--symbols`(심볼 선택)
    - `--target-minutes`(기존 호환 기본 12,000 유지)
  - 운영 안정성 보강:
    - 429/5xx/네트워크 오류 재시도(`--max-retries`)
    - 배치 진행률 출력(`--status-every`)
    - DB upsert 결과 기반 삽입/중복 건수 통계 출력
    - `to` 경계 중복 방지를 위한 1초 오프셋 처리
- 효과/의미:
  - 백테스트 기간 확장 전에 `market_data`를 안전하게 누적할 수 있어, 120/180/240일 결과 동일 문제를 구조적으로 해소할 수 있게 됨.

### 2.4 심볼 비중 재배분 시나리오 추가(Phase 4)
- 파일/모듈: `scripts/backtest_regime_transition_scenarios.py`
- 변경 내용:
  - 사용자 요청을 반영해 심볼 비중 재배분 시나리오 2종 추가:
    - `symbol_rebalanced`
    - `transition_sensitive_symbol_rebalanced`
  - 비중 정책:
    - BTC/ETH/SOL `1.2x`
    - XRP/DOGE `0.7x`
  - 총 리스크 수준을 크게 바꾸지 않도록 배율 합을 보정(`1.2*3 + 0.7*2 = 5.0`).
  - 구현 방식:
    - 시나리오별로 `StrategyConfig.SYMBOL_POSITION_MULTIPLIERS`를 오버라이드해 손익/MDD 계산에 반영.
- 효과/의미:
  - “DOGE/XRP 축소 시 다른 심볼 비중 확대” 효과를 동일 백테스트 프레임에서 즉시 비교 가능.

### 2.5 실거래/백테스트 공통 심볼 비중 핫픽스 적용(Phase 5)
- 파일/모듈:
  - `src/config/strategy.py`
  - `config/strategy_v3.yaml`
  - `src/bot/main.py`
  - `scripts/backtest_v3.py`
  - `src/agents/tools/strategy_policy_tool.py`
- 변경 내용:
  - 전략 공통 설정에 `SYMBOL_POSITION_MULTIPLIERS`와 안전 조회 함수(`get_symbol_position_multiplier`)를 추가.
  - `config/strategy_v3.yaml`에 운영 배율 정책(BTC/ETH/SOL 1.2, XRP/DOGE 0.7) 반영.
  - 실거래 진입 금액 계산을 `regime_ratio * symbol_multiplier` 기준으로 변경.
  - 백테스트도 동일 계산식을 적용해 실거래/백테스트 비중 규칙을 정렬.
  - 전략 정책 조회 도구에 심볼 배율 노출 필드 추가.
- 효과/의미:
  - 백테스트에서 유리한 비중 정책을 실거래 경로에 동일하게 반영해, 검증-운영 간 괴리를 축소.

---

## 3. 변경 파일 목록
### 3.1 신규
1) `scripts/backtest_regime_transition_scenarios.py`
2) `tests/test_strategy_position_sizing.py`

### 3.2 수정
1) `docs/work-plans/29_regime_transition_strategy_evaluation_and_hotfix_plan.md`
2) `docs/checklists/remaining_work_master_checklist.md`
3) `docs/work-result/29_regime_transition_strategy_evaluation_and_hotfix_result.md`
4) `scripts/backfill_for_regime.py`
5) `scripts/backtest_regime_transition_scenarios.py`
6) `docs/PROJECT_CHARTER.md`
7) `src/config/strategy.py`
8) `config/strategy_v3.yaml`
9) `src/bot/main.py`
10) `scripts/backtest_v3.py`
11) `src/agents/tools/strategy_policy_tool.py`

---

## 4. 검증 결과
### 4.1 코드/정적 검증
- 실행 명령:
  - `python3 -m py_compile src/config/strategy.py src/bot/main.py scripts/backtest_v3.py scripts/backtest_regime_transition_scenarios.py src/agents/tools/strategy_policy_tool.py`
  - `PYTHONPATH=. .venv/bin/python scripts/backtest_regime_transition_scenarios.py --help`
  - `python3 -m py_compile scripts/backfill_for_regime.py`
  - `PYTHONPATH=. .venv/bin/python scripts/backfill_for_regime.py --help`
  - `PYTHONPATH=. .venv/bin/python -m pytest tests/test_strategy_position_sizing.py -q`
  - `PYTHONPATH=. .venv/bin/python -m pytest tests/test_strategy_v3_logic.py -q`
- 결과:
  - 통과. 구문 오류 없음, 신규/기존 단위 테스트 통과.

### 4.2 정량 개선 증빙
- 측정 기간/표본:
  - 도구 준비 단계(기능 검증 1회)
- 측정 기준:
  - 시나리오 비교 자동화 실행 진입점 제공 여부
- 데이터 출처:
  - 실행 명령 출력(스크립트 help/compile)
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 시나리오 비교 자동화 스크립트 수 | 0 | 1 | +1 | 측정 불가(분모 0) |
| 단일 실행 지원 시나리오 수 | 1(baseline 수동) | 6(자동 집계) | +5 | +500.0 |

- 정량 측정 불가 시(예외):
  - 불가 사유: 실제 전략 성과(수익률/MDD)는 DB 기반 백테스트 실행 전이라 미확정
  - 대체 지표: 자동화 도구 가용성(스크립트/CLI) 확인
  - 추후 측정 계획: Phase 2에서 실제 백테스트 수치 테이블 추가

### 4.3 전략 성능 비교(OCI, 120/180/240일) - Phase 2
- 측정 기간/표본:
  - 120일/180일/240일 백테스트, 5개 심볼, 시나리오당 5~6 체결
- 측정 기준:
  - baseline 대비 수익/리스크 동시 개선 여부
- 데이터 출처:
  - OCI 실행 로그 + `/tmp/regime_scenarios_120d.csv`, `/tmp/regime_scenarios_180d.csv`, `/tmp/regime_scenarios_240d.csv`
- 재현 명령:
  - `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'cd /app && PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 120 --output /tmp/regime_scenarios_120d.csv'`
  - `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'cd /app && PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 180 --output /tmp/regime_scenarios_180d.csv'`
  - `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'cd /app && PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 240 --output /tmp/regime_scenarios_240d.csv'`
- Before/After 비교표 (baseline vs transition_sensitive):

| 지표 | Before (baseline) | After (transition_sensitive) | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 총 실현손익 (KRW) | -4,408 | +4,687 | +9,095 | +206.3 *(손실 기준 개선율)* |
| 승률 (%) | 40.0 | 66.7 | +26.7%p | +66.7 |
| 체결당 평균손익 (KRW) | -882 | +781 | +1,663 | +188.6 *(손실 기준 개선율)* |
| Profit Factor | 0.7007 | 1.4800 | +0.7793 | +111.2 |
| Max Drawdown (KRW) | 14,726 | 9,765 | -4,961 | -33.7 |

- 정량 측정 불가/제한:
  - 제한 사유:
    - 표본 부족(시나리오당 체결 6건 내외), ETH 0건
    - 120/180/240일 결과가 동일하여 유효 비교 구간이 사실상 동일 데이터 윈도우일 가능성 높음
  - 대체 지표: 승률/PF/MDD 동시 개선 여부 우선 확인
- 추후 계획:
    - 심볼별 원천 데이터 기간 확인 SQL 실행 후(최소/최대 timestamp), 데이터 윈도우를 늘려 재검증
    - BTC/XRP/DOGE 중심으로 체결 표본 확대 후 재평가

### 4.4 장기 백필 기능 개선 증빙(Phase 3)
- 측정 기간/표본:
  - 2026-03-06, 스크립트 기능 검증(로컬 정적+CLI) 1회
- 측정 기준:
  - 장기 백필에 필요한 파라미터/안정성 기능 제공 여부
- 데이터 출처:
  - `py_compile`, `--help` 출력, 코드 diff
- 재현 명령:
  - `python3 -m py_compile scripts/backfill_for_regime.py`
  - `PYTHONPATH=. .venv/bin/python scripts/backfill_for_regime.py --help`
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 장기 기간 파라미터(`--days`) | 0 | 1 | +1 | 측정 불가(분모 0) |
| 심볼 선택 파라미터(`--symbols`) | 0 | 1 | +1 | 측정 불가(분모 0) |
| 백필 안정성 옵션(재시도/진행률) | 0 | 2 | +2 | 측정 불가(분모 0) |
| 기본 실행 호환성(12,000분) | 지원 | 지원 | 0 | 0.0 |

- 정량 측정 불가 시(예외):
  - 불가 사유: 실제 DB rows 증가량은 OCI 실행 결과가 필요하며 본 변경셋에서는 코드/명령 정합만 검증
  - 대체 지표: CLI 옵션/정적 검증 통과
  - 추후 측정 계획: OCI에서 `--days 90/120` 실행 후 `market_data` row 증가량, first_ts 확장폭(일수) 기록

### 4.5 심볼 비중 재배분 기능 개선 증빙(Phase 4)
- 측정 기간/표본:
  - 2026-03-06, 코드/정적 검증 1회
- 측정 기준:
  - 심볼 비중 재배분 시나리오를 동일 백테스트 러너에서 재현 가능한지
- 데이터 출처:
  - 코드 diff + `py_compile` 결과
- 재현 명령:
  - `python3 -m py_compile scripts/backtest_regime_transition_scenarios.py`
  - `PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 120 --output /tmp/regime_scenarios_120d.csv`
- Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 심볼 비중 재배분 시나리오 수 | 0 | 2 | +2 | 측정 불가(분모 0) |
| 비중 정책 반영 가능 여부 | 불가 | 가능 | +1 | 측정 불가(분모 0) |

- 정량 측정 불가 시(예외):
  - 불가 사유: 성능 수치(손익/MDD)는 사용자 OCI 실행 결과 반영 단계
  - 대체 지표: 시나리오 정의/실행 경로 추가 및 정적 검증 통과
  - 추후 측정 계획: 21일/120일 결과에서 `transition_sensitive` 대비 재배분 시나리오 손익/MDD 비교표 추가

### 4.6 실거래 반영 가능 상태 증빙(Phase 5)
- 측정 기간/표본:
  - 2026-03-06, 설정 로드/계산 경로 검증 1회 + 사용자 OCI 백테스트 재실행 결과
- 측정 기준:
  - 실거래/백테스트에서 동일 배율 규칙을 사용할 수 있는지
- 데이터 출처:
  - 로컬 검증 출력(`get_config()`), 사용자 OCI 실행 로그(21일/120일 시나리오 결과)
- 재현 명령:
  - `PYTHONPATH=. .venv/bin/python - <<'PY' ... get_config().SYMBOL_POSITION_MULTIPLIERS ... PY`
  - `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'cd /app && PYTHONPATH=. python scripts/backtest_regime_transition_scenarios.py --days 120 --output /tmp/regime_scenarios_120d.csv'`
- Before/After 비교표 (120일, 동일 전환 민감 시나리오 기준):

| 지표 | Before (`transition_sensitive`) | After (`transition_sensitive_symbol_rebalanced`) | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 총 실현손익 (KRW) | -80,142 | -77,691 | +2,451 | +3.06 *(손실 축소율)* |
| 체결당 평균손익 (KRW) | -673 | -653 | +20 | +2.97 *(손실 축소율)* |
| Profit Factor | 0.5749 | 0.5839 | +0.0090 | +1.57 |
| Max Drawdown (KRW) | 113,210 | 112,854 | -356 | -0.31 |

- 정량 측정 불가 시(예외):
  - 불가 사유: 실거래 적용 후 24h/72h 운영 데이터는 아직 관측 전
  - 대체 지표: 동일 배율이 실거래/백테스트 코드 경로에 동시에 반영됐는지 정적/단위 검증으로 확인
  - 추후 측정 계획: 적용 후 `trading_history` SELL 표본 20건 이상 누적 시 실운영 성과로 재평가

---

## 5. 계획 대비 리뷰
- 계획과 일치한 부분:
  - Phase B(레짐 전환 백테스트)용 실행 도구를 선행 구축.
- 변경/추가된 부분:
  - 없음(계획 범위 내 착수).

---

## 6. 결론 및 다음 단계
- 현재 상태 요약:
  - 29는 `In Progress`. 도구/데이터/시나리오 검증을 거쳐 심볼 비중 핫픽스 코드 반영까지 완료.
  - 남은 단계는 OCI 배포 적용 후 24h/72h 운영 관측과 SELL 표본 누적 검증.
- 후속 작업:
  1) OCI 배포 적용:
     - `cd /opt/coin-pilot && git pull --ff-only origin f29`
     - `cd /opt/coin-pilot/deploy/cloud/oci && docker compose --env-file .env -f docker-compose.prod.yml up -d --build bot`
  2) 컨테이너 설정 반영 확인:
     - `docker compose --env-file .env -f docker-compose.prod.yml exec -T bot sh -lc 'cd /app && PYTHONPATH=. python -c "from src.config.strategy import get_config; print(get_config().SYMBOL_POSITION_MULTIPLIERS)"'`
  3) 24h/72h 운영 관측:
     - `scripts/ops/check_24h_monitoring.sh t1h`
     - `scripts/ops/ai_decision_canary_report.sh 24`
     - `scripts/ops/llm_usage_cost_report.sh 24`
  4) 악화 시 롤백:
     - `config/strategy_v3.yaml`의 `position_sizing.symbol_position_multipliers`를 전부 `1.0`으로 복원 후 bot 재기동

---

## 7. 설계/아키텍처 결정 리뷰(Phase 3)
- 최종 선택한 구조 요약:
  - 기존 `backfill_for_regime.py`를 확장해 “호환 기본값 + 장기 옵션” 구조로 유지.
- 고려했던 대안:
  1) 신규 스크립트(`backfill_long_range.py`) 별도 추가
  2) 기존 `backfill_historical_data.py` 재사용/개조
  3) 기존 `backfill_for_regime.py` 확장 (채택)
- 대안 대비 실제 이점:
  1) k8s job/기존 운영 습관(무인자 실행) 호환성 유지
  2) 분산된 백필 진입점을 하나로 정리해 운영 실수 감소
  3) 기존 upsert 제약(`uq_market_data_symbol_interval_ts`) 재사용으로 데이터 무결성 유지
- 트레이드오프와 완화:
  1) 단일 스크립트 복잡도 증가 → argparse/함수 분리로 가독성 보완
  2) 대량 백필 시간 증가 가능성 → 배치/대기/재시도 옵션으로 환경별 튜닝 가능

## 8. 한국어 주석 반영 결과(Phase 3)
- 주석을 추가/강화한 주요 지점:
  1) Upbit `to` 파라미터 경계 중복 방지(1초 오프셋) 이유
  2) 429/5xx 재시도 정책과 반복 구간 감지(무한루프 방지) 의도
- 주석에 포함한 핵심 요소:
  - 의도/왜: 장기 백필 중 중복/반복/임시장애 대응
  - 불변조건: `interval='1m'`, unique constraint 기반 upsert
  - 실패 케이스: API 반복 응답/네트워크 오류/비정상 payload 대응

## 9. 설계/아키텍처 결정 리뷰(Phase 5)
- 최종 선택한 구조 요약:
  - 심볼 비중 배율을 전략 공통 설정(`StrategyConfig`)으로 승격하고, 실거래/백테스트가 같은 설정을 참조하도록 통합.
- 고려했던 대안:
  1) 실거래 코드(`main.py`)에 심볼 하드코딩 분기 추가
  2) 백테스트에서만 심볼 후처리 배율 적용
  3) 공통 설정 + 공통 계산식으로 정렬 (채택)
- 대안 대비 실제 이점:
  1) 운영/백테스트 계산 괴리 최소화
  2) YAML 기반 즉시 롤백 가능(재배포 후 반영)
  3) 신규 심볼 추가 시 코드 수정 없이 설정만 확장 가능
- 트레이드오프와 완화:
  1) 설정 필드 증가로 복잡도 상승 -> 안전 폴백(`<=0`/비숫자 값은 `1.0`)으로 운영 리스크 완화
  2) 시나리오 러너와 계산 중복 가능성 -> post-processing 곱 방식 제거, 설정 오버라이드 방식으로 정렬
