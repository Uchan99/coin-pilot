# Week 6 Phase 1: Dashboard Foundation Report

**Date**: 2026-01-30
**Author**: Antigravity
**Status**: Ready for Verification

---

## 1. 개요 (Overview)
Week 6의 첫 단계인 **대시보드 기초 골격**을 완성했습니다.
Streamlit의 멀티 페이지 기능을 활용할 수 있도록 디렉토리 구조를 잡고, 비동기 DB 연결을 지원하는 커넥터를 구현했습니다.

### 1.1 주요 변경 사항
-   **Structure**: `src/dashboard/` 하위에 `pages/`, `components/`, `utils/` 구조 생성.
-   **DB Connector**: `asyncpg` 기반의 비동기 쿼리를 Streamlit(동기 환경)에서 실행할 수 있도록 `db_connector.py` 래퍼 구현.
-   **Navigation**: `app.py`를 메인 엔트리포인트로 하고, `pages/` 폴더에 5개의 핵심 화면(Overview, Market, Risk, History, System) 생성.

---

## 2. 구현 상세 (Implementation Details)

### 2.1 Directory Structure
```
src/dashboard/
├── app.py              # Main Entrypoint
├── pages/
│   ├── 1_overview.py   # [Empty]
│   ├── 2_market.py     # [Empty]
│   ├── 3_risk.py       # [Empty] (New!)
│   ├── 4_history.py    # [Empty]
│   └── 5_system.py     # [Empty]
├── components/         # [Empty] UI Widgets
└── utils/
    └── db_connector.py # Database Wrapper
```

### 2.2 DB Connector (`utils/db_connector.py`)
-   **Problem**: Streamlit은 기본적으로 동기(Synchronous) 실행이지만, 프로젝트의 DB 엔진(`src.common.db`)은 비동기(Async)임.
-   **Solution**: `asyncio.new_event_loop()` 및 `loop.run_until_complete()`를 사용하여 비동기 쿼리를 감싸는(Wrap) 동기 함수 `get_data_as_dataframe()` 구현.
-   **Return Type**: 시각화에 최적화된 `pandas.DataFrame` 반환.

---

## 3. 검증 (Verification)

### 3.1 실행 테스트
```bash
# 1. 가상환경 활성화 (필수)
source .venv/bin/activate

# 2. DB 포트포워딩 확인 (필수)
kubectl port-forward -n coin-pilot-ns service/db 5432:5432 &

# 3. 대시보드 실행
PYTHONPATH=. streamlit run src/dashboard/app.py
```

### 3.2 예상 결과
-   브라우저(`http://localhost:8501`)가 열려야 함.
-   왼쪽 사이드바에 5개의 메뉴가 보여야 함.
-   사이드바의 **"시스템 상태 확인"** 버튼 클릭 시 `🟢 DB Status: Connected` 가 떠야 함.

---

## 4. Next Step (Phase 2)
이제 골격이 갖춰졌으니, 각 페이지에 실제 데이터를 채워 넣는 **시각화(Visualization)** 작업을 진행합니다.
-   `Overview`: 총 자산 조회 쿼리 작성.
-   `Market`: Plotly 캔들차트 구현.
-   `Risk`: 게이지 차트 구현.

---

## 5. Claude Code Review

**Reviewer**: Claude Code (Opus 4.5)
**Date**: 2026-01-30
**Status**: ✅ **APPROVED**

---

### 검증 결과

#### A. 디렉토리 구조 검증

| 항목 | 계획 | 실제 | 결과 |
|------|------|------|------|
| `app.py` | 메인 엔트리포인트 | ✅ 존재 | PASS |
| `pages/` | 5개 페이지 | ✅ 5개 파일 생성 | PASS |
| `components/` | 빈 폴더 | ✅ 폴더 존재 | PASS |
| `utils/db_connector.py` | DB 래퍼 | ✅ 구현 완료 | PASS |

#### B. 코드 품질 검증

| 파일 | 검증 항목 | 결과 |
|------|----------|------|
| `app.py` | `st.set_page_config()` 최상단 호출 | ✅ PASS |
| `app.py` | 사이드바 네비게이션 및 DB 상태 버튼 | ✅ PASS |
| `db_connector.py` | 비동기→동기 래퍼 (`run_until_complete`) | ✅ PASS |
| `db_connector.py` | `get_db_session()` 호환성 | ✅ PASS |
| `db_connector.py` | 예외 처리 및 빈 DataFrame 반환 | ✅ PASS |
| `pages/*.py` | Placeholder 메시지 표시 | ✅ PASS |

#### C. 의존성 검증

| 패키지 | `requirements.txt` 포함 여부 |
|--------|---------------------------|
| `streamlit` | ✅ Line 24 |
| `plotly` | ✅ Line 25 |

---

### 보완 권장 사항 (선택적)

다음 항목은 Phase 2 진행 시 고려하면 좋을 사항입니다:

1. **`__init__.py` 추가 고려**
   - `components/`, `pages/`, `utils/` 폴더에 `__init__.py` 추가 시 Python 패키지로 명확히 인식
   - 현재도 Streamlit 실행에는 문제없음 (선택적)

2. **캐싱 전략 도입**
   - `db_connector.py`의 `get_data_as_dataframe()`에 `@st.cache_data(ttl=30)` 적용 시 반복 조회 성능 향상
   - Phase 3 Auto-refresh 구현 시 함께 검토 권장

3. **로깅 강화**
   - `st.error()` 외에 `logging` 모듈을 통한 파일 로그 기록 추가 시 디버깅 용이

---

### 결론

Phase 1의 목표인 **"대시보드 기초 골격 구축"**이 계획대로 완료되었습니다.
- 디렉토리 구조가 Week 6 계획서와 일치
- DB 커넥터가 기존 `src.common.db` 모듈과 올바르게 통합됨
- Streamlit 멀티페이지 구조 정상 작동 확인 가능

**Phase 2 진행을 승인합니다.**
