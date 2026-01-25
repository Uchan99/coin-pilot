import pytest
from unittest.mock import AsyncMock, patch
from src.agents.runner import runner
from src.agents.structs import AnalystDecision, GuardianDecision

@pytest.mark.asyncio
async def test_agent_runner_confirm_scenario():
    """Analyst CONFIRM + Guardian SAFE 시나리오 테스트"""
    
    mock_analyst = AnalystDecision(
        decision="CONFIRM",
        confidence=90,
        reasoning="Strong RSI support and BB touch."
    )
    
    mock_guardian = GuardianDecision(
        decision="SAFE",
        reasoning="Market volatility is stable."
    )

    with patch.object(runner.graph, "ainvoke", new_callable=AsyncMock) as mock_invoke, \
         patch("src.agents.runner.AgentRunner._log_decision", new_callable=AsyncMock) as mock_log:
        
        # Mocking Graph Output
        mock_invoke.return_value = {
            "analyst_decision": {
                "decision": "CONFIRM",
                "confidence": 90,
                "reasoning": "Strong RSI support and BB touch."
            },
            "guardian_decision": {
                "decision": "SAFE",
                "reasoning": "Market volatility is stable."
            }
        }
        
        is_approved, reasoning = await runner.run(
            "KRW-BTC", "MeanReversion", {}, {"rsi": 25}
        )
        
        assert is_approved is True
        assert "Analyst" in reasoning
        assert "Guardian" in reasoning
        assert mock_log.called

@pytest.mark.asyncio
async def test_agent_runner_low_confidence_rejection():
    """Analyst가 CONFIRM 했으나 신뢰도가 낮아 REJECT 되는 시나리오 (V1.2 정책)"""
    
    with patch.object(runner.graph, "ainvoke", new_callable=AsyncMock) as mock_invoke, \
         patch("src.agents.runner.AgentRunner._log_decision", new_callable=AsyncMock) as mock_log:
        
        mock_invoke.return_value = {
            "analyst_decision": {
                "decision": "REJECT",
                "confidence": 70,
                "reasoning": "[Low Confidence: 70] Seems okay but not sure."
            }
        }
        
        is_approved, reasoning = await runner.run(
            "KRW-BTC", "MeanReversion", {}, {"rsi": 25}
        )
        
        assert is_approved is False
        assert "Low Confidence" in reasoning
        assert mock_log.called

@pytest.mark.asyncio
async def test_agent_runner_timeout_fallback():
    """AI 호출 타임아웃 시 보수적 거절(REJECT) 시나리오 테스트"""
    
    with patch.object(runner.graph, "ainvoke", new_callable=AsyncMock) as mock_invoke:
        import asyncio
        mock_invoke.side_effect = asyncio.TimeoutError()
        
        is_approved, reasoning = await runner.run(
            "KRW-BTC", "MeanReversion", {}, {"rsi": 25}
        )
        
        assert is_approved is False
        assert "Timed Out" in reasoning
