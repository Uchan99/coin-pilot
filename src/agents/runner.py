import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, Any, Tuple

from langgraph.graph import StateGraph, END
from src.agents.state import AgentState
from src.agents.analyst import market_analyst_node
from src.agents.guardian import risk_guardian_node
from src.common.db import get_db_session
from src.common.models import AgentDecision
from src.agents.factory import get_analyst_llm
from src.common.notification import notifier

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
        initial_state = {
            "messages": [],
            "symbol": symbol,
            "strategy_name": strategy_name,
            "market_context": market_context,
            "indicators": indicators,
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
                indicators=indicators, market_context=market_context
            )
            
            return is_approved, reasoning
            
        except asyncio.TimeoutError:
            print(f"[!] AI Agent Timeout (20s) for {symbol}. Falling back to REJECT.")
            await self._log_decision(
                symbol, strategy_name, "REJECT",
                "AI Analysis Timed Out (Conservative Fallback)", None,
                indicators=indicators, market_context=market_context
            )
            return False, "AI Analysis Timed Out (Conservative Fallback: REJECT)"
        except Exception as e:
            print(f"[!] AI Agent Error for {symbol}: {e}. Falling back to REJECT.")
            # 에러 상황도 DB에 기록 (대시보드 노출 위해)
            await self._log_decision(
                symbol, strategy_name, "REJECT",
                f"AI Error: {str(e)}", None,
                indicators=indicators, market_context=market_context
            )
            return False, f"AI Analysis Error: {str(e)}"

    async def _log_decision(self, symbol, strategy, decision, reasoning, confidence,
                            indicators: Dict[str, Any] = None, market_context: Dict[str, Any] = None):
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
                    model_used=get_analyst_llm().model,
                    price_at_decision=price_at_decision,
                    regime=regime
                )
                session.add(log)
                await session.commit()

            # Discord 알림 전송 (REJECT/CONFIRM 모두)
            asyncio.create_task(notifier.send_webhook("/webhook/ai-decision", {
                "symbol": symbol,
                "decision": decision,
                "regime": indicators.get("regime", "UNKNOWN") if indicators else "UNKNOWN",
                "rsi": round(indicators.get("rsi", 0), 1) if indicators else 0,
                "confidence": confidence,
                "reason": reasoning[:1500] if reasoning else "No reason provided",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }))
        except Exception as e:
            print(f"[!] Failed to log agent decision: {e}")

# 싱글톤 인스턴스 (공유 사용)
runner = AgentRunner()
