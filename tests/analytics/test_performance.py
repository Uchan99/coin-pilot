import pandas as pd
import numpy as np
from src.analytics.performance import PerformanceAnalytics

class TestPerformanceAnalytics:
    def test_calculate_mdd(self):
        """
        MDD 계산 테스트
        100 -> 110 (Peak) -> 99 (Drawdown 10%) -> 120
        """
        equity = pd.Series([100, 110, 99, 120])
        mdd = PerformanceAnalytics.calculate_mdd(equity)
        
        # 110에서 99로 떨어짐: (99-110)/110 = -11/110 = -0.1 (-10%)
        assert np.isclose(mdd, 10.0)

    def test_calculate_sharpe_ratio(self):
        """
        Sharpe Ratio 계산 테스트
        수익률 [0.01, 0.01, 0.01] -> 평균 0.01, 표준편차 0 -> 0.0 (예외처리)
        수익률 [0.01, -0.01] -> 평균 0, 표준편차 0.01414 -> 0
        """
        returns = pd.Series([0.01, 0.02, 0.03])
        # mean=0.02, std=0.01
        sharpe = PerformanceAnalytics.calculate_sharpe_ratio(returns)
        assert np.isclose(sharpe, 2.0)

    def test_calculate_win_rate(self):
        """
        승률 계산 테스트
        """
        trades = [
            {'pnl': 10},
            {'pnl': -5},
            {'pnl': 0}, # 0은 패배로 간주 (취향 차이이나 보통 >0만 승리)
            {'pnl': 20}
        ]
        win_rate = PerformanceAnalytics.calculate_win_rate(trades)
        # 2 wins out of 4 tests
        assert win_rate == 0.5
