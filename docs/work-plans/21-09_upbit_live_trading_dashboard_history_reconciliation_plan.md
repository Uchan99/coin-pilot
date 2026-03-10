# 21-09. Upbit 실거래 전환용 Dashboard/History/Reconciliation 정합화 계획

**작성일**: 2026-03-10  
**작성자**: Codex  
**상태**: Approved  
**관련 계획 문서**: `docs/work-plans/21_live_trading_transition_1m_krw_plan.md`, `docs/work-plans/21-04_llm_token_cost_observability_dashboard_plan.md`, `docs/work-plans/22_dashboard_readability_and_live_data_reliability_plan.md`, `docs/work-plans/31_oci_ops_monitoring_cron_automation_and_gap_hardening_plan.md`  
**승인 정보**: 사용자 / 2026-03-10 / "dev21 브랜치에서 stage A 진행" 승인  

---

## 0. 트리거(Why started)
- 운영/모니터링에서 무엇이 관측됐는지:
  - 현재 주문 실행기는 `PaperTradingExecutor`이며, `account_state`, `positions`, `trading_history`도 paper 장부 기준으로 동작한다.
  - 대시보드/모바일 API/포트폴리오 도구는 모두 DB의 paper 잔고와 paper 포지션을 읽는 구조다.
  - Charter와 기존 21번 계획에는 "실거래 전환" 필요성이 명시돼 있으나, 대시보드/히스토리/정산 관점의 세부 준비 항목은 아직 분리 문서화되지 않았다.
- 왜 지금 계획 분리가 필요한지:
  - 실거래 전환은 단순히 Executor만 교체하는 작업이 아니라, 잔고/주문/체결/정산/reconciliation/UI 기준을 함께 바꾸는 아키텍처 변경이다.
  - 현재 `21-04`/`31`이 남아 있는 상황에서 실거래를 최우선 구현으로 올릴지 판단하려면, "무엇이 추가로 바뀌는지"를 먼저 구조적으로 명세해야 한다.

## 1. 문제 요약
- 증상:
  - 현재 시스템은 paper 장부를 단일 source of truth로 사용하므로, Upbit 실계좌 잔고/미체결 주문/부분 체결/실수수료/실슬리피지를 표현하지 못한다.
- 영향 범위(기능/리스크/데이터/비용):
  - 기능:
    - `src/engine/executor.py`가 실주문/주문조회/주문취소를 지원하지 않음
    - Dashboard와 mobile API가 실계좌 기준 portfolio/order lifecycle을 표현하지 못함
  - 리스크:
    - DB와 거래소 상태 불일치 시 중복 주문, 잘못된 PnL, 잔고 오판단 위험
    - 부분 체결/취소/재시도/네트워크 실패를 현재 schema가 충분히 구분하지 못함
  - 데이터:
    - `trading_history`는 order / fill / cancel / partial fill lifecycle audit log로는 불충분
    - `account_state`는 paper 잔고 1개 row 구조라 실시간 거래소 계좌 스냅샷/정산 이력 보존에 부적합
  - 비용:
    - 실거래 손실, 수수료, 슬리피지, 주문 실패 재시도 비용이 직접 발생
- 재현 조건:
  - `TRADING_MODE=live`로 전환해 실주문을 발행하고, Dashboard/History/API가 거래소 실계좌 상태와 동기화돼야 하는 시점

## 2. 원인 분석
- 가설:
  1) 현재 설계는 "signal -> paper fill -> DB 반영" 단일 흐름이라 실거래의 비동기 주문 lifecycle을 담기 어렵다.
  2) 현 Dashboard는 `positions`와 `account_state`를 직접 읽기 때문에, 거래소 원장과 정산된 canonical portfolio를 분리하지 못한다.
  3) 실거래 도입 시 가장 큰 리스크는 전략보다 reconciliation 실패다.
- 조사 과정:
  - `src/engine/executor.py`, `src/bot/main.py`, `src/common/models.py`, `src/dashboard/pages/1_overview.py`, `src/mobile/query_api.py`, `src/agents/tools/portfolio_tool.py`, `deploy/db/init.sql`을 확인했다.
  - `PaperTradingExecutor`가 잔고 차감/포지션 수정/거래 기록을 즉시 DB에 반영하는 구조임을 확인했다.
  - `Overview`, `/positions`, `/pnl`, `/risk`가 모두 paper 장부 기준으로 읽는 구조임을 확인했다.
- Root cause:
  - 현재 구조는 실거래용 `execution ledger`, `order lifecycle`, `exchange account snapshot`, `reconciliation state`가 없고, UI/리포트도 해당 계층을 읽지 않도록 설계돼 있다.

## 3. 대응 전략
- 단기:
  - 실거래 전환 전 필수 데이터 계약과 운영 체크리스트를 먼저 고정한다.
  - "실거래면 무엇이 바뀌는가"를 executor / DB / dashboard / history / monitoring 레벨로 분리한다.
- 근본 해결:
  - `paper ledger`와 `exchange truth`를 분리하고, `reconciliation`이 둘 사이의 canonical 상태를 만드는 구조로 전환한다.
- 안전장치(가드레일/차단/쿨다운/timeout 등):
  - `TRADING_MODE=paper|live|dry_run`
  - 실거래 초기에는 `BTC only` + `pilot capital` + `max_daily_orders` 축소
  - 주문 idempotency key / pending-order timeout / cancel-before-retry
  - 잔고/포지션 불일치 시 신규 BUY 차단
  - 킬스위치: 손실 한도, 정산 불일치, API 오류율, heartbeat 중단

## 4. 아키텍처 선택/대안/트레이드오프
- 최종 선택(예정):
  - **Executor 분리 + 거래소 스냅샷 + 정산 잡 + Dashboard canonical view**

- 고려 대안:
  1) 현재 `PaperTradingExecutor`를 직접 수정해 live 로직 혼합
  2) 거래소 API를 Dashboard에서 직접 조회
  3) `LiveTradingExecutor` + exchange snapshot/reconciliation 계층 추가(채택 예정)

- 대안 비교:
  1) 혼합:
    - 장점: 초기 코드량 적음
    - 단점: paper/live 분기 누적, 테스트/롤백 어려움
  2) UI 직접 조회:
    - 장점: 화면 반영 빠름
    - 단점: UI와 봇이 서로 다른 source of truth를 보게 됨
  3) 분리 구조:
    - 장점: auditability, rollback, reconciliation, 테스트 가능성 우수
    - 단점: schema/ops 작업량 증가

## 5. 구현/수정 내용 (예정)
### Phase A. 실거래 최소 데이터 계약 정의
1. 추가/수정이 필요한 저장 단위:
   - `exchange_account_snapshots`
   - `exchange_orders`
   - `exchange_fills`
   - `reconciliation_runs`
2. `trading_history`는 "전략 관점 trade log"로 유지하되, 거래소 원장(`exchange_orders`, `exchange_fills`)과 분리
3. `positions`, `account_state`는 paper/live 공용이 아니라 "정산 후 canonical portfolio view"로 재정의 검토

### Phase B. Live Executor + Dry Run
1. `LiveTradingExecutor` 신규 구현
   - 주문 생성
   - 주문 조회/취소
   - pending -> partial -> filled -> cancelled 반영
2. `TRADING_MODE`
   - `paper`
   - `dry_run` (서명/요청 준비만, 주문 전송 없음)
   - `live`
3. 실시간/주기 정산 잡
   - 거래소 주문/체결 이력 pull
   - DB 장부와 대조
   - 불일치 시 신규 BUY 차단

### Phase C. Dashboard / History / Mobile API 정합화
1. Dashboard 필수 카드
   - 거래소 현금 잔고
   - DB 기준 canonical 총 평가액
   - 미체결 주문 수
   - 정산 불일치 건수
   - 최근 체결 수/실현 손익
2. History 필수 컬럼
   - order_id / exchange_order_id
   - side / requested_qty / filled_qty / remaining_qty
   - avg_fill_price / fee / slippage
   - order_status (`pending`, `partial`, `filled`, `cancelled`, `rejected`)
   - source (`paper`, `live`, `reconciled`)
   - strategy / regime / exit_reason
3. Mobile API / portfolio tool 확장
   - `/positions`: canonical portfolio + source timestamp
   - `/pnl`: realized/unrealized + fee/slippage 반영
   - `/status`: exchange connectivity / reconciliation lag / open orders

### Phase D. Monitoring / Kill Switch
1. 실거래 전용 모니터링 항목
   - exchange API 성공률
   - open order age
   - stale account snapshot lag
   - reconciliation mismatch count
   - duplicate order reject count
2. 알림 기준
   - 잔고 snapshot lag > 2분 WARN
   - open order age > 5분 WARN
   - reconciliation mismatch > 0 FAIL
   - live order error rate >= 10% WARN / >= 20% FAIL

## 6. 실거래 기준 Dashboard/History 필수 체크리스트
### 6.1 Dashboard 필수
1. 거래소 실현금/주문가능 KRW 잔고
2. 보유 자산별 수량/평단/현재가/평가금액/미실현손익
3. 미체결 주문 수, 가장 오래된 open order age
4. 최근 24h realized PnL (수수료 반영)
5. 수수료 누적, 추정 슬리피지 누적
6. canonical portfolio timestamp와 exchange snapshot timestamp
7. reconciliation mismatch count
8. live mode / dry_run / paper mode 상태 표시
9. kill switch 상태와 차단 사유
10. API 에러율, 최근 주문 실패 사유 top N

### 6.2 History 필수
1. 전략 trade log와 거래소 order/fill log를 구분해서 볼 수 있어야 함
2. 각 BUY/SELL에 `exchange_order_id` 추적 가능해야 함
3. 부분 체결/취소/거절 상태가 남아야 함
4. 수수료와 평균 체결가가 저장돼야 함
5. paper/live source 구분이 있어야 함
6. 실현손익 계산 시 entry_avg_price 추정이 아니라 실제 fill 기준 집계 가능해야 함
7. 재시도/취소/정산으로 수정된 이력도 audit trail로 남아야 함

### 6.3 운영/정산 필수
1. 거래소 잔고 vs DB canonical balance 대조
2. 거래소 open orders vs DB pending orders 대조
3. 거래소 fills vs DB trading_history 대응관계 확인
4. 중복 주문 방지 키 저장
5. 실거래 키/환경변수/권한/IP allowlist 점검
6. 신규 BUY 차단 조건(정산 불일치, snapshot stale, kill switch) 검증

## 7. 검증 기준
- 재현 케이스에서 해결 확인:
  1. `dry_run`에서 주문 payload/서명/요청 로그만 생성되고 실주문은 전송되지 않는지
  2. `live` pilot 모드에서 exchange snapshot / order / fill / canonical portfolio가 일관되게 누적되는지
  3. reconciliation mismatch 상황에서 신규 BUY가 차단되는지
- 회귀 테스트:
  - `paper` 모드는 기존과 동일하게 동작
  - Dashboard paper view는 계속 열람 가능
  - `strategy_feedback`, `rule_funnel`, `mobile API`가 live schema 확장 후에도 깨지지 않아야 함
- 운영 체크:
  - 24h 동안 exchange account snapshot lag <= 2분
  - open order stuck 0건
  - reconciliation mismatch 0건
  - 수수료/실현손익/보유수량이 Upbit 계좌와 일치

## 8. 롤백
- 코드 롤백:
  - `TRADING_MODE=paper` 즉시 전환
  - live executor import 경로 비활성화
- 데이터/스키마 롤백:
  - exchange 계열 신규 테이블은 보존하되 live writer만 중단
  - canonical view를 paper source로 되돌림

## 9. 우선순위 판단
- 지금 최우선으로 바로 구현하기 어려운 이유:
  1. `21-04` 비용 snapshot/reconciliation이 아직 미완료라, 실거래 비용/정산 운영 기준이 완결되지 않았다.
  2. `31` cron/관측 자동화가 완료되지 않아, 실거래 전용 heartbeat/reconciliation alarm을 붙이기 어렵다.
  3. 현재 Dashboard/History는 paper 장부 가정이 강해서 live 전환 시 schema/API/UI를 한 번에 건드리는 대형 변경이 된다.
- 권장 우선순위:
  - **지금 즉시 구현 최우선 작업으로 올리기보다는, `21-04 -> 31` 이후에 실거래 전환 Phase를 여는 것이 안전하다.**
  - 단, 계획/체크리스트/데이터 계약은 지금 먼저 고정해도 된다.

## 10. 문서 반영
- work-plan/work-result 업데이트:
  - 본 계획은 `21` 실거래 전환 스트림의 하위 계획으로 추가
  - 구현 착수 시 별도 result 문서 생성
- PROJECT_CHARTER.md 업데이트 필요 여부 및 반영 내역:
  - 현재는 계획 확정 단계라 Charter 미수정
  - 실거래 정책(`TRADING_MODE`, kill switch, canonical source of truth`) 확정 시 Changelog 반영 예정

## 11. 후속 조치
1. `21-04` snapshot 수집 경로 마감
2. `31` 모니터링 cron/heartbeat 표준화
3. 실거래 전환 착수 전, 본 계획 기준으로 `Stage A (dry_run + schema)` 승인 재요청

## 12. 계획 변경 이력
- 2026-03-10: 사용자 요청에 따라 실거래 전환 시 Dashboard/History/Reconciliation이 어떻게 달라지는지 분리 명세하는 하위 계획으로 신규 작성.
- 2026-03-10: 사용자 승인 후 Stage A(실거래 최소 데이터 계약 정의) 구현에 착수. 범위는 exchange 원장 테이블 4종, ORM 모델, migration, baseline init, 최소 회귀 테스트로 한정한다.
