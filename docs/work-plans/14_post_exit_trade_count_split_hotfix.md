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

## 3. 구현 범위

### 3.1 DB/모델 확장

**변경 내용**
- `daily_risk_state`에 컬럼 추가
  - `buy_count INTEGER DEFAULT 0 NOT NULL`
  - `sell_count INTEGER DEFAULT 0 NOT NULL`

**수정 파일**
- `src/common/models.py`
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
  - `Total Fills` (`trade_count` 또는 `buy_count + sell_count`)
- 기존 `Trade Count` 카드 문구를 의미가 명확한 형태로 교체

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

- `tests/engine/test_risk_manager_trade_counts.py` (신규)
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
