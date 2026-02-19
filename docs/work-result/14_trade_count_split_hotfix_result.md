# 14. 일일 거래 카운트 분리 핫픽스 구현 결과

**작성일**: 2026-02-19  
**작성자**: Codex (GPT-5)  
**관련 계획서**: `docs/work-plans/14_post_exit_trade_count_split_hotfix.md`

---

## 1. 개요

`daily_risk_state.trade_count` 단일 필드로 BUY/SELL/리스크 제한을 동시에 처리하던 구조를 분리하여,

1. 리스크 제한은 `buy_count` 기준
2. 운영 모니터링은 `buy_count`, `sell_count`, `total fills` 분리 표시

로 정렬했다.

핵심 목적이었던 **Overview 보유 상태와 Risk 탭 거래 카운트 불일치** 문제를 해소하는 방향으로 구현했다.

---

## 2. 구현 내용

### 2.1 모델 확장

- 파일: `src/common/models.py`
- 변경:
  - `DailyRiskState.buy_count` 추가 (`Integer`, default `0`, not null)
  - `DailyRiskState.sell_count` 추가 (`Integer`, default `0`, not null)

---

### 2.2 RiskManager 정책 분리

- 파일: `src/engine/risk_manager.py`
- 변경:
  1. `get_daily_state()` 신규 상태 생성 시 `buy_count=0`, `sell_count=0` 명시 초기화
  2. `check_order_validity()`의 일일 거래 제한 기준을 `trade_count` -> `buy_count`로 변경
  3. `update_after_trade(session, pnl, side="SELL")` 시그니처 확장
     - `side="BUY"`: `buy_count += 1`, `trade_count += 1` (PnL/연패 로직 미적용)
     - `side="SELL"`(기본): `sell_count += 1`, `trade_count += 1` + 기존 PnL/연패/쿨다운 로직 유지

---

### 2.3 Bot 호출 경로 수정

- 파일: `src/bot/main.py`
- 변경:
  1. SELL 성공 시: `update_after_trade(..., side="SELL")` 명시
  2. BUY 성공 시: `update_after_trade(session, Decimal("0"), side="BUY")` 추가

효과:
- BUY 체결만 발생하는 구간에서도 `buy_count`와 `trade_count`가 증가한다.

---

### 2.4 Risk 대시보드 표시 개선

- 파일: `src/dashboard/pages/3_risk.py`
- 변경:
  1. 리스크 제한 Progress/Metric 기준을 `trade_count` -> `buy_count`로 변경
  2. `BUY Fills`, `SELL Fills`, `Total Fills` 카드 추가
  3. `trade_count`와 `buy_count + sell_count` 불일치 시 경고 노출

효과:
- 운영자 관점에서 리스크 제한용 카운트(BUY)와 체결 활동량(BUY+SELL)을 동시에 확인 가능.

---

### 2.5 마이그레이션 추가

- 파일: `migrations/v3_2_1_trade_count_split.sql`
- 내용:
  - `daily_risk_state`에 `buy_count`, `sell_count` 컬럼 추가 (`IF NOT EXISTS`)

---

### 2.6 테스트 추가

- 파일: `tests/test_risk_manager_trade_counts.py`
- 케이스:
  1. BUY 업데이트 시 `buy_count`/`trade_count` 증가 검증
  2. SELL 업데이트 시 `sell_count`/`trade_count` 증가 + PnL 반영 검증
  3. `max_daily_trades`가 `buy_count` 기준으로 차단되는지 검증

---

## 3. 변경 파일 목록

1. `src/common/models.py`
2. `src/engine/risk_manager.py`
3. `src/bot/main.py`
4. `src/dashboard/pages/3_risk.py`
5. `migrations/v3_2_1_trade_count_split.sql`
6. `tests/test_risk_manager_trade_counts.py`

---

## 4. 검증 결과

### 4.1 정적 검증

실행:
```bash
python3 -m py_compile src/common/models.py src/engine/risk_manager.py src/bot/main.py src/dashboard/pages/3_risk.py tests/test_risk_manager_trade_counts.py
```

결과:
- 통과

### 4.2 테스트 실행

실행:
```bash
PYTHONPATH=. .venv/bin/pytest -q tests/test_risk_manager_trade_counts.py
```

결과:
- 환경 이슈로 실패 (로컬 PostgreSQL test DB 연결 timeout)
- 실패 원인: `tests/conftest.py`의 `coinpilot_test@localhost:5432` 접근 불가

판단:
- 코드/문법/경로 수준 구현은 완료
- 통합 테스트는 DB 접근 가능한 환경에서 재실행 필요

---

## 5. 배포/적용 체크리스트

1. 마이그레이션 적용
```bash
kubectl exec -i -n coin-pilot-ns db-0 -- psql -U postgres -d coinpilot < migrations/v3_2_1_trade_count_split.sql
```

2. bot/dashboard 재배포

3. 운영 검증
```sql
SELECT date, buy_count, sell_count, trade_count
FROM daily_risk_state
ORDER BY date DESC
LIMIT 1;
```

기대값:
- BUY 체결 후 `buy_count` 증가
- SELL 체결 후 `sell_count` 증가
- `trade_count`는 총 체결 수로 증가

4. Risk 탭 확인
- Buy Count 제한 표시 정상
- BUY/SELL/Total 카드 값 일치 확인
- 불일치 시 경고 노출 여부 확인

---

## 6. 결론

14번 핫픽스의 핵심 목표(카운트 의미 분리, 리스크 제한 기준 정렬, 대시보드 가시성 개선)를 코드 수준에서 구현 완료했다.

다음 단계는 클러스터 마이그레이션 적용 후 실거동 검증이며, 해당 결과를 기반으로 15번(매도 후 사후 분석 강화) 착수 시 데이터/리스크 지표 정합성을 더 안정적으로 유지할 수 있다.
