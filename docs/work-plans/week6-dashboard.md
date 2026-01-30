# Week 6: Dashboard Enhancement & Polish Implementation Plan

**Date**: 2026-01-30
**Author**: Antigravity
**Status**: Revised (v2 - Feedback Integrated)

---

## 1. 개요 (Overview)
Week 6의 목표는 **"투명한 모니터링 및 성과 분석"**입니다.
기존에 구축된 Collector, Bot, DB가 생성하는 데이터를 **Streamlit Dashboard**를 통해 시각화하고, 시스템의 최종 완성도를 높이는 작업을 진행합니다.

### 1.1 목표 (Goals)
1.  **Visibility**: 현재 자산, 포지션, 수익률을 한눈에 파악.
2.  **Verify**: 봇이 의도대로 매매했는지 차트 위에서 확인 (Buy/Sell 마커).
3.  **Risk Control**: "손절 한도", "거래 횟수 제한" 등 리스크 규칙 준수 여부 시각화.
4.  **Documentation**: 운영 중 발생할 수 있는 문제에 대한 대응 매뉴얼(Playbook) 작성.

---

## 2. 대시보드 설계 (Dashboard Design)

### 2.1 기술 스택
-   **Framework**: Streamlit (Python)
-   **Database**: PostgreSQL (SQLAlchemy + AsyncPG)
    -   *Target Tables*: `market_candle` (TimescaleDB), `trade_history`, `positions`, `risk_logs`, `system_logs`
-   **Visualization**: Plotly Interactive Charts
-   **Deployment**: Local execution (Mode B) via `kubectl port-forward`.

### 2.2 주요 기능 (Features)

#### A. 홈 (Overview) - `1_overview.py`
-   **Key Metrics**: 총 자산(KRW), 일일 수익률(%), 승률(Win Rate), 총 거래 횟수.
-   **Active Positions**: 현재 보유 중인 코인 리스트, 평단가, 현재가, 수익률.

#### B. 시장 분석 (Market Analysis) - `2_market.py`
-   **Interactive Chart**: 선택한 코인(예: BTC-KRW)의 캔들차트.
-   **Signals**: 차트 위에 매수(▲)/매도(▼) 지점을 표시하여 전략의 진입/청산 타당성 검증.
-   **Indicators**: RSI, Bollinger Band 등 보조지표 오버레이.

#### C. 리스크 모니터 (Risk Management) - `3_risk.py` **(New)**
-   **Daily Limits**:
    -   금일 손실률 Gauge Chart (현재 / -5% 한도)
    -   금일 거래 횟수 Progress Bar (현재 / 10회 한도)
-   **Cooldown Status**: 3연패 쿨다운 상태 표시 (Active/Inactive).
-   **Risk Logs**: 최근 발생한 리스크 이벤트 (`risk_logs` 테이블) 히스토리.

#### D. 시스템 상태 (System Health) - `4_system.py`
-   **Component Status**: DB, Redis 연결 상태 (Ping).
-   **Notification Stats**: Week 5 구축한 알림 발송 내역 및 성공/실패 통계.
-   **Recent Logs**: 시스템 에러 로그 요약 (`system_logs` 테이블).

---

## 3. 구현 단계 (Step-by-Step)

### Phase 1: Foundation & Structure (Day 1)
-   **Directory Structure Refactoring**:
    ```
    src/dashboard/
    ├── app.py              # 메인 엔트리포인트 (Navigation)
    ├── pages/
    │   ├── 1_overview.py
    │   ├── 2_market.py
    │   ├── 3_risk.py       # (New) Risk Dashboard
    │   ├── 4_history.py    # Trade Logs
    │   └── 5_system.py
    ├── components/
    │   ├── metrics.py
    │   ├── charts.py
    │   └── tables.py
    └── utils/
    ```
-   **DB Connection**: `market_candle`, `trade_history` 등 핵심 테이블 매핑 확인.

### Phase 2: Core Visualization (Day 2)
-   **Metrics Component**: 자산/수익률 계산 로직 구현.
-   **Interactive Charts**: Plotly를 이용한 반응형 캔들차트 및 매매 마커 매핑.
-   **Risk Panel**: 리스크 한도 대비 현재 상태 시각화 컴포넌트 구현.

### Phase 3: Integration & Polish (Day 3)
-   **Notification Integration**: 알림 발송 로그 조회 기능 추가.
-   **Week 7 Prep**: AI Assistant 연동을 위한 UI Placeholder 및 API Interface 스켈레톤 추가.
-   **Auto-refresh**: `st.rerun()` + `time.sleep()` 기반의 Polling 메커니즘 적용 (주기: 30초).

### Phase 4: Documentation & Handover (Day 4)
-   `USER_MANUAL.md`: 대시보드 사용법 및 봇 운영 가이드.
-   `FAILURE_ANALYSIS.md`: 장애 발생 시 대응 절차.

---

## 4. 검증 계획 (Verification)
1.  **데이터 정확성 (Data Integrity)**
    -   대시보드 자산 = 거래소 잔고 = DB 기록 일치 여부 확인.
2.  **안정성 (Stability)**
    -   **Memory Leak Test**: `memory_profiler` 또는 `tracemalloc`을 사용하여 1시간 이상 실행 시 메모리 증가 추이 확인.
3.  **반응성 (Responsiveness)**
    -   차트 로딩 시간 3초 이내 달성 여부.

---

## 5. Claude Code Review

### Review #1 (v1 → v2)
**Date**: 2026-01-30
**Status**: 보완 요청 → Antigravity가 피드백 반영 완료

---

### Review #2 (v2 Final Review)
**Reviewer**: Claude Code (Opus 4.5)
**Date**: 2026-01-30
**Status**: ✅ **APPROVED**

#### 피드백 반영 확인

| 항목 | 반영 여부 |
|------|----------|
| DB 테이블 명세 | ✅ §2.1에 Target Tables 명시 |
| 리스크 대시보드 | ✅ §2.2.C `3_risk.py` 신규 추가 |
| 알림 시스템 연동 | ✅ §2.2.D Notification Stats 포함 |
| Week 7 챗봇 대비 | ✅ Phase 3 AI Interface 스켈레톤 |
| Auto-refresh 상세화 | ✅ Phase 3 Polling 30초 주기 명시 |
| 메모리 테스트 방법 | ✅ §4.2 memory_profiler/tracemalloc |
| 디렉토리 구조 | ✅ Phase 1 구체적 구조 명시 |

#### 최종 평가

- **PROJECT_CHARTER 정합성**: ✅ Week 6 목표(대시보드 고도화, 문서화) 완전 충족
- **system_overview.md 연계**: ✅ Dashboard 컴포넌트 역할과 일치
- **구현 가능성**: ✅ 4일 일정 내 현실적 범위
- **확장성**: ✅ Week 7 챗봇 연동 준비 완료

---

**결론**: 계획서 최종 승인. 코드 구현을 진행해주세요.
