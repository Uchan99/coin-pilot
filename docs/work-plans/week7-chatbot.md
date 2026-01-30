# Week 7 Work Plan: AI Chatbot Integration (v2)

## 1. Goal
**"데이터에 기반한 대화형 분석 도구 구축"**
사용자가 자연어로 질문하면, SQL을 통해 DB에서 데이터를 조회하거나(SQL Agent), 프로젝트 문서를 검색하여(RAG Agent) 답변하는 챗봇을 구현하고 대시보드에 통합합니다.

## 2. Design Decisions & Rationale (Why?)

### 2.1 Architecture: LangGraph Router Pattern
*   **Why?**: 단순 Chain이 아닌 **Graph** 구조를 사용하여, 질문의 의도에 따라 SQL Agent와 RAG Agent를 명확히 분기(Branching)하고, 필요시 검색 결과를 검증하는 루프(Loop)를 구성하기 위함입니다.
*   **Flow**: `User Query` -> `Router` -> (`SQL Agent` OR `RAG Agent`) -> `Final Response`

### 2.2 Tech Stack Selection
| Component | Tech | Selection Reason |
| :--- | :--- | :--- |
| **LLM (Dev)** | **Claude 3 Haiku (20240307)** | 개발 및 단순 쿼리 변환 시 비용 효율성 최적화 (PROJECT_CHARTER 준수, 3.5 Haiku는 API 미지원으로 3.0 사용) |
| **LLM (Prod)** | **Claude 3.5 Sonnet** | 복잡한 의도 파악 및 정확한 SQL 생성을 위한 고성능 모델 |
| **Embedding** | **HuggingFace (all-MiniLM-L6-v2)** | 로컬 실행 가능, 무료, 가벼우면서도 준수한 성능 (한국어 지원 고려 시 `ko-sbert` 검토 가능하나 일단 표준 모델 사용) |
| **Vector DB** | **pgvector** | 기존 PostgreSQL 인프라 재사용 (관리 포인트 최소화) |
| **Framework** | **LangGraph** | 상태 관리(State)와 복잡한 분기 처리에 특화됨 |

## 3. Detailed Architecture

### 3.1 System Architecture
```mermaid
graph TD
    User[User] -->|Text Query| Dashboard[Streamlit Dashboard]
    Dashboard -->|Stream| Router[Chat Router (src/agents/router.py)]
    
    subgraph "LangGraph Workflow"
        Router -->|Intent: DB Analysis| SQLAgent[SQL Agent]
        Router -->|Intent: Doc Search| RAGAgent[RAG Agent]
        Router -->|Intent: General| CurChat[General Chat]
        
        SQLAgent -->|Generate SQL| DB[(PostgreSQL)]
        RAGAgent -->|Vector Search| VectorStore[(pgvector)]
    end
    
    SQLAgent -->|Result| Synthesizer[Response Synthesizer]
    RAGAgent -->|Context| Synthesizer
    
    Synthesizer -->|Final Answer| Dashboard
```

### 3.2 Router Logic (Classification)
단순 키워드 매칭과 LLM 분류를 하이브리드로 사용합니다.
*   **1차 (Keyword)**: "수익률", "잔고", "얼마" -> `SQL Agent` 강제 라우팅
*   **2차 (LLM)**: 키워드로 불분명할 경우 LLM에게 의도 분류 요청 (`tool_choice` 활용)

### 3.3 Database Schema (pgvector)
RAG를 위한 임베딩 저장소 테이블을 추가합니다.
```sql
-- migrations/004_add_pgvector.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_embeddings (
    id SERIAL PRIMARY KEY,
    source_file TEXT NOT NULL, -- e.g., 'PROJECT_CHARTER.md'
    content TEXT NOT NULL,
    embedding vector(384),     -- all-MiniLM-L6-v2 dimension
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 검색 속도 향상을 위한 인덱스
CREATE INDEX ON document_embeddings USING ivfflat (embedding vector_cosine_ops);
```

## 4. Implementation Process

### Phase A: Architecture & Base Setup (Day 1)
*   **Step 1: Configuration & Migration**
    *   `src/agents/config.py`: 모델 설정 (`LLM_MODEL`, `EMBEDDING_MODEL`)
    *   `migrations/004_add_pgvector.sql`: 벡터 테이블 생성 스크립트 작성 및 실행
*   **Step 2: Vector Store Loader**
    *   `scripts/ingest_docs.py`: `docs/` 폴더 내 마크다운 파일을 청킹하여 DB에 저장하는 스크립트 구현

### Phase B: Agents Implementation (Day 2-3)
*   **Step 3: SQL Agent**
    *   `src/agents/sql_agent.py`: LangChain `SQLDatabase` 연동, Read-Only 권한 설정
    *   Prompt Engineering: "테이블 스키마와 컬럼 의미를 정확히 알려주는 시스템 프롬프트"
*   **Step 4: RAG Agent**
    *   `src/agents/rag_agent.py`: pgvector 기반 검색 및 답변 생성
*   **Step 5: Router (Main)**
    *   `src/agents/router.py`: LangGraph Entrypoint. 사용자 입력을 라우팅하고 에러 핸들링(Fallback) 구현
    *   **Fallback**: 에러 발생 시 "죄송합니다, 처리에 실패했습니다. (Error: ...)" 메시지 반환

### Phase C: UI Integration (Day 4)
*   **Step 6: Streamlit Chatbot**
    *   `src/dashboard/pages/06_chatbot.py`
    *   **Streaming**: `st.write_stream`과 `agent.astream()` 연동하여 타자 치듯 응답 출력

## 5. Verification Plan

### 5.1 Automated Tests
*   `tests/agents/test_router.py`: 의도 분류가 정확한지 테스트 (Mock LLM)
*   `tests/agents/test_sql.py`: 주요 재무 질문(수익률, 잔고)에 대해 올바른 SQL이 생성되는지 확인

### 5.2 Manual Verification Scenario
1.  **설정값 확인**: SQL Agent가 진짜 `SELECT`만 가능한지 확인 (DML 시도 -> 에러 기대)
2.  **RAG 정확도**: "이 프로젝트의 목표가 뭐야?" 질문 시 `PROJECT_CHARTER.md` 내용 인용 여부
3.  **UI 반응성**: 긴 답변 생성 시 스트리밍이 끊기지 않고 자연스러운지 확인

## 6. User Review & Safety
> [!WARNING]
> **Cost Alert**: 임베딩 생성(OpenAI 사용 시) 및 LLM 호출 비용이 발생할 수 있습니다. 초기에는 무료 Embedding 모델(HuggingFace)을 사용합니다.

---

## Claude Code Review

### Review #1 (v1 → v2)
**Date**: 2026-01-31
**Status**: 보완 요청 → Antigravity 피드백 반영 완료

---

### Review #2 (v2 Final Review)
**Reviewer**: Claude Code (Opus 4.5)
**Date**: 2026-01-31
**Status**: ✅ **APPROVED**

#### 피드백 반영 확인

| 권장 사항 | 반영 위치 | 상태 |
|----------|----------|------|
| LLM 모델 명시 | §2.2 Tech Stack Selection | ✅ Haiku(Dev)/Sonnet(Prod) |
| Embedding 모델 선택 | §2.2 Tech Stack Selection | ✅ HuggingFace all-MiniLM-L6-v2 |
| Router 라우팅 기준 | §3.2 Router Logic | ✅ 하이브리드 (키워드 + LLM) |
| pgvector DDL | §3.3 Database Schema | ✅ 전체 스크립트 포함 |
| 에러 핸들링 | §4 Phase B Step 5 | ✅ Fallback 로직 명시 |
| 스트리밍 구현 | §4 Phase C Step 6 | ✅ astream() 연동 명시 |
| 파일 네이밍 | §3.1 Architecture | ✅ `router.py`로 변경 |

#### v2 추가 개선 사항 (우수)

| 항목 | 내용 |
|------|------|
| **Design Rationale 섹션** | "왜 이 기술을 선택했는가" 근거 명시 |
| **General Chat 라우팅** | SQL/RAG 외 일반 대화 처리 경로 추가 |
| **Response Synthesizer** | Agent 결과 통합 노드 추가 |
| **Document Ingestion Script** | `scripts/ingest_docs.py` 명시 |
| **source_file 컬럼** | 임베딩 출처 추적 가능 |

#### PROJECT_CHARTER 정합성 최종 확인

| 로드맵 항목 | 계획서 반영 | 상태 |
|------------|------------|------|
| SQL Agent (자연어 → SQL) | §4 Phase B Step 3 | ✅ |
| RAG Agent (문서/규칙 검색) | §4 Phase B Step 4 | ✅ |
| Chatbot UI + Agent 통합 | §4 Phase C Step 6 | ✅ |
| 읽기 전용 권한 | §5.2 Manual Verification #1 | ✅ |
| LangGraph 통합 | §2.1, §3.1 | ✅ |

#### 최종 평가

| 항목 | 평가 |
|------|------|
| PROJECT_CHARTER 정합성 | ✅ 완전 일치 |
| 아키텍처 설계 | ✅ 우수 (Router + Synthesizer 패턴) |
| 기술 선택 근거 | ✅ 명확 (Why 섹션 추가) |
| 안전성 | ✅ Read-Only + Fallback |
| 구현 가능성 | ✅ 4일 일정 현실적 |
| 테스트 계획 | ✅ Unit + Manual 시나리오 |

---

**결론: 계획서 최종 승인. 코드 구현을 진행해주세요.**
