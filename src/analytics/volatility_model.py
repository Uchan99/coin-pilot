import pandas as pd
import numpy as np
from arch import arch_model
import redis
import json
import os
from typing import Optional, Dict

class VolatilityModel:
    """
    GARCH(1,1) 모델을 사용하여 시장 변동성을 예측하는 클래스입니다.
    예측된 변동성은 리스크 매니저가 포지션 크기를 조절하는 데 사용됩니다.
    
    Attributes:
        redis_client (redis.Redis): 변동성 상태를 저장할 Redis 클라이언트
        window_size (int): 학습에 사용할 윈도우 크기 (기본 90일 * 24시간 = 2160)
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0", window_size: int = 2160):
        # Redis 연결 설정 (환경 변수 우선)
        redis_url = os.getenv("REDIS_URL", redis_url)
        self.redis_client = redis.from_url(redis_url)
        self.window_size = window_size
        print(f"[VolatilityModel] Initialized with window_size={window_size}")

    def prepare_data(self, prices: pd.Series) -> pd.Series:
        """
        가격 데이터를 수익률(Return) 데이터로 변환합니다.
        GARCH 모델은 가격 자체가 아닌 수익률( 로그 수익률 권장)을 입력으로 받습니다.
        
        Args:
            prices (pd.Series): 시계열 가격 데이터
            
        Returns:
            pd.Series: 로그 수익률 (Log Return) * 100 (스케일링)
        """
        # 로그 수익률 계산: ln(P_t / P_{t-1})
        # 100을 곱하는 이유: GARCH 모델 수렴을 돕기 위해 스케일을 키움
        returns = 100 * np.log(prices / prices.shift(1))
        returns = returns.dropna() # 첫 번째 NaN 제거
        return returns

    def fit_predict(self, prices: pd.Series) -> float:
        """
        GARCH(1,1) 모델을 학습하고 다음 시점의 변동성을 예측합니다.
        
        Args:
            prices (pd.Series): 가격 데이터 (최소 window_size 이상 권장)
            
        Returns:
            float: 예측된 연율화 변동성 (Annualized Volatility)
        """
        try:
            # 1. 데이터 전처리
            returns = self.prepare_data(prices)
            
            # 데이터 부족 시 예외 처리
            if len(returns) < 100:
                print("[VolatilityModel] Not enough data to fit model.")
                return 0.0

            # 2. GARCH(1,1) 모델 정의
            # vol='Garch': 기본 GARCH 모델
            # p=1, q=1: GARCH(1,1) 설정 (가장 보편적)
            # dist='Normal': 오차항 정규분포 가정
            model = arch_model(returns, vol='Garch', p=1, q=1, dist='Normal')
            
            # 3. 모델 학습 (disp='off': 로그 출력 끔)
            res = model.fit(disp='off')
            
            # 4. 예측 (horizon=1: 다음 1개 시점 예측)
            forecast = res.forecast(horizon=1)
            
            # 5. 결과 추출 (variance -> std deviation)
            # forecast.variance.iloc[-1]은 마지막 시점의 예측 분산
            next_volatility = np.sqrt(forecast.variance.iloc[-1].values[0])
            
            # 연율화 (Hourly data 가정 시: sqrt(24 * 365) 곱하기, 여기서는 단순 1일 변동성 지수로 사용하거나 상황에 맞게 조정)
            # 현재는 단순히 모델이 뱉은 '스케일된 수익률의 표준편차'를 반환
            
            print(f"[VolatilityModel] Forecast Volatility: {next_volatility:.4f}")
            return float(next_volatility)

        except Exception as e:
            print(f"[VolatilityModel] Error fitting model: {e}")
            # 에러 발생 시 0.0 반환 (리스크 매니저가 기본값 사용하도록 유도)
            return 0.0

    def update_volatility_state(self, volatility: float, threshold: float = 2.0):
        """
        계산된 변동성을 Redis에 저장합니다.
        
        Args:
            volatility (float): 예측된 변동성 값
            threshold (float): 고변동성 기준 임계값
        """
        try:
            state = {
                "current_volatility": volatility,
                "is_high_volatility": volatility > threshold,
                "timestamp": pd.Timestamp.now().isoformat()
            }
            # Redis에 JSON 형태로 저장
            self.redis_client.set("coinpilot:volatility_state", json.dumps(state))
            
            # Prometheus 메트릭 업데이트 (MetricsExporter가 임포트 가능하다면)
            # 여기서는 직접 할 수 없으므로 생략하거나 추후 통합
            # from src.utils.metrics import metrics
            # metrics.volatility_index.set(volatility)
            
            print(f"[VolatilityModel] State updated: {state}")
            
        except Exception as e:
            print(f"[VolatilityModel] Error updating Redis: {e}")
            # Redis 장애 시 Fallback은 읽는 쪽(RiskManager)에서 처리

if __name__ == "__main__":
    # 간단한 테스트 코드
    # 랜덤 워크 데이터 생성
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=1000, freq="h")
    prices = 100 + np.cumsum(np.random.normal(0, 1, 1000))
    prices = pd.Series(prices, index=dates)
    
    vm = VolatilityModel()
    vol = vm.fit_predict(prices)
    vm.update_volatility_state(vol)
