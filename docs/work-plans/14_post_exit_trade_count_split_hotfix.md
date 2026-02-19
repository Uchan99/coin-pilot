# 14. 일일 거래 카운트 분리 핫픽스 계획

**작성일**: 2026-02-19  
**상태**: Draft (Hotfix)  
**우선순위**: P0 (즉시 적용 권장)

---

## 1. 배경 및 문제 정의

현재 `daily_risk_state.trade_count`는 아래 2개 목적에 동시에 사용되고 있다.

1. 리스크 제한: `MAX_DAILY_TRADES` 상한 체크  
2. 대시보드 표시: 당일 거래 활동량 표시

하지만 현재 구현은 `SELL` 완료 시에만 `trade_count`를 증가시켜, 다음 문제가 발생한다.

- Overview에는 보유 포지션(BUY 체결)이 보이는데 Risk 탭 `Trade Count`는 0으로 표시
- 일일 거래 제한이 BUY 기준으로 제대로 작동하지 않을 수 있음

핫픽스 목표는 "리스크 통제 기준"과 "운영 가시성 지표"를 분리하는 것이다.

---

## 2. 목표

1. `buy_count`, `sell_count`를 분리 저장한다.  
2. 리스크 제한(`MAX_DAILY_TRADES`)은 `buy_count` 기준으로 적용한다.  
3. Risk 대시보드는 `BUY/SELL/총 체결`을 동시에 표시한다.  
4. 기존 `trade_count`는 하위 호환 필드로 유지한다.

---

## 2.5 기술 스택 선택 이유 및 대안 비교

### 선택 기술
- PostgreSQL 스키마 확장(`daily_risk_state` 컬럼 추가)
- SQLAlchemy 모델 확장
- 기존 RiskManager/Bot/Dashboard 경로 수정

### 선택 이유
1. 현재 운영 데이터와 코드 경로를 그대로 활용해 핫픽스 반영 속도가 가장 빠름
2. 신규 인프라 도입 없이 정합성 문제를 해결 가능
3. 롤백이 단순함(코드/컬럼 단위)

### 대안 비교
1. `trade_count`만 유지하고 BUY/SELL 모두 카운트
- 장점: 구현 단순
- 단점: 리스크 제한 용도(BUY)와 운영 가시성 용도(BUY+SELL)를 분리할 수 없음

2. 별도 집계 테이블 신설
- 장점: 분석 확장성 높음
- 단점: 핫픽스 범위를 초과하며 마이그레이션/동기화 복잡도 증가

---

## 3. 구현 범위

### 3.1 DB/모델 확장

**변경 내용**
- `daily_risk_state`에 컬럼 추가
  - `buy_count INTEGER DEFAULT 0 NOT NULL`
  - `sell_count INTEGER DEFAULT 0 NOT NULL`
- `get_daily_state()` 신규 레코드 생성 경로에서 `buy_count=0`, `sell_count=0` 명시 초기화

**수정 파일**
- `src/common/models.py`
- `src/engine/risk_manager.py`
- `migrations/v3_2_1_trade_count_split.sql` (신규)

**완료 기준**
- 신규 컬럼이 생성되고 기존 데이터는 0으로 안전 초기화됨.

---

### 3.2 RiskManager 카운트 정책 분리

**변경 내용**
- `check_order_validity()`의 일일 거래 제한 체크를 `trade_count` → `buy_count`로 전환
- `update_after_trade(session, pnl, side="SELL")`로 시그니처 확장(하위 호환):
  - `side="BUY"`: `buy_count += 1`, `trade_count += 1`
  - `side="SELL"`: `sell_count += 1`, `trade_count += 1`, 기존 PnL/연패 로직 유지

**수정 파일**
- `src/engine/risk_manager.py`

**완료 기준**
- 일일 거래 제한이 BUY 체결 횟수 기준으로 동작.

---

### 3.3 Bot 호출 경로 보정

**변경 내용**
- BUY 성공 시 `update_after_trade(session, pnl=0, side="BUY")` 호출 추가
- SELL 성공 시 기존 호출을 `update_after_trade(session, pnl=<실손익>, side="SELL")`로 변경

**수정 파일**
- `src/bot/main.py`

**완료 기준**
- BUY만 발생해도 `daily_risk_state.buy_count`와 `trade_count`가 증가.

---

### 3.4 Risk 대시보드 표시 개선

**변경 내용**
- `3_risk.py`에서 다음 지표 표시
  - `Buy Count (today)`
  - `Sell Count (today)`
  - `Total Fills` (표시 기준: `buy_count + sell_count` 우선, `trade_count`는 하위 호환/검증용)
- 기존 `Trade Count` 카드 문구를 의미가 명확한 형태로 교체
- 정합성 점검: `trade_count != buy_count + sell_count`일 때 경고 배지 또는 점검 로그 노출

**수정 파일**
- `src/dashboard/pages/3_risk.py`

**완료 기준**
- 포지션 보유 중(BUY 체결) 상황에서 Risk 탭 카운트 불일치가 해소됨.

---

## 4. 마이그레이션 계획

신규 SQL: `migrations/v3_2_1_trade_count_split.sql`

```sql
ALTER TABLE daily_risk_state ADD COLUMN IF NOT EXISTS buy_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE daily_risk_state ADD COLUMN IF NOT EXISTS sell_count INTEGER NOT NULL DEFAULT 0;

-- 선택: 기존 데이터 보정 (정확한 과거 BUY/SELL 복원이 어렵다면 0 유지)
-- UPDATE daily_risk_state SET buy_count = 0 WHERE buy_count IS NULL;
-- UPDATE daily_risk_state SET sell_count = 0 WHERE sell_count IS NULL;
```

적용 예시:
```bash
kubectl exec -i -n coin-pilot-ns db-0 -- psql -U postgres -d coinpilot < migrations/v3_2_1_trade_count_split.sql
```

---

## 5. 검증 계획

### 5.1 코드/테스트

- `tests/test_risk_manager_trade_counts.py` (신규, 현행 테스트 트리 구조 기준)
  - BUY 호출 시 `buy_count`, `trade_count` 증가
  - SELL 호출 시 `sell_count`, `trade_count` 증가
  - `MAX_DAILY_TRADES`가 `buy_count` 기준으로 차단되는지 검증

### 5.2 운영 검증

1. BUY 1회 후:
```sql
SELECT date, buy_count, sell_count, trade_count
FROM daily_risk_state
ORDER BY date DESC
LIMIT 1;
```

기대값:
- `buy_count >= 1`
- `sell_count` 변화 없음
- `trade_count >= buy_count`

2. SELL 1회 후:
- `sell_count` 증가 확인
- Risk 탭에서 BUY/SELL/총 체결 지표 일치 확인

---

## 6. 롤백 계획

1. 코드 롤백: `kubectl rollout undo deployment/bot -n coin-pilot-ns` 및 dashboard 롤백  
2. DB 롤백(필요 시):
```sql
ALTER TABLE daily_risk_state DROP COLUMN IF EXISTS buy_count;
ALTER TABLE daily_risk_state DROP COLUMN IF EXISTS sell_count;
```

주의: 컬럼 삭제 롤백은 데이터 손실이 있으므로 긴급 상황에서만 수행.

---

## 7. 산출물

1. `migrations/v3_2_1_trade_count_split.sql`
2. `src/common/models.py` 업데이트
3. `src/engine/risk_manager.py` 업데이트
4. `src/bot/main.py` 업데이트
5. `src/dashboard/pages/3_risk.py` 업데이트
6. 테스트 코드 및 `docs/work-result/14_trade_count_split_hotfix_result.md`

---

## Claude Code Review

**검증일**: 2026-02-19
**검증 기준**: 현행 코드 대비 계획 정합성, 구현 가능성, 리스크

### 코드 크로스 체크 결과

| # | 항목 | 판정 | 비고 |
|---|------|------|------|
| 1 | `DailyRiskState` 모델에 `buy_count`/`sell_count` 미존재 확인 | ✅ 확인 | 현재 `trade_count`, `consecutive_losses`, `cooldown_until`, `is_trading_halted`, `total_pnl`만 존재 (models.py:87-100) |
| 2 | `update_after_trade()` 시그니처 확장 (`side` 파라미터) | ✅ 타당 | 현재 `(session, pnl)` → `(session, pnl, side="SELL")` 하위 호환 유지. risk_manager.py:235 |
| 3 | `check_order_validity()`에서 `trade_count` 기준 제한 | ✅ 확인 | L170: `state.trade_count >= self.max_daily_trades` → `buy_count`로 전환 필요 |
| 4 | `update_after_trade` 호출이 SELL 시에만 존재 | ✅ 확인 | bot/main.py:247 — BUY 성공 시 호출 없음. 계획대로 BUY 경로 추가 필요 |
| 5 | `trade_count` 하위 호환 유지 | ✅ 타당 | BUY/SELL 모두 `trade_count += 1` 동시 증가로 기존 대시보드 호환 |
| 6 | 마이그레이션 SQL | ✅ 안전 | `ADD COLUMN IF NOT EXISTS` + `DEFAULT 0` — 무중단 적용 가능 |

### Major Findings

없음. 핫픽스 범위가 명확하고 구현 경로가 정확히 식별되어 있음.

### Minor Findings

1. **`get_daily_state()` 초기화 경로** (risk_manager.py:72): 새 DailyRiskState 생성 시 `buy_count=0`, `sell_count=0` 초기값도 명시해야 함. 모델 default가 있더라도 명시적 초기화 권장.

2. **`trade_count` 정합성 보장**: `buy_count + sell_count`와 `trade_count`가 불일치할 가능성이 있음 (예: 수동 DB 수정, 과거 데이터). 대시보드에서 `Total Fills`를 `trade_count` vs `buy_count + sell_count` 중 어느 것을 표시할지 명확히 결정 필요.

3. **테스트 파일 위치**: 계획서에 `tests/engine/test_risk_manager_trade_counts.py`로 되어 있으나, 기존 테스트 구조(`tests/` 하위)와 일치하는지 확인 필요.

### 종합 판정: **PASS** ✅

P0 핫픽스로서 범위가 적절하고, 기존 코드 경로 분석이 정확함. 구현 진행 가능.

### 리뷰 반영 결정 (2026-02-19)

1. `get_daily_state()` 초기화 경로 명시: **반영 완료** (`3.1` 보강)
2. `trade_count` 정합성/표시 기준 명확화: **반영 완료** (`3.4` 보강)
3. 테스트 파일 경로 구조 정합화: **반영 완료** (`5.1` 경로 수정)

### Round 2 최종 검증 (2026-02-19)

**판정: APPROVED** ✅ — 미해결 항목 없음. 구현 착수 가능.

- Minor 3건 모두 계획서 본문에 반영 확인 완료
  - `get_daily_state()` 초기화 명시 (3.1:L65)
  - `Total Fills` 표시 기준 + 정합성 점검 로직 (3.4:L113-115)
  - 테스트 경로 `tests/test_risk_manager_trade_counts.py` (5.1:L149)
