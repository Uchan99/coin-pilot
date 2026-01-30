# Week 6 Walkthrough: Monitoring Dashboard Implementation

**Date**: 2026-01-30
**Author**: Antigravity
**Status**: Completed

---

## 1. 개요 (Overview)
Week 6의 목표는 운영 중인 CoinPilot 봇의 상태를 실시간으로 모니터링할 수 있는 **Streamlit 기반 대시보드**를 구축하는 것이었습니다.
기존 CLI 기반 확인 방식의 한계를 넘어, **자산 변동, 시장 차트, 리스크 상태, 시스템 연결성**을 시각화하여 운영 편의성을 극대화했습니다.

---

## 2. Phase 1: Foundation (기반 구축)

### 주요 성과
-   **Directory Structure**: `src/dashboard/{pages, components, utils}` 구조 확립.
-   **DB Connection**: `src/dashboard/utils/db_connector.py` 구현.
-   **Streamlit App**: `app.py` 메인 진입점 및 사이드바 네비게이션 구성.

### 기술적 이슈 및 해결
-   **AsyncIO Conflict**: Streamlit의 멀티스레드 환경과 `asyncpg`의 이벤트 루프 충돌 문제 발생.
-   **해결책**: Phase 2에서 **Sync Engine (psycopg2)** 전용 커넥터로 교체하여 근본 해결.

---

## 3. Phase 2: Visualization (핵심 시각화)

### 3.1 Overview Page (`1_overview.py`)
-   **Key Metrics**: 총 자산, 누적 손익(PnL), 승률, 보유 포지션 수 표시.
-   **Active Positions**: 현재 보유 중인 코인의 평단가, 현재가, 수익률 테이블 제공.

### 3.2 Market Analysis (`2_market.py`)
-   **Interactive Chart**: Plotly 기반 Candlestick Chart 구현.
-   **TimescaleDB Integration**: `time_bucket` 함수를 활용한 효율적인 OHLCV 데이터 조회.

### 3.3 Risk Monitor (`3_risk.py`)
-   **Daily Limits**: 금일 손익(-5%) 및 거래 횟수(10회) 제한 준수 여부를 Gauge/Progress Bar로 시각화.
-   **Status Check**: `trading_halt` 및 `consecutive_losses` 상태 표시.

### 3.4 Trade History (`4_history.py`)
-   **Log Viewer**: 필터링(Symbol, Side) 가능한 거래 내역 테이블.
-   **Statistics**: 매수/매도 비율(Pie Chart) 및 체결 상태(Bar Chart) 요약.

---

## 4. Phase 3: System Health & Polish (고도화)

### 4.1 System Health (`5_system.py`)
-   **Connectivity Check**:
    -   🟢 **DB**: PostgreSQL(TimescaleDB) 연결 상태.
    -   🟢 **Redis**: 캐시 서버 Ping 테스트.
    -   🟢 **n8n**: 워크플로우 엔진 Healthz 체크.
-   **Risk Audit**: 최근 발생한 리스크 이벤트 로그 조회.

### 4.2 Auto Refresh (`components/autorefresh.py`)
-   **Feature**: `streamlit-autorefresh` 라이브러리를 도입하여 브라우저 단에서 백그라운드 타이머 동작.
-   **UX**: 사이드바에서 On/Off 및 주기(Interval) 설정 가능. 사용자가 가만히 있어도 실시간 데이터 갱신.

### 4.3 Bot Brain Visualization (`2_market.py`)
-   **Observability**: 봇의 내부 상태(Indicators)와 판단 근거(Reasoning)를 Redis를 통해 실시간 중계.
-   **UI**: 차트 상단에 **🤖 Bot Brain** 섹션을 추가하여 현재 행동(Action), RSI 값, 결정 이유(Reason) 표시.
    -   예: "관망 중: RSI(45.2) > 30 (과매도 아님)"
-   **심볼 호환성**: DB와 봇의 심볼 형식이 다를 수 있어 역변환 로직 추가 (`BTC-KRW` ↔ `KRW-BTC`).
-   **테스트 도구**: `scripts/test_bot_status.py` - 봇 없이 Bot Brain UI 테스트 가능.


---

## 5. Phase 4: Documentation (문서화)

### 5.1 Deliverables
-   **[USER_MANUAL.md](../USER_MANUAL.md)**: 대시보드 사용법 및 봇 운영 가이드.
-   **[FAILURE_ANALYSIS.md](../FAILURE_ANALYSIS.md)**: 주요 장애 유형별 대응 플레이북.
-   **[Week 6 Troubleshooting Log](../troubleshooting/week6-ts.md)**: 개발 과정 기술 회고록.

---

## 6. 결론 및 향후 계획 (Conclusion)

Week 6 프로젝트를 통해 **"보이지 않는 봇"을 "보이는 시스템"으로 전환**하는 데 성공했습니다.
모든 기능이 계획대로 구현되었으며, `models.py`와의 정합성 검증 및 예외 처리(Defensive Coding)까지 완료되었습니다.

**Next Step (Week 7)**:
-   **AI Assistant Integration**: LLM 기반 챗봇을 대시보드에 통합하여 대화형으로 봇을 제어하는 기능 개발.
