from abc import ABC, abstractmethod
from typing import Dict, Optional, Tuple
from decimal import Decimal
from datetime import datetime, timedelta, timezone

class BaseStrategy(ABC):
    """
    모든 매매 전략의 기반이 되는 추상 클래스
    """
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def check_entry_signal(self, indicators: Dict) -> bool:
        """
        진입(매수) 신호를 확인합니다.
        """
        pass

    @abstractmethod
    def check_exit_signal(self, indicators: Dict, position_info: Dict) -> Tuple[bool, str]:
        """
        청산(매도) 신호를 확인합니다.
        Returns: (신호발생여부, 청산사유)
        """
        pass

from src.config.strategy import StrategyConfig

class MeanReversionStrategy(BaseStrategy):
    """
    평균 회귀(Mean Reversion) 전략 - v2.0 (설정 기반)
    
    기존 1.0의 엄격한 조건을 설정 파일(StrategyConfig) 기반으로 유연하게 변경함.
    과매도(RSI), 추세(MA), 거래량(Volume)을 복합적으로 고려하여 진입 시점을 포착함.
    """
    def __init__(self, config: StrategyConfig = None):
        """
        전략 초기화
        :param config: 전략 설정 객체 (없을 경우 기본값 생성)
        """
        super().__init__("MeanReversion")
        # 설정 주입 (Dependency Injection)
        self.config = config or StrategyConfig()
        
        # 성능 최적화를 위해 자주 쓰는 값 미리 변환
        self.tp_ratio = Decimal(str(self.config.TAKE_PROFIT))
        self.sl_ratio = Decimal(str(self.config.STOP_LOSS))
        self.max_hold_hours = self.config.MAX_HOLD_HOURS

    def check_entry_signal(self, indicators: Dict) -> bool:
        """
        진입(매수) 신호 확인
        
        [판단 로직]
        1. RSI < RSI_OVERSOLD (기본 33): 과매도 구간 여부
        2. Price > MA_TREND (기본 200): 장기 상승 추세 중 일시적 하락인지 확인 (역추세 매매 방지)
        3. Volume > Avg * Multiplier (기본 1.3배): 거래량을 동반한 하락(패닉 셀)인지 확인
        4. (Optional) Price <= BB Lower: 볼린저 밴드 하단 터치 여부 (설정에 따라 활성/비활성)
        """
        rsi = indicators.get("rsi")
        ma_200 = indicators.get("ma_200")
        bb_lower = indicators.get("bb_lower")
        vol_ratio = indicators.get("vol_ratio")
        close = indicators.get("close")

        # 필수 데이터 누락 시 판단 보류
        if None in [rsi, ma_200, vol_ratio, close]:
            return False

        # --- 조건 평가 ---
        
        # 1. RSI 과매도 조건 (기존 30 -> 33으로 완화됨)
        is_rsi_low = rsi < self.config.RSI_OVERSOLD
        
        # 2. 장기 추세 필터 (200일선 위에서만 매수)
        # 하락장에서의 저점 매수는 매우 위험하므로 상승 추세일 때만 진입
        is_above_trend = close > ma_200
        
        # 3. 거래량 급증 조건 (기존 1.5배 -> 1.3배로 완화됨)
        # 거래량 없는 하락은 질질 흐르는 것일 수 있으므로, 투매가 나온 시점을 포착
        is_vol_surge = vol_ratio > self.config.VOLUME_MULTIPLIER
        
        # 4. 볼린저 밴드 조건 (선택적)
        # RSI와 중복 성향이 강해 v2.0에서는 기본적으로 비활성화됨
        if self.config.USE_BB_CONDITION:
            if bb_lower is None:
                return False
            is_bb_low = close <= bb_lower
            
            # 모든 조건 만족 시 True
            signal = is_rsi_low and is_above_trend and is_vol_surge and is_bb_low
        else:
            # BB 조건 제외
            signal = is_rsi_low and is_above_trend and is_vol_surge
        
        if signal:
            print(f"[*] [Signal: {self.name}] Entry Signal Detected! "
                  f"(RSI: {rsi:.2f}, Price: {close}, VolRatio: {vol_ratio:.2f})")
        
        return signal

    def check_exit_signal(self, indicators: Dict, position_info: Dict) -> Tuple[bool, str]:
        """
        청산(매도) 신호 확인 (기존 로직 유지)
        """
        close = Decimal(str(indicators.get("close")))
        rsi = indicators.get("rsi")
        
        entry_price = Decimal(str(position_info.get("avg_price", 0)))
        opened_at = position_info.get("opened_at")
        
        if entry_price == 0 or not opened_at:
            return False, ""

        # 현재 수익률 계산
        pnl_ratio = (close - entry_price) / entry_price

        # 1. 익절 (Take Profit)
        if pnl_ratio >= self.tp_ratio:
            return True, f"Take Profit (+{pnl_ratio*100:.2f}%)"
            
        # 2. 손절 (Stop Loss)
        if pnl_ratio <= -self.sl_ratio:
            return True, f"Stop Loss ({pnl_ratio*100:.2f}%)"
            
        # 3. RSI 과매수 (Signal Exit)
        if rsi and rsi > self.config.RSI_OVERBOUGHT:
            return True, f"Signal Exit (RSI: {rsi:.2f} > {self.config.RSI_OVERBOUGHT})"
            
        # 4. 시간 초과 (Time Exit)
        now = datetime.now(timezone.utc)
        aware_opened_at = opened_at if opened_at.tzinfo else opened_at.replace(tzinfo=timezone.utc)
        
        hold_time = now - aware_opened_at
        if hold_time > timedelta(hours=self.max_hold_hours):
            return True, f"Time Exit ({hold_time.total_seconds()/3600:.1f} hours passed)"
            
        return False, ""
