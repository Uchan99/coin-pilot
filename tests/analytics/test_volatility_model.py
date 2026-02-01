import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from src.analytics.volatility_model import VolatilityModel

class TestVolatilityModel:
    @pytest.fixture
    def mock_redis(self):
        with patch('redis.from_url') as mock:
            yield mock

    @pytest.fixture
    def vol_model(self, mock_redis):
        return VolatilityModel()

    def test_prepare_data(self, vol_model):
        """
        가격 데이터를 수익률로 잘 변환하는지 테스트
        """
        prices = pd.Series([100, 101, 102, 101], index=pd.date_range("2024-01-01", periods=4))
        returns = vol_model.prepare_data(prices)
        
        # 첫 번째 값은 NaN으로 제거되므로 3개 남음
        assert len(returns) == 3
        # 로그 수익률 * 100 확인
        expected_return = 100 * np.log(101/100)
        assert np.isclose(returns.iloc[0], expected_return)

    def test_fit_predict_not_enough_data(self, vol_model):
        """
        데이터가 부족할 때 0.0을 반환하는지 테스트
        """
        prices = pd.Series([100]*10, index=pd.date_range("2024-01-01", periods=10))
        vol = vol_model.fit_predict(prices)
        assert vol == 0.0

    @patch('src.analytics.volatility_model.arch_model')
    def test_fit_predict_success(self, mock_arch, vol_model):
        """
        모델 학습 및 예측 성공 시나리오 테스트
        """
        # 충분한 데이터 생성
        prices = pd.Series(np.random.normal(100, 1, 200).cumsum() + 100)
        
        # Mocking arch_model result
        mock_res = MagicMock()
        mock_forecast = MagicMock()
        mock_forecast.variance.iloc[-1].values = [0.0004] # sqrt(0.0004) = 0.02
        mock_res.forecast.return_value = mock_forecast
        
        mock_model_instance = MagicMock()
        mock_model_instance.fit.return_value = mock_res
        mock_arch.return_value = mock_model_instance

        vol = vol_model.fit_predict(prices)
        
        assert vol == 0.02
        mock_model_instance.fit.assert_called_once()

    def test_update_volatility_state(self, vol_model):
        """
        Redis에 상태가 저장되는지 테스트
        """
        vol_model.redis_client = MagicMock()
        vol_model.update_volatility_state(3.5, threshold=2.0)
        
        vol_model.redis_client.set.assert_called_once()
        args = vol_model.redis_client.set.call_args[0]
        assert args[0] == "coinpilot:volatility_state"
        assert "3.5" in args[1]
        assert "true" in args[1].lower() # is_high_volatility should be true
