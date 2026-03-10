import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

from langgraph.graph import StateGraph, END
from src.agents.state import AgentState
from src.agents.analyst import market_analyst_node
from src.agents.guardian import risk_guardian_node
from src.common.db import get_db_session
from src.common.models import AgentDecision
from src.agents.factory import select_ai_decision_route
from src.common.notification import notifier
from src.common.llm_usage import build_usage_request_id, log_llm_usage_event
from src.common.rule_funnel import record_rule_funnel_event

def create_agent_graph():
    """AI 에이전트 워크플로우 그래프 생성"""
    workflow = StateGraph(AgentState)
    
    # 노드 추가
    workflow.add_node("analyst", market_analyst_node)
    workflow.add_node("guardian", risk_guardian_node)
    
    # 엣지 연결
    workflow.set_entry_point("analyst")
    
    # 조건부 라우팅: Analyst가 REJECT하면 종료, 아니면 Guardian으로
    def should_continue(state: AgentState):
        if state["analyst_decision"]["decision"] == "REJECT":
            return "end"
        return "continue"
    
    workflow.add_conditional_edges(
        "analyst",
        should_continue,
        {
            "end": END,
            "continue": "guardian"
        }
    )
    
    workflow.add_edge("guardian", END)
    
    return workflow.compile()

class AgentRunner:
    """AI 에이전트 실행 및 결과 관리 클래스"""
    
    def __init__(self):
        self.graph = create_agent_graph()

    async def run(self, 
                  symbol: str, 
                  strategy_name: str, 
                  market_context: Dict[str, Any],
                  indicators: Dict[str, Any]) -> Tuple[bool, str]:
        """
        AI 에이전트 워크플로우를 실행하고 최종 승인 여부를 반환합니다.
        
        Returns: (is_approved, reasoning)
        """
        llm_route = select_ai_decision_route(
            symbol=symbol,
            strategy_name=strategy_name,
            market_context=market_context,
            indicators=indicators,
        )

        initial_state = {
            "messages": [],
            "symbol": symbol,
            "strategy_name": strategy_name,
            "market_context": market_context,
            "indicators": indicators,
            "llm_route": llm_route,
            "rag_context": None,
            "replay_mode": False,
            "analyst_decision": None,
            "guardian_decision": None,
            "final_decision": "REJECT",
            "final_reasoning": "AI Analysis failed or timed out."
        }
        
        try:
            # V1.1 정책: 40초 타임아웃 적용 (Sonnet + 1시간봉 데이터 대응)
            result = await asyncio.wait_for(
                self.graph.ainvoke(initial_state),
                timeout=40.0
            )
            
            # 결과 분석
            is_approved = False
            reasoning = ""
            decision_str = "REJECT"
            
            analyst = result.get("analyst_decision")
            guardian = result.get("guardian_decision")
            boundary_violation = bool(analyst.get("boundary_violation")) if analyst else False
            boundary_terms = analyst.get("boundary_terms") if analyst else []
            
            if analyst and analyst["decision"] == "CONFIRM":
                if guardian and guardian["decision"] == "SAFE":
                    is_approved = True
                    decision_str = "CONFIRM"
                    reasoning = f"[Analyst] {analyst['reasoning']} | [Guardian] {guardian['reasoning']}"
                else:
                    decision_str = "REJECT"
                    reasoning = f"[Risk Warning] {guardian['reasoning'] if guardian else 'Guardian check failed'}"
            else:
                decision_str = "REJECT"
                reasoning = analyst["reasoning"] if analyst else "Market Analysis failed."

            # DB 로깅 (섹션 3.A)
            await self._log_decision(
                symbol, strategy_name, decision_str, reasoning,
                analyst.get("confidence") if analyst else None,
                indicators=indicators,
                market_context=market_context,
                boundary_violation=boundary_violation,
                boundary_terms=boundary_terms,
                model_used=self._format_model_used(llm_route),
            )
            
            return is_approved, reasoning
            
        except asyncio.TimeoutError:
            print(f"[!] AI Agent Timeout (40s) for {symbol}. Falling back to REJECT.")
            await log_llm_usage_event(
                route="ai_decision_pipeline",
                feature="ai_decision",
                provider=str((llm_route or {}).get("provider") or "unknown"),
                model=str((llm_route or {}).get("model") or "unknown"),
                status="error",
                request_id=build_usage_request_id(
                    "ai_decision_pipeline",
                    str((llm_route or {}).get("provider") or "unknown"),
                    str((llm_route or {}).get("model") or "unknown"),
                ),
                error_type="TimeoutError",
                meta={"symbol": symbol, "strategy_name": strategy_name},
            )
            await self._log_decision(
                symbol, strategy_name, "REJECT",
                "AI Analysis Timed Out (Conservative Fallback)", None,
                indicators=indicators,
                market_context=market_context,
                model_used=self._format_model_used(llm_route),
            )
            return False, "AI Analysis Timed Out (Conservative Fallback: REJECT)"
        except Exception as e:
            print(f"[!] AI Agent Error for {symbol}: {e}. Falling back to REJECT.")
            await log_llm_usage_event(
                route="ai_decision_pipeline",
                feature="ai_decision",
                provider=str((llm_route or {}).get("provider") or "unknown"),
                model=str((llm_route or {}).get("model") or "unknown"),
                status="error",
                request_id=build_usage_request_id(
                    "ai_decision_pipeline",
                    str((llm_route or {}).get("provider") or "unknown"),
                    str((llm_route or {}).get("model") or "unknown"),
                ),
                error_type=type(e).__name__,
                meta={"symbol": symbol, "strategy_name": strategy_name},
            )
            # 에러 상황도 DB에 기록 (대시보드 노출 위해)
            await self._log_decision(
                symbol, strategy_name, "REJECT",
                f"AI Error: {str(e)}", None,
                indicators=indicators,
                market_context=market_context,
                model_used=self._format_model_used(llm_route),
            )
            return False, f"AI Analysis Error: {str(e)}"

    @staticmethod
    def _format_model_used(llm_route: Dict[str, Any] | None) -> str:
        if not llm_route:
            return "unknown"
        provider = (llm_route.get("provider") or "unknown").strip().lower()
        model = (llm_route.get("model") or "unknown").strip()
        route_label = (llm_route.get("route_label") or "unknown").strip().lower()
        return f"{provider}:{model} ({route_label})"

    async def _log_decision(
        self,
        symbol,
        strategy,
        decision,
        reasoning,
        confidence,
        indicators: Dict[str, Any] = None,
        market_context: Dict[str, Any] = None,
        boundary_violation: bool = False,
        boundary_terms: Any = None,
        model_used: str = "unknown",
    ):
        """AI 판단 결과를 DB에 저장하고, REJECT 시 Discord 알림 전송"""
        try:
            # 결정 시점 가격 및 레짐 추출
            price_at_decision = indicators.get("close") if indicators else None
            # market_context는 list(캔들 데이터)이므로 regime은 indicators에서 추출
            regime = indicators.get("regime") if indicators else None

            async with get_db_session() as session:
                log = AgentDecision(
                    symbol=symbol,
                    strategy_name=strategy,
                    decision=decision,
                    reasoning=reasoning,
                    confidence=confidence,
                    model_used=model_used,
                    price_at_decision=price_at_decision,
                    regime=regime
                )
                session.add(log)
                # AI 최종 판정은 퍼널의 마지막 단계다.
                # decision 로그와 같은 트랜잭션에 묶어야 운영 집계에서 누락/불일치가 줄어든다.
                record_rule_funnel_event(
                    session,
                    symbol=symbol,
                    strategy_name=strategy,
                    regime=regime,
                    stage="ai_confirm" if decision == "CONFIRM" else "ai_reject",
                    result="confirm" if decision == "CONFIRM" else "reject",
                    reason=reasoning,
                )
                await session.commit()

            # Discord 알림 전송 (REJECT/CONFIRM 모두)
            asyncio.create_task(notifier.send_webhook("/webhook/ai-decision", {
                "symbol": symbol,
                "decision": decision,
                "regime": indicators.get("regime", "UNKNOWN") if indicators else "UNKNOWN",
                "rsi": round(indicators.get("rsi", 0), 1) if indicators else 0,
                "confidence": confidence,
                "boundary_violation": boundary_violation,
                "boundary_terms": boundary_terms or [],
                "model_used": model_used,
                "reason": reasoning[:1500] if reasoning else "No reason provided",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
        except Exception as e:
            print(f"[!] Failed to log agent decision: {e}")

# 싱글톤 인스턴스 (공유 사용)
runner = AgentRunner()
