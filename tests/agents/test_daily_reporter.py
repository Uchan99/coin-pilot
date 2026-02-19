import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.daily_reporter import DailyReporter

class TestDailyReporter:
    @pytest.fixture
    def mock_session_factory(self):
        # Async Context Manager Mock
        mock_session = AsyncMock()
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__.return_value = mock_session
        return mock_factory

    @pytest.fixture
    def reporter(self, mock_session_factory):
        with patch('src.agents.daily_reporter.ChatOpenAI') as MockLLM:
            reporter = DailyReporter(mock_session_factory)
            reporter.llm = MockLLM.return_value # Instance mock
            return reporter

    @pytest.mark.asyncio
    @patch('src.agents.daily_reporter.notifier')
    async def test_generate_and_send_no_data(self, mock_notifier, reporter, mock_session_factory):
        """
        데이터가 없을 때 리포트를 전송하지 않는지 테스트
        """
        # _fetch_daily_data가 None을 반환하도록 설정
        # (private method mocking 대신 session execution result를 조작하는 것이 정석이지만,
        # 여기서는 _fetch_daily_data 자체를 mocking하거나, session이 None을 반환하게 설정)
        
        # Method 1: Mocking internal method (Easiest for unit test)
        with patch.object(reporter, '_fetch_daily_data', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None
            
            await reporter.generate_and_send()
            
            mock_notifier.send_webhook.assert_not_called()

    @pytest.mark.asyncio
    @patch('src.agents.daily_reporter.notifier')
    async def test_generate_and_send_success(self, mock_notifier, reporter):
        """
        데이터가 있을 때 정상적으로 리포트 생성 및 전송하는지 테스트
        """
        mock_notifier.send_webhook = AsyncMock()
        
        fake_data = {
            "date": "2024-01-01",
            "total_pnl": 100.0,
            "trade_count": 5,
            "sell_trade_count": 3,
            "win_rate": 0.6,
            "mdd": 5.0
        }

        # Mocking LLM response
        reporter.llm = MagicMock()
        mock_chain = MagicMock()
        mock_chain.ainvoke = AsyncMock(return_value=MagicMock(content="Good job!"))
        # Chain 구성 (__or__) mocking이 까다로우므로 _generate_llm_summary를 patch
        
        with patch.object(reporter, '_fetch_daily_data', new_callable=AsyncMock) as mock_fetch, \
             patch.object(reporter, '_generate_llm_summary', new_callable=AsyncMock) as mock_llm_sum:
            
            mock_fetch.return_value = fake_data
            mock_llm_sum.return_value = "Great trading day!"
            
            await reporter.generate_and_send()
            
            mock_notifier.send_webhook.assert_called_once()
            args = mock_notifier.send_webhook.call_args[0]
            assert args[0] == "/webhook/daily-report"
            assert args[1]["summary"] == "Great trading day!"
            assert args[1]["pnl"] == "100 KRW"
            assert args[1]["win_rate"] == "60.0%"
