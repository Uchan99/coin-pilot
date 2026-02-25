# 21-01. 기준자산 고정 + 3중 캡 주문 체계 전환 구현 결과

작성일: 2026-02-26  
작성자: Codex (GPT-5)  
관련 계획서: `docs/work-plans/21-01_reference_equity_three_cap_execution_plan.md`  
상태: Verified  
완료 범위: Phase 1  
선반영/추가 구현: 없음  
관련 트러블슈팅(있다면): 없음  

---

## 1. 개요
- 구현 범위 요약:
  - 주문 금액 산정을 `기준자산(reference equity) + 3중 캡(min)`으로 전환
  - RiskManager 한도 계산 기준을 잔고 중심에서 기준자산 중심으로 정렬
  - 100만원 운용 기준 리스크/포지션 설정(YAML) 반영
- 목표(요약):
  - 심볼당 20% 비중 의도를 유지하면서 잔고 부족 주문을 구조적으로 방지
- 이번 구현이 해결한 문제(한 줄):
  - 잔고 기준 사이징으로 인한 주문 축소/불일치 문제를 기준자산 기반으로 교정

---

## 2. 구현 내용(핵심 위주)
### 2.1 YAML 리스크 설정 반영 경로 복구
- 파일/모듈: `src/config/strategy.py`
- 변경 내용:
  - `risk_management` 섹션 파싱 로직 추가
  - `MAX_POSITION_SIZE`, `MAX_TOTAL_EXPOSURE`, `MAX_CONCURRENT_POSITIONS`, `MAX_DAILY_LOSS` 등 YAML 값 반영
- 효과/의미:
  - 운영 설정 변경이 코드에 실제 반영되는 경로 보장

### 2.2 기준자산(reference equity) 도입 및 리스크 한도 정렬
- 파일/모듈: `src/engine/risk_manager.py`
- 변경 내용:
  - 생성자 기본값을 StrategyConfig 기준으로 동기화
  - `get_total_equity()`, `get_reference_equity()` 추가
  - 기준자산은 UTC 일 단위 캐시(일중 고정) 정책 적용
  - `check_order_validity()`에서 일일손실/단일주문/총노출 기준을 reference equity 기반으로 변경
  - `fee_buffer`(기본 0.2%)를 고려한 가용 현금 검증 추가
- 효과/의미:
  - 실시간 평가이익 변동으로 주문 목표가 비정상 확장되는 문제 완화
  - 현금/노출 한도를 동시에 강제해 잔고 부족 리젝트 위험 감소

### 2.3 봇 진입 로직을 3중 캡(min)으로 전환
- 파일/모듈: `src/bot/main.py`
- 변경 내용:
  - 진입 시 `target_cap / cash_cap / exposure_cap` 계산
  - `actual_invest_amount = min(...)` 적용 후 0 이하인 경우 명시적 SKIP
  - RiskManager 검증은 최종 주문금액 기준으로 수행
- 효과/의미:
  - 전략 의도(비중)와 실제 주문금액 간 괴리 축소
  - 잔고/노출 초과 주문을 사전 차단

### 2.4 100만원 운용 기준값 반영
- 파일/모듈: `config/strategy_v3.yaml`
- 변경 내용:
  - `position_size_ratio`: SIDEWAYS 0.9, BEAR 0.7
  - `risk_management` 섹션 추가:
    - `max_position_size: 0.20`
    - `max_total_exposure: 1.00`
    - `max_concurrent_positions: 5`
    - `allow_same_coin_duplicate: false`
    - `max_daily_loss: 0.03`
    - `max_daily_trades: 6`
- 효과/의미:
  - 사용자 목표(심볼당 20%, 필요 시 100% 홀딩 허용)에 맞는 운용 기준 확립

---

## 3. 변경 파일 목록
### 3.1 수정
1) `src/config/strategy.py`  
2) `src/engine/risk_manager.py`  
3) `src/bot/main.py`  
4) `config/strategy_v3.yaml`  
5) `docs/work-plans/21-01_reference_equity_three_cap_execution_plan.md`  
6) `docs/work-plans/21_live_trading_transition_1m_krw_plan.md`  
7) `docs/PROJECT_CHARTER.md`  

### 3.2 신규
1) `docs/work-result/21-01_reference_equity_three_cap_execution_result.md`  

---

## 4. DB/스키마 변경(있다면)
- 변경 사항: 없음
- 마이그레이션: 없음
- 롤백 전략/주의점: 코드/설정 롤백만 수행

---

## 5. 검증 결과(필수)
### 5.1 코드/정적 검증
- 실행 명령:
  - `python3 -m compileall src`
- 결과:
  - 통과(변경 파일 포함 컴파일 성공)

### 5.2 테스트 검증
- 실행 명령:
  - `.venv/bin/pytest -q tests/test_strategy_v3_logic.py`
  - `.venv/bin/pytest -q tests/test_strategy.py tests/test_strategy_v3_logic.py`
- 결과:
  - `test_strategy_v3_logic.py`: 4 passed
  - 전체 혼합 실행: 4 failed / 4 passed
  - 실패 원인: `tests/test_strategy.py`가 구형 인터페이스(`tp_ratio`, `sl_ratio`, `max_hold_hours`)를 사용하여 현재 `MeanReversionStrategy` 시그니처와 불일치(이번 변경과 무관한 기존 테스트 부채)

### 5.3 런타임/운영 반영 확인(선택)
- 확인 방법:
  - `.venv/bin/python`으로 `get_config()` / `RiskManager` 값 확인
- 결과:
  - `MAX_POSITION_SIZE=0.2`, `MAX_TOTAL_EXPOSURE=1.0`, `MAX_CONCURRENT_POSITIONS=5`, `MAX_DAILY_LOSS=0.03`, `MAX_DAILY_TRADES=6` 반영 확인

---

## 6. 배포/운영 확인 체크리스트(필수)
1) OCI `config/strategy_v3.yaml`가 본 변경값과 일치하는지 확인  
2) bot 재기동 후 로그에서 `Risk Rejected: 가용 현금 부족`/`노출 한도 도달` 메시지 비율 모니터링  
3) 24~48시간 paper 운용에서 잔고 부족 주문 에러(`Insufficient balance for BUY`) 재발 여부 점검  

---

## 7. 설계/아키텍처 결정 리뷰(필수)
- 최종 선택한 구조 요약:
  - 기준자산 고정(UTC 일 단위) + 3중 캡(min) 주문 구조
- 고려했던 대안:
  1) 실시간 총자산 연동 20%
  2) 잔고 기반 단순 20%(기존 유지)
  3) 목표 비중 리밸런싱 엔진
- 대안 대비 실제 이점(근거/관측 포함):
  1) 주문 목표가 평가손익에 과민하게 커지지 않음
  2) 현금 부족/총노출 초과를 한 번에 제어 가능
  3) 기존 구조를 유지한 채 핵심 수식만 교정해 변경 범위 최소화
- 트레이드오프(단점)와 보완/완화:
  1) 기준자산이 일중 고정이라 급격한 자산 변화에 즉시 반응하지 않음 -> 일 단위 재고정으로 안정성 우선
  2) 총노출 계산 시 현재가 조회가 필요해 DB/Redis 의존 증가 -> 캐시 우선 + DB fallback 유지

---

## 8. 한국어 주석 반영 결과(필수)
- 주석을 추가/강화한 주요 지점:
  1) `src/bot/main.py`: 3중 캡 설계 의도와 min 선택 이유
  2) `src/engine/risk_manager.py`: 설정 우선순위 및 fee buffer 안전값 처리
- 주석에 포함한 핵심 요소:
  - 의도/왜(why)
  - 실패 시 fallback 기준
  - 운영 안정성 우선 트레이드오프

---

## 9. 계획 대비 리뷰
- 계획과 일치한 부분:
  - 3중 캡 주문 정책 반영
  - 기준자산 정책(옵션 B: 일 단위 고정) 채택
  - 리스크 한도 및 포지션 설정 100만원 운용 기준 정렬
- 변경/추가된 부분(왜 바뀌었는지):
  - RiskManager 생성자에서 config 동기화를 명시적으로 추가(기존에는 max_per_order가 0.05로 고정될 수 있어 정책 반영 누락 위험)
- 계획에서 비효율적/오류였던 점(있다면):
  - 없음

---

## 10. 결론 및 다음 단계
- 현재 상태 요약:
  - 기준자산 기반 주문 산정/리스크 검증 경로가 코드에 반영됨
  - 100만원 운용 기준 설정이 YAML로 외부화되어 운영 조정 가능
- 후속 작업(다음 plan 번호로 넘길 것):
  1) `tests/test_strategy.py` 레거시 인터페이스 정리(테스트 부채 해소)
  2) OCI에서 24~48시간 paper 관측 후 실거래 executor 전환 단계 진입

---

## 11. References
- `docs/work-plans/21-01_reference_equity_three_cap_execution_plan.md`
- `src/bot/main.py`
- `src/engine/risk_manager.py`
- `src/config/strategy.py`
- `config/strategy_v3.yaml`

---

## 12. 운영 FAQ 반영 (WSL/OCI + 3중 캡 예시)
### 12.1 WSL과 OCI 실행 차이
- WSL:
  - 개발자가 로컬에서 직접 `docker compose up -d` 실행
- OCI:
  - `systemd` 서비스가 compose를 호출해 실행/재시작
  - 서비스 파일: `deploy/cloud/oci/systemd/coinpilot-compose.service`
  - 운영 경로: `/opt/coin-pilot/deploy/cloud/oci`

### 12.2 OCI에서 어떤 git branch가 배포되는가
- OCI는 `/opt/coin-pilot`에서 **현재 checkout된 branch/commit**이 배포 기준
- 자동으로 `main`을 쓰지 않음
- 확인 명령:
  - `git branch --show-current`
  - `git rev-parse --short HEAD`

### 12.3 3중 캡이 잔고 부족을 줄이는 이유 (숫자 예시)
- 조건:
  - 기준자산 1,000,000원
  - `max_per_order=0.20`, SIDEWAYS 비율 `0.9`
  - 현금 150,000원, 수수료 버퍼 0.2%
  - 총노출 잔여 300,000원
- 계산:
  - `target_cap = 1,000,000 * 0.20 * 0.9 = 180,000`
  - `cash_cap = 150,000 * (1 - 0.002) = 149,700`
  - `exposure_cap = 300,000`
  - `order_amount = min(180,000, 149,700, 300,000) = 149,700`
- 결론:
  - 최종 주문금액이 가용 현금 이하로 강제되어, 잔고 부족 리젝트를 구조적으로 완화
