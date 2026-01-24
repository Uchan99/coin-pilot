# Week 2 Implementation Plan: Rule Engine & Risk Manager

> **작성일**: 2026-01-24 (Finalized)
> **목표**: 매매 전략(Rule Engine)과 리스크 관리(Risk Manager) 핵심 로직 구현 및 검증
> **Ref**: `PROJECT_CHARTER.md` Section 3 & 4

## 1. Goal Description
Week 2의 핵심 목표는 **"매매 판단의 뇌"**를 만드는 것입니다.
AI가 아닌 **Rule-Based 시스템**이 트레이딩의 핵심 의사결정(진입/청산)과 리스크 통제를 담당하도록 구현합니다.

## 2. User Review Required
> [!IMPORTANT]
> **전략 파라미터 확인**:
> *   **RSI Period**: 14 (진입 < 30, 청산 > 70)
> *   **Moving Average (Filter)**: **200일 일봉** 기준 (Daily MA).
>     *   *Note*: 장기 추세 확인을 위해 1분봉이 아닌 일봉 데이터를 사용합니다.
> *   **Bollinger Band**: 20일(20개 캔들), 2.0 표준편차.
> *   **Volume**: 20일 평균의 1.5배 이상.

> [!WARNING]
> **Hard-coded Risk Rules**:
> *   단일 종목 최대 비중: 5%
> *   계좌 일일 손실 한도: -5% (도달 시 당일 거래 중단)
> *   3연패 시 2시간 쿨다운 (DB에 상태 저장)

> [!WARNING]
> **백테스팅 주의사항**:
> *   이 전략은 과거 데이터로 검증되지 않았습니다.
> *   Week 2 완료 후 최소 3개월 과거 데이터로 백테스팅 수행을 강력히 권장합니다.

## 3. Proposed Changes

### A. Dependencies & Config
#### [MODIFY] [requirements.txt](file:///home/syt07203/workspace/coin-pilot/requirements.txt)
*   `numpy>=1.24.0`, `scipy>=1.10.0`, `pandas-ta>=0.3.14b` (순수 Python 지표 라이브러리)

### B. Common Utilities `src/common/`
#### [NEW] [indicators.py](file:///home/syt07203/workspace/coin-pilot/src/common/indicators.py)
*   `pandas-ta` 기반 지표 계산.
*   **Validation**: 데이터 개수 부족 시 `InsufficientDataError` 발생.

#### [MODIFY] [models.py](file:///home/syt07203/workspace/coin-pilot/src/common/models.py)
*   **TradingHistory 확장**: `strategy_name`, `signal_info` 필드 추가.
*   **State Persistence Tables** (Week 2에 마이그레이션 또는 `init.sql` 업데이트):
    ```python
    class DailyRiskState(Base):
        __tablename__ = "daily_risk_state"
        date = Column(Date, primary_key=True)
        total_pnl = Column(Numeric, default=0)
        trade_count = Column(Integer, default=0)
        consecutive_losses = Column(Integer, default=0)
        cooldown_until = Column(DateTime, nullable=True)
        is_trading_halted = Column(Boolean, default=False)
    
    class AccountState(Base):
        __tablename__ = "account_state"
        id = Column(Integer, primary_key=True)
        balance = Column(Numeric, nullable=False)
    
    class Position(Base):  # Stateless Pod 지원을 위해 DB 저장
        __tablename__ = "positions"
        symbol = Column(String, primary_key=True)
        quantity = Column(Numeric, nullable=False)
        avg_price = Column(Numeric, nullable=False)
    ```

### C. Rule Engine `src/engine/`
#### [NEW] [strategy.py](file:///home/syt07203/workspace/coin-pilot/src/engine/strategy.py)
*   `MeanReversionStrategy`:
    *   `check_entry_signal(candle)`: **모두(AND)** 만족 시 True 반환.
        1.  RSI < 30
        2.  Price > Daily MA(200) (일봉 데이터 조회 필요)
        3.  Price <= BB Lower
        4.  Volume > Avg Volume(20) * 1.5

#### [NEW] [risk_manager.py](file:///home/syt07203/workspace/coin-pilot/src/engine/risk_manager.py)
*   **Stateful**: `DailyRiskState` 테이블 CRUD.
*   `check_order_validity`: 일일 손실 한도 확인.
*   `update_trade_result`: 매매 종료 시 PnL 업데이트 및 3연패 쿨다운 설정.

#### [NEW] [executor.py](file:///home/syt07203/workspace/coin-pilot/src/engine/executor.py)
*   `PaperTradingExecutor`:
    *   **Balance Init**: DB `AccountState` 조회 -> 없으면 Env `PAPER_BALANCE` -> 기본값 1000만원.
    *   **Execution**: `Position` 테이블 업데이트, `TradingHistory` 기록.

### D. Verification Scripts `scripts/`
#### [NEW] [backfill_historical_data.py](file:///home/syt07203/workspace/coin-pilot/scripts/backfill_historical_data.py)
*   **Scope**: 최근 200일 치 **일봉(day)** 및 **1분봉(minute)** 데이터 수집.
*   **Rate Limit**: `asyncio.sleep(0.15)`로 초당 10회 제한 준수.

## 4. Verification Plan

### Automated Tests (`tests/`)
*   **Fixture (`tests/conftest.py`)**: `test_db` fixture를 사용하여 **In-Memory SQLite** 또는 별도 DB로 테스트 격리(Isolation) 보장.
*   **Scenarios**:
    *   `test_strategy.py`: 모든 조건(AND) 충족 시에만 진입 신호 발생 확인.
    *   `test_risk.py`: 손실 한도 초과 시 주문 거부 확인.

## 5. Week 2 Implementation Checklist
**구현 완료 기준** (Claude Code Review 반영):
- [ ] `src/common/indicators.py` 작성 (RSI, BB, MA, Vol)
- [ ] `src/common/models.py` 업데이트 (DailyRiskState, AccountState, Position)
- [ ] Week 1 `init.sql` 업데이트 또는 마이그레이션 수행
- [ ] `src/engine/strategy.py` 구현 (AND 조건 명시)
- [ ] `src/engine/risk_manager.py` 구현 (DB 상태 연동)
- [ ] `src/engine/executor.py` 구현 (PaperTrading, 잔고 관리)
- [ ] `scripts/backfill_historical_data.py` 작성 (Rate limit)
- [ ] `tests/` 구조 생성 및 `conftest.py` (DB Isolation) 작성
- [ ] Unit Tests 작성 및 Pass
- [ ] `scripts/simulate_strategy.py` 수동 검증 수행

---

## Claude Code Review (2nd Verification) - Status
**검토일:** 2026-01-24
**상태:** ✅ **Plan Updated & Approved** (위 계획에 모든 피드백 반영됨)

### Actioned Items:
- [x] **DailyRiskState Schema**: Defined in Section 3.B.
- [x] **MA(200) Calculation**: Clarified usage of Daily candles in Section 2 & 3.C.
- [x] **Paper Trading Balance**: Defined priority (DB > Env) in Section 3.C.
- [x] **Positions Persistence**: Added `Position` table for Stateless/K8s support.
- [x] **Rate Limiting**: Added to `backfill_historical_data.py` plan.
- [x] **Test Isolation**: Added `conftest.py` with in-memory DB plan.
- [x] **Strategy Logic**: Clarified AND logic for entry signals.

---

## Claude Code Final Approval

**검토일:** 2026-01-24
**검토자:** Claude Code (Operator & Reviewer)
**상태:** ✅ **최종 승인 (APPROVED FOR IMPLEMENTATION)**

---

### 1. 최종 검증 결과

#### 1.1 계획서 품질 평가 ✅

본 Week 2 계획서는 **3차 리뷰를 거쳐** 다음 기준을 모두 충족했습니다:

| 평가 항목 | 상태 | 비고 |
|:---|:---:|:---|
| PROJECT_CHARTER 정합성 | ✅ | Rule-Based 시스템 철학 준수 |
| 기술 스택 일관성 | ✅ | pandas-ta, PostgreSQL, FastAPI |
| 데이터 모델 완전성 | ✅ | 3개 신규 테이블 스키마 정의 완료 |
| K8s 확장성 고려 | ✅ | Stateless Pod 설계 (Position DB 저장) |
| 테스트 전략 명확성 | ✅ | Unit Test + 수동 시뮬레이션 |
| 구현 범위 명확성 | ✅ | 10개 체크리스트 항목 명시 |
| 리스크 관리 설계 | ✅ | 상태 영속화, 쿨다운, 손실 한도 |

---

### 2. Critical Issues 해결 확인 ✅

1차 및 2차 리뷰에서 지적된 **모든 Critical Issues가 해결**되었습니다:

#### 2.1 DailyRiskState 스키마 정의 ✅
- **위치:** 섹션 3.B (라인 46-53)
- **평가:** 모든 필수 컬럼 포함 (date, total_pnl, trade_count, consecutive_losses, cooldown_until, is_trading_halted)

#### 2.2 MA(200) 일봉 기준 명확화 ✅
- **위치:** 섹션 2 (라인 15-16), 섹션 3.C (라인 72)
- **평가:** "200일 일봉 기준 (Daily MA)" 명시, 1분봉과 혼동 방지

#### 2.3 PaperTradingExecutor 초기 잔고 설정 ✅
- **위치:** 섹션 3.C (라인 83)
- **평가:** 우선순위 명확 (DB → Env → 기본값 1000만원)

#### 2.4 Position 영속화 (K8s Stateless) ✅
- **위치:** 섹션 3.B (라인 60-64)
- **평가:** Stateless Pod 설계로 K8s Deployment 사용 가능

#### 2.5 Upbit API Rate Limit 대응 ✅
- **위치:** 섹션 3.D (라인 89)
- **평가:** `asyncio.sleep(0.15)` 명시 (초당 6.67회, 한도 10회 이하)

#### 2.6 테스트 격리 전략 ✅
- **위치:** 섹션 4 (라인 94)
- **평가:** In-Memory SQLite 또는 별도 DB 사용 명시

#### 2.7 진입 조건 AND 로직 ✅
- **위치:** 섹션 3.C (라인 70-74)
- **평가:** "모두(AND) 만족" 명시, 4개 조건 나열

---

### 3. 프로젝트 현황 대조 분석

#### 3.1 기존 인프라 확인 ✅

현재 Week 1에서 구축된 인프라:
- [deploy/db/init.sql](deploy/db/init.sql): TimescaleDB, pgvector, 4개 테이블
- [deploy/docker-compose.yml](deploy/docker-compose.yml): PostgreSQL 15 + TimescaleDB
- [src/common/models.py](src/common/models.py): 4개 ORM 모델
- [src/collector/main.py](src/collector/main.py): Upbit 1분봉 수집기

#### 3.2 Week 2 추가 필요 사항

**A. 데이터베이스 스키마 추가 (3개 테이블)**
1. **daily_risk_state**: 일일 리스크 상태 추적
2. **account_state**: Paper Trading 잔고 관리
3. **positions**: 포지션 영속화 (K8s Stateless)

**B. TradingHistory 테이블 확장**
- `strategy_name VARCHAR(50)`: 전략 이름
- `signal_info JSONB`: 진입 당시 지표 값

**C. 의존성 추가**
- `numpy>=1.24.0`
- `scipy>=1.10.0`
- `pandas-ta>=0.3.14b`

---

### 4. 구현 전 준비 사항 (Action Items)

Week 2 구현을 시작하기 **전에** 다음 작업을 완료하세요:

#### 🔴 Mandatory (필수)

**A. `deploy/db/init.sql` 업데이트**
```sql
-- 아래 테이블들을 init.sql 하단에 추가
CREATE TABLE IF NOT EXISTS daily_risk_state (
    date DATE PRIMARY KEY,
    total_pnl NUMERIC(20, 8) DEFAULT 0 NOT NULL,
    trade_count INTEGER DEFAULT 0 NOT NULL,
    consecutive_losses INTEGER DEFAULT 0 NOT NULL,
    cooldown_until TIMESTAMP WITH TIME ZONE,
    is_trading_halted BOOLEAN DEFAULT FALSE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS account_state (
    id SERIAL PRIMARY KEY,
    balance NUMERIC(20, 8) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 초기 잔고 1000만원 설정
INSERT INTO account_state (id, balance) VALUES (1, 10000000.0)
ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS positions (
    symbol VARCHAR(20) PRIMARY KEY,
    quantity NUMERIC(20, 8) NOT NULL,
    avg_price NUMERIC(20, 8) NOT NULL,
    opened_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**B. `trading_history` 테이블 컬럼 추가**
```sql
-- init.sql의 trading_history CREATE 문에 추가
-- 또는 별도 ALTER 문 실행
ALTER TABLE trading_history ADD COLUMN IF NOT EXISTS strategy_name VARCHAR(50);
ALTER TABLE trading_history ADD COLUMN IF NOT EXISTS signal_info JSONB;
CREATE INDEX IF NOT EXISTS idx_trading_history_strategy ON trading_history (strategy_name);
```

**C. `requirements.txt` 업데이트**
```txt
numpy>=1.24.0
scipy>=1.10.0
pandas-ta>=0.3.14b
```

**D. `src/common/models.py` 업데이트**
- 3개 ORM 모델 추가 (DailyRiskState, AccountState, Position)
- TradingHistory에 2개 필드 추가

---

### 5. 구현 우선순위 (Implementation Order)

다음 순서로 구현하는 것을 **강력히 권장**합니다:

**Phase 1: Foundation (주 초반)**
1. DB 스키마 업데이트 (`init.sql`, `models.py`)
2. 의존성 설치 (`requirements.txt`)
3. `indicators.py` 작성 (RSI, BB, MA, Volume)
4. `backfill_historical_data.py` 작성 및 과거 데이터 수집

**Phase 2: Core Logic (주 중반)**
5. `strategy.py` 작성 (MeanReversionStrategy)
6. `risk_manager.py` 작성 (DB 연동)
7. `executor.py` 작성 (PaperTradingExecutor)

**Phase 3: Testing & Verification (주 후반)**
8. `tests/` 구조 생성 및 `conftest.py`
9. Unit Tests 작성 (`test_indicators.py`, `test_strategy.py`, `test_risk.py`)
10. `simulate_strategy.py` 작성 및 수동 검증

---

### 6. 잠재적 이슈 및 대응 방안

#### 6.1 pandas-ta 설치 실패 가능성
**문제:** pandas-ta는 활발히 업데이트되지 않는 라이브러리입니다.
**대응:**
```bash
# 설치 실패 시 대안
pip install ta  # Technical Analysis Library in Python
```

#### 6.2 MA(200) 계산 시 데이터 부족
**문제:** backfill 전에 전략 실행 시 일봉 데이터가 200개 미만일 수 있습니다.
**대응:**
```python
# indicators.py에서 예외 처리
if len(daily_candles) < 200:
    raise InsufficientDataError(f"Need 200 daily candles, got {len(daily_candles)}")
```

#### 6.3 Position 테이블 동시성 문제
**문제:** 여러 Pod가 동시에 같은 symbol의 Position을 업데이트할 수 있습니다.
**대응:**
```python
# executor.py에서 트랜잭션 격리
async with session.begin():
    position = await session.execute(
        select(Position).where(Position.symbol == symbol).with_for_update()
    )
```

---

### 7. 최종 승인 조건 충족 확인

| 승인 조건 | 충족 여부 | 근거 |
|:---|:---:|:---|
| 모든 Critical Issues 해결 | ✅ | 섹션 2 참고 |
| 스키마 정의 완전성 | ✅ | 3개 테이블 스키마 명시 |
| 기술 스택 일관성 | ✅ | pandas-ta, PostgreSQL |
| K8s 확장성 고려 | ✅ | Stateless Pod 설계 |
| 테스트 전략 명확성 | ✅ | Unit + 수동 시뮬레이션 |
| 구현 체크리스트 제공 | ✅ | 10개 항목 (섹션 5) |
| PROJECT_CHARTER 정합성 | ✅ | Rule-Based 철학 준수 |
| 문서 가독성 | ✅ | 섹션 구조, 코드 블록 |

---

### 8. 최종 결론

**✅ Week 2 Implementation Plan이 최종 승인되었습니다.**

이 계획서는:
- **3차 리뷰를 거쳐** 모든 Critical Issues가 해결되었으며,
- **PROJECT_CHARTER v3.0**의 설계 철학을 충실히 따르고,
- **실무적 구현 가능성**과 **K8s 확장성**을 모두 고려한,
- **Week 3(AI Integration)**로 자연스럽게 이어질 수 있는

**프로덕션 수준의 구현 계획서**입니다.

---

### 9. 다음 단계 (Next Steps)

**즉시 진행 가능:**
1. 섹션 4의 "구현 전 준비 사항" 필수 항목 완료
2. Phase 1 (Foundation) 착수: DB 스키마 업데이트 및 의존성 설치
3. `backfill_historical_data.py` 작성 및 과거 데이터 수집

**구현 완료 후:**
1. 섹션 5의 체크리스트 10개 항목 모두 체크
2. `simulate_strategy.py` 로그에서 `ENTRY`, `EXIT`, `RISK_REJECT` 확인
3. Week 2 완료 보고서 작성 (성공/실패 패턴 분석 포함)

---

**Approved by:** Claude Code (Sonnet 4.5)
**Approval Date:** 2026-01-24
**Status:** ✅ **READY FOR IMPLEMENTATION**

---

**Antigravity에게:**
위 계획서대로 구현을 진행해 주세요. 구현 중 불명확한 부분이나 예상치 못한 이슈가 발생하면, 즉시 Claude Code에게 검토를 요청해 주세요.

**성공적인 Week 2 구현을 기원합니다! 🚀**
