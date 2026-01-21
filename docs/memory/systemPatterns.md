# System Patterns

## Architecture
- **MSA 지향 구조**: 계층형 분리보다는 기능별 서비스 분리를 지향.
  - `collector`: 데이터 수집 전담.
  - `engine`: 매매 전략 및 리스크 관리 핵심 로직.
  - `assistant`: LLM 기반 분석 및 SQL 생성 보조.
  - `api`: 대시보드 및 외부 연동 인터페이스.
  - `common`: 공유 모델 및 유틸리티.

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
- **Backend Framework**: FastAPI
- **ORM**: SQLAlchemy (Async/AsyncIO)
- **Database**: PostgreSQL (TimescaleDB, pgvector)
- **AI/LLM**: LangGraph, LangChain
- **Infra**: Docker, Kubernetes (Minikube)
