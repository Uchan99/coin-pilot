# CoinPilot v3.0

> **Kubernetes-native Crypto Trading System**  
> "Reaction over Prediction" — Rule-based core trading with AI assistance.

CoinPilot v3.0은 **Microservice Architecture (MSA)** 기반의 자동매매 시스템으로, **PostgreSQL (TimescaleDB + pgvector)**을 중심으로 한 데이터 파이프라인과 **LangGraph** 기반의 AI Agent를 결합하여 안정적이고 지능적인 트레이딩 환경을 제공합니다.

---

## 🚩 Core Philosophy (핵심 철학)

1.  **Reaction over Prediction (예측보다 대응)**
    *   미래 가격을 예측하려 하기보다, 현재 시장 상황(Rule)에 맞춰 기계적으로 대응합니다.
2.  **Rule-Based Core (룰 기반 핵심)**
    *   자산이 오가는 매매 결정은 검증된 알고리즘(Rule Engine)이 담당합니다.
    *   AI는 매매를 직접 수행하지 않고, 시장 분석, 리스크 감지, 데이터 조회(SQL) 등 **보조(Assistant)** 역할에 집중합니다.
3.  **Principled Engineering**
    *   "Why"가 설명되지 않는 코드는 작성하지 않습니다.
    *   모든 핵심 로직은 한국어 주석으로 상세히 설명됩니다.

---

## 🏗 Architecture

이 프로젝트는 기능별 독립성을 위해 MSA 구조를 지향합니다.

### 1. Services
*   **Collector** (`src/collector`): Upbit API 등을 통한 실시간 데이터 수집.
*   **Engine** (`src/engine`): 매매 전략(Rule Engine) 및 리스크 관리(Risk Manager).
*   **Assistant** (`src/assistant`): LangGraph 기반 AI 분석 및 SQL 생성.
*   **API** (`src/api`): 대시보드 및 외부 연동을 위한 FastAPI 서버.

### 2. Database Strategy
*   **PostgreSQL 16**: 메인 관계형 데이터베이스.
*   **TimescaleDB**: `market_data` 등 시계열 데이터의 고성능 처리 및 압축 관리 (Hypertable).
*   **pgvector**: AI Agent의 기억(Memory) 및 뉴스 임베딩 저장을 위한 벡터 검색 지원.

---

## 🤖 AI Assistant Architecture

AI는 **매매 결정을 내리지 않고**, 분석과 리스크 감지를 담당하는 **보조 역할(Assistant Role)**에 집중합니다.

### AI Agents
| Agent | 역할 | 입력 | 출력 |
| :--- | :--- | :--- | :--- |
| **SQL Agent** | 자연어 질의 → SQL 변환 | "최근 4시간 RSI 30 이하?" | `SELECT * FROM market_candle ...` |
| **RAG Agent** | 뉴스 리스크 감지 | "해킹", "규제", "상폐" 키워드 | `HALT_TRADING` or `CLEAR` |
| **Volatility Model** | 변동성 예측 → 포지션 사이징 | 시장 데이터 | 변동성 높음 → 포지션 50% 축소 |
| **Critic Agent** | SQL/검색 결과 타당성 검증 | Agent 출력 결과 | 승인 or 재작업 요청 |

### 핵심 원칙: **"AI가 실패해도 시스템은 동작한다"**
- Rule Engine과 Risk Manager는 AI와 독립적으로 작동합니다.
- AI는 보조 정보를 제공하되, 최종 결정권은 없습니다.

---

## 🛡️ Risk Management

자산을 보호하기 위한 **Hard-coded 규칙**으로, AI가 오버라이드할 수 없습니다.

| 규칙 | 값 | 위반 시 조치 |
| :--- | :--- | :--- |
| **단일 포지션 한도** | 총 자산의 5% | 주문 거부 |
| **일일 최대 손실** | -5% | 당일 거래 중단 |
| **일일 최대 거래** | 10회 | 당일 거래 중단 |
| **쿨다운** | 3연패 시 | 2시간 거래 중단 |
| **최소 거래 간격** | 30분 | 주문 지연 |

---

## 📊 Trading Strategy

### Mean Reversion + Trend Filter
과매도 구간 반등을 노리되, 역추세 진입을 방지합니다.

#### 진입 조건 (Long)
| 조건 | 기준 | 근거 |
| :--- | :--- | :--- |
| **RSI (14)** | < 30 | 과매도 구간 진입 |
| **Price vs MA(200)** | > MA 200 | 장기 상승 추세 확인 (필터) |
| **Volume** | > 20일 평균의 1.5배 | 의미 있는 매도 압력 확인 |
| **Bollinger Band** | 하단 밴드 터치 | 통계적 극단값 도달 |

#### 청산 조건
| 유형 | 조건 | 설명 |
| :--- | :--- | :--- |
| **Take Profit** | +5% 도달 | 목표 수익 달성 시 전량 청산 |
| **Stop Loss** | -3% 도달 | 손실 제한 (필수) |
| **Signal Exit** | RSI > 70 | 과매수 구간 진입 시 청산 |
| **Time Exit** | 48시간 경과 | 장기 보유 방지 |

---

## 🛠 Tech Stack

| Category | Stack | Rationale |
| :--- | :--- | :--- |
| **Language** | Python 3.10+ | Type Hinting 적극 활용 |
| **Framework** | FastAPI | 비동기 API 서버 |
| **Database** | PostgreSQL 16 | TimescaleDB (Time-series) + pgvector (Vector) |
| **ORM** | SQLAlchemy AsyncIO | 비동기 DB 처리 |
| **AI Framework** | LangGraph, LangChain | Multi-Agent Workflow 관리 |
| **LLM** | GPT-4o-mini / Claude 3.5 | 비용 효율성 |
| **Volatility Model** | GARCH / PyTorch | 변동성 예측용 |
| **Infra** | Docker, Kubernetes | MSA, Self-healing (Minikube 개발 환경) |
| **CI/CD** | GitHub Actions | 자동화 |

---

## 📂 Project Structure

```text
coin-pilot/
├── deploy/             # Docker Compose 및 K8s 설정
│   ├── db/             # DB 초기화 스크립트 (init.sql)
│   └── docker-compose.yml
├── docs/               # 프로젝트 문서 및 메모리
│   ├── memory/         # Context, Design Patterns
│   └── work-plans/     # 주차별 작업 계획서
├── scripts/            # 유틸리티 스크립트 (DB 검증 등)
├── src/                # 소스 코드
│   ├── collector/      # 데이터 수집기
│   ├── engine/         # 매매 엔진 (Strategy, Risk)
│   ├── assistant/      # AI 에이전트
│   └── common/         # 공통 모듈 (DB, Models)
└── tests/              # 테스트 코드
```

---

## 🚀 Getting Started

### Prerequisites
*   Docker & Docker Compose
*   Python 3.10+ (Check `requirements.txt`)
*   Upbit API Key (Paper Trading 또는 실전 모드)

### Installation & Run
1.  **환경 설정 (Environment Setup)**
    ```bash
    # .env 파일 생성 및 설정
    cp .env.example .env
    # .env 파일에 API Key 및 환경 변수 설정
    ```

2.  **데이터베이스 실행 (Run Database)**
    ```bash
    # PostgreSQL + TimescaleDB + pgvector 구동
    cd deploy
    docker-compose up -d db
    ```

3.  **애플리케이션 실행 (Run Services)**
    ```bash
    # Collector 실행 (데이터 수집)
    python -m src.collector.main

    # Rule Engine 실행 (매매 엔진)
    python -m src.engine.main

    # API Server 실행 (대시보드)
    python -m src.api.main
    ```

---

## 📅 Development Roadmap

| Week | 주제 | 핵심 작업 |
| :--- | :--- | :--- |
| **Week 1** | Foundation | 데이터 파이프라인 (Collector, DB), Paper Trading 로직 |
| **Week 2** | Core Logic | Rule Engine, Risk Manager, 백테스팅 엔진 |
| **Week 3** | AI Integration | SQL Agent, RAG Agent, LangGraph 통합 |
| **Week 4** | Infrastructure | Docker, K8s 배포, 모니터링 (Prometheus/Grafana) |
| **Week 5** | Finish | 대시보드(Streamlit), 문서화(실패 분석 포함) |

---

## 🎯 Differentiation Points (차별화 요소)

이 프로젝트는 단순 트레이딩 봇이 아닌 **엔지니어링 역량 증명용 포트폴리오**입니다.

| 일반적인 프로젝트 | **CoinPilot v3.0** |
| :--- | :--- |
| "가격 예측 90% 정확도" | **예측 불가능성 인정, 대응 중심 설계** |
| 수익률만 강조 | **리스크 관리 + 실패 분석 문서화** |
| 로컬 실행 | **Kubernetes 배포 + CI/CD** |
| AI 의존 | **AI 실패 시에도 동작하는 Fallback 설계** |
| Agent 단순 사용 | **Agent Memory + Self-Reflection** |
| 단일 전략 | **Mean Reversion + Trend Filter 조합** |

### 증명하고자 하는 역량
1. **Quant Architecture:** 데이터 파이프라인, 백테스팅, 실행 엔진 구현
2. **LLM Agent Design:** LangGraph, Tool-using, Multi-Agent 오케스트레이션
3. **MLOps/DevOps:** Kubernetes, 모니터링, CI/CD
4. **Finance Domain:** 리스크 관리, 성과 측정, 시장 미시구조 이해

---



---

> **Note**: 이 프로젝트는 학습 및 실전 매매를 목적으로 하며, 투자의 책임은 사용자 본인에게 있습니다.
