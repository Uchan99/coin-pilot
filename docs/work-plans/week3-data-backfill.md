# Implementation Plan - Smart Data Backfill

## Problem
Currently, the `collector` only fetches the latest 1-minute candle. If the service is down for any period, that data gap remains permanently in the database, causing "empty charts" and affecting technical indicator calculations (e.g., MA, RSI).

## Proposed Changes

### `src/collector/main.py`
Modify `UpbitCollector` to include a `backfill` method.

#### 1. `get_last_candle_time()`
- Query the database to find the timestamp of the most recent saved candle.
- If no data exists, fetch a default amount (e.g., last 200 minutes).

#### 2. `backfill()` (Run on Startup)
- Calculate `delta = now(UTC) - last_candle_time`.
- If `delta > 1 minute`:
    - Calculate required `count` (minutes elapsed).
    - **Pagination Logic**: Loop to fetch all missing data in chunks of 200 (Upbit API Limit).
        - `while count > 0`: fetch `min(count, 200)`, save, reduce count.
    - **Safe Saving**: Use `ON CONFLICT DO NOTHING` (requires unique constraint) or check existence to prevent duplicates.

#### 3. Execution Flow
- Start -> **Run Backfill (with Pagination)** -> Enter Main Loop (1 min interval).

#### 4. Data Integrity (New)
- **Constraint**: Add `UNIQUE(symbol, interval, timestamp)` to `market_data` table to prevent duplicates during backfill or race conditions.

## Verification Plan
1. Stop collector.
2. Wait for 5 minutes (create a 5-minute gap).
3. Restart collector.
4. Verify in logs: `[*] Backfilling 5 missing candles...`
5. Check DB: Ensure no gaps in timestamps.

---

## Claude Code Review

**검토일:** 2026-01-26
**검토자:** Claude Code (Operator & Reviewer)

### ✅ 계획 대비 구현 상태

| 항목 | 계획 | 구현 | 상태 |
|------|------|------|------|
| `get_last_candle_time()` | DB에서 마지막 캔들 시간 조회 | ✓ 구현됨 (`main.py:20-30`) | ✅ |
| `backfill()` 시작 시 실행 | Start → Backfill → Main Loop | ✓ 구현됨 (`main.py:124`) | ✅ |
| 200개 이상 gap 시 루프 처리 | Loop to fetch all chunks | ✗ 미구현 (최대 200개만 fetch) | ⚠️ |

### 🔴 Critical: 데이터 무결성 (Data Integrity)

**문제:** `MarketData` 테이블에 `(symbol, interval, timestamp)` 조합에 대한 UNIQUE 제약이 없습니다.

```python
# main.py:72-74 주석에서도 인지됨
# TODO: Week 4에서 unique constraints 추가 필요.
```

**영향:**
- 동일 캔들이 중복 저장될 수 있음
- 기술 지표(MA, RSI) 계산 시 왜곡 발생 가능
- TimescaleDB 하이퍼테이블 쿼리 성능 저하

**권장 조치:**
```sql
ALTER TABLE market_data
ADD CONSTRAINT uq_market_data_symbol_interval_ts
UNIQUE (symbol, interval, timestamp);
```

### 🟡 Scalability (K8s 환경)

**문제:** 여러 Collector Pod가 동시에 시작되면, 모두 같은 gap을 감지하고 동시에 backfill 시도 가능

**권장 조치:**
- PostgreSQL Advisory Lock 사용
- 또는 Kubernetes Leader Election 패턴 적용
- 단기 해결: `ON CONFLICT DO NOTHING` 사용 (UNIQUE 제약 추가 후)

### 🟡 코드 품질

1. **Timezone 처리:** `datetime.utcnow()`는 Python 3.12+에서 deprecated. `datetime.now(timezone.utc)` 사용 권장 (`main.py:55`)

2. **Gap > 200 미처리:** 계획서에는 "loop to fetch all missing data in chunks"라고 명시되어 있으나, 현재 구현은 최대 200개만 fetch. 장기 다운타임 후 재시작 시 전체 gap이 채워지지 않음.

3. **에러 핸들링:** `backfill()` 함수에 try-except 블록 없음. API 장애 시 전체 startup 실패 가능.

### ✅ 긍정적 요소

- UTC 시간 처리에 대한 주석이 상세함 (`main.py:46-54`)
- 기존 데이터 없을 때 초기 200개 fetch 로직 적절
- 1분 이내 gap은 무시하는 로직 적절

### 📋 Week 4 이전 권장 작업

| 우선순위 | 작업 | 이유 |
|----------|------|------|
| P0 | UNIQUE 제약 추가 | 중복 데이터 방지 필수 |
| P1 | `ON CONFLICT DO NOTHING` 적용 | K8s 다중 Pod 안전성 |
| P2 | Gap > 200 루프 처리 | 장기 다운타임 대응 |

### 결론

계획서의 핵심 기능은 구현되었으나, **데이터 무결성 보장을 위한 UNIQUE 제약**이 반드시 추가되어야 합니다. 현재 상태로 프로덕션 배포 시 중복 데이터 이슈가 발생할 수 있습니다.
