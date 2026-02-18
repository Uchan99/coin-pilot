# CoinPilot AI 고도화 계획서
> **문서 버전**: v1.0
> **작성일**: 2026-02-09
> **목표**: AI 신뢰성 강화 및 학습 기반 전략 개선

---

## 1. 개요

### 1.1 배경
2026년 AI 엔지니어링 트렌드는 "에이전틱 AI의 신뢰성(Reliability)"에 집중하고 있다.
CoinPilot은 이미 Rule Engine + AI Assistant 하이브리드 구조를 갖추고 있으나,
다음 영역에서 고도화가 필요하다:

1. **AI 판단의 평가 체계 (EvalOps)**: AI가 왜 그런 결정을 내렸는지 검증
2. **경험 기반 학습 (Episodic Memory)**: 과거 성공/실패 패턴을 기억하고 활용
3. **자아 성찰 (Self-Reflection)**: 매수 전 2차 검증 강화

### 1.2 기대 효과

| 기능 | 수익 기여 | 포트폴리오 가치 |
|------|-----------|-----------------|
| EvalOps | 간접 (오판 감소) | ⭐⭐⭐ 높음 |
| Episodic Memory | 직접 (패턴 학습) | ⭐⭐⭐ 높음 |
| Self-Reflection | 간접 (리스크 감소) | ⭐⭐ 중간 |

---

## 2. Phase 1: EvalOps (AI 판단 평가 체계)

### 2.1 목표
AI Agent의 모든 결정을 기록하고, 사후에 "올바른 판단이었는지" 평가하는 체계 구축

### 2.2 현재 상태
- `agent_decisions` 테이블에 결정 기록 중
- Reject 사유 Discord 알림 구현됨
- **미비점**: 사후 평가 없음 (결과 대비 판단 검증 불가)

### 2.3 구현 방안

#### 2.3.1 Decision Outcome Tracker
```python
# src/evaluation/outcome_tracker.py
from datetime import datetime, timedelta
from decimal import Decimal

class DecisionOutcomeTracker:
    """
    AI 결정의 실제 결과를 추적하고 평가
    """
    
    async def evaluate_decision(
        self, 
        decision_id: int,
        evaluation_window_hours: int = 48
    ) -> dict:
        """
        과거 AI 결정이 올바랐는지 평가
        
        평가 기준:
        1. BUY 결정 → 48시간 내 가격 변동
        2. REJECT 결정 → 48시간 내 가격 변동 (기회비용)
        """
        decision = await self.get_decision(decision_id)
        
        # 결정 시점 가격
        entry_price = decision.price_at_decision
        
        # 48시간 후 가격
        future_price = await self.get_price_after(
            decision.symbol,
            decision.created_at,
            hours=evaluation_window_hours
        )
        
        price_change = (future_price - entry_price) / entry_price
        
        # 평가
        if decision.action == "BUY":
            if price_change > 0.05:  # +5% 이상
                outcome = "EXCELLENT"
            elif price_change > 0:
                outcome = "GOOD"
            elif price_change > -0.03:
                outcome = "ACCEPTABLE"
            else:
                outcome = "BAD"
        
        elif decision.action == "REJECT":
            if price_change > 0.05:  # 놓친 기회
                outcome = "MISSED_OPPORTUNITY"
            elif price_change < -0.03:  # 올바른 회피
                outcome = "CORRECT_AVOIDANCE"
            else:
                outcome = "NEUTRAL"
        
        return {
            "decision_id": decision_id,
            "action": decision.action,
            "price_change": float(price_change),
            "outcome": outcome,
            "reasoning_quality": await self.evaluate_reasoning(decision)
        }
    
    async def evaluate_reasoning(self, decision) -> dict:
        """
        LLM-as-a-Judge: AI의 추론 과정 평가
        """
        judge_prompt = f"""
        다음은 AI 트레이딩 에이전트의 결정 기록입니다.
        
        ## 시장 상황
        - 심볼: {decision.symbol}
        - RSI: {decision.indicators.get('rsi')}
        - 거래량 비율: {decision.indicators.get('vol_ratio')}
        - 현재가 vs MA20: {decision.indicators.get('ma_position')}
        
        ## AI 결정
        - 행동: {decision.action}
        - 신뢰도: {decision.confidence}
        - 추론: {decision.reasoning}
        
        ## 평가 기준
        1. 리스크 규칙 준수 여부 (손절 -3%, 익절 +5% 규칙)
        2. 제시한 근거와 데이터의 일치 여부
        3. 시장 국면 고려 여부
        
        JSON 형식으로 평가해주세요:
        {{
            "rule_compliance": true/false,
            "data_consistency": true/false,
            "regime_awareness": true/false,
            "overall_score": 1-10,
            "feedback": "개선점"
        }}
        """
        
        # Claude API 호출 (Judge Model)
        response = await self.llm.ainvoke(judge_prompt)
        return parse_json(response.content)
```

#### 2.3.2 평가 결과 저장 스키마
```python
# src/common/models.py 에 추가

class DecisionEvaluation(Base):
    """AI 결정 평가 결과"""
    __tablename__ = "decision_evaluations"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    decision_id: Mapped[int] = mapped_column(ForeignKey("agent_decisions.id"))
    
    # 결과 평가
    price_change_percent: Mapped[Decimal]
    outcome: Mapped[str]  # EXCELLENT, GOOD, BAD, MISSED_OPPORTUNITY 등
    
    # LLM Judge 평가
    rule_compliance: Mapped[bool]
    data_consistency: Mapped[bool]
    regime_awareness: Mapped[bool]
    overall_score: Mapped[int]  # 1-10
    feedback: Mapped[str]
    
    evaluated_at: Mapped[datetime]
```

#### 2.3.3 일간 평가 리포트
```python
# src/evaluation/daily_report.py

async def generate_daily_eval_report() -> str:
    """
    일간 AI 판단 평가 리포트 생성
    n8n → Discord 전송용
    """
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    # 어제 결정들의 평가 결과 집계
    evaluations = await get_evaluations_for_date(yesterday)
    
    total = len(evaluations)
    excellent = sum(1 for e in evaluations if e.outcome == "EXCELLENT")
    good = sum(1 for e in evaluations if e.outcome == "GOOD")
    bad = sum(1 for e in evaluations if e.outcome == "BAD")
    missed = sum(1 for e in evaluations if e.outcome == "MISSED_OPPORTUNITY")
    
    avg_score = sum(e.overall_score for e in evaluations) / total if total > 0 else 0
    
    report = f"""
    📊 **AI 판단 평가 리포트** ({yesterday})
    
    **결정 수**: {total}건
    **결과 분포**:
    - 🏆 Excellent: {excellent}건
    - ✅ Good: {good}건
    - ❌ Bad: {bad}건
    - 😢 Missed Opportunity: {missed}건
    
    **평균 추론 점수**: {avg_score:.1f}/10
    
    **개선 필요 영역**:
    {summarize_feedback(evaluations)}
    """
    
    return report
```

### 2.4 구현 일정

| Day | 작업 | 산출물 |
|-----|------|--------|
| Day 1 | DB 스키마 추가, Outcome Tracker 기본 구현 | `decision_evaluations` 테이블 |
| Day 2 | LLM-as-Judge 프롬프트 설계 및 구현 | `evaluate_reasoning()` |
| Day 3 | 일간 리포트 + n8n 연동 | Discord 리포트 |
| Day 4 | 테스트 및 과거 데이터 평가 | 평가 데이터 축적 |

---

## 3. Phase 2: Episodic Memory (경험 기반 학습)

### 3.1 목표
과거 성공/실패 거래 패턴을 pgvector에 저장하고, 새로운 거래 기회 발생 시 유사 패턴을 검색하여 의사결정에 반영

### 3.2 현재 상태
- pgvector 확장 설치됨
- `langchain_pg_embedding` 테이블 존재 (RAG용)
- **미비점**: 거래 패턴 임베딩 없음

### 3.3 구현 방안

#### 3.3.1 Trade Pattern Embedding
```python
# src/memory/episodic_memory.py
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import PGVector

class EpisodicMemory:
    """
    거래 경험을 벡터로 저장하고 검색
    """
    
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
        self.vector_store = PGVector(
            collection_name="trade_episodes",
            connection_string=DATABASE_URL,
            embedding_function=self.embeddings
        )
    
    async def store_trade_episode(self, trade: Trade, outcome: str):
        """
        완료된 거래를 에피소드로 저장
        """
        # 거래 패턴을 텍스트로 변환
        episode_text = f"""
        ## 거래 에피소드
        
        ### 시장 상황
        - 심볼: {trade.symbol}
        - 진입 RSI: {trade.entry_rsi}
        - 진입 시 MA20 대비: {trade.entry_ma_position}%
        - 거래량 비율: {trade.entry_vol_ratio}
        - 시장 국면: {trade.market_regime}
        
        ### 거래 결과
        - 보유 시간: {trade.hold_hours}시간
        - 수익률: {trade.pnl_percent}%
        - 청산 사유: {trade.exit_reason}
        - 결과 평가: {outcome}
        
        ### 학습 포인트
        - AI 신뢰도: {trade.ai_confidence}
        - 실제 결과와 일치: {trade.prediction_correct}
        """
        
        metadata = {
            "symbol": trade.symbol,
            "outcome": outcome,
            "pnl_percent": float(trade.pnl_percent),
            "entry_rsi": float(trade.entry_rsi),
            "market_regime": trade.market_regime,
            "trade_id": trade.id
        }
        
        await self.vector_store.aadd_texts(
            texts=[episode_text],
            metadatas=[metadata]
        )
    
    async def find_similar_episodes(
        self, 
        current_indicators: dict,
        symbol: str,
        top_k: int = 5
    ) -> list:
        """
        현재 상황과 유사한 과거 에피소드 검색
        """
        query = f"""
        심볼: {symbol}
        RSI: {current_indicators['rsi']}
        MA20 대비: {current_indicators['ma_position']}%
        거래량 비율: {current_indicators['vol_ratio']}
        """
        
        results = await self.vector_store.asimilarity_search_with_score(
            query=query,
            k=top_k,
            filter={"symbol": symbol}  # 같은 코인만
        )
        
        return results
    
    async def get_pattern_insight(self, similar_episodes: list) -> dict:
        """
        유사 에피소드들로부터 인사이트 도출
        """
        if not similar_episodes:
            return {"recommendation": "NEUTRAL", "confidence": 0.5}
        
        # 결과 집계
        outcomes = [ep.metadata["outcome"] for ep, _ in similar_episodes]
        pnls = [ep.metadata["pnl_percent"] for ep, _ in similar_episodes]
        
        success_rate = sum(1 for o in outcomes if o in ["EXCELLENT", "GOOD"]) / len(outcomes)
        avg_pnl = sum(pnls) / len(pnls)
        
        if success_rate >= 0.7 and avg_pnl > 0:
            recommendation = "BULLISH"
            confidence = success_rate
        elif success_rate <= 0.3 or avg_pnl < -2:
            recommendation = "BEARISH"
            confidence = 1 - success_rate
        else:
            recommendation = "NEUTRAL"
            confidence = 0.5
        
        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "success_rate": success_rate,
            "avg_pnl": avg_pnl,
            "sample_size": len(similar_episodes)
        }
```

#### 3.3.2 Agent 통합
```python
# src/agents/analyst.py 수정

async def market_analyst_node(state: AgentState) -> dict:
    """
    Market Analyst Node - Episodic Memory 통합
    """
    symbol = state["symbol"]
    indicators = state["indicators"]
    
    # 1. 기존 기술적 분석
    technical_analysis = analyze_indicators(indicators)
    
    # 2. [신규] Episodic Memory 조회
    memory = EpisodicMemory()
    similar_episodes = await memory.find_similar_episodes(indicators, symbol)
    pattern_insight = await memory.get_pattern_insight(similar_episodes)
    
    # 3. LLM에게 종합 판단 요청
    prompt = f"""
    ## 기술적 분석
    {technical_analysis}
    
    ## 과거 유사 패턴 분석 (Episodic Memory)
    - 유사 거래 수: {pattern_insight['sample_size']}건
    - 과거 성공률: {pattern_insight['success_rate']:.1%}
    - 평균 수익률: {pattern_insight['avg_pnl']:.2f}%
    - 패턴 기반 권장: {pattern_insight['recommendation']}
    
    위 정보를 종합하여 매수/관망 결정을 내려주세요.
    특히 과거 유사 패턴에서 실패한 경우가 많다면 신중하게 판단하세요.
    """
    
    # ... LLM 호출 및 결정
```

### 3.4 구현 일정

| Day | 작업 | 산출물 |
|-----|------|--------|
| Day 1 | EpisodicMemory 클래스 구현 | `episodic_memory.py` |
| Day 2 | 거래 완료 시 자동 저장 로직 | Trade → Episode 파이프라인 |
| Day 3 | Analyst Agent 통합 | 프롬프트 수정 |
| Day 4 | 테스트 및 초기 데이터 시딩 | 시뮬레이션 거래 데이터 |

---

## 4. Phase 3: Self-Reflection 강화

### 4.1 목표
현재 Guardian Agent를 강화하여 "비평가(Critic)" 역할 추가

### 4.2 현재 상태
- Guardian Agent: 리스크 검토 (SAFE/WARNING)
- **미비점**: 전략 일관성 검증 없음

### 4.3 구현 방안

#### 4.3.1 Critic Agent 추가
```python
# src/agents/critic.py

from langchain_core.prompts import ChatPromptTemplate

CRITIC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """
    당신은 트레이딩 결정을 검토하는 비평가입니다.
    Analyst가 내린 결정이 다음 규칙과 일관성이 있는지 검증하세요:
    
    ## 핵심 규칙
    1. 손절 -3%, 익절 +5% 엄수
    2. 동시 포지션 3개 이하
    3. 전체 노출 20% 이하
    4. RSI 40 이상에서는 매수 금지
    
    ## 시장 국면별 규칙
    - BEAR: 매수 포지션 50% 축소, 손절 타이트하게
    - SIDEWAYS: 정상 운영
    - BULL: 익절폭 확대 가능
    
    결정이 규칙과 상충되면 VETO, 일관성 있으면 APPROVE.
    """),
    ("human", """
    ## Analyst 결정
    - 행동: {action}
    - 심볼: {symbol}
    - 신뢰도: {confidence}
    - 추론: {reasoning}
    
    ## 현재 상태
    - 시장 국면: {market_regime}
    - 현재 포지션 수: {open_positions}
    - 현재 노출: {current_exposure}%
    - RSI: {rsi}
    
    이 결정을 승인하시겠습니까?
    """)
])

async def critic_node(state: AgentState) -> dict:
    """
    Critic Node: Analyst 결정의 규칙 준수 여부 검증
    """
    llm = get_llm().with_structured_output(CriticDecision)
    
    chain = CRITIC_PROMPT | llm
    
    result = await chain.ainvoke({
        "action": state["analyst_decision"]["action"],
        "symbol": state["symbol"],
        "confidence": state["analyst_decision"]["confidence"],
        "reasoning": state["analyst_decision"]["reasoning"],
        "market_regime": state["market_context"]["regime"],
        "open_positions": state["portfolio"]["open_count"],
        "current_exposure": state["portfolio"]["exposure_percent"],
        "rsi": state["indicators"]["rsi"]
    })
    
    return {"critic_decision": result.dict()}
```

#### 4.3.2 LangGraph 워크플로우 수정
```python
# src/agents/runner.py 수정

def create_agent_graph():
    workflow = StateGraph(AgentState)
    
    # 노드 추가
    workflow.add_node("analyst", market_analyst_node)
    workflow.add_node("critic", critic_node)      # [신규]
    workflow.add_node("guardian", risk_guardian_node)
    
    # 진입점
    workflow.set_entry_point("analyst")
    
    # Analyst → Critic (CONFIRM인 경우만)
    workflow.add_conditional_edges(
        "analyst",
        lambda s: "critic" if s["analyst_decision"]["decision"] == "CONFIRM" else "end",
        {"critic": "critic", "end": END}
    )
    
    # Critic → Guardian (APPROVE인 경우만)
    workflow.add_conditional_edges(
        "critic",
        lambda s: "guardian" if s["critic_decision"]["verdict"] == "APPROVE" else "end",
        {"guardian": "guardian", "end": END}
    )
    
    workflow.add_edge("guardian", END)
    
    return workflow.compile()
```

### 4.4 구현 일정

| Day | 작업 | 산출물 |
|-----|------|--------|
| Day 1 | Critic Agent 구현 | `critic.py` |
| Day 2 | LangGraph 워크플로우 수정 | 3단계 검증 플로우 |

---

## 5. MCP 도입 (Future Work)

### 5.1 현재 판단
**도입 보류** - 다음 이유로 현재 단계에서는 시기상조

| 이유 | 설명 |
|------|------|
| 사용자 제한 | 본인만 사용하는 시스템, MCP의 "연결성" 가치 낮음 |
| 구현 비용 | 1주+ 소요, 인프라 재설계 필요 |
| 우선순위 | 거래 발생 → 데이터 축적이 먼저 |

### 5.2 도입 시점
다음 조건 충족 시 재검토:

1. ✅ 월 50건 이상 거래 발생
2. ✅ EvalOps 체계 운영 중
3. ✅ 외부 LLM 클라이언트 연동 필요성 발생

### 5.3 도입 시 아키텍처 (참고용)
```
[Claude Desktop / IDE] 
        │
        ▼ (MCP Protocol)
┌───────────────────────────────────┐
│       MCP Host (FastMCP)          │
├───────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐        │
│  │ Market  │  │ Quant   │        │
│  │ Data    │  │Analytics│        │
│  │ Server  │  │ Server  │        │
│  └────┬────┘  └────┬────┘        │
│       │            │              │
│  ┌────┴────────────┴────┐        │
│  │   Execution Server   │        │
│  │   (Risk Guardrails)  │        │
│  └──────────────────────┘        │
└───────────────────────────────────┘
```

---

## 6. 전체 로드맵

| Phase | 기능 | 기간 | 선행 조건 |
|-------|------|------|-----------|
| **Phase 1** | EvalOps | 4일 | 거래 데이터 필요 |
| **Phase 2** | Episodic Memory | 4일 | Phase 1 완료 |
| **Phase 3** | Self-Reflection | 2일 | Phase 2와 병행 가능 |
| (Future) | MCP | 1주+ | 위 조건 충족 시 |

**총 예상: 10일 (2주)**

---

## 7. 성공 지표

| 지표 | 현재 | 목표 |
|------|------|------|
| AI 판단 정확도 | 측정 불가 | 60% 이상 |
| 평균 추론 점수 | 측정 불가 | 7/10 이상 |
| 유사 패턴 기반 성공률 | 측정 불가 | 55% 이상 |
| Critic VETO 비율 | 측정 불가 | 10~20% |

---

## 8. 파일 구조 (예상)
```
src/
├── evaluation/
│   ├── __init__.py
│   ├── outcome_tracker.py      # Phase 1
│   ├── llm_judge.py            # Phase 1
│   └── daily_report.py         # Phase 1
├── memory/
│   ├── __init__.py
│   └── episodic_memory.py      # Phase 2
├── agents/
│   ├── analyst.py              # Phase 2 수정
│   ├── critic.py               # Phase 3 신규
│   ├── guardian.py
│   └── runner.py               # Phase 3 수정
```

---

## Claude Code Review

**검토일**: 2026-02-12
**검토자**: Claude Code (Opus 4.6)
**대상 코드 기준**: `src/agents/`, `src/common/models.py`, `src/engine/strategy.py`, `config/strategy_v3.yaml`

---

### 1. 전반적 평가

AI 고도화 방향(EvalOps → Episodic Memory → Self-Reflection)은 프로젝트 Charter의 "Agent Memory"(4.2)와 "Self-Reflection"(4.2) 미구현 항목을 체계적으로 채우는 좋은 계획입니다. 다만 초안 수준답게 **현재 코드 구현 상태와 맞지 않는 부분**, **선행 조건 미충족**, **과도한 설계** 등이 다수 발견됩니다.

**Overall: 수정 후 진행 (CONDITIONAL)** - 아래 피드백 반영 후 재계획 권장

---

### 2. 선행 조건: 거래 데이터 부족 문제 (CRITICAL)

계획서 자체에서도 "Phase 1 선행 조건: 거래 데이터 필요"라고 명시했는데, 이것이 현재 가장 큰 블로커입니다.

- **12번 계획**(전략 파라미터 튜닝)이 해결되지 않으면 거래 자체가 발생하지 않음
- 거래가 없으면 EvalOps의 `DecisionOutcomeTracker`가 평가할 데이터가 없음
- Episodic Memory에 저장할 에피소드도 없음

**결론**: **12번 계획 실행 → 거래 발생 확인 → 최소 1~2주 데이터 축적 → 13번 계획 실행** 순서가 필수입니다. 현재 상태에서 13번을 구현해도 빈 테이블에 빈 리포트만 생성됩니다.

---

### 3. Phase 1: EvalOps 검토

#### 3.1 DecisionOutcomeTracker ⚠️ 코드-현실 불일치

**계획서 코드의 문제점:**

1. **`decision.indicators` 접근 불가**: 현재 `AgentDecision` 모델(`src/common/models.py:140`)에는 `indicators` 컬럼이 없습니다. `reasoning`(Text), `confidence`(Integer), `price_at_decision`, `regime`만 있습니다. 계획서 코드의 `decision.indicators.get('rsi')` 등은 동작하지 않습니다.

2. **`price_at_decision` 활용**: 이 필드는 이미 v3.1에서 추가되어 있으므로(work-result/11 참조) 기본적인 가격 변동 추적은 가능합니다. 다만 48시간 후 가격을 가져오는 `get_price_after()` 메서드는 `market_data` 테이블에서 조회해야 하는데, 1분봉 데이터의 보존 기간을 확인해야 합니다.

3. **BUY/REJECT 판정 기준**: 계획서에서 BUY +5% → EXCELLENT, -3% → BAD로 분류하는데, 이것은 Charter의 TP/SL 기준과 정확히 일치합니다. 다만 레짐별로 TP/SL이 다르므로(BEAR: TP 3%, SL 5%), **레짐을 고려한 동적 평가 기준**이 필요합니다.

#### 3.2 LLM-as-Judge ⚠️ 비용 대비 효과 우려

- 매 결정마다 LLM Judge를 호출하면 **비용이 2배** 증가 (Analyst 1회 + Judge 1회)
- 현재 Analyst에 Claude Haiku/Sonnet을 사용 중인데, Judge에도 LLM을 쓰면 비용 부담
- **대안**: 규칙 기반 평가를 먼저 구현하고 (가격 변동 기반 outcome 자동 판정), LLM Judge는 주간 리포트 수준으로 빈도 축소 권장

#### 3.3 DecisionEvaluation 스키마 ✅ 기본 구조 적절

- DB 모델 자체는 합리적이나, 현재 프로젝트에서 `Mapped[...]` 형식(SQLAlchemy 2.0 Mapped Column)을 사용하고 있지 않습니다. 기존 코드(`models.py`)는 `Column(...)` 클래식 방식을 사용 중이므로 **스타일 통일 필요**합니다.

#### 3.4 일간 평가 리포트 ⚠️ 기존 DailyReporter와 중복

- `src/agents/daily_reporter.py`에 이미 일간 리포트 시스템이 존재합니다
- 계획서의 `src/evaluation/daily_report.py`와 역할이 중복됩니다
- **권장**: 별도 파일을 만들기보다 기존 `DailyReporter`에 EvalOps 섹션을 추가하는 것이 효율적

---

### 4. Phase 2: Episodic Memory 검토

#### 4.1 기존 인프라와의 관계 ✅ 잘 파악됨

- Charter에서 "Agent Memory: pgvector 인프라는 준비됨"(8.3절)이라고 명시
- `AgentMemory` 모델(`models.py:72`)에 이미 `embedding = Column(Vector(1536))` 필드 존재
- `langchain_pg_embedding` 테이블도 존재 (RAG Agent용)

#### 4.2 EpisodicMemory 클래스 ⚠️ 설계 과잉

1. **OpenAI Embeddings 의존**: 계획서가 `OpenAIEmbeddings(model="text-embedding-3-small")`을 사용하는데, 프로젝트의 LLM 스택은 **Claude 중심** (Charter 5절: Claude 3.5 Haiku Dev / Claude 4.5 Sonnet Prod)입니다. OpenAI Embeddings를 별도로 쓰면 API 키가 2개(Anthropic + OpenAI) 필요하고 비용도 증가합니다.

   **대안**:
   - Anthropic의 Voyage AI embeddings 사용 (Anthropic 에코시스템)
   - 또는 로컬 임베딩 모델 사용 (sentence-transformers 등, K8s에서 사이드카로)
   - 하지만 현재 `daily_reporter.py`에서 이미 `ChatOpenAI(model="gpt-4o-mini")`를 사용 중이므로 OpenAI 키는 이미 프로젝트에 존재합니다. 일관성 측면에서 OpenAI Embeddings 사용도 수용 가능.

2. **PGVector → LangChain PGVector**: `langchain_community.vectorstores.PGVector`는 deprecated 경고가 나올 수 있습니다. 최신 LangChain에서는 `langchain_postgres.PGVector`를 권장합니다.

3. **텍스트 기반 임베딩의 한계**: 거래 패턴(RSI, 거래량, 레짐 등)은 **수치 데이터**인데, 이를 텍스트로 변환 후 임베딩하는 것은 비효율적입니다. 유사 패턴 검색이라면 수치 기반 유사도(유클리디안 거리 등)가 더 정확합니다.

   **대안**: 수치 지표를 직접 벡터화하여 `pgvector`에 저장
   ```
   vector = [rsi_14, rsi_7, vol_ratio, ma_position, regime_encoded]
   ```
   이 방식이 LLM 임베딩보다 빠르고, API 호출 비용도 없으며, 유사 패턴 검색이 더 정확합니다.

#### 4.3 Agent 통합 ⚠️ 현재 코드 구조와 불일치

계획서에서 `src/agents/analyst.py` 수정을 언급하는데:
- 현재 `analyst.py`는 `market_analyst_node(state: AgentState)` 형태의 LangGraph 노드
- 계획서 코드도 같은 형태이지만, `EpisodicMemory()` 인스턴스를 **매 호출마다 새로 생성**하고 있음 → DB 커넥션 풀 관점에서 비효율
- 싱글톤 또는 의존성 주입 패턴 사용 권장

#### 4.4 데이터 축적 기간 필요 (CRITICAL)

Episodic Memory가 의미있으려면 **최소 50건 이상의 완결된 거래(진입→청산) 데이터**가 필요합니다. 현재 거래가 발생하지 않는 상태이므로, 12번 계획 → 데이터 축적 → 13번 Phase 2 순서가 필수입니다.

---

### 5. Phase 3: Self-Reflection 검토

#### 5.1 Critic Agent ⚠️ 과도한 LLM 호출 (3단계)

현재 워크플로우: `Analyst → Guardian → 결과`
계획 워크플로우: `Analyst → Critic → Guardian → 결과`

- **LLM 호출이 2회 → 3회로 증가** (비용 50% 증가)
- 현재 Agent Runner에 20초 타임아웃(`runner.py:76`)이 설정되어 있는데, 3단계 LLM 호출이 20초 내에 완료될지 불확실
- Charter의 "AI가 실패해도 시스템은 동작한다" 원칙상, LLM 호출 횟수가 늘면 실패 확률도 높아짐

**대안**: Critic을 별도 LLM 호출이 아닌 **규칙 기반 검증기**로 구현
- RSI 40 이상 매수 금지 → 코드로 검증 가능 (이미 `strategy.py`에서 하고 있음)
- 동시 포지션 3개 이하 → 코드로 검증 가능 (이미 `risk_manager.py`에서 하고 있음)
- 전체 노출 20% 이하 → 코드로 검증 가능

계획서의 Critic 프롬프트에 나열된 규칙들 대부분이 **이미 Rule Engine과 Risk Manager에서 하드코딩 검증** 중입니다. LLM을 추가 호출하여 같은 규칙을 다시 검증하는 것은 중복이며 비효율적입니다.

#### 5.2 실질적으로 Critic이 추가할 수 있는 가치

LLM Critic이 의미있는 경우:
- "이 진입은 직전 3연패 직후인데, 심리적 뇌동매매 아닌가?" → 현재 `cooldown` 규칙으로 부분 커버됨
- "지표는 OK이지만 뉴스/외부 이벤트 리스크가 있는가?" → RAG Agent 영역

**결론**: Critic Agent는 Phase 3가 아닌 **Future Consideration**으로 격하하고, Phase 2(Episodic Memory) 데이터가 충분히 쌓인 후 재검토를 권장합니다.

#### 5.3 LangGraph 워크플로우 수정 ⚠️ 코드 불일치

계획서의 `create_agent_graph()` 코드가 현재 `runner.py`의 구조와 다릅니다:
- 현재: `should_continue` 함수로 `"end"`/`"continue"` 라우팅
- 계획: 람다 함수로 `"critic"`/`"end"` 라우팅
- `AgentState`에 `critic_decision` 필드 추가 필요 (`state.py` 수정)

---

### 6. MCP 도입 보류 ✅ 동의

계획서의 MCP 보류 판단은 현재 상황에서 정확합니다. 프로젝트 Charter에서도 "Week 8 이후 필요 시 검토"로 명시되어 있습니다.

---

### 7. 기존 구현과의 중복 정리

| 계획서 항목 | 기존 구현 상태 | 중복 여부 |
|-------------|---------------|-----------|
| `agent_decisions` 테이블에 결정 기록 | ✅ 이미 구현 (`models.py:140`) | 중복 |
| Reject 사유 Discord 알림 | ✅ 이미 구현 (`runner.py:150`) | 중복 |
| `price_at_decision` 저장 | ✅ 이미 구현 (v3.1) | 중복 |
| `regime` 저장 | ✅ 이미 구현 (v3.1) | 중복 |
| `AgentMemory` 테이블 (pgvector) | ✅ 스키마 존재 (`models.py:72`) | 부분 중복 (활용 안됨) |
| Guardian Agent 리스크 검토 | ✅ 이미 구현 (`guardian.py`) | Critic과 역할 중복 |
| 일간 리포트 n8n → Discord | ✅ 이미 구현 (`daily_reporter.py`) | 평가 리포트와 중복 |

---

### 8. 수정 권장 사항 요약

#### 8.1 우선순위 재조정

| 순서 | 항목 | 기간 | 비고 |
|------|------|------|------|
| **0** | 12번 계획 실행 (파라미터 튜닝) | 1일 | **선행 필수** |
| **1** | 거래 데이터 축적 대기 | 1~2주 | 모니터링 |
| **2** | EvalOps (규칙 기반 Outcome 평가만) | 2일 | LLM Judge는 보류 |
| **3** | Episodic Memory (수치 벡터 방식) | 3일 | 텍스트 임베딩 대신 수치 벡터 |
| **4** | LLM Judge (주간 리포트용) | 1일 | 일간 → 주간으로 축소 |
| **5** | Critic Agent | Future | 데이터 충분 시 재검토 |

#### 8.2 코드 스타일 통일 (필수)

- 계획서 코드: `Mapped[int]` (SQLAlchemy 2.0)
- 기존 코드: `Column(BigInteger)` (SQLAlchemy 1.x 스타일)
- → 기존 스타일에 맞춰 `Column(...)` 방식으로 작성

#### 8.3 LLM 비용 관리 (필수)

현재 프로젝트에서 LLM 호출 지점:
1. Analyst Agent (Claude Haiku/Sonnet)
2. Guardian Agent (Claude Haiku/Sonnet)
3. Daily Reporter (GPT-4o-mini)

계획서 추가:
4. LLM Judge (추가 비용)
5. Episodic Memory 임베딩 (OpenAI Embeddings)
6. Critic Agent (추가 비용)

**3개 → 6개**로 LLM 호출 지점이 2배 증가합니다. **비용 시뮬레이션**을 먼저 수행하고, 예산 한도 내에서 구현 범위를 결정해야 합니다.

#### 8.4 파일 구조 수정 (권장)

계획서의 `src/evaluation/` 디렉토리 신설은 합리적이나, `src/memory/`는 기존 `src/agents/` 내에 통합하는 것이 나을 수 있습니다. 이미 `AgentMemory` 모델이 `src/common/models.py`에 있고, 메모리 활용 주체가 Agent이므로:

```
src/
├── evaluation/
│   ├── __init__.py
│   └── outcome_tracker.py    # Phase 2 (EvalOps)
├── agents/
│   ├── episodic_memory.py    # Phase 3 (기존 agents/ 내 배치)
│   ├── analyst.py            # Phase 3 수정
│   └── ...
```

---

### 9. 최종 의견

이 계획은 프로젝트의 AI 고도화 로드맵으로서 방향성은 올바르지만, **현재 거래가 발생하지 않는 상태에서 실행하면 빈 시스템만 만들어질 위험**이 큽니다. 12번 파라미터 튜닝 → 거래 데이터 축적을 먼저 완료한 후, 축적된 데이터의 양과 패턴을 보고 구현 범위를 재조정하는 것을 강력히 권장합니다.

특히 **LLM 비용 증가 문제**와 **기존 구현과의 중복**을 해소하지 않으면 복잡도만 올라가고 실질적 효과는 제한적일 수 있습니다. "규칙 기반 먼저, LLM 보조 나중에"라는 Charter의 핵심 철학을 AI 평가 시스템에도 동일하게 적용하는 것이 바람직합니다.