# 21-09. Upbit 실거래 전환용 Dashboard/History/Reconciliation 정합화 결과

작성일: 2026-03-10  
작성자: Codex  
관련 계획서: `docs/work-plans/21-09_upbit_live_trading_dashboard_history_reconciliation_plan.md`  
상태: In Progress (Stage A 최소 데이터 계약 구현 완료)

---

## 0. 해결한 문제 정의
- 증상:
  - 현재 CoinPilot는 `PaperTradingExecutor` 중심 구조라, 실거래에서 필수인 거래소 계좌 스냅샷/주문 상태/체결 이력/정산 결과를 별도 원장으로 보존할 수 없었다.
- 영향:
  - Upbit 실거래 전환 시 Dashboard/History가 실제 거래소 상태를 그대로 보여줄 수 없고, DB 장부와 거래소 원장 불일치 시 신규 BUY 차단/정산/audit trail의 근거가 부족했다.
- 재현 조건:
  - `TRADING_MODE=live` 또는 `dry_run`으로 전환해 실주문 lifecycle을 다뤄야 하는 시점
- Root cause:
  - 기존 schema는 paper 장부(`account_state`, `positions`, `trading_history`)에 집중돼 있었고, exchange-level ledger 계층이 없었다.

## 1. 이번 Stage A 범위
1. 실거래 최소 데이터 계약 테이블 4종 추가
   - `exchange_account_snapshots`
   - `exchange_orders`
   - `exchange_fills`
   - `reconciliation_runs`
2. SQLAlchemy ORM 모델 추가
3. migration 파일 추가
4. baseline `deploy/db/init.sql` 동기화
5. 최소 회귀 테스트 추가

## 2. 구현 내용
### 2.1 거래소 계좌 스냅샷 원장 추가
- 파일:
  - `src/common/models.py`
  - `migrations/v3_3_5_upbit_live_trading_foundation.sql`
  - `deploy/db/init.sql`
- 변경 내용:
  - `exchange_account_snapshots` 테이블과 ORM 모델 추가
  - 자산 심볼별 `balance`, `locked`, `avg_buy_price`, `unit_currency`, `raw_payload` 보존
- 이유:
  - `account_state`는 paper 현금 1개 row 구조라, 실계좌 KRW/코인/잠금 잔고를 표현할 수 없기 때문

### 2.2 거래소 주문 원장 추가
- 파일:
  - `src/common/models.py`
  - `migrations/v3_3_5_upbit_live_trading_foundation.sql`
  - `deploy/db/init.sql`
- 변경 내용:
  - `exchange_orders` 테이블과 ORM 모델 추가
  - `exchange_order_id`, `client_order_id`, `state`, `requested/executed/remaining volume`, `fee`, `locked`, `raw_payload` 저장
  - `uq_exchange_orders_exchange_order_id` unique constraint 추가
- 이유:
  - `trading_history`는 전략 관점 trade log로는 충분하지만, pending/partial/cancelled order lifecycle audit에는 부족하기 때문

### 2.3 거래소 체결 원장 추가
- 파일:
  - `src/common/models.py`
  - `migrations/v3_3_5_upbit_live_trading_foundation.sql`
  - `deploy/db/init.sql`
- 변경 내용:
  - `exchange_fills` 테이블과 ORM 모델 추가
  - `exchange_trade_id`, `fill_price`, `fill_volume`, `fee`, `filled_at` 저장
- 이유:
  - 한 주문이 여러 fill로 나뉠 수 있어, 실제 체결 평균가/실현손익/수수료 계산을 fill 단위로 보존해야 하기 때문

### 2.4 정산 실행 이력 추가
- 파일:
  - `src/common/models.py`
  - `migrations/v3_3_5_upbit_live_trading_foundation.sql`
  - `deploy/db/init.sql`
- 변경 내용:
  - `reconciliation_runs` 테이블과 ORM 모델 추가
  - `mode`, `status`, `account/order/fill/portfolio mismatch count`, `details` 저장
- 이유:
  - 실거래 전환의 핵심 리스크는 전략보다 정산 불일치이므로, mismatch를 실행 단위로 남겨야 신규 BUY 차단/kill switch 근거를 수치화할 수 있기 때문

## 3. Before / After 정량 증빙
| 항목 | Before | After | 변화량 | 변화율(%) |
|---|---:|---:|---:|---:|
| 실거래 전용 exchange 원장 테이블 | 0 | 4 | +4 | N/A |
| 실거래 전용 ORM 모델 | 0 | 4 | +4 | N/A |
| 실거래 Stage A migration 파일 | 0 | 1 | +1 | N/A |
| Stage A 전용 회귀 테스트 | 0 | 3 passed | +3 | N/A |

## 4. 측정 기준
- 기간:
  - 2026-03-10 Stage A 정적 구현 검증
- 표본 수:
  - 신규 테스트 3건
- 성공 기준:
  - 신규 테이블/모델/constraint가 코드 기준으로 존재
  - baseline init과 migration 정의가 일치
  - 기존 paper schema를 제거하지 않고 실거래 기초 계층만 증분 추가
- 실패 기준:
  - ORM import 실패
  - migration/init syntax 불일치
  - unique constraint 또는 핵심 mismatch column 누락

## 5. 증빙 근거 (명령)
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/utils/test_live_trading_foundation_schema.py
python3 -m py_compile src/common/models.py
rg -n "exchange_account_snapshots|exchange_orders|exchange_fills|reconciliation_runs" src/common/models.py deploy/db/init.sql migrations/v3_3_5_upbit_live_trading_foundation.sql
```

## 6. 측정 불가 사유 / 대체 지표 / 추후 계획
- 측정 불가 사유:
  - 아직 live executor, Upbit API 호출, reconciliation job, Dashboard canonical view가 구현되지 않아 실거래 정합성은 운영 수치로 측정할 수 없다.
- 대체 지표:
  - schema/model/init/test 수준에서 데이터 계약 존재 여부와 naming consistency를 검증했다.
- 추후 계획:
  1. Stage B에서 `LiveTradingExecutor`와 `TRADING_MODE=dry_run|live` 추가
  2. 정산 잡과 exchange snapshot 수집 경로 구현
  3. Dashboard/History/Mobile API가 canonical portfolio view를 읽도록 확장

## 7. 리스크 / 가정 / 미확정 사항
- 리스크:
  - 현재 `trading_history`와 신규 exchange 원장의 연결 규칙(`trade <-> order/fill mapping`)은 아직 미정이므로, Stage B에서 명확한 link key가 필요하다.
- 가정:
  - Upbit 주문/체결 응답의 핵심 식별자는 `exchange_order_id`, `exchange_trade_id`로 충분하다.
- 미확정:
  - canonical portfolio를 별도 materialized view/table로 둘지, 정산 시 `positions/account_state`를 갱신할지는 Stage B/C에서 확정한다.

## 8. README / 체크리스트 동기화
- `README.md`:
  - 미반영
  - 사유: `21-09`는 아직 Stage A만 완료됐고, 실거래 기능 자체가 활성화되지 않았다.
- `remaining_work_master_checklist.md`:
  - 최근 업데이트 로그에 `21-09` 계획 분리 사실을 반영
  - 별도 main row 추가는 없음 (`21` 에픽의 하위 계획)
