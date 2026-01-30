# Week 7 Troubleshooting Log
**Subject**: Chatbot Integration Issues (Dependencies, Models, Async)
**Date**: 2026-01-31

Week 7(AI Chatbot Integration) 진행 중 발생한 주요 문제점과 해결 과정을 기록합니다.

## 1. LangChain Dependency Hell (Package Conflicts)

### 🔴 Issue
`langchain`, `langgraph`, `langchain-anthropic` 등을 설치하는 과정에서 심각한 의존성 충돌이 발생했습니다.
*   `ModuleNotFoundError: No module named 'langchain.chains'`
*   `langgraph-prebuilt`가 `langchain-core>=1.0.0`을 요구하나, 설치된 버전과의 불일치 발생.
*   원인: `langchain-classic` (1.x), `langchain` (0.3.x) 등 구버전과 신버전 패키지가 혼재되어 설치됨.

### 🟢 Resolution
과감하게 기존 관련 패키지를 모두 제거하고, **LangChain 0.3.x 표준 생태계**로 버전을 통일하여 재설치했습니다.

**해결 명령어**:
```bash
pip uninstall -y langchain langchain-classic langchain-huggingface langchain-anthropic langchain-openai
pip install langchain==0.3.0 \
            langchain-community==0.3.0 \
            langchain-anthropic==0.3.15 \
            langchain-openai==0.3.19 \
            langchain-huggingface==0.2.0 \
            langgraph==1.0.7
```

**Lesson**: LangChain은 버전 업데이트가 매우 빠르므로, 프로젝트 시작 시 `requirements.txt`에 버전을 명시적으로 **Pinning**하는 것이 필수적입니다.

---

## 2. LLM Model Not Found Error (404)

### 🔴 Issue
설정 파일(`config.py`)에 `LLM_MODEL = "claude-3-5-haiku-latest"`로 지정했으나, 실행 시 **404 Not Found** 에러가 발생했습니다.
*   에러 메시지: `{'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-5-haiku-latest'}}`

### 🟢 Resolution
Anthropic API에서 해당 Alias(`latest`)를 지원하지 않거나, 사용자의 API 키 권한 문제로 추정되었습니다.
안정적인 동작을 위해 **특정 날짜 버전(`claude-3-haiku-20240307`)** 으로 모델명을 변경했습니다.

**Code Change (`src/agents/config.py`)**:
```python
# Before
LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-5-haiku-latest")

# After
LLM_MODEL = os.getenv("LLM_MODEL", "claude-3-haiku-20240307")
```

---

## 3. SQLDatabase Async Support Issue

### 🔴 Issue
LangChain의 `SQLDatabase` Toolkit은 기본적으로 `sqlalchemy`의 동기(Sync) 드라이버를 필요로 합니다.
하지만 우리 프로젝트(`src/common/db.py`)는 `asyncpg` (비동기) URL만 제공하고 있었습니다.
이로 인해 에이전트 초기화 시 드라이버 호환성 에러가 발생했습니다.

### 🟢 Resolution
동기 처리가 필요한 도구를 위해 **URL 변환 유틸리티 함수**를 추가했습니다.

**Code Change (`src/common/db.py`)**:
```python
def get_sync_db_url() -> str:
    """
    LangChain SQLDatabase 등 동기식 연결이 필요한 도구를 위한 URL 반환
    (asyncpg -> psycopg2)
    """
    if not DATABASE_URL:
        return "postgresql+psycopg2://..."
    return DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
```

---

## 4. Streamlit Async Integration

### 🔴 Issue
`src/agents/router.py`는 `async/await` 기반의 비동기 함수(`process_chat`)로 작성되었으나, Streamlit은 기본적으로 동기 방식으로 동작합니다.
단순 호출 시 `coroutine object`만 반환되고 실제 실행되지 않는 문제가 있었습니다.

### 🟢 Resolution
`asyncio.run()`을 사용하여 Streamlit의 동기 컨텍스트 내에서 비동기 이벤트 루프를 생성하고 실행하도록 처리했습니다.

**Code Change (`src/dashboard/pages/06_chatbot.py`)**:
```python
import asyncio
...
# Run async agent loop in sync streamlit environment
response = asyncio.run(process_chat(prompt))
```

---

## 5. PGVector Table Schema Mismatch

### 🟡 Issue (Minor)
마이그레이션 스크립트(`004_add_pgvector.sql`)에서 `document_embeddings` 테이블을 생성했으나, LangChain의 `PGVector.from_documents()`는 내부적으로 자체 스키마를 사용합니다:
- `langchain_pg_collection`: 컬렉션 메타데이터
- `langchain_pg_embedding`: 실제 임베딩 데이터

### 🟢 Resolution
기능 동작에는 영향 없음. 마이그레이션 스크립트의 `document_embeddings` 테이블은 사용되지 않으므로 제거하거나, 향후 Custom 구현 시 활용 가능.

**검증 SQL**:
```sql
-- 실제 사용 테이블 확인
SELECT table_name FROM information_schema.tables
WHERE table_name LIKE '%langchain%';
-- Result: langchain_pg_collection, langchain_pg_embedding
```

---

## 6. Unused Import Error (Dashboard)

### 🔴 Issue
`06_chatbot.py`에서 사용하지 않는 모듈을 import하여 실행 시 `ModuleNotFoundError` 발생:
```python
from src.common.notification import send_telegram_message  # 미존재 모듈
```

### 🟢 Resolution
해당 import 라인 삭제.

**Lesson**: 개발 중 복사-붙여넣기로 인한 불필요한 import는 즉시 정리하는 습관이 필요합니다.

---

## Summary
Week 7에서는 AI/LLM 생태계의 복잡한 의존성 관리와 비동기/동기 환경 간의 통합 이슈가 주요 챌린지였습니다.
표준화된 버전을 사용하고, 명시적인 트러블슈팅을 통해 안정적인 시스템을 구축할 수 있었습니다.

| Issue | Severity | Status |
|-------|----------|--------|
| LangChain Dependency Hell | 🔴 High | ✅ Resolved |
| LLM Model Not Found (404) | 🔴 High | ✅ Resolved |
| SQLDatabase Async Support | 🟡 Medium | ✅ Resolved |
| Streamlit Async Integration | 🟡 Medium | ✅ Resolved |
| PGVector Table Schema | 🟢 Low | ✅ Documented |
| Unused Import Error | 🟢 Low | ✅ Resolved |
