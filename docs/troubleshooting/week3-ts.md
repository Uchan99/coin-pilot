# Week 3 Troubleshooting Report: AI Agent Integration

**Project**: CoinPilot - AI-Powered Cryptocurrency Trading System
**Author**: [Hur Youchan]
**Date**: 2026-01-26
**Tech Stack**: Python 3.10+, LangGraph, LangChain, PostgreSQL (asyncpg), Pydantic, pytest

---

## Executive Summary

Week 3 AI Agent 통합 과정에서 **비동기 DB 드라이버 제약**, **외부 API 의존성 테스트**, **타입 안전성 위반** 등 3가지 주요 기술적 문제를 해결했습니다. 각 문제에 대해 근본 원인을 분석하고, 확장 가능한 아키텍처 개선을 통해 해결책을 도출했습니다.

### Skills Demonstrated
`Async Programming` `Design Patterns (Factory)` `Unit Testing & Mocking` `Type Safety` `Database Migration` `Problem Solving`

---

## Issue #1: Asyncpg Multiple Statements Restriction

### Problem Statement
DB 마이그레이션 스크립트(`scripts/migrate_week3.py`) 실행 시 다음 에러 발생:

```
asyncpg.exceptions.PostgresSyntaxError: cannot insert multiple commands into a prepared statement
```

### Technical Context
- **Environment**: Python async/await 기반 PostgreSQL 연결
- **Driver**: asyncpg (비동기 PostgreSQL 드라이버)
- **Operation**: DDL 스크립트 실행 (CREATE TABLE, CREATE INDEX)

### Root Cause Analysis

```
[asyncpg Driver]
     │
     ▼
┌─────────────────────────────────────────┐
│  execute("CREATE TABLE; CREATE INDEX")  │  ← 단일 Prepared Statement
│           ↓                             │
│    PostgreSQL Protocol 제한             │
│    - 보안: SQL Injection 방지           │
│    - 성능: Statement 캐싱 최적화        │
│           ↓                             │
│    ❌ Multiple Commands 거부            │
└─────────────────────────────────────────┘
```

asyncpg는 **Prepared Statement**를 활용하여 성능을 최적화하고 SQL Injection을 방지합니다. 이 메커니즘은 하나의 `execute()` 호출에 **단일 SQL 문장만 허용**합니다.

### Solution

**Before (Error-prone)**
```python
sql = """
CREATE TABLE agent_decisions (...);
CREATE INDEX idx_agent_decisions_symbol ON agent_decisions (symbol);
CREATE INDEX idx_agent_decisions_created ON agent_decisions (created_at);
"""
await session.execute(text(sql))  # ❌ Error
```

**After (Fixed)**
```python
commands = [
    "CREATE TABLE agent_decisions (...)",
    "CREATE INDEX idx_agent_decisions_symbol ON agent_decisions (symbol)",
    "CREATE INDEX idx_agent_decisions_created ON agent_decisions (created_at)"
]
for cmd in commands:
    await session.execute(text(cmd))  # ✅ Sequential execution
```

### Key Takeaway
> **Library Constraints Awareness**: 사용하는 라이브러리의 내부 동작 방식과 제약 사항을 사전에 파악하는 것이 중요합니다. asyncpg의 경우 공식 문서에서 이 제약을 명시하고 있으며, 마이그레이션 도구(Alembic 등) 사용 시에도 동일한 패턴이 적용됩니다.

---

## Issue #2: External API Dependency in Unit Tests

### Problem Statement
`tests/test_agents.py` 실행 시 API Key 없이도 Pydantic Validation Error 발생:

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ChatAnthropic
anthropic_api_key
  Input should be a valid string
```

### Technical Context
- **Test Framework**: pytest + pytest-asyncio
- **Mocking Target**: LangChain의 ChatAnthropic (LLM Client)
- **Challenge**: 외부 API 의존성 격리

### Root Cause Analysis

```
[기존 구조 - 강한 결합]

market_analyst_node()
        │
        ▼
┌───────────────────────────────┐
│  llm = ChatAnthropic(         │  ← 모듈 로딩 시점에 인스턴스화
│    api_key=os.getenv(...)     │
│  )                            │
│         │                     │
│         ▼                     │
│  Pydantic Validation 실행     │  ← 테스트 환경에서도 실행됨
│         │                     │
│         ▼                     │
│  ❌ API Key 없으면 에러       │
└───────────────────────────────┘

문제점:
1. Hard-coded Dependency: 함수 내부에서 직접 객체 생성
2. Early Binding: Mock 적용 전에 이미 validation 실행
3. Tight Coupling: 테스트가 실제 LLM 클라이언트에 의존
```

### Solution: Factory Pattern

**Design Pattern 적용으로 의존성 역전(DI) 구현**

```
[개선된 구조 - Factory Pattern]

market_analyst_node()
        │
        ▼
┌─────────────────────┐     ┌─────────────────────┐
│  get_analyst_llm()  │ ←── │  factory.py         │
│  (Factory Function) │     │  - 객체 생성 전담   │
└─────────────────────┘     │  - 테스트 시 Mock   │
        │                   └─────────────────────┘
        ▼
┌─────────────────────┐
│  ChatAnthropic()    │  ← 실제 사용 시에만 인스턴스화
│  또는 Mock Object   │  ← 테스트 시 Mock 주입
└─────────────────────┘
```

**Implementation**

```python
# src/agents/factory.py (Factory Layer)
_analyst_llm = None

def get_analyst_llm():
    global _analyst_llm
    if _analyst_llm is None:
        _analyst_llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",
            temperature=0,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    return _analyst_llm
```

```python
# src/agents/analyst.py (Consumer)
from src.agents.factory import get_analyst_llm

async def market_analyst_node(state: AgentState):
    llm = get_analyst_llm()  # Factory를 통한 의존성 주입
    ...
```

```python
# tests/test_agents.py (Test with Mock)
with patch("src.agents.analyst.get_analyst_llm") as mock_factory:
    mock_llm = AsyncMock()
    mock_llm.with_structured_output.return_value = mock_llm
    mock_llm.ainvoke.return_value = AnalystDecision(...)
    mock_factory.return_value = mock_llm

    # 테스트 실행 - 실제 API 호출 없음
    result = await market_analyst_node(test_state)
```

### Benefits Achieved

| Aspect | Before | After |
|--------|--------|-------|
| **Testability** | API Key 필수, 네트워크 의존 | 완전 격리된 단위 테스트 |
| **Flexibility** | LLM 교체 시 코드 전체 수정 | Factory만 수정 |
| **Performance** | 매 요청 새 인스턴스 | 싱글톤 캐싱 |

### Key Takeaway
> **Testability Reflects Design Quality**: 테스트 작성이 어렵다면 코드 구조(강한 결합)에 문제가 있다는 신호입니다. Factory Pattern은 **의존성 역전 원칙(DIP)**을 적용하여 테스트 용이성과 확장성을 동시에 확보하는 검증된 해결책입니다.

---

## Issue #3: Pydantic Schema Violation in Agent Logic

### Problem Statement
코드 리뷰 중 `RiskGuardian` 에이전트가 스키마에 정의되지 않은 값을 반환하는 잠재적 버그 발견:

```python
# guardian.py (Bug)
return {"guardian_decision": {"decision": "SKIP", ...}}

# structs.py (Schema)
class GuardianDecision(BaseModel):
    decision: Literal["SAFE", "WARNING"]  # "SKIP"은 정의되지 않음!
```

### Technical Context
- **Type System**: Pydantic v2 with Literal types
- **Validation Mode**: Runtime validation (Structured Output)
- **Risk Level**: 런타임 에러로 매매 실패 가능성

### Root Cause Analysis

```
[버그 발생 시나리오]

Analyst → REJECT
    │
    ▼
Guardian 호출됨 (LangGraph Edge 조건 외의 방어 로직)
    │
    ▼
return {"decision": "SKIP"}  ← 스키마에 없는 값
    │
    ▼
Pydantic Validation (if structured output 사용 시)
    │
    ▼
❌ ValidationError → 매매 로직 중단

근본 원인:
- 예외 케이스를 급하게 처리하면서 Contract(Schema) 검토 누락
- "타입 안전성"을 위한 Pydantic이 오히려 런타임 폭탄으로 변질
```

### Solution: Schema-Compliant Exception Handling

**원칙**: 스키마 확장보다 기존 스키마 내에서 의미를 표현

```python
# Fixed Code - Schema 준수
if state["analyst_decision"]["decision"] == "REJECT":
    return {
        "guardian_decision": {
            "decision": "WARNING",      # ✅ 스키마에 정의된 값 사용
            "reasoning": "Skipped: Analyst already rejected."  # 사유 명시
        }
    }
```

### Design Decision Rationale

| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| A. 스키마에 "SKIP" 추가 | 의도 명확 | 불필요한 스키마 확장, 다른 코드 영향 | ❌ |
| B. "WARNING" + reasoning 활용 | 스키마 유지, 의미 전달 가능 | 약간의 의미 혼동 | ✅ 채택 |
| C. 예외 케이스에서 None 반환 | 단순 | 후속 로직에서 None 처리 필요 | ❌ |

### Key Takeaway
> **Schema as Contract**: 정의된 데이터 모델(Interface)은 시스템 간의 **계약**입니다. 예외 처리나 엣지 케이스 구현 시에도 반드시 스키마 범위 내에서 해결책을 찾아야 합니다. 이는 API 설계, 마이크로서비스 통신 등 모든 시스템 통합에 적용되는 원칙입니다.

---

## Summary: Lessons Learned

### Technical Insights

| Issue | Category | Pattern/Principle Applied |
|-------|----------|---------------------------|
| Asyncpg Multiple Statements | DB Driver Constraint | Library Documentation Study |
| LLM Mocking Difficulty | Testability | **Factory Pattern**, DIP |
| Schema Violation | Type Safety | **Design by Contract** |

### Architecture Improvements Made

```
[Before: Tightly Coupled]          [After: Loosely Coupled]

┌─────────────┐                   ┌─────────────┐
│   Agent     │                   │   Agent     │
│   Node      │──────────────────▶│   Node      │
│             │  직접 의존        │             │
└──────┬──────┘                   └──────┬──────┘
       │                                 │
       ▼                                 ▼
┌─────────────┐                   ┌─────────────┐
│ ChatAnthropic│                   │  Factory    │◀─── Mock 주입 지점
│  (Hard-coded)│                   │  (DI Point) │
└─────────────┘                   └──────┬──────┘
                                         │
                                         ▼
                                  ┌─────────────┐
                                  │ ChatAnthropic│
                                  │ or Mock     │
                                  └─────────────┘
```

### Personal Growth

이번 트러블슈팅 경험을 통해 다음 역량을 강화했습니다:

1. **문제 분석력**: 에러 메시지에서 근본 원인까지 추적하는 체계적 디버깅
2. **설계 사고**: 당장의 버그 수정이 아닌, 확장 가능한 아키텍처 개선
3. **문서화 습관**: 해결 과정을 기록하여 팀 내 지식 공유 및 재발 방지

---

## References

- [asyncpg Documentation - Prepared Statements](https://magicstack.github.io/asyncpg/current/)
- [LangChain Testing Guide](https://python.langchain.com/docs/guides/testing)
- [Pydantic v2 - Literal Types](https://docs.pydantic.dev/latest/concepts/types/#literal-types)
- [Factory Pattern - Refactoring Guru](https://refactoring.guru/design-patterns/factory-method)

---

## Issue #4: Model Availability & Strategy Adjustment (AI 404 Error)

### Problem Statement
AI Agent 연결 테스트(`debug_simulation.py`) 중 Anthropic API로부터 `404 Not Found` 및 `401 Authentication Error`가 간헐적으로 발생했습니다.

```json
{'type': 'error', 'error': {'type': 'not_found_error', 'message': 'model: claude-3-5-sonnet-20241022'}}
```

### Technical Context
- **Provider**: Anthropic API
- **Model Target**: `claude-3-5-sonnet-20241022` (Sonnet 3.5 New)
- **Constraint**: API Key의 Tier 또는 Beta 접근 권한에 따라 특정 모델 ID 사용이 제한될 수 있음.

### Root Cause Analysis
API Key의 권한 레벨이나 지역적 제한, 또는 회사/조직 계정 정책에 따라 최신 모델(`20241022` 버전)에 대한 접근이 차단된 상태였습니다. 반면, `claude-sonnet-4-5-20250929`(최신 4.5 모델)와 `claude-3-haiku`는 정상 응답함을 확인했습니다.

### Solution: Dual-Model Strategy for Dev/Prod

단순히 모델 ID만 바꾸는 것이 아니라, 개발 단계와 운영 단계의 모델을 분리하는 전략을 수립했습니다.

**1. Strategy Definition**
| 환경 | 모델 | 선정 이유 |
|------|------|-----------|
| **Development** | `claude-3-haiku-20240307` | 비용 효율성, 빠른 응답 속도 (디버깅 용이) |
| **Production** | `claude-sonnet-4-5-20250929` | 시장 분석의 정확도와 추론 능력 극대화 |

**2. Implementation**
`src/agents/factory.py` 코드를 수정하여 상황에 따라 모델을 유연하게 교체할 수 있도록 주석 처리 및 가이드를 추가했습니다.

```python
return ChatAnthropic(
    model="claude-sonnet-4-5-20250929", # Production (High Reasoning)
    # model="claude-3-haiku-20240307",    # Development (Low Cost)
    temperature=0,
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
)
```

### Key Takeaway
> **Dependency Flexibility**: 외부 API(LLM 포함)에 의존하는 시스템은 언제든 **공급자의 사정(모델 단종, 정책 변경, 서버 오류)**에 의해 중단될 수 있습니다. 특정 모델에 강결합되지 않도록 설정을 추상화하고, Fallback 대안(예: Haiku)을 마련해두는 것이 중요합니다.
