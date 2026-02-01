import pandas as pd
import numpy as np
from typing import Dict, List

class PerformanceAnalytics:
    """
    백테스팅 및 실거래 성과를 분석하는 클래스입니다.
    MDD, Sharpe Ratio, Win Rate 등 전문적인 지표를 계산합니다.
    """

    @staticmethod
    def calculate_mdd(equity_curve: pd.Series) -> float:
        """
        MDD (Maximum Drawdown)를 계산합니다.
        
        Args:
            equity_curve (pd.Series): 자산 곡선 (누적 자산 가치)
            
        Returns:
            float: MDD (백분율, 양수로 반환. 예: 15.5 -> 15.5%)
        """
        if equity_curve.empty:
            return 0.0
            
        # Drawdown 계산
        # roll_max: 현재 시점까지의 최고점 (Peak)
        roll_max = equity_curve.cummax()
        
        # drawdown: 최고점 대비 현재 하락률
        drawdown = (equity_curve - roll_max) / roll_max
        
        # max_drawdown: 가장 깊었던 하락폭 (음수)
        max_drawdown = drawdown.min()
        
        # 퍼센트로 변환하여 양수로 반환 (예: -0.15 -> 15.0)
        return abs(max_drawdown) * 100

    @staticmethod
    def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0) -> float:
        """
        Sharpe Ratio (샤프 비율)를 계산합니다.
        
        Args:
            returns (pd.Series): 수익률 시리즈 (Periodical returns)
            risk_free_rate (float): 무위험 수익률 (기본 0)
            
        Returns:
            float: Sharpe Ratio
        """
        if returns.empty or returns.std() == 0:
            return 0.0
            
        # 초과 수익률 = 수익률 - 무위험 수익률
        excess_returns = returns - risk_free_rate
        
        # 샤프 비율 = (초과 수익률 평균) / (초과 수익률 표준편차)
        # 연율화는 데이터 주기에 따라 다르므로 여기서는 raw ratio 반환
        sharpe = excess_returns.mean() / excess_returns.std()
        
        # 데이터가 일간(Daily)이라면 * sqrt(252), 시간(Hourly)이라면 * sqrt(24*365) 등을 곱해야 함
        # 여기서는 단순 비율만 반환
        return sharpe

    @staticmethod
    def calculate_win_rate(trades: List[Dict]) -> float:
        """
        승률 (Win Rate)을 계산합니다.
        
        Args:
            trades (List[Dict]): 거래 내역 리스트 (각 딕셔너리는 'pnl' 키를 가져야 함)
            
        Returns:
            float: 승률 (0.0 ~ 1.0)
        """
        if not trades:
            return 0.0
            
        # 수익 거래(PnL > 0) 개수
        winning_trades = sum(1 for t in trades if t.get('pnl', 0) > 0)
        
        return winning_trades / len(trades)

    @staticmethod
    def generate_report(equity_curve: pd.Series, trades: List[Dict]) -> Dict:
        """
        종합 성과 리포트를 생성합니다.
        """
        # 자산 곡선에서 수익률 계산
        returns = equity_curve.pct_change().dropna()
        
        mdd = PerformanceAnalytics.calculate_mdd(equity_curve)
        sharpe = PerformanceAnalytics.calculate_sharpe_ratio(returns)
        win_rate = PerformanceAnalytics.calculate_win_rate(trades)
        
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1 if not equity_curve.empty else 0.0

        return {
            "total_return_pct": total_return * 100,
            "mdd_pct": mdd,
            "sharpe_ratio": sharpe,
            "win_rate": win_rate,
            "total_trades": len(trades)
        }
