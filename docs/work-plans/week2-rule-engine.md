# Week 2 Implementation Plan: Rule Engine & Risk Manager

> **작성일**: 2026-01-23
> **목표**: 매매 전략(Rule Engine)과 리스크 관리(Risk Manager) 핵심 로직 구현 및 검증

## 1. Goal Description
Week 2의 핵심 목표는 **"매매 판단의 뇌"**를 만드는 것입니다.
AI가 아닌 **Rule-Based 시스템**이 트레이딩의 핵심 의사결정(진입/청산)과 리스크 통제를 담당하도록 구현합니다.
(Reference: `PROJECT_CHARTER.md` Section 3 & 4)

## 2. User Review Required
> [!IMPORTANT]
> **전략 파라미터 확인**:
> *   **RSI Period**: 14 (진입 < 30, 청산 > 70)
> *   **Moving Average**: 200일 (추세 필터용)
> *   **Bollinger Band**: 20일, 2.0 표준편차
> *   **Volume**: 20일 평균의 1.5배 이상

> [!WARNING]
> **Hard-coded Risk Rules**:
> *   단일 종목 최대 비중: 5%
> *   계좌 일일 손실 한도: -5% (도달 시 당일 거래 중단)
> *   이 규칙들은 코드 레벨에서 강제되어야 하며, AI가 수정할 수 없습니다.

## 3. Proposed Changes

### A. Common Utilities `src/common/`
#### [NEW] [indicators.py](file:///home/syt07203/workspace/coin-pilot/src/common/indicators.py)
*   `pandas` / `ta-lib` (or `numpy`) 기반 기술적 지표 계산 함수.
*   `calculate_rsi`, `calculate_ma`, `calculate_bb`, `calculate_volume_ratio`.

### B. Rule Engine `src/engine/`
#### [NEW] [strategy.py](file:///home/syt07203/workspace/coin-pilot/src/engine/strategy.py)
*   `BaseStrategy`: 전략 인터페이스 정의.
*   `MeanReversionStrategy`: `PROJECT_CHARTER` 3.1절 전략 구현.
    *   `check_entry_signal(candle)`: 매수 신호 판별.
    *   `check_exit_signal(position, candle)`: 매도/손절/익절 신호 판별.

#### [NEW] [risk_manager.py](file:///home/syt07203/workspace/coin-pilot/src/engine/risk_manager.py)
*   **Safety Layer**: 주문 실행 전 최종 관문.
*   `check_order_validity(account, order)`: 자산 비중, 일일 손실 한도 체크.
*   `can_trade()`: 쿨다운 상태 및 일일 최대 거래 횟수 확인.

#### [NEW] [executor.py](file:///home/syt07203/workspace/coin-pilot/src/engine/executor.py)
*   (Week 2 범위: Mock/Paper Trading)
*   실제 거래소 API 호출 대신 DB에 매매 기록(`trading_history`)을 남기거나 로그 출력.

### C. Database Models `src/common/`
#### [MODIFY] [models.py](file:///home/syt07203/workspace/coin-pilot/src/common/models.py)
*   필요 시 `TradeHistory` 모델 구체화 (Strategy Name, Signal Info 등 필드 추가).

## 4. Verification Plan

### Automated Tests
*   **Unit Tests**:
    *   `tests/test_indicators.py`: 지표 계산 정확성 검증 (알려진 데이터셋 대조).
    *   `tests/test_strategy.py`: 특정 캔들 패턴 주입 시 진입/청산 신호 발생 여부.
    *   `tests/test_risk.py`: 한도 초과 주문 시 `Reject` 반환 여부.

### Manual Verification
*   `scripts/simulate_strategy.py` (임시):
    *   과거 데이터(Historic Data)를 로드하여 전략 시뮬레이션 돌려보기.
    *   로그 상에 `ENTRY`, `EXIT`, `RISK_REJECT`가 정상적으로 찍히는지 확인.
