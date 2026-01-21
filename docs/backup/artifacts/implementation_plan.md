# Week 1: PostgreSQL Schema Design and Project Structure

이 계획서는 CoinPilot v3.0의 기초가 되는 DB 스키마 설계와 프로젝트 구조 정의를 목표로 합니다.

## User Review Required

> [!IMPORTANT]
> **데이터베이스 설계 원칙**
> 1. 시계열 데이터(캔들)와 관계형 데이터(거래 내역)의 분리 고려.
> 2. AI SQL Agent가 쿼리하기 쉬운 명확한 테이블 및 컬럼 명명 규칙 준수.
> 3. 리스크 관리(Hard-coded rules)를 위한 제약 조건 반영.

## Proposed Changes

### Project Structure (MSA-ready)

`coin-pilot/` 디렉토리 아래에 다음과 같은 구조를 사용합니다.

```text
coin-pilot/
├── src/                # 소스 코드 메인 디렉토리
│   ├── collector/      # 데이터 수집기 (Upbit API)
│   ├── engine/         # Rule Engine & Executor
│   ├── assistant/      # AI SQL/RAG Agents
│   ├── common/         # 공통 라이브러리 (Shared DB Models, Utils)
│   └── api/            # 외부 연동 및 대시보드 인터페이스
├── docs/               # 문서 (Charter, Plans, Guides)
├── deploy/             # Docker, K8s 관련 설정 (PgBouncer 포함)
├── tests/              # 단위 및 통합 테스트
└── scripts/            # 유틸리티 스크립트
```

### PostgreSQL Schema Design (TimescaleDB 기반)

#### 1. `market_data` (시계열 데이터 - Hypertable)
- `id`: BIGSERIAL
- `symbol`: VARCHAR(20) - 코인 심볼
- `interval`: VARCHAR(10) - 봉 간격
- `open_price`, `high_price`, `low_price`, `close_price`: NUMERIC(20, 8)
- `volume`: NUMERIC(20, 8)
- `timestamp`: TIMESTAMP WITH TIME ZONE (PK 구성요소)
- **Settings**:
    - `SELECT create_hypertable('market_data', 'timestamp');`
    - `SELECT add_compression_policy('market_data', INTERVAL '7 days');`
- **Indices**:
    - `idx_market_data_symbol_interval_time` (symbol, interval, timestamp DESC)

#### 2. `trading_history` (거래 기록)
- `id`: UUID (PK)
- `symbol`: VARCHAR(20)
- `side`: VARCHAR(10) (BUY/SELL)
- `order_type`: VARCHAR(10) (LIMIT/MARKET)
- `price`: NUMERIC(20, 8)
- `quantity`: NUMERIC(20, 8)
- `fee`: NUMERIC(20, 8)
- `status`: VARCHAR(20)
- `created_at`: TIMESTAMP WITH TIME ZONE
- `executed_at`: TIMESTAMP WITH TIME ZONE
- **Indices**:
    - `idx_trading_history_symbol_created` (symbol, created_at DESC)

#### 3. `risk_audit` (리스크 위반 기록)
- `id`: SERIAL (PK)
- `violation_type`: VARCHAR(50)
- `description`: TEXT
- `related_order_id`: UUID (FK -> trading_history)
- `timestamp`: TIMESTAMP WITH TIME ZONE

#### 4. `agent_memory` (AI 에이전트 기억장치)
- `id`: UUID (PK)
- `agent_type`: VARCHAR(20) (SQL_AGENT, RAG_AGENT)
- `context`: JSONB
- `decision`: TEXT
- `outcome`: VARCHAR(20) (SUCCESS, FAILURE)
- `embedding`: VECTOR(1536) (pgvector 사용)
- `created_at`: TIMESTAMP WITH TIME ZONE

## Verification Plan

### Automated Tests
- `pytest`를 사용하여 각 테이블 생성 및 제약 조건 검증.
- TimescaleDB 하이퍼테이블 및 압축 정책 설정 확인.
- `pgvector` 확장 설치 및 `agent_memory` 테이블 생성 확인.
- `EXPLAIN ANALYZE`를 통한 복합 인덱스 활용 여부 검증.

### Manual Verification
- `docker-compose`로 DB 띄운 후 `psql`을 통해 `\dt`, `\d+ table_name`으로 상세 구조 확인.
- Upbit API 샘플 데이터 100건 이상 삽입 후 조회 속도 테스트.
