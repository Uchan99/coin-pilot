# Test Branch Report: Streamlit Dashboard Implementation

**작성일**: 2026-01-26
**브랜치**: `test`
**주제**: AI Agent 모니터링을 위한 Streamlit 대시보드 구축 및 비동기 이슈 해결

---

## 1. 개요 (Overview)
본 문서는 `test` 브랜치에서 진행된 **CoinPilot AI Dashboard** 구축 과정과, 그 과정에서 발생한 주요 기술적 이슈 및 해결책을 상세히 기록한 문서입니다. 프론트엔드 없이 로그로만 확인하던 AI의 판단 내역을 시각화하여 테스트 효율을 높이는 것이 목적이었습니다.

---

## 2. 주요 구현 사항
*   **Tech Stack**: Python, Streamlit, Plotly, SQLAlchemy (Startlette/FastAPI 없이 직접 DB 연결)
*   **기능**:
    1.  **AI Decision Log**: `agent_decisions` 테이블 실시간 조회 및 시각화 (CONFIRM/REJECT 색상 구분).
    2.  **Market Chart**: `market_data` 테이블의 OHLCV + 보조지표 시각화.
    3.  **Manual Simulation**: 사이드바 버튼을 통해 `simulate_with_ai.py` 강제 실행.

---

## 3. 트러블슈팅 로그 (Critical Issues)

### 이슈 1: Streamlit과 Asyncio Event Loop 충돌

#### 🔴 문제 상황 (The Problem)
대시보드 실행 시 `RuntimeError: Event loop is closed` 또는 `Task ... attached to a different loop` 에러가 발생하며 앱이 크래시됨.

```
RuntimeError: Event loop is closed
...
RuntimeError: Task <Task pending ...> got Future <Future pending ...> attached to a different loop
```

#### 🔍 원인 분석 (Root Cause)
1.  **Streamlit의 실행 모델**: Streamlit은 스크립트가 변경되거나 상호작용이 있을 때마다 전체 스크립트를 **재실행(Rerun)** 합니다.
2.  **Asyncio Loop 수명 주기**: `asyncio.run()`은 실행될 때마다 새로운 Event Loop를 생성하고 닫습니다.
3.  **Global DB Engine**: `src.common.db`에 정의된 전역 `engine` 객체는 `asyncpg` 연결 풀을 가지고 있는데, 이 풀은 **생성 당시의 Event Loop**에 강하게 결합되어 있습니다.
4.  **충돌**: Streamlit이 재실행되면서 새로운 루프가 생성되지만, 전역 `engine`은 이미 닫힌(또는 다른) 루프에 묶여 있어 연결을 재사용하려다 실패함.

#### ✅ 해결 방안 (Solution)

**1단계: Local Engine w/ NullPool 도입**
전역 엔진 대신, 대시보드 전용 엔진을 만들고 **Connection Pool을 비활성화(`NullPool`)** 했습니다. 이렇게 하면 매 요청마다 새로 연결을 맺고 끊으므로, 풀이 특정 루프에 종속되는 문제를 피할 수 있습니다.

```python
# src/dashboard/app.py
from sqlalchemy.pool import NullPool

dashboard_engine = create_async_engine(
    DATABASE_URL,
    poolclass=NullPool,  # 핵심: 풀링 비활성화
    echo=False
)
```

**2단계: Event Loop 재사용 로직**
`asyncio.run()` 대신 현재 실행 중인 루프가 있으면 그것을 쓰고, 없으면 새로 만드는 유틸리티 함수를 사용했습니다.

```python
def run_async(coroutine):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)
```

---

### 이슈 2: AI 에러 로그 누락 (Backend Latent Bug) 🚨

#### 🔴 문제 상황
더미 API Key로 시뮬레이션을 돌렸을 때, 콘솔에는 401 Error가 뜨지만 대시보드에는 아무런 기록도 나타나지 않음. 이는 **운영 환경(Dev/Main)에서도 AI 오류 발생 시 아무런 흔적이 남지 않는 심각한 결함**임을 의미함.

#### 🔍 원인 분석
`AgentRunner.run()` 메서드의 `except` 블록에서 에러를 `print()`로 출력만 하고, `_log_decision` 메서드를 호출하지 않은 채 종료함.

```python
# Before (Buggy Code in Dev/Main)
except Exception as e:
    print(f"Error: {e}")
    return False, str(e)  # DB 저장 안 함 -> 감사(Audit) 불가능
```

#### ✅ 해결 방안 (Backend Fix)
`src/agents/runner.py`를 수정하여 예외 상황에서도 반드시 DB에 로그를 남기도록 조치함.
이 수정 사항은 **Dashboard와 무관하게 모든 환경에 필수적**이므로, 반드시 `dev` 브랜치로 병합(Merge/Cherry-pick)해야 함.

```python
# After (Fixed in Test Branch)
except Exception as e:
    print(f"[!] AI Agent Error: {e}")
    # 에러 상황도 DB에 기록 (Visible in Dashboard & Audit)
    await self._log_decision(
        symbol, strategy_name, "REJECT", 
        f"AI Error: {str(e)}", None
    )
    return False, f"AI Analysis Error: {str(e)}"
```

---

## 4. 파일 매니페스트 (Files Created)

| 파일 경로 | 설명 |
|----------|------|
| `src/dashboard/app.py` | Streamlit 대시보드 메인 로직 |
| `scripts/debug_simulation.py` | 매수 신호를 강제로 발생시키는 디버그용 스크립트 |
| `scripts/check_db.py` | DB에 저장된 데이터 확인용 유틸리티 |
| `docs/test/dashboard-implementation.md` | 본 문서 |

## 5. 결론 및 향후 계획
`test` 브랜치에서의 실험을 통해 **"복잡한 백엔드 설정 없이도 DB 직접 접속을 통해 모니터링 시스템을 구축할 수 있음"** 을 확인했습니다.
이 방식은 향후 프로덕션 환경(Kubernetes)에서도 **Admin Pod** 형태로 띄워 운영자가 시스템 상태를 파악하는 데 유용하게 쓰일 수 있습니다.
