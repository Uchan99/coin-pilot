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

### 이슈 3: AI API 호출 오류 (401 & 404)

#### 🔴 문제 상황
`debug_simulation.py` 실행 시 다음과 같은 에러들이 순차적으로 발생함.
1.  **401 Unauthorized**: "invalid x-api-key"
2.  **404 Not Found**: "model: claude-3-5-sonnet-20241022" (API Key 권한 부족)

#### ✅ 해결 방안
1.  **401 해결**: `.env` 파일에 유효한 `ANTHROPIC_API_KEY` 설정.
2.  **404 해결**: 사용자의 API Key 등급에서 접근 가능한 모델(`claude-3-haiku-20240307`)로 `factory.py` 코드를 수정.

---

## 4. 파일 매니페스트 (Files Created)

| 파일 경로 | 설명 |
|----------|------|
| `src/dashboard/app.py` | Streamlit 대시보드 메인 로직 |
| `scripts/debug_simulation.py` | 매수 신호를 강제로 발생시키는 디버그용 스크립트 |
| `scripts/check_db.py` | DB에 저장된 데이터 확인용 유틸리티 |
| `docs/test/dashboard-implementation.md` | 본 문서 |

## 5. 브랜치 관리 및 배포 전략 (Branch Strategy)
본 대시보드 및 수정 사항은 다음과 같은 전략으로 관리됩니다.

### Phase 1: 운영 필수 패치 (Backport to Dev)
`test` 브랜치에서 발견된 백엔드 결함(로그 누락, 모델명 하드코딩)은 운영 환경에 필수적이므로 `dev`로 병합합니다.
```bash
git checkout dev
git cherry-pick <commit-hash>
# 또는 수동으로 runner.py 관련 수정 사항만 적용
```

### Phase 2: 검증용 브랜치 유지 (Sync)
`test` 브랜치는 Sandbox 환경으로 유지하며, `dev`의 변경 사항을 주기적으로 받아옵니다.
```bash
git checkout test
git merge dev  # 최신 코드 동기화
```

### Phase 3: 도구 성숙화 (Feature Promotion)
대시보드 기능이 충분히 안정화되고 프로덕션에 필요하다고 판단되면 별도 기능 브랜치로 격상합니다.
```bash
git checkout -b feature/dashboard  # test에서 분기
# ... 다듬기 및 테스트 ...
git push origin feature/dashboard  # dev로 PR 생성
```

---

## 6. 결론
`test` 브랜치에서의 실험을 통해 **"복잡한 백엔드 설정 없이도 DB 직접 접속을 통해 모니터링 시스템을 구축할 수 있음"** 을 확인했습니다.
또한 이 과정에서 **운영 환경의 잠재적 버그(`runner.py` 로그 누락)** 를 발견하고 수정하는 성과를 거두었습니다.

### 최종 수정 반영 내역
1.  **Backend Fix**: `runner.py`의 에러 로깅 추가 및 하드코딩된 `model_used` 수정.
2.  **Dashboard Improvement**: `os.system`을 `subprocess.run`으로 교체하여 보안 강화 및 에러 메시지 UI 노출.

---

## Claude Code Review

**검토일**: 2026-01-26
**검토자**: Claude Code (Operator & Reviewer)
**상태**: ✅ **승인 (조건부)** - 아래 필수 수정사항 반영 후 dev/main 병합 권장

---

### 1. 코드 검증 결과

| 파일 | 검증 항목 | 결과 |
|------|----------|------|
| `src/dashboard/app.py` | NullPool 적용 | ✅ 정상 |
| `src/dashboard/app.py` | Event Loop 재사용 로직 | ✅ 정상 |
| `src/agents/runner.py` | 예외 시 DB 로깅 | ✅ 정상 (113-120 라인) |
| `src/agents/analyst.py` | Confidence < 80 강제 REJECT | ✅ 정상 (V1.2 정책 반영) |

---

### 2. 🚨 필수 수정사항 (dev/main 병합 전)

#### 2.1 Critical: `model_used` 하드코딩 불일치

**위치**: `src/agents/runner.py:132`

```python
# 현재 (Buggy)
model_used="claude-3-5-sonnet-20241022"  # 하드코딩됨

# 실제 사용 모델 (factory.py)
model="claude-3-haiku-20240307"
```

**문제점**: 감사(Audit) 로그에 잘못된 모델명이 기록되어, 향후 모델 변경 시 추적이 불가능해짐.

**권장 수정**:
```python
# src/agents/runner.py
from src.agents.factory import get_analyst_llm

# _log_decision 내에서
model_used=get_analyst_llm().model  # 또는 상수 정의
```

#### 2.2 Required: runner.py 예외 처리 로직 → dev/main 병합 필수

`test` 브랜치의 `runner.py:113-120` 수정 사항은 **대시보드와 무관하게 운영 필수 패치**입니다.

```python
except Exception as e:
    print(f"[!] AI Agent Error for {symbol}: {e}. Falling back to REJECT.")
    await self._log_decision(
        symbol, strategy_name, "REJECT",
        f"AI Error: {str(e)}", None
    )
    return False, f"AI Analysis Error: {str(e)}"
```

**병합 방법**: `git cherry-pick` 또는 해당 변경 수동 적용.

---

### 3. ⚠️ 권장 개선사항 (Optional)

#### 3.1 대시보드: `os.system()` 보안 및 모니터링 이슈

**위치**: `src/dashboard/app.py:55`

```python
# 현재
os.system("PYTHONPATH=. .venv/bin/python scripts/simulate_with_ai.py")
```

**문제점**:
- 실행 결과(stdout/stderr) 캡처 불가
- 실패 시 사용자에게 정보 전달 불가
- 잠재적 보안 취약점 (인젝션 가능성)

**권장 수정**:
```python
import subprocess
result = subprocess.run(
    [".venv/bin/python", "scripts/simulate_with_ai.py"],
    capture_output=True, text=True,
    env={**os.environ, "PYTHONPATH": "."}
)
if result.returncode != 0:
    st.sidebar.error(f"Simulation Failed: {result.stderr}")
else:
    st.sidebar.success("Simulation Completed!")
```

#### 3.2 대시보드: Auto-Refresh 기능 부재

현재 수동 새로고침만 가능. 실시간 모니터링을 위해 `st.rerun()` 또는 `streamlit-autorefresh` 패키지 도입 권장.

```python
# 예시: 30초마다 자동 갱신
from streamlit_autorefresh import st_autorefresh
st_autorefresh(interval=30000, key="dashboard_refresh")
```

#### 3.3 TradingHistory 연동 미구현

`app.py:109-110`에 TODO로 남아있음. Week 3 범위 외로 판단되나, 향후 구현 시 동일한 `NullPool` 패턴 적용 권장.

---

### 4. 아키텍처 평가

| 항목 | 평가 |
|------|------|
| Streamlit + 직접 DB 연결 방식 | ✅ 테스트/모니터링 용도로 적절 |
| NullPool 사용 (Event Loop 격리) | ✅ 올바른 접근 |
| Admin Pod 배포 구상 (K8s) | ✅ 확장성 고려됨 |
| FastAPI 우회 (REST API 미사용) | ⚠️ 프로덕션에서는 API 레이어 권장 |

---

### 5. 결론 및 병합 권고

| 브랜치 | 병합 대상 | 우선순위 |
|--------|----------|----------|
| `test` → `dev` | `runner.py` 예외 처리 수정 | 🔴 **긴급** |
| `test` → `dev` | `runner.py` model_used 수정 | 🟠 **높음** |
| `test` → `main` | 위 수정 완료 후 통합 | 🟢 **정상** |

**대시보드 자체**는 `test` 브랜치에서 유지하거나, 별도 `feature/dashboard` 브랜치로 분리 권장. 프로덕션 배포 전 `os.system()` 및 Auto-refresh 개선 필요.

---

**다음 단계**:
1. `model_used` 하드코딩 수정
2. `runner.py` 변경사항 dev 브랜치로 cherry-pick
3. (Optional) 대시보드 개선사항 반영 후 별도 PR 생성
