# CoinPilot 프로젝트: 주요 시행착오와 해결 과정

**작성일**: 2026-02-15  
**작성자**: 허유찬  
**프로젝트**: CoinPilot v3.0 - Kubernetes 기반 실시간 암호화폐 거래 시스템

---

## 🎯 프로젝트 개요

CoinPilot은 "Reaction over Prediction" 철학을 기반으로 한 **Rule-Based 트레이딩 엔진 + AI Assistant** 아키텍처의 암호화폐 자동 매매 시스템입니다.

**핵심 기술 스택**: Python, FastAPI, PostgreSQL (asyncpg), Redis, Kubernetes (Minikube), LangGraph, APScheduler  
**개발 기간**: 8주 (2026년 1월 ~ 2월)  
**배포 환경**: Kubernetes 클러스터 (다중 Pod 환경)  
**시스템 규모**: 5개 마이크로서비스, 초당 10건 시장 데이터 수집, 수십 개 알림 워크플로우

---

## 🔥 가장 큰 시행착오 TOP 3

### 1. 분산 시스템 동시성 제어 실패 (Race Condition)
**난이도**: ⭐⭐⭐⭐⭐ | **심각도**: 🔴 CRITICAL (자금 손실 가능)

#### 📌 문제 상황
Kubernetes HPA(Horizontal Pod Autoscaler) 환경에서 여러 Pod가 동시에 같은 종목을 매매할 때 **포지션 데이터 덮어쓰기(Lost Update)** 발생.

**재현 시나리오**:
```
[Pod A] SELECT Position (qty=10) → 계산 (10+5=15) → UPDATE qty=15
        ↓ (동시 진행)
[Pod B] SELECT Position (qty=10) → 계산 (10+3=13) → UPDATE qty=13  ❌ Pod A의 업데이트 덮어쓰기!
        
최종 결과: qty=13 (기대값: 18) → 5 BTC 매수가 증발
```

#### 🔍 근본 원인 분석

**기술적 원인**:
1. **Non-Atomic Check-Then-Act 패턴**: `SELECT → Calculate → UPDATE`가 분리됨
2. **PostgreSQL READ COMMITTED 격리 수준**: 다른 트랜잭션의 변경사항을 즉시 반영 (일관성 보장 안 됨)
3. **No Row-Level Locking**: 동시 UPDATE 허용

**왜 K8s에서 더 심각한가?**
- HPA로 부하 시 자동으로 Pod 복제 (최대 10개)
- Load Balancer가 요청을 여러 Pod에 분산
- 네트워크 지연으로 Race Condition 확률 증가

#### ✅ 해결 과정

**1단계: 문제 발견**
- Claude Code의 Implementation Review 과정에서 동시성 이슈 사전 검토 중 발견
- 실제 프로덕션 배포 전이라 피해 없음

**2단계: 솔루션 연구**
3가지 대안을 비교 분석:

| 방법 | 정확성 | 성능 | 복잡도 | 선택 |
|------|--------|------|--------|------|
| Pessimistic Locking (FOR UPDATE) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ✅ 채택 |
| Optimistic Locking (Version) | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ❌ |
| REPEATABLE READ Isolation | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ❌ |

**3단계: Pessimistic Locking 구현**

```python
# Before (위험한 코드)
stmt = select(Position).where(Position.symbol == symbol)
existing_pos = await session.execute(stmt)  # ❌ No Lock

# After (안전한 코드)
stmt = select(Position).where(Position.symbol == symbol).with_for_update()
existing_pos = await session.execute(stmt)  # ✅ Exclusive Lock
# 다른 트랜잭션은 여기서 대기 (Lock이 풀릴 때까지)
```

**PostgreSQL에서의 동작**:
```sql
BEGIN;
SELECT * FROM positions WHERE symbol = 'KRW-BTC' FOR UPDATE;  -- 이 시점에 Row Lock 획득
-- 다른 트랜잭션이 같은 행을 FOR UPDATE 하면 WAITING 상태
UPDATE positions SET quantity = 15;
COMMIT;  -- Lock 해제, 대기 중인 트랜잭션 재개
```

**4단계: 동시성 테스트 작성**

```python
async def test_concurrent_buy_orders():
    """10개의 동시 매수 주문 시 포지션 정확성 검증"""
    tasks = [buy_order(session, qty=i) for i in range(1, 11)]
    await asyncio.gather(*tasks)
    
    # 검증: 총 수량 = 1+2+...+10 = 55
    final_pos = await get_position(session, "KRW-BTC")
    assert final_pos["quantity"] == Decimal("55")  # ✅ Race Condition 없음
```

#### 💡 배운 점

1. **분산 시스템 설계 원칙**: "돈과 관련된 코드는 항상 Lock을 먼저 생각하라"
2. **격리 수준 이해**: READ COMMITTED vs REPEATABLE READ vs SERIALIZABLE
3. **Pre-production Review의 중요성**: 코드 리뷰로 프로덕션 배포 전 발견하여 실제 자금 손실 방지

**영향**: 재무 데이터 무결성 보장, K8s 환경에서 안전한 수평 확장 가능

---

### 2. 비동기 데이터베이스 테스트 환경 구축 실패
**난이도**: ⭐⭐⭐⭐ | **심각도**: 🔴 CRITICAL (테스트 불가능)

#### 📌 문제 상황
`pytest-asyncio` 기반 DB 테스트 실행 시 2개 이상의 테스트가 연속 실행되면 실패:

```python
FAILED tests/test_risk_manager.py::test_cooldown_enforcement
sqlalchemy.exc.InterfaceError: (asyncpg.exceptions.InterfaceError)
cannot perform operation: another operation is in progress
```

**재현 조건**:
- 단일 테스트: ✅ 통과
- 연속 테스트 (2개 이상): ❌ 실패

#### 🔍 근본 원인 분석

**기술 스택 특성**:
- **SQLAlchemy AsyncEngine**: 기본적으로 `QueuePool` 사용 (pool_size=5, max_overflow=10)
- **asyncpg 드라이버**: 한 번에 **하나의 operation만 허용** (strict single-operation enforcement)
- **pytest-asyncio**: 각 테스트 종료 시 `await session.rollback()` 호출

**충돌 발생 타임라인**:
```
Test 1: SELECT ... → (session.rollback 시작) → [Connection을 Pool에 반환]
                  ↓ (비동기 rollback 진행 중)
Test 2: (Pool에서 같은 Connection 획득) → SELECT ... 
        → ❌ InterfaceError: another operation is in progress
```

**왜 발생하나?**
- 이전 트랜잭션의 롤백이 완전히 종료되기 전에 Pool에서 같은 연결을 재사용
- asyncpg의 엄격한 동시성 제어와 SQLAlchemy의 Connection Pool 재사용이 충돌

#### ✅ 해결 과정

**1단계: 가설 검증**
```python
# 가설 1: scope="function"으로 변경하면 해결되나?
# → 테스트 속도 50% 느려짐 (매번 스키마 재생성)

# 가설 2: pool_pre_ping=True로 연결 유효성 검사?
# → 근본 해결 안 됨 (여전히 간헐적 실패)

# 가설 3: NullPool로 Connection Pool 비활성화?
# → ✅ 완벽히 해결!
```

**2단계: NullPool 적용**

```python
# tests/conftest.py
from sqlalchemy import pool

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=pool.NullPool  # ✅ Connection Pooling 비활성화
    )
    # NullPool 동작:
    # - 연결 요청: 새로운 DB 연결 생성
    # - 연결 종료: 즉시 Close (Pool에 보관 안 함)
    # - 매번 Fresh Connection 보장
```

**3단계: 환경별 전략 수립**

| 환경 | Pool 전략 | 이유 |
|------|-----------|------|
| 테스트 | `NullPool` | 격리성 우선 (테스트 간 완전 독립) |
| 프로덕션 | `QueuePool` | 성능 우선 (연결 재사용) |

#### 💡 배운 점

1. **비동기 라이브러리 제약 이해**: asyncpg의 single-operation enforcement는 문서화된 제약사항
2. **테스트 환경 설계 원칙**: 성능 < 격리성 < 신뢰성
3. **트레이드오프 의사결정**: 테스트 실행 시간 10% 증가 vs 100% 안정성

**성능 영향**:
- 테스트 실행 시간: 약 10% 증가 (연결 생성 오버헤드)
- 프로덕션 코드: 영향 없음 (테스트 환경에만 적용)

**영향**: 15개 비동기 DB 테스트 안정화, CI/CD 파이프라인 차단 해제

---

### 3. 전략 로직과 테스트 시나리오 불일치 (Strategy Testing)
**난이도**: ⭐⭐⭐⭐ | **심각도**: 🟡 MEDIUM (백테스팅 신뢰도 저하)

#### 📌 문제 상황
Mean Reversion 전략의 진입 조건 테스트 실패:

```python
async def test_mean_reversion_entry_signal(test_db, candle_data_for_entry):
    strategy = MeanReversionStrategy()
    indicators = get_all_indicators(candle_data_for_entry)
    
    # RSI < 30이고 BB 하단 터치 시나리오에서 진입 신호 기대
    assert strategy.check_entry_signal(indicators) == True
    
# 실제 결과
AssertionError: assert False == True
```

**디버깅 로그**:
```
RSI: 28.5 ✅ (< 30 만족)
BB Lower: 18500, Current Price: 18200 ✅ (<= BB Lower 만족)
Volume Ratio: 2.3 ✅ (> 1.5 만족)
MA(200): 21500, Price: 18200 ❌ (Price > MA(200) 조건 위반)
→ Entry Signal: False (Trend Filter 불통과)
```

#### 🔍 근본 원인 분석

**전략 철학 vs 테스트 시나리오 미스매치**:

```python
# 전략 진입 조건 (모두 AND)
def check_entry_signal(self, indicators: Dict) -> bool:
    is_rsi_low = indicators["rsi"] < 30           # 과매도
    is_above_trend = indicators["close"] > indicators["ma_200"]  # 장기 상승 추세
    is_bb_low = indicators["close"] <= indicators["bb_lower"]    # BB 하단
    is_vol_surge = indicators["vol_ratio"] > 1.5                 # 거래량 급증
    
    return is_rsi_low and is_above_trend and is_bb_low and is_vol_surge
```

**전략 의도**: "상승 추세 내에서 일시적 과매도 구간 매수" (Bull Market Pullback)

**테스트가 만든 시나리오**: "하락 추세에서의 과매도" (Bear Market Crash)
```python
# 잘못된 테스트 픽스처
base_price = 50000
# 초반 200분: 횡보 (MA 200 ≈ 50,000)
# 이후 99분: 급락 (50,000 → 18,000, 64% 하락)
# 결과: Current Price (18,000) < MA(200) (44,000) → Trend Filter 불통과
```

**문제점**:
1. RSI를 30 미만으로 만들기 위해 과도한 하락폭 설정 (64%)
2. MA(200)은 느리게 반응하는 지표라 급락 후에도 한동안 높은 값 유지
3. 한 조건(RSI)을 만족시키려다 다른 조건(Trend Filter)을 깨뜨림

#### ✅ 해결 과정

**1단계: 전략 철학 재확인**
- Mean Reversion은 "상승장의 일시적 조정" 시나리오를 가정
- Trend Filter는 "장기적으로 상승 추세에 있는지" 확인하는 안전장치

**2단계: 시나리오 재설계 (3-Phase Approach)**

```python
# 수정된 테스트 픽스처
def generate_mean_reversion_entry_candles():
    # Phase 1 (0-250분): 완만한 상승 (20,000 → 25,000, MA 형성용)
    for i in range(250):
        price = 20000 + (5000 * i / 250)
        candles.append({'close': price})
    
    # Phase 2 (250-294분): 급등 (25,000 → 88,500, Bubble 형성)
    for i in range(250, 294):
        price = 25000 + (63500 * (i - 250) / 44)
        candles.append({'close': price, 'volume': 100 + 200*(i-250)/44})
    
    # Phase 3 (294-299분): 급락 (88,500 → 63,500, RSI < 30 유도)
    for i in range(294, 299):
        price = 88500 - (25000 * (i - 294) / 5)
        candles.append({'close': price, 'volume': 450})
```

**최종 지표 값**:
```
Current Price: 63,500
MA(200): 21,247 (Phase 1의 완만한 상승 평균)
✅ 63,500 > 21,247 → Trend Filter 통과
RSI: 28.3 (Phase 3의 급락으로 과매도)
Volume Ratio: 3.2 (폭락 시 거래량 폭증)
→ Entry Signal: True ✅
```

#### 💡 배운 점

1. **테스트는 프로덕션 코드만큼 중요**: 잘못된 테스트는 잘못된 전략을 승인하거나 올바른 전략을 거부함
2. **복합 AND 조건 테스트 설계**:
   - 각 조건을 독립적으로 만족시키는지 확인
   - 한 조건을 만족시키려다 다른 조건을 깨뜨리지 않는지 검증
3. **도메인 지식의 중요성**: 금융 지표(MA, RSI, BB)의 특성을 이해해야 현실적인 시나리오 설계 가능

**영향**: 백테스팅 신뢰도 향상, 전략 검증 가능, 실전 배포 전 전략 철학 재확인

---

## 📊 기타 주요 트러블슈팅 (요약)

### 4. AI Agent Decision DB 저장 실패 — Silent Failure (List vs Dict)
**난이도**: ⭐⭐⭐ | **심각도**: 🔴 CRITICAL (수일간 데이터 손실)

**문제**: AI Agent가 정상적으로 분석/결정을 내리고 있었지만, 결과가 DB에 **전혀 저장되지 않는** 상태가 며칠간 지속. 대시보드 AI Decision 탭이 완전히 비어있어 발견.

**근본 원인**:
```python
# bot/main.py에서 market_context 생성
market_context = df.tail(10).to_dict(orient="records")  # → list 반환

# runner.py의 _log_decision()에서
regime = market_context.get("regime")  # ❌ list에 .get() 없음 → AttributeError
```
- `_log_decision()` 내부의 `try/except`가 에러를 잡아서 `print()`만 출력
- AI 분석 결과 자체는 정상 반환되지만, **DB 저장만 조용히 실패** (Silent Failure)
- 로그를 주의 깊게 보지 않으면 발견 불가

**해결**: `market_context.get("regime")` → `indicators.get("regime")` (2곳 수정)

**교훈**: Silent Failure는 가장 위험한 버그. 중요 데이터 저장 로직은 반드시 저장 후 검증하거나, 실패 시 명확한 알림 필요

### 5. Timezone-aware vs Naive Datetime 충돌
- **문제**: DB에서 aware 객체 반환, 코드에서 naive 객체 비교 → TypeError
- **해결**: 프로젝트 전체에서 `datetime.now(timezone.utc)` 통일
- **영향**: 쿨다운 체크, Time Exit 조건 등 시간 기반 로직 정상화

### 6. Kubernetes DNS 해석 실패
- **문제**: 단축 도메인(`db`) 간헐적 해석 실패
- **해결**: FQDN(`db.coin-pilot-ns.svc.cluster.local`) 사용
- **영향**: 네트워크 안정성 향상

### 7. 전략 파라미터 반복 튜닝 (v3.0 → v3.3)
- **문제**: 초기 파라미터가 지나치게 엄격해 3일간 거래 0건, 완화 시 시간당 10건 과다 진입
- **여정**: v3.0(너무 엄격) → v3.1(너무 느슨) → v3.2(중간값) → v3.3(RSI7만 v3.0 복원)
- **해결**: RSI14=42(고정), RSI7은 레짐별 차등(BEAR=30, SIDEWAYS=35, BULL=42)
- **교훈**: 파라미터 튜닝은 한 번에 하나씩만 변경하고 충분한 모니터링 필요

### 9. AI Agent 1분봉 → 1시간봉 전환 및 역할 분리
- **문제**: AI에 1분봉 10개만 제공 → 모든 하락을 "Falling Knife"로 판단, confidence=15~25
- **해결**: 1시간봉 24개로 변경 → confidence 평균 61.7로 상승 (max=85)
- **추가**: Rule Engine과 AI Agent가 RSI/MA를 중복 검증하는 문제 발견 → 프롬프트 재설계로 역할 분리
- **비용 최적화**: Haiku($0.001/call) vs Sonnet($0.02/call) 비교 운영 후 Sonnet 채택

### 8. CI/CD scipy 빌드 실패
- **문제**: scipy가 wheel 없는 환경에서 소스 빌드하며 BLAS/LAPACK 누락
- **해결**: `libopenblas-dev`, `--only-binary=scipy` 추가
- **영향**: GitHub Actions CI 안정화

---

## 🌟 현재 프로젝트 상태

### 시스템 안정성
- ✅ **DB 동시성 제어**: FOR UPDATE로 Race Condition 방지
- ✅ **테스트 커버리지**: 15개 비동기 DB 테스트 안정화
- ✅ **CI/CD 파이프라인**: pytest, type check, 보안 취약점 스캔 자동화

### 배포 현황
- **환경**: Minikube (로컬 K8s 클러스터)
- **서비스**: Bot, Collector, Dashboard, DB(PostgreSQL), Redis, n8n
- **모니터링**: Streamlit 대시보드 (시장 현황, 포지션, AI 의사결정, 시스템 헬스체크)
- **알림**: Discord 웹훅 (거래 체결, AI Decision(CONFIRM/REJECT + confidence), Daily Report)

### AI Agent 운영
- **모델**: Claude Sonnet 4.5 (prod), Claude Haiku 4.5 (dev 전환 가능)
- **데이터**: 1시간봉 24개 제공, 40초 타임아웃
- **Confidence Threshold**: 60 이상이어야 CONFIRM 유효

### 개발 단계
- **현재**: v3.3 (Regime-based Adaptive Strategy, RSI7 v3.0 복원)
- **다음**: Oracle Cloud Always Free 이전 준비 (안정화 후)

---

## 💎 기술적 성장 포인트

### 1. 분산 시스템 설계 역량
- Kubernetes 환경에서의 동시성 제어 (Pessimistic Locking)
- Race Condition, Lost Update 등 분산 시스템 특유의 문제 해결

### 2. 비동기 프로그래밍 숙련도
- asyncpg, SQLAlchemy AsyncEngine, pytest-asyncio 조합 운용
- Connection Pool 관리 및 트레이드오프 의사결정

### 3. 테스트 주도 개발 (TDD)
- 복잡한 금융 로직의 테스트 시나리오 설계
- Mock/Fixture를 활용한 외부 API 의존성 격리 (Factory Pattern)

### 4. 문제 해결 방법론
- 근본 원인 분석 (Root Cause Analysis)
- 다중 솔루션 비교 평가 및 최적 선택
- 체계적 디버깅 (가설 수립 → 검증 → 재설계)

### 5. 문서화 습관
- 트러블슈팅 로그 작성 (12개 문서)
- 재발 방지 Best Practices 정리
- 팀 내 지식 공유 (Implementation Plan, Walkthrough)

---

## 🎯 결론

CoinPilot 프로젝트를 통해 **"개발 → 배포 → 트러블슈팅 → 개선"의 전체 사이클**을 경험했습니다. 특히:

1. **분산 시스템의 Race Condition**을 코드 리뷰 단계에서 사전 발견하여 실제 자금 손실 방지
2. **비동기 DB 테스트 환경 구축**으로 CI/CD 파이프라인 안정화
3. **전략 테스트 시나리오 재설계**로 백테스팅 신뢰도 확보

이러한 경험을 통해 "**문제를 해결하는 것보다 문제가 발생하지 않도록 설계하는 것**"의 중요성을 깨달았습니다.

**기술의 표면적인 사용법이 아닌, 내부 동작 원리를 이해하고 트레이드오프를 의식적으로 선택하는 엔지니어**로 성장하고 있습니다.
