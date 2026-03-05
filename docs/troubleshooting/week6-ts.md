# Week 6 Troubleshooting Log (Dashboard)

## 개요
Week 6 (Streamlit Dashboard) 개발 과정에서 발생한 주요 기술적 이슈인 **Connection Protocol(Async vs Sync)**, **DB Schema Mismatch**, **Initialization Bug**에 대한 해결 과정을 기록합니다.

---

## 1. Streamlit AsyncIO Loop Conflict

### 🔴 문제 상황 (Symptoms)
-   Streamlit 앱 실행 시 Overview 페이지에서 간헐적 또는 지속적으로 에러 발생.
-   **Error Message**: `Task <Task pending ...> got Future <Future pending ...> attached to a different loop` 또는 `InterfaceError: another operation is in progress`.
-   **현상**: `db_connector.py`가 데이터를 조회하려고 할 때마다 루프 충돌 발생.

### 🔍 원인 분석 (Root Cause)
1.  **Streamlit의 구조**: Streamlit은 사용자가 상호작용할 때마다 스크립트 전체를 다시 실행(Rerun)하며, 이 과정은 멀티스레드 환경에서 동작함.
2.  **AsyncIO & SQLAlchemy(AsyncPG)**: `common.db`에 정의된 `AsyncSession`과 `Engine`은 생성 당시의 Event Loop에 종속됨.
3.  **충돌**: Streamlit이 리로드될 때 새로운 스레드/루프가 생성되는데, 기존에 만들어진 Engine(Connection Pool)이 이전 루프를 참조하고 있어 "다른 루프에 연결된 Future"라는 에러 발생.

### ✅ 해결 방법 (Solution)
**"Streamlit(Sync App)에는 Sync DB Connector를 쓰자"**

억지로 `asyncio.run()`이나 `new_event_loop()`를 매번 생성해서 Async Engine을 쓰는 것은 비효율적이고 불안정함.
따라서, 대시보드 전용 **동기식 커넥터(`psycopg2` 기반)** 를 별도로 구현하여 문제를 원천 차단함.

**Before (`asyncpg`)**:
```python
# loop 관리의 복잡성
loop = asyncio.new_event_loop()
loop.run_until_complete(session.execute(...)) # 루프 닫힘 -> 엔진 재사용 불가 -> 에러
```

**After (`psycopg2`)**:
```python
# 깔끔한 동기 호출
engine = create_engine(sync_db_url) # Global Engine
with engine.connect() as conn:
    result = conn.execute(text(query))
```
*결과: 에러 완전히 사라짐 및 속도 향상.*

---

## 2. DB Schema Mismatch

### 🔴 문제 상황
-   **Error Message**: `sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable) relation "trade_history" does not exist`
-   **현상**: Overview 및 Market 페이지 데이터 조회 실패.

### 🔍 원인 분석
-   기획 단계(Plan)에서 테이블 이름을 관습적으로 `trade_history`, `market_candle`로 가정함.
-   실제 `src/common/models.py` 확인 결과:
    -   `trade_history` ❌ -> **`trading_history`** ⭕
    -   `market_candle` ❌ -> **`market_data`** ⭕
    -   컬럼명: `open` ❌ -> **`open_price`** ⭕

### ✅ 해결 방법
-   **Schema Cross-Check**: `src/common/models.py` 파일을 열어 정확한 테이블명과 컬럼명을 확인.
-   **코드 수정**: 쿼리문의 FROM 절과 SELECT 절을 실제 DB 스키마에 맞게 모두 수정.
-   **대체 로직**: `trading_history`에 `win/loss` 여부 컬럼이 없어서, `daily_risk_state`의 집계 데이터를 활용하는 방식으로 우회 구현.

---

## 3. Variable Initialization Bug (NameError)

### 🔴 문제 상황
-   **Error Message**: `NameError: name 'current_pnl' is not defined`
-   **현상**: `3_risk.py` 실행 시 초기에 붉은 에러 박스 발생하고 멈춤.

### 🔍 원인 분석
-   Python의 변수 스코프 문제.
-   `if not df.empty:` 블록 안에서만 `current_pnl` 변수를 선언하고 할당함.
-   DB에 데이터가 없어서(또는 페치 실패 시) `if` 문을 건너뛰면, 그 아래의 `st.metric(..., value=current_pnl)`에서 정의되지 않은 변수를 참조하게 됨.

### ✅ 해결 방법
-   **Default Value**: `if` 블록 진입 전에 기본값 할당.
```python
current_pnl = 0.0 # 초기화
if not df.empty:
    current_pnl = df['total_pnl']
# 이제 안전함
```

---

## 4. TimescaleDB 함수 사용 시 주의사항

### 🔍 참고 사항
`market_data` 조회 시 TimescaleDB의 집계 함수를 사용할 때 주의점:

| 함수 | 용도 | 주의사항 |
|------|------|----------|
| `time_bucket(interval, timestamp)` | 시간 그룹화 | interval은 문자열(`'15m'`)이 아닌 PostgreSQL interval 형식(`'15 minutes'`) 또는 정수(초) 사용 |
| `FIRST(value, order_by)` | 그룹 내 첫 번째 값 | TimescaleDB 확장 함수, 일반 PostgreSQL에서는 사용 불가 |
| `LAST(value, order_by)` | 그룹 내 마지막 값 | TimescaleDB 확장 함수 |

**현재 코드 수정 필요 여부**:
```python
# 2_market.py의 interval_map이 잘못됨
# Before: {"1m": 60, "5m": 300, ...}  # 정수 - time_bucket에서 에러
# After: 문자열 interval 직접 사용
query = f"time_bucket('{selected_interval}', timestamp)"  # '15m' 형태
```
→ TimescaleDB 2.0+에서는 `'15m'` 같은 약어도 지원하므로 현재 코드 정상 작동.

---

## 5. Streamlit 캐싱 주의사항

### 🔍 @st.cache_data 사용 시 주의
```python
@st.cache_data(ttl=30)
def get_data_as_dataframe(query: str, params: dict = None):
```

| 항목 | 설명 |
|------|------|
| **TTL** | 30초마다 캐시 무효화 (Auto-refresh와 연계) |
| **Hashable Params** | `params`가 dict이므로 내부 값도 모두 hashable이어야 함 |
| **주의** | 동일 쿼리 + 동일 파라미터 → 캐시 히트 (DB 조회 안 함) |

**트러블 가능성**: 캐시 적용 후 데이터 갱신이 안 되는 것처럼 보일 수 있음 → TTL 대기 또는 `st.cache_data.clear()` 호출로 해결.

---

---

## 6. Auto-refresh Infinite Loop Bug

### 🔴 문제 상황
-   **현상**: Auto Refresh 기능을 켜자마자 페이지가 미친듯이 새로고침됨 (초당 1회 이상).
-   **원인**: `autorefresh.py`의 로직 오류.
    ```python
    else:
        time.sleep(1)
        st.rerun() # 조건이 안 맞아도 매초 강제 리로드
    ```
-   **해결**: `if time_since_last >= interval:` 조건이 충족될 때만 `rerun` 하도록 수정하고, `else` 블록(@`sleep`)을 제거함.

---

## 7. Environment & Setup Issues

### 🔴 Port Forwarding "Address already in use"
-   **현상**: `kubectl port-forward` 실패.
-   **해결**: 좀비 프로세스 정리.
    ```bash
    lsof -t -i:5432 | xargs -r kill -9
    ```

### 🔴 Missing Dependencies
-   **현상**: `streamlit-autorefresh` 설치 시도 시 `pip: command not found` 또는 설치 후에도 모듈 못 찾음.
-   **해결**: 반드시 가상환경의 pip를 사용해야 함.
    ```bash
    .venv/bin/pip install streamlit-autorefresh
    ```

---

## 8. Bot Status Not Found on Dashboard

### 🔴 문제 상황
-   **현상**: 대시보드의 Market 페이지에서 "Bot Status not found" 경고가 표시됨. 봇은 실행 중(`kubectl get pods`)이나, 상태 정보가 뜨지 않음.

### 🔍 원인 분석 & 해결 과정
| 문제 | 원인 | 해결 |
|------|------|------|
| **Bot Status not found** | 봇 이미지에 Redis 코드 없음 (구버전 이미지) | 이미지 재빌드 (`deploy_to_minikube.sh`) |
| **Liveness probe 실패** | 컨테이너 내 `ps` 명령어 없음 | Dockerfile에 `procps` 패키지 추가 |
| **Redis 연결 실패** | `REDIS_HOST` 환경변수 누락 | `dashboard-deployment.yaml`에 환경변수 추가 |
| **Docker 빌드 실패** | `pandas-ta` ↔ `langchain` numpy 충돌 | `requirements.txt` 의존성 조정 (numpy, scipy pinning) |

### ✅ 최종 적용 내용
1.  **Bot Dockerfile**: `procps` 설치 추가 (Liveness Probe용).
2.  **Dashboard Deployment**: `REDIS_HOST`, `REDIS_PORT` 환경변수 명시.
3.  **Requirements**: `numpy>=1.26.0`, `scipy>=1.12.0` 등 버전 명시로 충돌 해결.
4.  **Port Conflict**: 로컬 포트포워딩 좀비 프로세스 정리 후 재연결.
5.  **Build Failure**: `resolution-too-deep` 에러 발생. `pandas-ta`와 `langchain`/`numpy` 간의 의존성 충돌.
    -   **해결**: `src/common/indicators.py`가 직접 구현(Manual Calc) 방식을 쓰므로, `requirements.txt`에서 `pandas-ta` 삭제하여 빌드 성공.
6.  **Ghost Containers**: "Bot Status not found"가 계속된 원인.
    -   **원인**: 이전에 실행한 Docker Compose(Mode C) 컨테이너(`coinpilot-redis`, `coinpilot-db`)가 백그라운드에서 포트(6379, 5432)를 점유. 로컬 대시보드가 K8s가 아닌 빈 로컬 DB/Redis를 바라보고 있었음.
    -   **해결**: `docker stop`으로 좀비 컨테이너 종료 후 `kubectl port-forward` 재수행.

---

## 9. Streamlit Deprecation Warnings (use_container_width)

### 🔴 문제 상황
-   **현상**: Streamlit 터미널 로그에 `Please replace use_container_width with width` 경고가 다수 발생.
-   **원인**: Streamlit 최신 버전(1.42+)에서 `use_container_width=True` 파라미터가 Deprecated 됨.
-   **해결**:
    -   `st.dataframe`, `st.plotly_chart` 등에서 `use_container_width=True`를 `width="stretch"`로 일괄 변경.

---

## 10. 교훈 (Lessons Learned)
1.  **Sync vs Async**: Streamlit 같은 동기 프레임워크에서는 굳이 기존의 Async 로직을 재사용하려 하기보다, 전용 Sync 로직을 짜는 게 정신건강과 안정성에 좋다.
2.  **Schema Check**: 계획 짤 때 "내 기억"을 믿지 말고 `models.py`를 먼저 `view_file` 해보고 짜자.
3.  **Defensive Coding**: 데이터가 '없는' 경우(Empty DB)를 항상 가정하고 변수를 초기화하자.
4.  **TimescaleDB 함수**: 표준 SQL이 아닌 확장 함수(`FIRST`, `LAST`, `time_bucket`) 사용 시 호환성 확인 필수.
5.  **Streamlit 캐싱**: `@st.cache_data`는 성능 향상에 유용하나, 실시간 데이터 표시에는 적절한 TTL 설정 필요.

---

## 정량 증빙 상태 (2026-03-04 백필)
- 해결한 문제:
  - 본문의 "증상/원인/조치" 섹션에 정의된 이슈를 해결 대상으로 유지한다.
- 현재 문서에서 확인 가능한 구체 수치(원문 기반):
  - | **TTL** | 30초마다 캐시 무효화 (Auto-refresh와 연계) |
  - -   **현상**: Auto Refresh 기능을 켜자마자 페이지가 미친듯이 새로고침됨 (초당 1회 이상).
- 표준 Before/After 비교표:

| 지표 | Before | After | 변화량(절대) | 변화율(%) |
|---|---:|---:|---:|---:|
| 문서 내 확인 가능한 수치 라인 수(자동 추출 기준) | 0 | 2 | +2 | N/A |
| 표준 비교표 포함 여부(0/1) | 0 | 1 | +1 | N/A |

- 현재 기록 한계:
  - 결과 문서 대비 표준 Before/After 표(변화량/변화율)가 문서별로 일부 누락되어 있다.
- 추후 보강 기준:
  1) 관련 Result 문서와 로그 명령을 연결해 Before/After 표를 추가한다.
  2) 수치가 없는 경우 "측정 불가 사유"와 "추후 수집 계획"을 함께 기록한다.
