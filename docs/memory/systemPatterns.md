# System Patterns

## Core Design Principle
> **"AI가 실패해도 시스템은 동작한다"** (PROJECT_CHARTER 2.2절)

- Rule Engine + Risk Manager = **Core (필수, 100%)**
- SQL Agent + RAG Agent + Volatility Model = **Assistant (보조, 대체/비활성 가능)**
- AI는 의사결정을 보조하지만, 핵심 매매 로직은 검증 가능한 룰 기반 시스템이 담당

## Architecture
- **MSA 지향 구조**: 계층형 분리보다는 기능별 서비스 분리를 지향.
  - `collector`: 데이터 수집 전담 (Upbit API 연동).
  - `engine`: 매매 전략(Rule Engine) 및 리스크 관리(Risk Manager) 핵심 로직.
  - `assistant`: LLM 기반 분석 및 SQL 생성 보조 (LangGraph 워크플로우).
  - `api`: 대시보드 및 외부 연동 인터페이스 (FastAPI).
  - `common`: 공유 모델(ORM) 및 유틸리티(DB 연결).

## Database Strategy
- **PostgreSQL 15/16 + TimescaleDB**: 시계열 데이터 처리 성능 확보.
- **Hypertable**: `market_data` 테이블을 하이퍼테이블로 변환하여 관리 (7일 압축 정책 적용).
- **Relational Tables**: `trading_history`, `risk_audit` 등 정규화된 관계형 테이블 사용.
- **Vector Search**: `pgvector`를 활용하여 `agent_memory` 테이블 내 임베딩 데이터 저장 및 유사도 검색.

## Project Structure
```text
coin-pilot/
├── deploy/
│   ├── db/
│   │   └── init.sql
│   └── docker-compose.yml
├── docs/
│   ├── memory/
│   ├── troubleshooting/
│   ├── work-plans/
│   ├── work-result/
│   └── PROJECT_CHARTER.md
├── scripts/
│   ├── check_data.py
│   ├── reinit_db.py
│   └── verify_db.py
├── src/
│   ├── api/
│   ├── assistant/
│   ├── collector/
│   │   └── main.py
│   ├── common/
│   │   ├── db.py
│   │   └── models.py
│   └── engine/
├── tests/
├── requirements.txt
├── CLAUDE.md
└── README.md
```

## Tech Stack
- **Language**: Python 3.10+
- **Backend Framework**: FastAPI (비동기 API)
- **ORM**: SQLAlchemy (Async/AsyncIO + asyncpg)
- **Database**: PostgreSQL 15 (TimescaleDB 하이퍼테이블, pgvector 벡터 검색)
- **AI/LLM Framework**: LangGraph (워크플로우), LangChain (도구 연동)
- **LLM Provider**: GPT-4o-mini / Claude 3.5 (비용 효율성)
- **Volatility Model**: GARCH / PyTorch (선택적)
- **Vector DB**: ChromaDB (뉴스 및 Agent Memory 저장)
- **Infra**: Docker, Kubernetes (Minikube)
- **CI/CD**: GitHub Actions

## Key Decisions Log
| 결정 | 근거 | 참조 |
| :--- | :--- | :--- |
| TimescaleDB 선택 | 시계열 쿼리 성능, 압축 정책 | PROJECT_CHARTER 5절 |
| ORM-SQL 분리 | TimescaleDB 확장은 SQL로, 앱 로직은 ORM으로 | week1-ts.md Issue #4 |
| pgvector 사용 | Agent Memory 임베딩 저장 및 유사도 검색 | PROJECT_CHARTER 4.2절 |
| LangGraph 채택 | Multi-Agent 오케스트레이션, 워크플로우 관리 | PROJECT_CHARTER 1.2절 |
