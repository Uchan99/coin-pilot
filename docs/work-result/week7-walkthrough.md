# Week 7 Walkthrough: AI Chatbot Integration
**Date**: 2026-01-31
**Author**: Antigravity (Assistant)

## 1. Executive Summary
Week 7의 목표인 **"데이터 기반 대화형 분석 도구(AI Chatbot)"** 구축을 완료했습니다.
LangChain과 Claude(Haiku)를 활용하여 프로젝트 문서(RAG)와 자산 데이터(SQL)를 조회할 수 있는 하이브리드 Chatbot Agent를 개발하고, 이를 Streamlit 대시보드에 성공적으로 통합했습니다.

## 2. Architecture Overview
*   **Vector Infrastructure**: `pgvector` 기반의 지식 베이스 구축 (문서 34개)
*   **Agent System**: LangGraph State Machine을 활용한 라우팅 구조
    *   `Router`: 사용자 의도 파악 (DB 조회 vs 문서 검색 vs 일반 대화)
    *   `SQL Agent`: 안전한 Read-Only SQL 쿼리 생성 및 실행
    *   `RAG Agent`: 벡터 검색을 통한 Q&A 수행
*   **User Interface**: 비동기 처리를 지원하는 Streamlit Chatbot UI

## 3. Implementation Details

### Phase A: Architecture & Infrastructure
**Goal**: 챗봇 구동을 위한 데이터베이스 및 문서 임베딩 환경 구축

1.  **Configuration (`src/agents/config.py`)**:
    *   Model: `claude-3-haiku-20240307` (LLM), `all-MiniLM-L6-v2` (Embedding)
    *   설정 파일 분리로 유지보수성 확보

2.  **Database Migration (`migrations/004_add_pgvector.sql`)**:
    *   PostgreSQL `vector` 확장 활성화
    *   임베딩 저장용 테이블 스키마 및 IVFFlat 인덱스 구성

3.  **Data Ingestion (`scripts/ingest_docs.py`)**:
    *   `docs/` 디렉토리 내 마크다운 파일 34개 파싱
    *   301개의 청크(Chunk)로 분할하여 벡터 저장소 적재 완료

### Phase B: Agents Implementation
**Goal**: 실제 질의 응답을 수행하는 핵심 로직(Back-end) 구현

1.  **SQL Agent (`src/agents/sql_agent.py`)**:
    *   LangChain `SQLDatabase` Toolkit 활용
    *   **Safety**: DML(수정/삭제) 금지 프롬프트 및 Read-Only 권한 원칙 적용
    *   `account_state`, `market_data` 테이블 조회 가능

2.  **RAG Agent (`src/agents/rag_agent.py`)**:
    *   `PGVector` + `create_retrieval_chain` 조합
    *   프로젝트 아키텍처, 매매 전략(손절 규칙 등)에 대한 정확한 답변 생성

3.  **Router Agent (`src/agents/router.py`)**:
    *   **LangGraph** 기반의 유연한 라우팅 설계
    *   Hybrid Routing: 1차 키워드 매칭(Fast) → 2차 LLM 분류(Slow)
    *   Fallback 처리: 에러 발생 시 일반 대화 모드로 우회

### Phase C: UI Integration
**Goal**: 사용자가 쉽게 접근할 수 있는 웹 인터페이스(Front-end) 구현

1.  **Chatbot Dashboard (`src/dashboard/pages/06_chatbot.py`)**:
    *   Streamlit의 `chat_message`, `chat_input` 컴포넌트 활용
    *   **Async Bridge**: `asyncio.run()`을 통해 비동기 Agent 로직과 동기 Streamlit 런타임 연결
    *   로딩 인디케이터(`st.spinner`) 및 대화 히스토리 관리(`st.session_state`) 구현

## 4. Verification Results

### Integration Test Scenarios
모든 기능이 통합 테스트(`tests/agents/test_manual.py`) 및 UI 수동 테스트를 통과했습니다.

| Scenario | Input Query | Router Action | Agent Response | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Financial** | "현재 총 자산이 얼마야?" | `db_query` | SQL Agent: `SELECT balance ...` 실행 후 "10,000,000 KRW" | ✅ Pass |
| **Market Data** | "비트코인 가격 알려줘" | `db_query` | SQL Agent: `SELECT close_price ...` 실행 후 가격 반환 | ✅ Pass |
| **Knowledge** | "이 프로젝트의 아키텍처는?" | `doc_search` | RAG Agent: 문서 검색 후 아키텍처 요약 | ✅ Pass |
| **Rules** | "손절 규칙이 뭐야?" | `doc_search` | RAG Agent: 리스크 관리 규칙 설명 | ✅ Pass |
| **General** | "안녕, 넌 누구니?" | `general_chat` | Router: 기본 인사말 반환 | ✅ Pass |

## 5. Known Issues & Future Work
*   **Streaming UI**: 현재는 답변 완료 후 전체 출력 방식입니다. 향후 Token 단위 스트리밍 적용을 검토할 수 있습니다 (Known Issue).
*   **History Persistence**: 대화 내역이 세션에만 저장되므로, 영구 저장을 위한 DB 테이블 설계가 필요할 수 있습니다.
*   **Advanced Analysis**: 단순 조회를 넘어, "최근 변동성이 큰 코인은?"과 같은 복합 분석 에이전트로 고도화할 예정입니다.

## 6. Deliverables

### 6.1 Code Artifacts
| File | Description |
|------|-------------|
| `src/agents/config.py` | LLM/Embedding 모델 설정 |
| `src/agents/sql_agent.py` | DB 조회 Agent |
| `src/agents/rag_agent.py` | 문서 검색 Agent |
| `src/agents/router.py` | LangGraph 기반 라우터 |
| `src/dashboard/pages/06_chatbot.py` | Chatbot UI |
| `scripts/ingest_docs.py` | 문서 임베딩 스크립트 |
| `tests/agents/test_manual.py` | 통합 테스트 |

### 6.2 Documentation
- **[Week 7 Troubleshooting Log](../troubleshooting/week7-ts.md)**: 의존성 충돌, 모델 에러 등 해결 과정 기록

### 6.3 Dependencies (Pinned)
```
langchain==0.3.0
langchain-anthropic==0.3.15
langchain-openai==0.3.19
langchain-huggingface==0.2.0
langchain-community==0.3.0
langgraph==1.0.7
```

---

## 7. Conclusion
Week 7을 통해 CoinPilot은 단순한 자동매매 봇을 넘어, 사용자와 상호작용하며 정보를 제공하는 **Intelligent Assistant**로 진화했습니다.
이 기반은 향후 Week 8의 고도화 작업(Monitoring, Notification, Volatility Model)과 연동되어 더욱 강력한 분석 도구가 될 것입니다.
