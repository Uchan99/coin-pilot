# Migration Context: CoinPilot v3.0

> **작성일**: 2026-01-21
> **목적**: VMware(Linux)에서 WSL2(Windows)로 개발 환경 이전에 따른 맥락 보존 및 인수인계

---

## 1. Project Identity & User Persona
- **Project Name**: CoinPilot v3.0 (Kubernetes-native Crypto Trading System)
- **User Role**: Aspiring AI/ML Engineer (Focus on "Deep Understanding" & "Principles")
- **Core Philosophy**:
    - **Reaction over Prediction**: 예측보다 대응을 중시.
    - **Rule-Based Core**: 핵심 매매는 룰 엔진이, AI는 보조(Risk/SQL)만 수행.
    - **Principles**: 코드를 작성하기 전 "왜?"를 설명하고, 한국어 주석을 상세히 달 것.

## 2. Current Status (Week 1 Completed)
- **Objective**: PostgreSQL Schema Design & Project Structure Definition.
- **Accomplishments**:
    - **Infra**: Docker Compose로 PostgreSQL 16 + TimescaleDB + pgvector 구동 완료.
    - **Schema**: `market_data` (Hypertable), `trading_history`, `risk_audit`, `agent_memory` 테이블 생성 완료.
    - **Code**: `src/common/db.py` (SQLAlchemy AsyncIO), `src/collector/main.py` (Upbit 1분봉 수집) 구현.
    - **Verification**: `scripts/verify_db.py`, `scripts/check_data.py`로 정상 동작 검증됨.

## 3. Technology Stack Decisions (Why?)
- **MSA Structure**: `collector`, `engine`, `assistant`의 독립적 확장 및 장애 격리.
- **TimescaleDB**: 수백만 건의 캔들 데이터를 처리하기 위한 시계열 최적화 (Hypertable, 압축 정책).
- **pgvector**: 별도의 Vector DB 없이 AI Agent의 기억(Memory)을 관계형 데이터와 함께 관리하기 위함.
- **AsyncIO**: 데이터 수집과 조회 병목을 최소화하기 위해 비동기 처리 도입.

## 4. Pending Tasks (Week 2 Plan)
- **Goal**: Rule Engine & Risk Manager Implementation.
- **Core Logic**:
    - RSI, Moving Average 등 기술적 지표 계산 유틸리티 구현.
    - 진입/청산 전략(Mean Reversion + Trend Filter) 구현.
    - 리스크 관리(손실 한도, 쿨다운) 로직 구현.

## 5. Important Rules & Constraints (For AI Agent)
1.  **Teaching Mode**: 코드를 짜기 전에 반드시 논리와 아키텍처를 한국어로 설명할 것.
2.  **Safety First**: 금융 봇이므로 메모리 누수나 무한 루프에 각별히 주의할 것.
3.  **Documentation**: 변경 사항은 항상 Artifact(`task.md`, `walkthrough.md`)와 Memory Bank(`docs/memory/`)에 업데이트할 것.

## 6. How to Restore Context
새 환경에서 이 파일을 읽었다면, 아래 단계를 수행하여 '뇌'를 동기화하세요:
1.  `docs/memory/activeContext.md`와 `systemPatterns.md`를 필독하여 기술적 세부 사항 파악.
2.  `docs/troubleshooting/week1-ts.md`를 읽어 과거 시행착오 숙지.
3.  현재 상태를 **Week 2 시작 직전**으로 인식하고, 사용자의 다음 지시에 대기.
